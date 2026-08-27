"""Level model."""
from typing import Dict, List, Optional

from models.room import Room


class Level:
    """A game level consisting of multiple rooms."""

    def __init__(
        self,
        level_id: int = 1,
        name: str = "",
        rooms: Optional[Dict[str, Room]] = None,
        start_room: str = "",
        boss_room: Optional[str] = None,
    ) -> None:
        self.level_id: int = level_id
        self.name: str = name
        self.rooms: Dict[str, Room] = rooms if rooms is not None else {}
        self.start_room: str = start_room
        self.boss_room: Optional[str] = boss_room
        self.completed: bool = False

    def get_room(self, room_id: str) -> Optional[Room]:
        """Get a room by its ID."""
        return self.rooms.get(room_id)

    def is_complete(self) -> bool:
        """Check if all enemies in the level are dead."""
        for room in self.rooms.values():
            if room.living_enemies():
                return False
        self.completed = True
        return True

    def to_dict(self) -> dict:
        """Serialize level to dict."""
        return {
            "level_id": self.level_id,
            "name": self.name,
            "rooms": {k: v.to_dict() for k, v in self.rooms.items()},
            "start_room": self.start_room,
            "boss_room": self.boss_room,
            "completed": self.completed,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Level":
        """Deserialize level from dict."""
        lv = cls(
            level_id=data.get("level_id", 1),
            name=data.get("name", ""),
            start_room=data.get("start_room", ""),
            boss_room=data.get("boss_room"),
        )
        lv.rooms = {k: Room.from_dict(v) for k, v in data.get("rooms", {}).items()}
        lv.completed = data.get("completed", False)
        return lv
