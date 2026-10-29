# -*- coding: utf-8 -*-
"""
状态机包（从 zhuangtaiji/core 复制，纯标准库实现，零第三方依赖、零外部引用）

仅导出有限状态机 / 层次状态机相关符号，供《暗黑破坏神：灾厄纪元》使用。
按"复制即复用"原则内联到本项目，与源工具零耦合。
"""
from .state_machine import (
    GenericStateMachine,
    create_state_machine,
    register_guard,
    register_action,
    GUARD_REGISTRY,
    ACTION_REGISTRY,
)
from .hierarchical_state_machine import HierarchicalStateMachine

__all__ = [
    "GenericStateMachine",
    "create_state_machine",
    "HierarchicalStateMachine",
    "register_guard",
    "register_action",
    "GUARD_REGISTRY",
    "ACTION_REGISTRY",
]
