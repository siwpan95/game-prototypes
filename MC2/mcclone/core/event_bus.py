# -*- coding: utf-8 -*-
"""event_bus — MC2 事件总线，统一到 allin_engine.core.event_bus.EventBus。

整合说明（去「本地平行实现」为「引擎上层应用」）：
  MC2 原本自带一套轻量事件总线（仅日志订阅）。整合后，MC2 的事件真正流经
  allin_engine 的统一事件总线（递归保护 / 容错 / 调试日志一应俱全），与 MC1
  共用同一套引擎事件实现，构成统一产品。

  - 对外 API 完全保持兼容：subscribe(event_type, handler) / emit(event_type, **data)
    以及 EventTypes 常量均不变，全部既有测试与业务逻辑零改动。
  - 订阅者签名自适应：MC2 既有 handler 既有 ``(event_type, data)`` 也有 ``(data)``，
    适配器按函数签名自动分发，两种写法都继续可用。
  - emit 的 **kwargs 汇总为 data 字典后交给引擎总线，语义与原实现一致。
"""

from __future__ import annotations

import inspect
import logging
from typing import Any, Callable, Dict, List, Optional

from allin_engine.core.event_bus import EventBus as _EngineEventBus

# 事件类型常量（保留原样，确保既有代码与测试零改动）。
class EventTypes:
    """事件类型常量（字符串）。M1 四类 + M2 扩展（见 §9 / T-M2-09）。"""

    # ── M1 既有事件 ──
    PLAYER_MOVED = "PLAYER_MOVED"
    BLOCK_BROKEN = "BLOCK_BROKEN"
    BLOCK_PLACED = "BLOCK_PLACED"
    PLAYER_LANDED = "PLAYER_LANDED"
    DEBUG = "DEBUG"

    # ── M2 新增事件（生存/合成，T-M2-09）──
    PLAYER_DIED = "PLAYER_DIED"        # HP 归零瞬间
    PLAYER_RESPAWN = "PLAYER_RESPAWN"  # 重生完成
    ITEM_CRAFTED = "ITEM_CRAFTED"      # 合成成功（携带 id/n）

    # ── M3 新增事件（模拟/作业/层，T-M3-12）──
    Z_LEVEL_CHANGED = "Z_LEVEL_CHANGED"    # 当前 Z 层切换
    SIM_TICK = "SIM_TICK"                  # 模拟步进（≤20Hz）
    JOB_CREATED = "JOB_CREATED"            # 作业被指派
    JOB_DONE = "JOB_DONE"                  # 作业完成（改世界）
    JOB_CANCELLED = "JOB_CANCELLED"        # 作业被取消

    # ── M4 新增事件（生物/世界，T-M4-09）──
    CREATURE_SPAWNED = "CREATURE_SPAWNED"  # 刷怪成功（kind, x, y）
    CREATURE_DIED = "CREATURE_DIED"        # 生物 hp<=0（kind, x, y, drops）
    CREATURE_HIT = "CREATURE_HIT"          # 玩家近战命中生物（kind, id, dmg）
    PLAYER_HIT = "PLAYER_HIT"              # 生物近身攻击玩家（dmg, kind）
    CREATURE_TAMED = "CREATURE_TAMED"      # R7 占位（驯服，本里程碑不 emit）
    SOUND_PLAYED = "SOUND_PLAYED"          # R8 占位（音效钩子，name）

    # ── M5 新增事件（存档/读档，T-M5-*）──
    SAVE_GAME = "SAVE_GAME"            # 游戏状态已写入存档（path）
    LOAD_GAME = "LOAD_GAME"            # 从存档还原完成（path）

    # ── M6 新增事件（渲染与体验美化，T-M6-*）──
    PLAYER_STEP = "PLAYER_STEP"        # 玩家在地面水平移动（脚步尘土，x, y）


# 默认日志订阅者用到的 logger（M1 仅日志，不触发任何游戏逻辑）。
_logger = logging.getLogger("mc_clone.event")


def log_subscriber(event_type: str, data: dict) -> None:
    """默认日志订阅者：把事件打印到日志（M1 仅日志）。"""
    _logger.info("[事件] %s %s", event_type, data)


def _dispatch(handler: Callable, event_type: str, data: Any) -> None:
    """按订阅者签名自适应调用：支持 ``(event_type, data)`` 与 ``(data)`` 两种写法。"""
    data = data if data is not None else {}
    try:
        params = inspect.signature(handler).parameters
    except (ValueError, TypeError):
        params = {}  # 内置/C 扩展 callable 无法 introspect → 视为单参
    if len(params) >= 2:
        handler(event_type, data)
    else:
        handler(data)


class EventBus:
    """MC2 事件总线 —— 适配器，底层为 allin_engine 统一事件总线。

    emit 同步调用所有订阅者（经引擎总线，带递归保护与容错）；
    订阅者签名 ``(event_type, data)`` 或 ``(data)`` 均可。
    """

    def __init__(self, engine_bus: Optional[_EngineEventBus] = None) -> None:
        # 允许外部传入共享引擎总线（统一产品场景下 MC1/MC2 共用同一总线）；
        # 默认各自持有一个引擎总线实例，行为与原有「每游戏一个总线」一致。
        self._engine_bus = engine_bus or _EngineEventBus()
        self._wrappers: Dict[str, List[Callable]] = {}

    def subscribe(self, event_type: str,
                  handler: Callable) -> None:
        """订阅某类事件；同一 handler 按注册顺序调用。"""
        def _adapt(data: Any) -> None:
            _dispatch(handler, event_type, data)
        self._engine_bus.subscribe(event_type, _adapt)
        self._wrappers.setdefault(event_type, []).append(handler)

    def emit(self, event_type: str, **data) -> int:
        """发布事件（同步调用所有订阅者，流经引擎总线）。

        返回：被通知的订阅者数量（引擎总线提供）。
        """
        return self._engine_bus.emit(event_type, data if data else {})

    # ── 兼容查询（按需透传到引擎总线）──
    def has_listeners(self, event_type: str) -> bool:
        return self._engine_bus.has_listeners(event_type)

    def listener_count(self, event_type: str) -> int:
        return self._engine_bus.listener_count(event_type)

    def total_listeners(self) -> int:
        return self._engine_bus.total_listeners()

    def registered_events(self) -> List[str]:
        return self._engine_bus.registered_events()

    def clear(self, event_type: Optional[str] = None) -> None:
        self._engine_bus.clear(event_type)
        if event_type:
            self._wrappers.pop(event_type, None)
        else:
            self._wrappers.clear()
