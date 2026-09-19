"""
卡牌系统 — 卡牌定义、卡组管理与卡牌库。

支持从 JSON 数据驱动加载卡牌定义。
卡牌可包含自定义效果函数（effects）。

使用方式:

    card = Card("slash", "斩击", damage=8, ap_cost=1)
    deck = CardDeck()
    deck.add(card)

    lib = CardLibrary()
    lib.load_from_json("data/cards/")
    card = lib.get_card("slash")
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional

from allin_engine.core.data_library import DataLibrary


# ---------------------------------------------------------------
# Card — 卡牌定义
# ---------------------------------------------------------------

@dataclass
class Card:
    """一张可打出的卡牌。

    Attributes:
        id: 唯一标识符
        name: 卡牌名称
        description: 卡牌描述
        ap_cost: 行动点消耗
        nerve_cost: 心智消耗
        damage: 对敌伤害
        block: 格挡值
        heal: 治疗量
        playable: 是否可打出
        effect: 自定义效果函数（接受 CombatState，修改状态）
        metadata: 扩展属性
    """

    id: str
    name: str
    description: str = ""
    ap_cost: int = 1
    nerve_cost: int = 0
    damage: int = 0
    block: int = 0
    heal: int = 0
    playable: bool = True
    effect: Optional[Callable[[Any], None]] = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        """序列化为字典（不含 effect 函数）。"""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "ap_cost": self.ap_cost,
            "nerve_cost": self.nerve_cost,
            "damage": self.damage,
            "block": self.block,
            "heal": self.heal,
            "playable": self.playable,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Card":
        """从字典反序列化。"""
        return cls(
            id=data["id"],
            name=data["name"],
            description=data.get("description", ""),
            ap_cost=data.get("ap_cost", 1),
            nerve_cost=data.get("nerve_cost", 0),
            damage=data.get("damage", 0),
            block=data.get("block", 0),
            heal=data.get("heal", 0),
            playable=data.get("playable", True),
            metadata=data.get("metadata", {}),
        )

    def __repr__(self) -> str:
        parts = [f"Card({self.id}: {self.name}"]
        if self.damage:
            parts.append(f" dmg={self.damage}")
        if self.block:
            parts.append(f" block={self.block}")
        if self.heal:
            parts.append(f" heal={self.heal}")
        parts.append(f" AP={self.ap_cost})")
        return "".join(parts)

    @property
    def cost(self) -> tuple[int, int]:
        """返回 (ap_cost, nerve_cost) 元组。"""
        return (self.ap_cost, self.nerve_cost)


# ---------------------------------------------------------------
# CardDeck — 卡组管理器
# ---------------------------------------------------------------

class CardDeck:
    """卡组管理器。

    支持添加、移除、抽牌、洗牌等操作。

    使用方式:

        deck = CardDeck()
        deck.add(Card("slash", "斩击", damage=8))
        hand = deck.draw(5)
    """

    def __init__(self):
        self._cards: list[Card] = []

    # ---- 基础操作 ----

    def add(self, card: Card) -> None:
        """添加卡牌。"""
        self._cards.append(card)

    def add_batch(self, cards: list[Card]) -> None:
        """批量添加卡牌。"""
        self._cards.extend(cards)

    def remove(self, card_id: str) -> bool:
        """按 ID 移除一张卡牌。

        :returns: 是否成功移除
        """
        for i, c in enumerate(self._cards):
            if c.id == card_id:
                self._cards.pop(i)
                return True
        return False

    def remove_all(self, card_id: str) -> int:
        """按 ID 移除所有同名卡牌。

        :returns: 移除的卡牌数量
        """
        before = len(self._cards)
        self._cards = [c for c in self._cards if c.id != card_id]
        return before - len(self._cards)

    def get(self, card_id: str) -> Optional[Card]:
        """按 ID 查找卡牌。"""
        for c in self._cards:
            if c.id == card_id:
                return c
        return None

    def has(self, card_id: str) -> bool:
        """检查是否包含指定卡牌。"""
        return self.get(card_id) is not None

    def clear(self) -> None:
        """清空卡组。"""
        self._cards.clear()

    # ---- 抽牌 ----

    def draw(self, n: int = 1) -> list[Card]:
        """从顶部抽 n 张牌。

        :param n: 抽牌数量
        :returns: 抽到的卡牌列表
        """
        drawn: list[Card] = []
        for _ in range(n):
            if not self._cards:
                break
            drawn.append(self._cards.pop())
        return drawn

    def shuffle(self) -> None:
        """洗牌。"""
        random.shuffle(self._cards)

    def discard(self, card: Card) -> None:
        """弃牌（放入弃牌堆）。"""
        self._cards.append(card)

    def discard_batch(self, cards: list[Card]) -> None:
        """批量弃牌。"""
        self._cards.extend(cards)

    # ---- 查询 ----

    @property
    def count(self) -> int:
        """卡组中的卡牌总数。"""
        return len(self._cards)

    @property
    def is_empty(self) -> bool:
        """卡组是否为空。"""
        return len(self._cards) == 0

    @property
    def cards(self) -> list[Card]:
        """返回卡牌列表（只读）。"""
        return list(self._cards)

    def list_ids(self) -> list[str]:
        """列出所有卡牌 ID。"""
        return [c.id for c in self._cards]

    def list_by_name(self, name: str) -> list[Card]:
        """按名称模糊查找（子串匹配）。"""
        name_lower = name.lower()
        return [c for c in self._cards if name_lower in c.name.lower()]

    # ---- 序列化 ----

    def to_dict(self) -> dict:
        """导出为可序列化字典。"""
        return {
            "cards": [c.to_dict() for c in self._cards],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "CardDeck":
        """从字典恢复卡组。"""
        deck = cls()
        for cd in data.get("cards", []):
            deck.add(Card.from_dict(cd))
        return deck

    # ---- 魔术方法 ----

    def __len__(self) -> int:
        return len(self._cards)

    def __iter__(self):
        return iter(self._cards)

    def __contains__(self, card_id: str) -> bool:
        return self.has(card_id)

    def __repr__(self) -> str:
        return f"CardDeck({len(self._cards)} cards)"


# ---------------------------------------------------------------
# CardLibrary — 卡牌库（基于 DataLibrary）
# ---------------------------------------------------------------

class CardLibrary(DataLibrary[Card]):
    """卡牌库 — 管理和检索所有可用的卡牌定义。

    继承自 DataLibrary，支持从 JSON 文件/目录加载卡牌数据。

    使用方式:

        lib = CardLibrary()
        lib.load_from_json("data/cards/")
        lib.load_from_mod_dir("mods/my_mod/")
        card = lib.get_card("slash")
    """

    def __init__(self, logger: Any = None):
        super().__init__(
            factory=Card.from_dict,
            item_key="cards",
            item_name="卡牌",
            logger=logger,
        )

    # ── 查询（CardLibrary 特有接口） ──

    def get_card(self, card_id: str) -> Optional[Card]:
        """获取卡牌定义（返回副本）。

        返回浅拷贝以避免外部修改库中模板。
        effect 函数不会被拷贝。
        """
        card = self._items.get(card_id)
        if card is None:
            return None
        return Card(
            id=card.id,
            name=card.name,
            description=card.description,
            ap_cost=card.ap_cost,
            nerve_cost=card.nerve_cost,
            damage=card.damage,
            block=card.block,
            heal=card.heal,
            playable=card.playable,
            effect=card.effect,
            metadata=dict(card.metadata),
        )

    def has_card(self, card_id: str) -> bool:
        """卡牌定义是否存在。"""
        return self.has(card_id)

    def list_cards(self, card_type: str | None = None) -> list[Card]:
        """列出所有卡牌（或按类型筛选）。

        :param card_type: 类型筛选（如 "attack", "defense", "utility"）
        """
        cards = list(self._items.values())
        if card_type:
            cards = [c for c in cards if c.metadata.get("type") == card_type]
        return cards

    @property
    def all_cards(self) -> dict[str, Card]:
        """返回所有卡牌定义（只读）。"""
        return self.all_items

    @classmethod
    def from_json(cls, source: str | Path) -> "CardLibrary":
        """从 JSON 创建 CardLibrary（兼容旧版 API）。"""
        lib = cls()
        lib.load_from_json(source)
        return lib
