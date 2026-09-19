# -*- coding: utf-8 -*-
"""
决策脑（Brain）—— 把决策引擎接入 allin_engine 的 ECS 世界
============================================================

这是本次增强的关键粘合层：让「状态机 / 行为树 / 决策树 / 差分引擎」成为
游戏实体（Entity）真正可驱动的「大脑」，由 World 的主循环每帧 tick。

设计要点（结合游戏引擎研发沉淀）：
* BlackboardComponent —— 实体级的共享黑板，行为树节点读写它；
  与 allin_engine 的全局 world.set_data 解耦，支持「每个 NPC 各自一份状态」。
* BrainComponent —— 挂在实体上的「决策脑」，可持有行为树 / 状态机 / 决策树。
* BrainSystem —— 每帧遍历拥有 BrainComponent 的实体：
    - 行为树：根驱动 tick（响应式，每帧重评估）——适合 AI 行为编排；
    - 状态机：事件驱动，这里不主动推进（由游戏事件触发 trigger）；
    - 决策树：一次性路由，提供 decide() 供系统按需调用。
* 通过 EventBus 发出 BRAIN_TICK 事件，便于其它系统（渲染/日志）响应。

用法：
    from allin_engine.core import World, Entity, Component
    from allin_engine.ai.decision import (BlackboardComponent, BrainComponent,
                                          BrainSystem, build_behavior_tree)

    world = World()
    world.add_system(BrainSystem())
    npc = world.create_entity("goblin")
    npc.add(BlackboardComponent({"hp": 30, "see_player": True}))
    tree = build_behavior_tree(spec)
    npc.add(BrainComponent(tree=tree, name="goblin_ai"))
    world.update(0.016)   # BrainSystem 自动 tick 行为树
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from allin_engine.core import Component, System, World

from .behavior_tree import BehaviorTree, Blackboard, Status
from .state_machine import GenericStateMachine, HierarchicalStateMachine
from .decision_tree import DecisionTree


# 与 core/event_bus.EventTypes 对齐的事件名（避免循环导入，这里定义字符串常量）
EVENT_BRAIN_TICK = "brain_tick"
EVENT_BRAIN_DECISION = "brain_decision"


class BlackboardComponent(Component):
    """实体级共享黑板：行为树节点读写它。"""

    def __init__(self, data: Optional[Dict[str, Any]] = None):
        self.blackboard = Blackboard(data or {})


class BrainComponent(Component):
    """挂在实体上的「决策脑」。可持有行为树 / 状态机 / 决策树（择一或组合）。"""

    def __init__(self, tree: Optional[BehaviorTree] = None,
                 machine: Optional[Any] = None,
                 decision: Optional[DecisionTree] = None,
                 name: str = "brain"):
        self.tree = tree                      # BehaviorTree | None
        self.machine = machine                # GenericStateMachine / HSM | None
        self.decision = decision              # DecisionTree | None
        self.name = name
        self.last_status: Optional[str] = None
        self.last_decision: Optional[str] = None
        self.tick_count: int = 0

    def decide(self, features: Dict[str, Any]) -> Optional[str]:
        """用持有的决策树做一次路由决策（一次性）。"""
        if self.decision is None:
            return None
        res = self.decision.decide(features)
        self.last_decision = res.label
        return res.label


class BrainSystem(System):
    """每帧驱动实体上的行为树 / 状态机。priority 较低以便其它系统先更新数据。"""

    priority: int = 20

    def __init__(self, event_bus=None):
        self.event_bus = event_bus

    def _emit(self, etype: str, data: Any) -> None:
        if self.event_bus is not None:
            try:
                self.event_bus.emit(etype, data)
            except Exception:
                pass

    def update(self, world: World, dt: float) -> None:
        for entity in world.each(BrainComponent):
            brain = entity.get(BrainComponent)

            # 优先复用实体级黑板
            bb = None
            if entity.has(BlackboardComponent):
                bb = entity.get(BlackboardComponent).blackboard

            # 行为树：根驱动 tick（响应式重评估）
            if brain.tree is not None:
                if bb is not None and brain.tree.blackboard is not bb:
                    brain.tree.bind(bb)  # 绑定到实体级黑板（仅首次）
                try:
                    status = brain.tree.tick()
                    brain.last_status = status.value if hasattr(status, "value") else str(status)
                except Exception as e:
                    brain.last_status = f"ERROR:{e}"
                self._emit(EVENT_BRAIN_TICK, {
                    "eid": entity.eid, "brain": brain.name,
                    "status": brain.last_status, "tick": brain.tree.tick_count,
                })

            # 状态机：事件驱动，不在此主动推进（由游戏事件调用 machine.trigger）
            # 决策树：按需调用 brain.decide()，不在此自动执行

            brain.tick_count += 1
