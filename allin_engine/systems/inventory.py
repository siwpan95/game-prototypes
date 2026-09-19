"""
背包系统 — 物品管理与容量控制。

支持添加、移除、查询物品，按类型筛选，
容量限制与堆叠物品支持，自动整理。

使用方式:

    inv = Inventory(capacity=20)
    inv.add(InventoryItem("sword", "铁剑", "weapon"))
    inv.has("sword")   # → True
    inv.list_by_type("weapon")  # → [InventoryItem(...)]
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


# ---------------------------------------------------------------
# InventoryItem — 物品数据类
# ---------------------------------------------------------------

@dataclass
class InventoryItem:
    """背包物品。

    Attributes:
        item_id: 唯一标识符
        name: 显示名称
        item_type: 物品类型（weapon / armor / consumable / key / quest / material）
        description: 物品描述
        quantity: 堆叠数量
        max_stack: 最大堆叠数（0 = 不可堆叠）
        value: 物品价值/权重
        metadata: 扩展属性
    """

    item_id: str
    name: str
    item_type: str = "consumable"
    description: str = ""
    quantity: int = 1
    max_stack: int = 1
    value: int = 0
    usable: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def is_stackable(self) -> bool:
        """是否可以堆叠。"""
        return self.max_stack > 1

    @property
    def total_weight(self) -> int:
        """总重量 = 单个重量 * 数量。"""
        single_weight = self.metadata.get("weight", 0)
        return single_weight * self.quantity

    def can_merge(self, other: "InventoryItem") -> bool:
        """检查两个物品能否合并（同 ID 且可堆叠）。"""
        return (
            self.item_id == other.item_id
            and self.is_stackable
            and self.quantity + other.quantity <= self.max_stack
        )

    def merge(self, other: "InventoryItem") -> int:
        """合并物品，返回未能合并的溢出数量。"""
        if not self.can_merge(other):
            return other.quantity
        total = self.quantity + other.quantity
        self.quantity = min(total, self.max_stack)
        return max(0, total - self.max_stack)

    def to_dict(self) -> dict:
        """序列化为字典。"""
        return {
            "item_id": self.item_id,
            "name": self.name,
            "item_type": self.item_type,
            "description": self.description,
            "quantity": self.quantity,
            "max_stack": self.max_stack,
            "value": self.value,
            "usable": self.usable,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "InventoryItem":
        """从字典反序列化。"""
        return cls(
            item_id=data["item_id"],
            name=data["name"],
            item_type=data.get("item_type", "consumable"),
            description=data.get("description", ""),
            quantity=data.get("quantity", 1),
            max_stack=data.get("max_stack", 1),
            value=data.get("value", 0),
            usable=data.get("usable", False),
            metadata=data.get("metadata", {}),
        )


# ---------------------------------------------------------------
# Inventory — 背包管理器
# ---------------------------------------------------------------

class Inventory:
    """背包管理器。

    特性：
    - 容量限制（可配置）
    - 堆叠物品自动合并
    - 按类型/ID 查询与筛选
    - 自动整理（按类型排序）
    - to_dict / from_dict 存档支持
    - from_data_list 批量加载
    """

    def __init__(self, capacity: int = 20, max_weight: int = 0):
        """
        :param capacity: 最大物品槽位数（0 = 无限制）
        :param max_weight: 最大总重量（0 = 无限制）
        """
        self._items: dict[str, InventoryItem] = {}
        self._capacity: int = capacity
        self._max_weight: int = max_weight

    # ---- 容量 ----

    @property
    def capacity(self) -> int:
        """物品槽位容量上限。"""
        return self._capacity

    @capacity.setter
    def capacity(self, value: int) -> None:
        self._capacity = max(0, value)

    @property
    def max_weight(self) -> int:
        """最大承重上限。"""
        return self._max_weight

    @max_weight.setter
    def max_weight(self, value: int) -> None:
        self._max_weight = max(0, value)

    @property
    def is_full(self) -> bool:
        """背包是否已满（按槽位）。"""
        if self._capacity == 0:
            return False
        return len(self._items) >= self._capacity

    @property
    def remaining_slots(self) -> int:
        """剩余槽位数。"""
        if self._capacity == 0:
            return 9999
        return max(0, self._capacity - len(self._items))

    @property
    def total_weight(self) -> int:
        """当前总重量。"""
        return sum(item.total_weight for item in self._items.values())

    @property
    def is_overweight(self) -> bool:
        """是否超重。"""
        if self._max_weight == 0:
            return False
        return self.total_weight > self._max_weight

    # ---- 基础操作 ----

    def add(self, item: InventoryItem) -> tuple[bool, str]:
        """添加物品到背包。

        自动合并可堆叠的同 ID 物品；不可堆叠且背包满时拒绝。

        :returns: (是否成功, 消息)
        """
        # 尝试合并到已有堆叠
        if item.item_id in self._items and item.is_stackable:
            existing = self._items[item.item_id]
            overflow = existing.merge(item)
            if overflow > 0:
                item.quantity = overflow
            else:
                return (True, f"已添加 {item.name} x{item.quantity}（已合并）")

        # 检查容量
        if self.is_full and item.item_id not in self._items:
            return (False, f"背包已满！无法添加 {item.name}。")

        self._items[item.item_id] = item
        return (True, f"已添加 {item.name} x{item.quantity}")

    def add_batch(self, items: list[InventoryItem]) -> tuple[int, int]:
        """批量添加物品。

        :returns: (成功数, 失败数)
        """
        ok, fail = 0, 0
        for item in items:
            success, _ = self.add(item)
            if success:
                ok += 1
            else:
                fail += 1
        return (ok, fail)

    def remove(self, item_id: str, quantity: int = 0) -> bool:
        """移除物品。

        :param item_id: 物品 ID
        :param quantity: 移除数量（0 = 全部移除）
        :returns: 是否成功移除
        """
        item = self._items.get(item_id)
        if item is None:
            return False

        if quantity == 0 or quantity >= item.quantity:
            del self._items[item_id]
        else:
            item.quantity = max(0, item.quantity - quantity)
            if item.quantity == 0:
                del self._items[item_id]
        return True

    def get(self, item_id: str) -> Optional[InventoryItem]:
        """获取物品。"""
        return self._items.get(item_id)

    def has(self, item_id: str) -> bool:
        """检查是否拥有某物品。"""
        return item_id in self._items

    def count(self, item_id: str) -> int:
        """获取某物品的堆叠数量。"""
        item = self._items.get(item_id)
        return item.quantity if item else 0

    # ---- 查询与筛选 ----

    def list_by_type(self, item_type: str) -> list[InventoryItem]:
        """按类型筛选物品。"""
        return [item for item in self._items.values() if item.item_type == item_type]

    def list_all(self) -> list[InventoryItem]:
        """返回所有物品列表。"""
        return list(self._items.values())

    @property
    def all_items(self) -> list[InventoryItem]:
        """返回所有物品列表。"""
        return list(self._items.values())

    @property
    def item_count(self) -> int:
        """物品槽位占用数。"""
        return len(self._items)

    @property
    def total_quantity(self) -> int:
        """所有物品的总数量（含堆叠）。"""
        return sum(item.quantity for item in self._items.values())

    def find(self, name: str) -> list[InventoryItem]:
        """按名称模糊查找物品（子串匹配）。"""
        name_lower = name.lower()
        return [
            item for item in self._items.values()
            if name_lower in item.name.lower()
        ]

    # ---- 整理 ----

    def sort_by_type(self) -> None:
        """按物品类型排序（不改变字典，仅用于展示）。"""
        # 内置 dict 在 Python 3.7+ 保持插入顺序；
        # 这里重建字典以达到排序效果
        sorted_items = sorted(
            self._items.values(),
            key=lambda i: (i.item_type, i.name),
        )
        self._items = {item.item_id: item for item in sorted_items}

    def clear(self) -> None:
        """清空背包。"""
        self._items.clear()

    # ---- 批量加载 ----

    def from_data_list(self, data: list[dict]) -> None:
        """从字典列表批量加载物品。

        :param data: 物品字典列表
        """
        for d in data:
            item = InventoryItem.from_dict(d)
            # 如果 ID 已存在且可堆叠，合并
            if item.item_id in self._items and item.is_stackable:
                self._items[item.item_id].merge(item)
            else:
                self._items[item.item_id] = item

    # ---- 序列化 ----

    def to_dict(self) -> dict:
        """导出为可序列化字典。"""
        return {
            "capacity": self._capacity,
            "max_weight": self._max_weight,
            "items": [item.to_dict() for item in self._items.values()],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Inventory":
        """从字典恢复背包状态。"""
        inv = cls(
            capacity=data.get("capacity", 20),
            max_weight=data.get("max_weight", 0),
        )
        inv.from_data_list(data.get("items", []))
        return inv

    def __len__(self) -> int:
        return len(self._items)

    def __contains__(self, item_id: str) -> bool:
        return item_id in self._items

    def __iter__(self):
        return iter(self._items.values())

    def __repr__(self) -> str:
        return f"Inventory({len(self._items)}/{self._capacity or '∞'} items)"
