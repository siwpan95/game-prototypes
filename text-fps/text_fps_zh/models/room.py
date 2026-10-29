"""Room model."""
from typing import Dict, List, Optional

from models.enemy import Enemy
from models.item import Item


class Room:
    """A room in the game level."""

    def __init__(
        self,
        room_id: str = "",
        name: str = "",
        description: str = "",
        exits: Optional[Dict[str, str]] = None,
        enemies: Optional[List[Enemy]] = None,
        items: Optional[List[Item]] = None,
        cover_objects: Optional[List[str]] = None,
        destructibles: Optional[List[str]] = None,
        traps: Optional[List[dict]] = None,
    ) -> None:
        self.room_id: str = room_id
        self.name: str = name
        self.description: str = description
        self.exits: Dict[str, str] = exits if exits is not None else {}
        self.enemies: List[Enemy] = enemies if enemies is not None else []
        self.items: List[Item] = items if items is not None else []
        self.visited: bool = False
        self.cover_objects: List[str] = cover_objects if cover_objects is not None else []
        self.destructibles: List[str] = destructibles if destructibles is not None else []
        self.traps: List[dict] = traps if traps is not None else []

    def has_cover(self) -> bool:
        """Check if the room has cover objects."""
        return len(self.cover_objects) > 0

    def remove_enemy(self, enemy: Enemy) -> None:
        """Remove an enemy from the room."""
        if enemy in self.enemies:
            self.enemies.remove(enemy)

    def remove_item(self, item: Item) -> None:
        """Remove an item from the room."""
        if item in self.items:
            self.items.remove(item)

    def add_item(self, item: Item) -> None:
        """Add an item to the room."""
        self.items.append(item)

    def get_exit(self, direction: str) -> Optional[str]:
        """Get the room_id for a given direction, or None."""
        return self.exits.get(direction)

    def living_enemies(self) -> List[Enemy]:
        """Return list of living enemies in the room."""
        return [e for e in self.enemies if e.is_alive]

    def to_dict(self) -> dict:
        """Serialize room to dict."""
        return {
            "room_id": self.room_id,
            "name": self.name,
            "description": self.description,
            "exits": dict(self.exits),
            "enemies": [e.to_dict() for e in self.enemies],
            "items": [i.to_dict() for i in self.items],
            "visited": self.visited,
            "cover_objects": list(self.cover_objects),
            "destructibles": list(self.destructibles),
            "traps": list(self.traps),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Room":
        """Deserialize room from dict."""
        r = cls(
            room_id=data.get("room_id", ""),
            name=data.get("name", ""),
            description=data.get("description", ""),
            exits=data.get("exits", {}),
            cover_objects=data.get("cover_objects", []),
            destructibles=data.get("destructibles", []),
            traps=data.get("traps", []),
        )
        r.enemies = [Enemy.from_dict(e) for e in data.get("enemies", [])]
        r.items = [Item.from_dict(i) for i in data.get("items", [])]
        r.visited = data.get("visited", False)
        return r
