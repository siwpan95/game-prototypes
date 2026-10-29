"""Room Generator — 从故事数据生成房间定义。"""

from __future__ import annotations
from typing import Any


class RoomGenerator:
    """房间数据生成器。"""

    def __init__(self, story_data: Any = None):
        self.story_data = story_data or {}

    def generate(self) -> list[dict]:
        """
        生成房间列表。

        Returns:
            [{"room_id": ..., "name": ..., "description": ..., "exits": ...}, ...]
        """
        rooms: list[dict] = []
        if isinstance(self.story_data, dict):
            rooms_data = self.story_data.get("rooms", {})
            if isinstance(rooms_data, dict):
                for rid, robj in rooms_data.items():
                    if isinstance(robj, dict):
                        exits = robj.get("exits", {})
                        if isinstance(exits, dict):
                            exits = {k: v for k, v in exits.items()}
                        rooms.append({
                            "room_id": rid,
                            "name": robj.get("name", rid),
                            "description": robj.get("description", ""),
                            "chapter": robj.get("chapter", ""),
                            "items": robj.get("items", []),
                            "characters": robj.get("characters", []),
                            "exits": exits,
                            **{k: v for k, v in robj.items()
                               if k not in ("name", "description", "chapter",
                                       "items", "characters", "exits")},
                        })
        return rooms
