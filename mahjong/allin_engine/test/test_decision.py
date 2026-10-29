# -*- coding: utf-8 -*-
"""
test/test_decision.py — 决策/行为范式子系统单元测试

覆盖：状态机(FSM/HSM)、行为树、决策树、差分引擎、ECS 脑、固定步长循环、加载器。

运行：
    cd D:/allin/tools && python -m allin_engine.test.test_decision
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))

from allin_engine.ai.decision import (
    GenericStateMachine,
    create_state_machine,
    HierarchicalStateMachine,
    BehaviorTree,
    Blackboard,
    Status,
    DecisionTree,
    DecisionResult,
    FiniteDifference,
    StateDiff,
    ReactiveTracker,
    BrainComponent,
    BlackboardComponent,
    BrainSystem,
    default_brains_config,
    build_brain_from_spec,
    load_decision_config,
)
from allin_engine.core import World, Entity, Component, System, EventBus
from allin_engine.core.game_loop import FixedTimestepLoop, GameLoopStats


# ══════════════════════════════════════════════════════════
# 配置
# ══════════════════════════════════════════════════════════

def _fsm_config():
    return {"state_machines": {
        "SM_Test": {
            "initial": "a",
            "states": {
                "a": {"content": "A", "transitions": {"go": "b"}},
                "b": {"content": "B", "transitions": {"back": "a"}},
            }
        }
    }}


# ══════════════════════════════════════════════════════════
# 状态机 (FSM)
# ══════════════════════════════════════════════════════════

def test_fsm_transition():
    sm = GenericStateMachine("SM_Test", _fsm_config())
    assert sm.current_state_id == "a"
    sid, _ = sm.trigger("go")
    assert sid == "b"
    sid, _ = sm.trigger("back")
    assert sid == "a"


def test_fsm_invalid_event():
    sm = GenericStateMachine("SM_Test", _fsm_config())
    res = sm.trigger("nope")
    assert res[0] is None


def test_fsm_factory_returns_fsm():
    sm = create_state_machine("SM_Test", _fsm_config())
    assert isinstance(sm, GenericStateMachine)


def test_fsm_internal_transition():
    # 内部转移：# 前缀，不离开状态
    cfg = {"state_machines": {
        "SM_I": {
            "initial": "x",
            "states": {
                "x": {"content": "X",
                      "transitions": {"ping": "#x", "leave": "y"}},
                "y": {"content": "Y", "transitions": {}},
            }
        }
    }}
    sm = GenericStateMachine("SM_I", cfg)
    sid, _ = sm.trigger("ping")
    assert sid == "x"
    sid, _ = sm.trigger("leave")
    assert sid == "y"


# ══════════════════════════════════════════════════════════
# 层次状态机 (HSM)
# ══════════════════════════════════════════════════════════

def test_hsm_nested_initial():
    cfg = default_brains_config()
    hsm = create_state_machine("SM_Hier", cfg)
    assert hsm.current_state_id == "power/off"


def test_hsm_transition_into_substate():
    cfg = default_brains_config()
    hsm = create_state_machine("SM_Hier", cfg)
    hsm.trigger("turn_on")
    assert hsm.current_state_id == "power/on/idle"


def test_hsm_internal_reset():
    cfg = default_brains_config()
    hsm = create_state_machine("SM_Hier", cfg)
    hsm.trigger("turn_on")
    hsm.trigger("run")
    assert hsm.current_state_id == "power/on/working"
    sid, _ = hsm.trigger("fault")
    assert sid == "power/on/error"
    # 内部转移 #on：仍留在 error（原地执行）
    sid, _ = hsm.trigger("reset")
    assert sid == "power/on/error"


# ══════════════════════════════════════════════════════════
# 行为树 (Behavior Tree)
# ══════════════════════════════════════════════════════════

def test_bt_selector_high_load():
    cfg = default_brains_config()
    bt = build_brain_from_spec(cfg["behavior_trees"]["BT_SelfHeal"],
                               Blackboard({"fault": False, "load": 90}))
    status = bt.run()
    assert status == Status.SUCCESS
    assert bt.blackboard.get("scaled") is True


def test_bt_selector_normal():
    cfg = default_brains_config()
    bt = build_brain_from_spec(cfg["behavior_trees"]["BT_SelfHeal"],
                               Blackboard({"fault": False, "load": 30}))
    bt.run()
    assert bt.blackboard.get("healthy") is True


def test_bt_sequence_fault():
    cfg = default_brains_config()
    bt = build_brain_from_spec(cfg["behavior_trees"]["BT_SelfHeal"],
                               Blackboard({"fault": True, "load": 10}))
    bt.run()
    assert bt.blackboard.get("isolated") is True
    assert bt.blackboard.get("restarted") is True


def test_bt_inverter():
    bb = Blackboard({})
    from allin_engine.ai.decision import Inverter, Condition
    cond = Condition("c", lambda ctx: False)
    inv = Inverter("inv", cond)
    tree = BehaviorTree(inv, bb)
    assert tree.tick() == Status.SUCCESS  # inverter 翻转 FAILURE->SUCCESS


# ══════════════════════════════════════════════════════════
# 决策树 (Decision Tree)
# ══════════════════════════════════════════════════════════

def test_dt_vip_urgent():
    cfg = default_brains_config()
    dt = build_brain_from_spec(cfg["decision_trees"]["DT_Route"])
    res = dt.decide({"vip": True, "urgent": True, "load": 95})
    assert res.label == "vip_urgent"
    assert "VIP加急通道" in res.path[-1]


def test_dt_normal_low():
    cfg = default_brains_config()
    dt = build_brain_from_spec(cfg["decision_trees"]["DT_Route"])
    res = dt.decide({"vip": False, "urgent": False, "load": 40})
    assert res.label == "normal"


# ══════════════════════════════════════════════════════════
# 差分引擎 (Difference Engine)
# ══════════════════════════════════════════════════════════

def test_fd_quadratic():
    fd = FiniteDifference([0, 1, 4, 9])  # x^2
    assert fd.generate(1)[0] == 16
    assert fd.generate(1)[0] == 25


def test_state_diff_changed():
    entries = StateDiff.diff({"a": 1, "b": 2}, {"a": 1, "b": 20, "c": 3})
    kinds = {e.kind for e in entries}
    assert "changed" in kinds
    assert "added" in kinds


def test_reactive_tracker_subscribe():
    logs = []
    tracker = ReactiveTracker({"status": "idle"})
    tracker.subscribe("status", lambda e, s: logs.append(e.new))
    tracker.update({"status": "running", "progress": 50})
    assert logs == ["running"]


# ══════════════════════════════════════════════════════════
# ECS 脑 (Brain)
# ══════════════════════════════════════════════════════════

def test_brain_component_tick():
    cfg = default_brains_config()
    world = World()
    world.add_system(BrainSystem())
    npc = world.create_entity("goblin")
    npc.add(BlackboardComponent({"fault": False, "load": 30}))
    npc.add(BrainComponent(
        tree=build_brain_from_spec(cfg["behavior_trees"]["BT_SelfHeal"]),
        name="goblin_ai"))
    world.update(0.016)
    brain = npc.get(BrainComponent)
    assert brain.last_status == "SUCCESS"
    assert npc.get(BlackboardComponent).blackboard.get("healthy") is True


def test_brain_event_bus_hook():
    cfg = default_brains_config()
    bus = EventBus()
    received = []
    bus.subscribe("brain_tick", lambda d: received.append(d))
    world = World()
    world.add_system(BrainSystem(event_bus=bus))
    npc = world.create_entity("n")
    npc.add(BlackboardComponent({"fault": False, "load": 95}))
    npc.add(BrainComponent(tree=build_brain_from_spec(cfg["behavior_trees"]["BT_SelfHeal"])))
    world.update(0.016)
    assert len(received) == 1
    assert received[0]["status"] == "SUCCESS"


# ══════════════════════════════════════════════════════════
# 固定步长循环 (Game Loop)
# ══════════════════════════════════════════════════════════

def test_fixed_loop_steps():
    calls = []
    loop = FixedTimestepLoop(lambda dt: calls.append(dt), fixed_dt=1 / 60)
    loop.advance(0.05)  # ~3 次固定步
    assert len(calls) == 3
    assert loop.stats.alpha >= 0 and loop.stats.alpha < 1


def test_fixed_loop_clamp():
    calls = []
    loop = FixedTimestepLoop(lambda dt: calls.append(dt), fixed_dt=1 / 60,
                             max_frame_time=0.10)
    loop.advance(10.0)  # 超长帧被钳制
    assert len(calls) <= 7  # 0.10 / (1/60) ≈ 6


# ══════════════════════════════════════════════════════════
# 加载器 (Loader)
# ══════════════════════════════════════════════════════════

def test_loader_default_config():
    cfg = default_brains_config()
    assert "behavior_trees" in cfg
    assert "decision_trees" in cfg
    assert "state_machines" in cfg


def test_loader_from_dict():
    cfg = load_decision_config(default_brains_config())
    assert "behavior_trees" in cfg


def test_loader_build_all_specs():
    cfg = default_brains_config()
    bt = build_brain_from_spec(cfg["behavior_trees"]["BT_SelfHeal"])
    dt = build_brain_from_spec(cfg["decision_trees"]["DT_Route"])
    hsm = build_brain_from_spec(cfg["state_machines"]["SM_Hier"])
    assert isinstance(bt, BehaviorTree)
    assert isinstance(dt, DecisionTree)
    assert isinstance(hsm, HierarchicalStateMachine)
