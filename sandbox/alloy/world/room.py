"""
房间与关卡结构 — 融合房间定义、传送门与数据驱动机关。

包含:
  - Room: 房间/地点定义，含出口和交互元素
  - Portal: 传送门定义，玩家移动到目标房间
  - Mechanism: 数据驱动机关，含触发条件和动作
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


# ============================================================
# Room — 房间/地点
# ============================================================

@dataclass
class Room:
    """一个房间或地点。

    属性:
        room_id: 唯一标识
        name: 显示名称
        description: 房间描述文本
        items: 此房间中的物品 ID 列表
        characters: 此房间中的角色 ID 列表
        exits: 出口映射 {"north": "room_id", ...}
        is_dark: 是否为黑暗房间（需光源）
        ambient_text: 环境描述文本（进入时显示）
        chapter: 所属章节
        metadata: 扩展元数据
    """

    room_id: str
    name: str = ""
    description: str = ""
    items: list[str] = field(default_factory=list)
    characters: list[str] = field(default_factory=list)
    exits: dict[str, str] = field(default_factory=dict)
    is_dark: bool = False
    ambient_text: str = ""
    chapter: str = ""
    metadata: dict = field(default_factory=dict)

    def get_exit(self, direction: str) -> str | None:
        """获取指定方向的出口房间 ID，无出口则返回 None。"""
        return self.exits.get(direction.lower())

    def has_exit(self, direction: str) -> bool:
        """检查指定方向是否有出口。"""
        return direction.lower() in self.exits

    def set_exit(self, direction: str, target_room_id: str) -> None:
        """设置指定方向的出口。"""
        self.exits[direction.lower()] = target_room_id

    def remove_exit(self, direction: str) -> None:
        """移除指定方向的出口。"""
        self.exits.pop(direction.lower(), None)

    def has_item(self, item_id: str) -> bool:
        """检查房间中是否有指定物品。"""
        return item_id in self.items

    def add_item(self, item_id: str) -> None:
        """添加物品到房间。"""
        if item_id not in self.items:
            self.items.append(item_id)

    def remove_item(self, item_id: str) -> bool:
        """从房间移除物品，成功返回 True。"""
        try:
            self.items.remove(item_id)
            return True
        except ValueError:
            return False

    def has_character(self, char_id: str) -> bool:
        """检查房间中是否有指定角色。"""
        return char_id in self.characters

    def to_dict(self) -> dict:
        """序列化为字典。"""
        return {
            "room_id": self.room_id,
            "name": self.name,
            "description": self.description,
            "items": self.items,
            "characters": self.characters,
            "exits": self.exits,
            "is_dark": self.is_dark,
            "ambient_text": self.ambient_text,
            "chapter": self.chapter,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Room":
        """从字典反序列化。"""
        return cls(
            room_id=data["room_id"],
            name=data.get("name", ""),
            description=data.get("description", ""),
            items=data.get("items", []),
            characters=data.get("characters", []),
            exits=data.get("exits", {}),
            is_dark=data.get("is_dark", False),
            ambient_text=data.get("ambient_text", ""),
            chapter=data.get("chapter", ""),
            metadata=data.get("metadata", {}),
        )


# ============================================================
# Portal — 传送门
# ============================================================

@dataclass
class Portal:
    """传送门定义。

    玩家移动到传送门所在位置时，自动切换到目标房间。

    属性:
        portal_id: 传送门唯一标识
        col: 所在列坐标
        row: 所在行坐标
        char: 地图上显示的字符
        target_room: 目标房间 ID
        target_col: 目标房间的出生列
        target_row: 目标房间的出生行
        one_way: 是否为单向传送门
        locked: 是否锁定（需满足条件才能使用）
        lock_condition: 锁定条件描述
    """

    portal_id: str
    col: int
    row: int
    target_room: str
    target_col: int = 0
    target_row: int = 0
    char: str = "▣"
    one_way: bool = False
    locked: bool = False
    lock_condition: str = ""

    def can_use(self) -> bool:
        """检查传送门是否可用。"""
        return not self.locked

    def unlock(self) -> None:
        """解锁传送门。"""
        self.locked = False

    def to_dict(self) -> dict:
        """序列化为字典。"""
        return {
            "portal_id": self.portal_id,
            "col": self.col,
            "row": self.row,
            "char": self.char,
            "target_room": self.target_room,
            "target_col": self.target_col,
            "target_row": self.target_row,
            "one_way": self.one_way,
            "locked": self.locked,
            "lock_condition": self.lock_condition,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Portal":
        """从字典反序列化。"""
        return cls(
            portal_id=data["portal_id"],
            col=data["col"],
            row=data["row"],
            target_room=data["target_room"],
            target_col=data.get("target_col", 0),
            target_row=data.get("target_row", 0),
            char=data.get("char", "▣"),
            one_way=data.get("one_way", False),
            locked=data.get("locked", False),
            lock_condition=data.get("lock_condition", ""),
        )


# ============================================================
# Mechanism — 数据驱动机关
# ============================================================

@dataclass
class MechanismAction:
    """机关动作定义。

    属性:
        type: 动作类型 (replace_at | replace_region | replace_area | set_flag | unlock_portal | spawn_item)
        params: 动作参数字典
    """

    type: str
    params: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        """序列化为字典。"""
        return {"type": self.type, "params": self.params}

    @classmethod
    def from_dict(cls, data: dict) -> "MechanismAction":
        """从字典反序列化。"""
        params = {k: v for k, v in data.items() if k != "type"}
        return cls(type=data["type"], params=params)


@dataclass
class Mechanism:
    """数据驱动机关定义。

    属性:
        mech_id: 机关唯一标识
        trigger_type: 触发类型 (CARD_COLLECTED | MEMORY_TRIGGERED | ITEM_USED | FLAG_SET | ENTER_ROOM)
        trigger_id: 触发器 ID
        desc: 机关描述
        actions: 触发时执行的动作列表
        one_shot: 是否只触发一次
        triggered: 是否已触发
        condition: 额外触发条件（flag 检查等）
    """

    mech_id: str
    trigger_type: str
    trigger_id: str
    desc: str = ""
    actions: list[MechanismAction] = field(default_factory=list)
    one_shot: bool = True
    triggered: bool = False
    condition: dict | None = None

    def can_trigger(self) -> bool:
        """检查机关是否可触发。"""
        if self.one_shot and self.triggered:
            return False
        return True

    def execute(self, context: dict | None = None) -> list[MechanismAction]:
        """标记已触发并返回动作列表。"""
        self.triggered = True
        return self.actions

    def reset(self) -> None:
        """重置机关状态。"""
        self.triggered = False

    def to_dict(self) -> dict:
        """序列化为字典。"""
        return {
            "mech_id": self.mech_id,
            "trigger_type": self.trigger_type,
            "trigger_id": self.trigger_id,
            "desc": self.desc,
            "actions": [a.to_dict() for a in self.actions],
            "one_shot": self.one_shot,
            "triggered": self.triggered,
            "condition": self.condition,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Mechanism":
        """从字典反序列化。"""
        actions = [MechanismAction.from_dict(a) for a in data.get("actions", [])]
        return cls(
            mech_id=data["mech_id"],
            trigger_type=data["trigger_type"],
            trigger_id=data["trigger_id"],
            desc=data.get("desc", ""),
            actions=actions,
            one_shot=data.get("one_shot", True),
            triggered=data.get("triggered", False),
            condition=data.get("condition"),
        )
