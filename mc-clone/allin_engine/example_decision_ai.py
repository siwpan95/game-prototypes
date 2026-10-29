# -*- coding: utf-8 -*-
"""
allin_engine — 决策 / 行为范式 集成示例
========================================

演示从 zhuangtaiji 项目集成并增强的四种核心决策范式，以及如何把它们真正
「挂到 ECS 实体上」由引擎主循环驱动：

  1. 状态机 (FSM / HSM)        —— 时序演化：状态 + 事件转移
  2. 行为树 (Behavior Tree)    —— 响应式行为编排：根驱动、每帧重评估
  3. 决策树 (Decision Tree)    —— 一次性特征空间路由决策
  4. 差分引擎 (Difference Eng) —— 有限差分递推 + 状态差量/响应式追踪

粘合与增强：
  * BrainComponent / BlackboardComponent / BrainSystem —— 把 BT/SM/DT/差分
    接入 World 主循环，每个 NPC 拥有独立黑板（每个实体一份状态）。
  * FixedTimestepLoop —— 固定步长 + 单帧钳制，避免「死亡螺旋」，与 GameEngine
    的 advance() 集成。

运行：
    cd <仓库根>
    python -m allin_engine.example_decision_ai
"""

import os
import sys

# 将 allin_engine 的父目录加入 sys.path，使 allin_engine 包可被导入
_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, _PROJECT_ROOT)

from allin_engine import (
    GameEngine,
    World, Entity, Component, System, EventBus, EventTypes,
    # 决策范式
    GenericStateMachine, create_state_machine, HierarchicalStateMachine,
    BehaviorTree, Blackboard,
    DecisionTree,
    FiniteDifference, StateDiff, ReactiveTracker,
    BrainComponent, BlackboardComponent, BrainSystem,
    default_brains_config, load_decision_config, build_brain_from_spec,
    FixedTimestepLoop,
)
from allin_engine.ai.decision import build_behavior_tree, build_decision_tree


# ══════════════════════════════════════════════════════════
# 示例 1: 有限状态机 (FSM) —— 声明式 + 事件驱动
# ══════════════════════════════════════════════════════════

def example_fsm():
    print("=" * 60)
    print("示例 1: 有限状态机 (FSM)")

    # 用配置声明一个「开关」状态机，并注册动作回调观察 enter/exit
    log = []

    def on_action(action_type, state_id, detail):
        log.append(f"  [{action_type}] -> {state_id}: {detail.get('description', '')}")

    config = {
        "state_machines": {
            "Switch": {
                "initial": "off",
                "states": {
                    "off": {"content": "关闭",
                            "on_enter": "断电",
                            "transitions": {"toggle": "on"}},
                    "on":  {"content": "开启",
                            "on_enter": "通电",
                            "transitions": {"toggle": "off",
                                            "blink": "#blink"}},  # 内部转移
                    "blink": {"content": "闪烁中"},
                },
            }
        }
    }
    sm = create_state_machine("Switch", config, on_action=on_action)
    print(f"  初始状态: {sm.current_state_id} ({sm.current_content})")
    sm.trigger("toggle")
    print(f"  toggle 后: {sm.current_state_id} ({sm.current_content})")
    # 内部转移：原地执行动作但不离开状态
    sm.trigger("blink")
    print(f"  blink(内部转移) 后仍在: {sm.current_state_id}")
    sm.trigger("toggle")
    print(f"  再次 toggle 后: {sm.current_state_id} ({sm.current_content})")
    print(f"  动作日志共 {len(log)} 条")


# ══════════════════════════════════════════════════════════
# 示例 2: 层次状态机 (HSM) —— 子状态 / 历史 / 内部转移
# ══════════════════════════════════════════════════════════

