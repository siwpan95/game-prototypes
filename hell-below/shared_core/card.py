"""
Card — 卡牌定义（卡牌战斗模式可选模块）。
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Callable, Optional


@dataclass
class Card:
    """一张可打出的卡牌。"""
    id: str
    name: str
    description: str = ""
    ap_cost: int = 1           # 行动点消耗
    nerve_cost: int = 0        # 心智消耗
    damage: int = 0            # 对敌伤害
    block: int = 0             # 格挡值
    heal: int = 0              # 治疗量
    playable: bool = True
    metadata: dict = field(default_factory=dict)

    # 效果函数：接受 CombatState，修改状态
    effect: Callable[[Any], None] | None = None

    def to_dict(self) -> dict:
        return {
            "id": self.id, "name": self.name,
            "description": self.description,
            "ap_cost": self.ap_cost, "nerve_cost": self.nerve_cost,
            "damage": self.damage, "block": self.block,
            "heal": self.heal, "playable": self.playable,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Card":
        return cls(
            id=data["id"], name=data["name"],
            description=data.get("description", ""),
            ap_cost=data.get("ap_cost", 1),
            nerve_cost=data.get("nerve_cost", 0),
            damage=data.get("damage", 0),
            block=data.get("block", 0),
            heal=data.get("heal", 0),
            playable=data.get("playable", True),
            metadata=data.get("metadata", {}),
        )


class CardDeck:
    """卡组管理器。"""

    def __init__(self):
        self.cards: list[Card] = []

    def add(self, card: Card) -> None:
        self.cards.append(card)

    def remove(self, card_id: str) -> bool:
        for i, c in enumerate(self.cards):
            if c.id == card_id:
                self.cards.pop(i)
                return True
        return False

    def get(self, card_id: str) -> Optional[Card]:
        for c in self.cards:
            if c.id == card_id:
                return c
        return None

    def shuffle(self) -> None:
        import random
        random.shuffle(self.cards)

    @property
    def count(self) -> int:
        return len(self.cards)


def get_card_by_id(card_id: str, deck: list[Card] | None = None) -> Optional[Card]:
    """按 ID 查找卡牌（兼容性函数）。"""
    from shared_core.combat_engine import DEFAULT_DECK
    search_list = deck or DEFAULT_DECK or []
    for c in search_list:
        if c.id == card_id:
            return c
    return None


# 默认空卡组
DEFAULT_DECK: list[Card] = []
