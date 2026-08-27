"""Item Generator — 从故事数据生成物品定义。"""

from __future__ import annotations
from typing import Any


class ItemGenerator:
    """物品数据生成器。"""

    def __init__(self, story_data: Any = None):
        self.story_data = story_data or {}

    def generate(self) -> list[dict]:
        """
        生成物品列表。

        Returns:
            [{"item_id": ..., "name": ..., "description": ..., "item_type": ...}, ...]
        """
        items: list[dict] = []
        if isinstance(self.story_data, dict):
            items_data = self.story_data.get("items", {})
            if isinstance(items_data, dict):
                for iid, iobj in items_data.items():
                    if isinstance(iobj, dict):
                        items.append({
                            "item_id": iid,
                            "name": iobj.get("name", iid),
                            "description": iobj.get("description", ""),
                            "item_type": iobj.get("type", "misc"),
                            "usable": iobj.get("usable", False),
                            **{k: v for k, v in iobj.items()
                               if k not in ("name", "description", "type", "usable")},
                        })
        return items
