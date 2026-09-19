"""
物品系统 — 可收集、使用和装备的游戏物品。

物品类型涵盖钥匙、记忆、日记、工具、消耗品、武器、防具等。
支持使用效果（sanitary/hp/corruption 调整）和装备属性。
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Item:
    """一个游戏物品。

    属性:
        item_id: 物品唯一标识
        name: 显示名称
        description: 物品描述
        item_type: 物品类型
        usable: 是否可使用
        equippable: 是否可装备
        effects: 使用效果 { "hp": +10, "sanity": -5, "corruption": +2 }
        stats: 装备属性 { "attack": 5, "defense": 3, "speed": 1 }
        metadata: 扩展元数据
    """

    item_id: str
    name: str = ""
    description: str = ""
    item_type: str = "misc"  # misc | key | memory | journal | tool | card | consumable | weapon | armor
    usable: bool = False
    equippable: bool = False
    effects: dict[str, int] = field(default_factory=dict)
    stats: dict[str, int] = field(default_factory=dict)
    metadata: dict = field(default_factory=dict)

    # ================================================================
    # 类型判断
    # ================================================================

    @property
    def is_key(self) -> bool:
        """是否为钥匙类物品。"""
        return self.item_type == "key"

    @property
    def is_weapon(self) -> bool:
        """是否为武器。"""
        return self.item_type == "weapon"

    @property
    def is_armor(self) -> bool:
        """是否为防具。"""
        return self.item_type == "armor"

    @property
    def is_consumable(self) -> bool:
        """是否为消耗品。"""
        return self.item_type == "consumable"

    @property
    def is_journal(self) -> bool:
        """是否为日记/文档类。"""
        return self.item_type in ("journal", "memory")

    # ================================================================
    # 使用与效果
    # ================================================================

    def get_effect(self, key: str) -> int:
        """获取指定效果值，不存在返回 0。"""
        return self.effects.get(key, 0)

    def get_stat(self, key: str) -> int:
        """获取指定装备属性值，不存在返回 0。"""
        return self.stats.get(key, 0)

    # ================================================================
    # 序列化
    # ================================================================

    def to_dict(self) -> dict:
        """序列化为字典。"""
        return {
            "item_id": self.item_id,
            "name": self.name,
            "description": self.description,
            "item_type": self.item_type,
            "usable": self.usable,
            "equippable": self.equippable,
            "effects": self.effects,
            "stats": self.stats,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Item":
        """从字典反序列化。"""
        return cls(
            item_id=data["item_id"],
            name=data.get("name", ""),
            description=data.get("description", ""),
            item_type=data.get("item_type", "misc"),
            usable=data.get("usable", False),
            equippable=data.get("equippable", False),
            effects=data.get("effects", {}),
            stats=data.get("stats", {}),
            metadata=data.get("metadata", {}),
        )

    def __repr__(self) -> str:
        return f"Item({self.item_id}, type={self.item_type})"


# ================================================================
# 预设工具函数
# ================================================================

def create_key(item_id: str, name: str, description: str = "") -> Item:
    """创建钥匙类物品的便捷函数。"""
    return Item(item_id=item_id, name=name, description=description, item_type="key")


def create_consumable(
    item_id: str, name: str, effects: dict[str, int], description: str = ""
) -> Item:
    """创建消耗品物品的便捷函数。"""
    return Item(
        item_id=item_id,
        name=name,
        description=description,
        item_type="consumable",
        usable=True,
        effects=effects,
    )


def create_weapon(
    item_id: str,
    name: str,
    stats: dict[str, int],
    description: str = "",
) -> Item:
    """创建武器物品的便捷函数。"""
    return Item(
        item_id=item_id,
        name=name,
        description=description,
        item_type="weapon",
        equippable=True,
        stats=stats,
    )


def create_armor(
    item_id: str,
    name: str,
    stats: dict[str, int],
    description: str = "",
) -> Item:
    """创建防具物品的便捷函数。"""
    return Item(
        item_id=item_id,
        name=name,
        description=description,
        item_type="armor",
        equippable=True,
        stats=stats,
    )
