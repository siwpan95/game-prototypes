"""Base class for all puzzles."""

from abc import ABC, abstractmethod
from typing import Any


class BasePuzzle(ABC):
    """Abstract base class that every puzzle type must inherit from."""

    # Subclasses override these class attributes
    puzzle_name: str = "base"
    puzzle_type: str = "content"  # content | mixed | generated

    def __init__(self, difficulty: str = "medium"):
        self.difficulty: str = difficulty
        self.solved: bool = False
        self.data: dict[str, Any] = {}
        self._generate()

    @abstractmethod
    def _generate(self) -> None:
        """Generate puzzle data based on difficulty."""

    @abstractmethod
    def check_answer(self, answer: Any) -> bool:
        """Return True if the provided answer is correct."""

    @abstractmethod
    def get_hint(self) -> str:
        """Return a hint string for the current puzzle."""

    def reset(self) -> None:
        """Reset the puzzle to a fresh state."""
        self.solved = False
        self.data = {}
        self._generate()