def example_hsm():
    print()
    print("=" * 60)
    print("示例 2: 层次状态机 (HSM)")

    cfg = default_brains_config()["state_machines"]["SM_Hier"]
    hsm = create_state_machine("SM_Hier", {"state_machines": {"SM_Hier": cfg}})
    print(f"  初始路径: {hsm.current_state_id}")          # power/off
    hsm.trigger("turn_on")                                 # -> power/on/idle
    print(f"  turn_on -> {hsm.current_state_id}")
    hsm.trigger("run")                                     # -> power/on/working
    print(f"  run     -> {hsm.current_state_id}")
    hsm.trigger("fault")                                   # -> power/on/error
    print(f"  fault   -> {hsm.current_state_id}")
    # 从 error 触发 reset：目标是 #on（以 # 开头 = UML 内部转移），
    # 语义是「原地执行复位动作而不离开当前状态」，因此仍停留在 error。
    # 若要真正恢复到 on 的默认子状态 idle，应使用普通转移 "reset": "on"。
    hsm.trigger("reset")
    print(f"  reset(#on 内部转移) -> {hsm.current_state_id} (原地复位, 仍停留)")
    hsm.trigger("power_off")                               # -> power/off
    print(f"  power_off -> {hsm.current_state_id}")


# ══════════════════════════════════════════════════════════
# 示例 3: 行为树 (Behavior Tree) —— 声明式 + 黑板
# ══════════════════════════════════════════════════════════

def example_behavior_tree():
    print()
    print("=" * 60)
    print("示例 3: 行为树 (Behavior Tree)")

    # 「故障自愈」行为树：每帧从根重评估，根据黑板状态决定动作
    spec = {
        "name": "故障自愈",
        "root": {
            "type": "selector", "name": "根·优先处理",
            "children": [
                {"type": "sequence", "name": "故障处理", "children": [
                    {"type": "condition", "name": "检测到故障", "key": "fault", "op": "truthy"},
                    {"type": "action", "name": "隔离故障", "kind": "set", "key": "isolated", "value": True},
                    {"type": "action", "name": "尝试重启", "kind": "set", "key": "restarted", "value": True},
                ]},
                {"type": "sequence", "name": "高负载处理", "children": [
                    {"type": "condition", "name": "负载过高", "key": "load", "op": "gt", "value": 80},
                    {"type": "action", "name": "横向扩容", "kind": "set", "key": "scaled", "value": True},
                ]},
                {"type": "action", "name": "维持常态", "kind": "set", "key": "healthy", "value": True},
            ],
        },
    }
    bb = Blackboard({"fault": False, "load": 90})
    tree = build_behavior_tree(spec, blackboard=bb)
    status = tree.run()
    print(f"  高负载场景: status={status.value}, scaled={bb.get('scaled')}, healthy={bb.get('healthy')}")

    # 切到故障场景
    bb.set("fault", True)
    bb.set("load", 10)
    status = tree.run()
    print(f"  故障场景:   status={status.value}, isolated={bb.get('isolated')}, restarted={bb.get('restarted')}")


# ══════════════════════════════════════════════════════════
# 示例 4: 决策树 (Decision Tree) —— 一次性路由
# ══════════════════════════════════════════════════════════

def example_decision_tree():
    print()
    print("=" * 60)
    print("示例 4: 决策树 (Decision Tree)")

    cfg = default_brains_config()["decision_trees"]["DT_Route"]
    dt: DecisionTree = build_decision_tree(cfg)

    cases = [
        {"vip": True, "urgent": True, "load": 95},
        {"vip": True, "urgent": False, "load": 95},
        {"vip": False, "urgent": False, "load": 90},
        {"vip": False, "urgent": False, "load": 30},
    ]
    for feat in cases:
        res = dt.decide(feat)
        print(f"  {feat} -> 路由={res.label}, payload={res.payload}, 路径={res.path}")


# ══════════════════════════════════════════════════════════
# 示例 5: 差分引擎 —— 有限差分递推 + 响应式差量追踪
# ══════════════════════════════════════════════════════════

