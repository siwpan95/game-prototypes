"""Domain models for the puzzle game."""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class GameState:
    """Global game state."""

    current_room: str = "menu"
    inventory: list = field(default_factory=list)
    flags: dict[str, bool] = field(default_factory=dict)
    puzzles: dict[str, Any] = field(default_factory=dict)
    score: int = 0
    streak: int = 0
    puzzles_solved: int = 0
    mode: str = "balanced"       # content_heavy | balanced | generated_heavy
    difficulty: str = "medium"   # easy | medium | hard | random
