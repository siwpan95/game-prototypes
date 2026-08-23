# -*- coding: utf-8 -*-
"""
alloy.ai.decision — 决策/行为范式子包
==============================================

从 zhuangtaiji 项目集成并增强的多范式决策引擎，覆盖游戏 AI 与状态管理的
四种核心范式：

  * 状态机 (FSM / HSM)  —— 状态 + 事件转移的时序演化
      state_machine / hierarchical_state_machine / create_state_machine
  * 行为树 (Behavior Tree) —— 根驱动、每帧重评估的响应式行为编排
      behavior_tree / Blackboard / build_behavior_tree
  * 决策树 (Decision Tree) —— 基于特征空间的一次性路由决策
      decision_tree / DecisionResult / build_decision_tree
  * 差分引擎 (Difference Engine) —— 巴贝奇有限差分 + 状态差量/响应式
      difference_engine / FiniteDifference / StateDiff / ReactiveTracker

粘合层（接入 ECS 世界循环）：
  * brain.BrainComponent / BlackboardComponent / BrainSystem

数据驱动：
  * loader.default_brains_config / build_brain_from_spec / load_decision_config
"""
from __future__ import annotations

# 状态机
from .state_machine import (
    GenericStateMachine,
    create_state_machine,
    register_guard,
    GUARD_REGISTRY,
)
from .hierarchical_state_machine import HierarchicalStateMachine

# 行为树
from .behavior_tree import (
    BehaviorTree,
    Blackboard,
    Status,
    Sequence,
    Selector,
    Parallel,
    Inverter,
    Succeeder,
    Failer,
    Repeater,
    Condition,
    Action,
    build_behavior_tree,
)

# 决策树
from .decision_tree import (
    DecisionTree,
    DecisionResult,
    build_decision_tree,
)

# 差分引擎
from .difference_engine import (
    FiniteDifference,
    StateDiff,
    DiffEntry,
    ReactiveTracker,
)

# ECS 粘合层
from .brain import (
    BrainComponent,
    BlackboardComponent,
    BrainSystem,
    EVENT_BRAIN_TICK,
    EVENT_BRAIN_DECISION,
)

# 数据驱动加载
from .loader import (
    DEFAULT_CONFIG,
    default_brains_config,
    load_decision_config,
    build_brain_from_spec,
    build_behavior_tree_from_spec,
    build_decision_tree_from_spec,
    build_state_machine_from_spec,
    build_finite_difference_from_spec,
)

__all__ = [
    # 状态机
    "GenericStateMachine", "create_state_machine", "register_guard", "GUARD_REGISTRY",
    "HierarchicalStateMachine",
    # 行为树
    "BehaviorTree", "Blackboard", "Status", "Sequence", "Selector", "Parallel",
    "Inverter", "Succeeder", "Failer", "Repeater", "Condition", "Action",
    "build_behavior_tree",
    # 决策树
    "DecisionTree", "DecisionResult", "build_decision_tree",
    # 差分引擎
    "FiniteDifference", "StateDiff", "DiffEntry", "ReactiveTracker",
    # ECS 粘合层
    "BrainComponent", "BlackboardComponent", "BrainSystem",
    "EVENT_BRAIN_TICK", "EVENT_BRAIN_DECISION",
    # 加载
    "DEFAULT_CONFIG", "default_brains_config", "load_decision_config",
    "build_brain_from_spec", "build_behavior_tree_from_spec",
    "build_decision_tree_from_spec", "build_state_machine_from_spec",
    "build_finite_difference_from_spec",
]

__version__ = "1.0.0"
