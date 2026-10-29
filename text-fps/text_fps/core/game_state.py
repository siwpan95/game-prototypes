"""GameState - Central game state container."""
from typing import List, Optional

from core.event_bus import EventBus
from core.constants import PHASE_PLAYER_TURN
from models.player import Player
from models.room import Room
from models.level import Level


class GameState:
    """Central container for all mutable game state."""

    def __init__(self, event_bus: EventBus) -> None:
        self.event_bus: EventBus = event_bus
        self.player: Optional[Player] = None
        self.current_room: Optional[Room] = None
        self.levels: List[Level] = []
        self.current_level: int = 0
        self.turn: int = 0
        self.phase: str = PHASE_PLAYER_TURN
        self.dirty: bool = True
        self.log: List[str] = []
        self.max_log_lines: int = 200

    def advance_turn(self) -> None:
        """Advance the turn counter and mark state dirty."""
        self.turn += 1
        self.dirty = True

    def add_log(self, msg: str) -> None:
        """Add a message to the game log."""
        self.log.append(msg)
        if len(self.log) > self.max_log_lines:
            self.log = self.log[-self.max_log_lines:]
        self.dirty = True
        self.event_bus.publish("log_updated", {"message": msg})

    def load_level(self, level: Level) -> None:
        """Load a level into the game state."""
        self.levels.append(level)
        self.current_level = level.level_id
        self.current_room = level.get_room(level.start_room)
        if self.player is None:
            self.player = Player(name="Player")
            from data.weapons import create_weapon
            self.player.weapons.append(create_weapon("pistol"))
            self.player.position = level.start_room
        else:
            self.player.position = level.start_room
        self.phase = PHASE_PLAYER_TURN
        self.turn = 0
        self.dirty = True
        self.add_log(f"--- Level {level.level_id}: {level.name} ---")
        if self.current_room:
            self.add_log(self.current_room.description)

    def to_dict(self) -> dict:
        """Serialize game state to dict."""
        return {
            "player": self.player.to_dict() if self.player else None,
            "current_room": self.current_room.room_id if self.current_room else None,
            "current_level": self.current_level,
            "turn": self.turn,
            "phase": self.phase,
            "log": self.log[-50:],  # Save last 50 log entries
        }

    @classmethod
    def from_dict(cls, data: dict, event_bus: EventBus) -> "GameState":
        """Deserialize game state from dict."""
        gs = cls(event_bus=event_bus)
        if data.get("player"):
            gs.player = Player.from_dict(data["player"])
        gs.current_level = data.get("current_level", 0)
        gs.turn = data.get("turn", 0)
        gs.phase = data.get("phase", PHASE_PLAYER_TURN)
        gs.log = data.get("log", [])
        return gs
