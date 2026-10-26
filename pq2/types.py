"""核心数据类型定义"""

from dataclasses import dataclass, field
from enum import IntEnum
from typing import Optional


@dataclass
class Attribute:
    """装备属性（好/坏）"""
    label: str
    value: int  # 正值为好属性，负值为坏属性


@dataclass
class Item:
    """装备物品"""
    label: str
    level: int


@dataclass
class Monster:
    """怪物"""
    name: str
    level: int
    drop: str = ""  # 掉落物名，"*" 表示掉落特殊物品


@dataclass
class Race:
    """种族"""
    name: str
    attributes: list = field(default_factory=list)


@dataclass
class Class:
    """职业"""
    name: str
    attributes: list = field(default_factory=list)


@dataclass
class Stack:
    """可堆叠物品（法术、背包物品）"""
    name: str
    count: int = 1


@dataclass
class Quest:
    """任务"""
    label: str
    monster: Optional[Monster] = None


@dataclass
class QueueItem:
    """行动队列项"""
    type: int = 0  # 0=Task, 1=Plot
    label: str = ""
    ms: int = 0


# ============ 枚举 ============

class Equipment(IntEnum):
    """装备槽位"""
    Weapon = 0
    Shield = 1
    Helm = 2
    Hauberk = 3
    Brassairts = 4
    Vambraces = 5
    Gauntlets = 6
    Gambeson = 7
    Cuisses = 8
    Greaves = 9
    Sollerets = 10


EQUIPMENT_LABELS = [
    "Weapon", "Shield", "Helm", "Hauberk", "Brassairts",
    "Vambraces", "Gauntlets", "Gambeson", "Cuisses", "Greaves", "Sollerets",
]


class QueueItemType(IntEnum):
    Task = 0
    Plot = 1


class CurrentActionType(IntEnum):
    Loading = 0
    Kill = 1
    Buying = 2
    Selling = 3
    Market = 4
    None_ = 5
    Heading = 6


class Color(IntEnum):
    Gray = 1
    Silver = 2
    White = 3
    Yellow = 4
    Red = 5


class GameState(IntEnum):
    None_ = 0
    Ready = 1
    Finished = 2


class LoadError(IntEnum):
    None_ = 0
    FileNotFound = 1
    InvalidPermissions = 2
    NotValidSaveFile = 3
    UnknownSaveVersion = 4
    Corrupt = 5          # A7/ADR-001：信封/结构层损坏（解压失败/JSON 解析失败/mac 不匹配）


class SaveError(IntEnum):
    None_ = 0
    InvalidPath = 1
    InvalidPermissions = 2
    OutOfSpace = 3
