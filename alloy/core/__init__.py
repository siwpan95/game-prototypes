"""
alloy.core — 统一游戏引擎核心层
==========================================

提供 ECS 架构、事件总线、全局配置和资源路径管理。

核心模块：
    - ecs:        Entity-Component-System 架构
    - event_bus:  松耦合发布/订阅事件总线
    - config:     全局配置常量
    - paths:      资源路径工具

用法：
    from alloy.core import World, Entity, Component, System
    from alloy.core import EventBus, EventTypes
    from alloy.core.config import CELL, COLS, ROWS
    from alloy.core.paths import ROOT, get_assets_dir
"""

from __future__ import annotations

# ── ECS ────────────────────────────────────────────────

from alloy.core.ecs import (
    # Entity & Component
    Entity,
    Component,
    is_component,

    # System
    System,

    # World
    World,
)

# ── 可序列化 World ──────────────────────────────────
from alloy.core.world_serial import SerializableWorld

# ── 事件总线 ──────────────────────────────────────────

from alloy.core.event_bus import (
    EventBus,
    EventTypes,
    EventHandler,
)


# ── 序列化 & 数据驱动 ────────────────────────────────

from alloy.core.serializable import Serializable, Snapshotable
from alloy.core.data_library import DataLibrary

# ── 可选依赖探测 ────────────────────────────────────
from alloy.core.deps import (
    MissingDependencyError,
    feature_flags,
    has,
    require,
    report,
)

# ── 游戏循环（固定时间步长） ─────────────────────────

from alloy.core.game_loop import (
    FixedTimestepLoop,
    GameLoopStats,
)


# ── 可逆装配内核（Context：注册即回滚） ──────────────

from alloy.core.context import (
    Context,
    DuplicateServiceError,
)


# ── 世界事件日志（WorldLog：日志即事实源） ───────────

from alloy.core.world_log import (
    WorldLog,
)


# ── 公共接口 ──────────────────────────────────────────

__all__ = [
    # ECS
    "Entity",
    "Component",
    "is_component",
    "System",
    "World",
    "SerializableWorld",

    # 依赖探测
    "MissingDependencyError",
    "feature_flags",
    "has",
    "require",
    "report",

    # Event Bus
    "EventBus",
    "EventTypes",
    "EventHandler",

    # Serialization & Data
    "Serializable",
    "Snapshotable",
    "DataLibrary",

    # Game Loop
    "FixedTimestepLoop",
    "GameLoopStats",

    # 可逆装配内核
    "Context",
    "DuplicateServiceError",

    # 世界事件日志
    "WorldLog",
]
