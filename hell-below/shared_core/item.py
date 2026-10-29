"""Item — 游戏中可收集/使用的物品定义。"""

from __future__ import annotations
from dataclasses import dataclass, field


@dataclass
class Item:
    """一个游戏物品。"""
    item_id: str
    name: str
    description: str
    item_type: str = "misc"  # fragment, key, memory, journal, tool, card, consumable
    usable: bool = False
    effects: dict[str, int] = field(default_factory=dict)
    imagery_related: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "item_id": self.item_id, "name": self.name,
            "description": self.description, "item_type": self.item_type,
            "usable": self.usable, "effects": self.effects,
            "imagery_related": self.imagery_related, "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Item":
        return cls(
            item_id=data["item_id"], name=data["name"],
            description=data["description"],
            item_type=data.get("item_type", "misc"),
            usable=data.get("usable", False),
            effects=data.get("effects", {}),
            imagery_related=data.get("imagery_related", []),
            metadata=data.get("metadata", {}),
        )
