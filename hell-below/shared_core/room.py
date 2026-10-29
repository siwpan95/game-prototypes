"""Room — 游戏世界中的房间/地点定义。"""

from __future__ import annotations
from dataclasses import dataclass, field


@dataclass
class Room:
    """一个房间/地点。"""
    room_id: str
    name: str
    description: str
    chapter: str = ""
    items: list[str] = field(default_factory=list)
    characters: list[str] = field(default_factory=list)
    exits: dict[str, str] = field(default_factory=dict)  # {"north": "room_id"}
    is_dark: bool = False
    ambient_text: str = ""
    # 扩展字段
    metadata: dict = field(default_factory=dict)

    def get_exit(self, direction: str) -> str | None:
        return self.exits.get(direction.lower())

    def has_item(self, item_id: str) -> bool:
        return item_id in self.items

    def to_dict(self) -> dict:
        return {
            "room_id": self.room_id, "name": self.name,
            "description": self.description, "chapter": self.chapter,
            "items": self.items, "characters": self.characters,
            "exits": self.exits, "is_dark": self.is_dark,
            "ambient_text": self.ambient_text, "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Room":
        return cls(
            room_id=data["room_id"], name=data["name"],
            description=data["description"],
            chapter=data.get("chapter", ""),
            items=data.get("items", []),
            characters=data.get("characters", []),
            exits=data.get("exits", {}),
            is_dark=data.get("is_dark", False),
            ambient_text=data.get("ambient_text", ""),
            metadata=data.get("metadata", {}),
        )
