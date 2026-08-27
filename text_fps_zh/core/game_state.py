"""GameState - Central game state container."""
from typing import List, Optional

from core.constants import PHASE_PLAYER_TURN
from models.player import Player
from models.room import Room
from models.level import Level


class GameState:
    """Central container for all mutable game state."""

    def __init__(self) -> None:
        self.player: Optional[Player] = None
        self.current_room: Optional[Room] = None
        self.levels: List[Level] = []
        self.current_level: int = 0
        self.turn: int = 0
        self.phase: str = PHASE_PLAYER_TURN
        self.dirty: bool = True
        self.selected_enemy_index: int = 0  # F5: player's chosen target (transient, not persisted)
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
        self.add_log(f"--- 关卡 {level.level_id}: {level.name} ---")
        if self.current_room:
            self.add_log(self.current_room.description)

    def to_dict(self) -> dict:
        """Serialize game state to dict (F2/F16: full room & level state + version)."""
        return {
            "version": 1,
            "player": self.player.to_dict() if self.player else None,
            "current_room": self.current_room.to_dict() if self.current_room else None,
            "levels": [lv.to_dict() for lv in self.levels],
            "current_level": self.current_level,
            "turn": self.turn,
            "phase": self.phase,
            "log": self.log[-50:],  # Save last 50 log entries
        }

    @classmethod
    def from_dict(cls, data: dict) -> "GameState":
        """Deserialize game state from dict (F2: restore full levels & current_room)."""
        gs = cls()
        if data.get("player"):
            gs.player = Player.from_dict(data["player"])
        gs.current_level = data.get("current_level", 0)
        gs.turn = data.get("turn", 0)
        gs.phase = data.get("phase", PHASE_PLAYER_TURN)
        gs.log = data.get("log", [])
        # F2: restore full level state (enemy alive/item state preserved)
        gs.levels = [Level.from_dict(lv) for lv in data.get("levels", [])]
        # F2: restore current room from its full dict (new format)
        cr = data.get("current_room")
        if isinstance(cr, dict):
            gs.current_room = Room.from_dict(cr)
        elif isinstance(cr, str) and gs.levels:
            # Legacy format: only a room id; resolve against restored levels if possible
            for lv in gs.levels:
                room = lv.get_room(cr)
                if room:
                    gs.current_room = room
                    break
        return gs