def example_difference_engine():
    print()
    print("=" * 60)
    print("示例 5: 差分引擎 (Difference Engine)")

    # 有限差分：由初始值表用加法递推后续项（巴贝奇思想）
    fd = FiniteDifference([0, 12, 28, 48])  # 二阶差分 -> 二次函数
    print(f"  递推 4 项: {[round(x, 1) for x in fd.generate(4)]}")

    # 响应式差量追踪：仅当订阅键变化时才触发回调
    tracker = ReactiveTracker({"hp": 100, "mp": 50})
    tracker.subscribe("hp", lambda e, st: print(f"  HP 变化: {e.old} -> {e.new} (触发治疗特效)"))
    tracker.set("mp", 60)                 # 未订阅 mp，仅内部更新
    tracker.set("hp", 72)                 # 订阅命中，触发回调
    print(f"  最终状态: {tracker.state}")


# ══════════════════════════════════════════════════════════
# 示例 6: ECS 脑 (Brain) —— 把行为树挂到实体，由主循环驱动
# ══════════════════════════════════════════════════════════

def example_ecs_brain():
    print()
    print("=" * 60)
    print("示例 6: ECS 脑 (Brain) —— 行为树 + 主循环驱动")

    engine = GameEngine()
    engine.add_core().add_ai_brain()      # 装配 ECS + 决策脑系统

    # 用默认「故障自愈」行为树构造一个 NPC 大脑
    bt_spec = default_brains_config()["behavior_trees"]["BT_SelfHeal"]
    tree = build_behavior_tree(bt_spec)

    npc = engine.world.create_entity("goblin")
    # 每个实体一份独立黑板（关键增强：避免共享状态污染）
    npc.add(BlackboardComponent({"fault": True, "load": 10, "healthy": False}))
    npc.add(BrainComponent(tree=tree, name="goblin_ai"))

    # 监听脑 tick 事件
    events = []

    def on_brain_tick(data):
        events.append(data)

    engine.bus.subscribe("brain_tick", on_brain_tick)

    # 推进若干帧：BrainSystem 每帧自动 tick 行为树并写回实体黑板
    for _ in range(3):
        engine.advance(1.0 / 60.0)

    brain = npc.get(BrainComponent)
    bb = npc.get(BlackboardComponent).blackboard
    print(f"  npc 被 tick 次数: {brain.tick_count}, 末次状态: {brain.last_status}")
    print(f"  实体黑板: isolated={bb.get('isolated')}, restarted={bb.get('restarted')}, healthy={bb.get('healthy')}")
    print(f"  收到 brain_tick 事件: {len(events)} 次")


# ══════════════════════════════════════════════════════════
# 示例 7: 固定步长主循环 (Fixed Timestep) —— 避免死亡螺旋
# ══════════════════════════════════════════════════════════

def example_fixed_timestep():
    print()
    print("=" * 60)
    print("示例 7: 固定步长主循环 (Fixed Timestep)")

    update_calls = {"n": 0}
    render_calls = {"n": 0}

    def update_fn(dt: float) -> None:
        update_calls["n"] += 1

    def render_fn(alpha: float) -> None:
        render_calls["n"] += 1

    loop = FixedTimestepLoop(update_fn, render_fn, fixed_dt=1.0 / 60.0, max_frame_time=0.25)

    # 模拟一次卡顿的渲染帧（0.1 秒真实耗时）
    loop.advance(0.10)
    print(f"  推进 0.10s: update 调用 {update_calls['n']} 次 (固定步长 1/60), render {render_calls['n']} 次")

    # 模拟极端卡顿（1 秒）：被 max_frame_time 钳制，不会无限补帧
    update_calls["n"] = 0
    loop.advance(1.0)
    capped = int(loop.max_frame_time / loop.fixed_dt)
    print(f"  推进 1.00s: update 调用 {update_calls['n']} 次 (上限≈{capped}, 防死亡螺旋)")


# ══════════════════════════════════════════════════════════
# 主程序
# ══════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("  allin_engine — 决策 / 行为范式 集成示例")
    print("=" * 60 + "\n")

    example_fsm()
    example_hsm()
    example_behavior_tree()
    example_decision_tree()
    example_difference_engine()
    example_ecs_brain()
    example_fixed_timestep()

    print()
    print("=" * 60)
    print("  全部 7 个示例运行完毕!")
    print("=" * 60)
