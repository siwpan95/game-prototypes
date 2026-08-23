"""
alloy AI 子包。

提供叙事引擎、对话引擎和内容生成三大核心模块。

主要导出：
- NarrativeEngine, Scene, Option, ConditionEvaluator — 分支剧情系统
- DialogueEngine, MatchResult — 对话管理和响应生成
- ContentGenerator, GenerationConfig — AI 内容生成（Ollama/DeepSeek 双后端）
"""

from .narrative import (
    NarrativeEngine,
    Scene,
    Option,
    ConditionEvaluator,
    NarrativeState,   # 原名 GameState，已重命名
    GameState,        # 已废弃别名，请改用 NarrativeState
    SceneHistory,
    load_scenes_from_json,
)
from .dialogue import (
    DialogueEngine,
    MatchResult,
)
from .generator import (
    ContentGenerator,
    GenerationConfig,
    get_generator,
    reset_generator,
)

# 决策/行为范式子包：状态机 / 行为树 / 决策树 / 差分引擎 + ECS 脑
from .decision import (
    GenericStateMachine,
    create_state_machine,
    HierarchicalStateMachine,
    BehaviorTree,
    Blackboard,
    DecisionTree,
    FiniteDifference,
    StateDiff,
    ReactiveTracker,
    BrainComponent,
    BlackboardComponent,
    BrainSystem,
    default_brains_config,
    load_decision_config,
    build_brain_from_spec,
)

__all__ = [
    # narrative
    "NarrativeEngine",
    "Scene",
    "Option",
    "ConditionEvaluator",
    "NarrativeState",   # 原名 GameState，已重命名
    "GameState",        # 已废弃别名，请改用 NarrativeState
    "SceneHistory",
    "load_scenes_from_json",
    # dialogue
    "DialogueEngine",
    "MatchResult",
    # generator
    "ContentGenerator",
    "GenerationConfig",
    "get_generator",
    "reset_generator",
    # decision / behavior paradigms
    "GenericStateMachine",
    "create_state_machine",
    "HierarchicalStateMachine",
    "BehaviorTree",
    "Blackboard",
    "DecisionTree",
    "FiniteDifference",
    "StateDiff",
    "ReactiveTracker",
    "BrainComponent",
    "BlackboardComponent",
    "BrainSystem",
    "default_brains_config",
    "load_decision_config",
    "build_brain_from_spec",
]

__version__ = "1.0.0"
