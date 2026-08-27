"""Inventory — 统一背包/物品管理。"""

from __future__ import annotations
from typing import Optional

from shared_core.item import Item


class Inventory:
    """背包管理器。"""

    def __init__(self):
        self._items: dict[str, Item] = {}

    def add(self, item: Item) -> None:
        self._items[item.item_id] = item

    def remove(self, item_id: str) -> bool:
        return self._items.pop(item_id, None) is not None

    def get(self, item_id: str) -> Optional[Item]:
        return self._items.get(item_id)

    def has(self, item_id: str) -> bool:
        return item_id in self._items

    def list_by_type(self, item_type: str) -> list[Item]:
        return [i for i in self._items.values() if i.item_type == item_type]

    @property
    def count(self) -> int:
        return len(self._items)

    @property
    def all_items(self) -> list[Item]:
        return list(self._items.values())

    def to_dict(self) -> dict:
        return {iid: item.to_dict() for iid, item in self._items.items()}

    def from_data_list(self, data: list[dict]) -> None:
        """从字典列表加载物品。"""
        for d in data:
            item = Item.from_dict(d)
            self._items[item.item_id] = item
