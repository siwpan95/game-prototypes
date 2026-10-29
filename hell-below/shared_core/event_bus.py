"""
Event Bus — 发布/订阅事件总线。

从领域驱动架构（BrianSimpson_CN 等）合并而来。
用于解耦模块间通信，所有游戏均可选用。
"""

from __future__ import annotations
from typing import Any, Callable, Dict, List


class EventTypes:
    """事件类型常量。"""
    # 通用事件
    ROOM_ENTER = "room_enter"
    ROOM_EXIT = "room_exit"
    ITEM_TAKE = "item_take"
    ITEM_DROP = "item_drop"
    ITEM_USE = "item_use"
    FLAG_CHANGE = "flag_change"
    NARRATIVE_TRIGGER = "narrative"
    PUZZLE_SOLVED = "puzzle_solved"
    CHAPTER_CHANGE = "chapter_change"
    GAME_OVER = "game_over"

    # 故事模式事件
    IMAGERY_DISCOVER = "imagery_discover"
    BRANCH_TAKEN = "branch_taken"
    CHOICE_MADE = "choice_made"
    SHARD_FOUND = "shard_found"
    DREAM_ENTER = "dream_enter"
    DREAM_EXIT = "dream_exit"

    # 战斗事件
    COMBAT_START = "combat_start"
    COMBAT_END = "combat_end"
    CARD_PLAYED = "card_played"
    ENEMY_TURN = "enemy_turn"


class EventBus:
    """简单的事件总线，支持发布/订阅。"""

    def __init__(self):
        self._listeners: Dict[str, List[Callable[..., None]]] = {}

    def subscribe(self, event_type: str, listener: Callable[..., None]) -> None:
        """订阅事件。"""
        if event_type not in self._listeners:
            self._listeners[event_type] = []
        if listener not in self._listeners[event_type]:
            self._listeners[event_type].append(listener)

    def unsubscribe(self, event_type: str, listener: Callable) -> bool:
        """取消订阅。返回是否成功移除。"""
        if event_type in self._listeners:
            try:
                self._listeners[event_type].remove(listener)
                return True
            except ValueError:
                pass
        return False

    def publish(self, event_type: str, **kwargs: Any) -> int:
        """发布事件，返回通知的监听器数量。"""
        count = 0
        for listener in self._listeners.get(event_type, []):
            try:
                listener(**kwargs)
                count += 1
            except Exception as e:
                print(f"[EventBus] Error in listener for {event_type}: {e}")
        return count

    def clear(self) -> None:
        """清除所有订阅。"""
        self._listeners.clear()

    def listeners_count(self, event_type: str) -> int:
        """返回某事件的监听器数量。"""
        return len(self._listeners.get(event_type, []))
