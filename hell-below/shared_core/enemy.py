"""
Enemy — 敌人定义（卡牌战斗模式可选模块）。
"""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class IntentType(Enum):
    ATTACK = "attack"
    BLOCK = "block"
    SWIFT = "swift"
    IGNORE_RING = "ignore_ring"
    COPY = "copy"
    HIGH_PRESS = "high_press"
    STAGGER = "stagger"


@dataclass
class Intent:
    """敌人行动意图。"""
    name: str = "攻击"
    description: str = ""
    damage: int = 5
    effect_tag: str = ""   # BLOCK, SWIFT, IGNORE_RING, COPY, HIGH_PRESS, STAGGER


@dataclass
class Enemy:
    """敌人模板定义。"""
    id: str
    name: str
    hp: int = 50
    max_hp: int = 50
    armor: int = 0
    is_boss: bool = False
    intents: list[Intent] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "id": self.id, "name": self.name,
            "hp": self.hp, "max_hp": self.max_hp,
            "armor": self.armor, "is_boss": self.is_boss,
            "intents": [{"name": i.name, "damage": i.damage,
                        "effect_tag": i.effect_tag} for i in self.intents],
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Enemy":
        intents_data = data.get("intents", [])
        intents = [Intent(**i) for i in intents_data] if intents_data else []
        return cls(
            id=data["id"], name=data["name"],
            hp=data.get("hp", 50), max_hp=data.get("max_hp", 50),
            armor=data.get("armor", 0),
            is_boss=data.get("is_boss", False),
            intents=intents,
            metadata=data.get("metadata", {}),
        )


@dataclass
class EnemyInstance:
    """敌人在单场战斗中的实例。"""

    def __init__(self, template: Enemy):
        self.id = template.id
        self.name = template.name
        self.hp = template.hp
        self.max_hp = template.max_hp
        self.armor = template.armor
        self.is_boss = template.is_boss
        # 意图列表（循环使用）
        self._intents = list(template.intents)
        if not self._intents:
            self._intents = [Intent(name="攻击", damage=5)]
        self._intent_idx: int = 0

    def choose_intent(self) -> Intent:
        """选择本轮意图。"""
        intent = self._intents[self._intent_idx % len(self._intents)]
        self._intent_idx += 1
        return intent

    def peek_intent(self) -> Intent:
        """窥视下一轮意图（不推进）。"""
        return self._intents[self._intent_idx % len(self._intents)]

    @property
    def alive(self) -> bool:
        return self.hp > 0
