"""Base class for all puzzles."""

import random
from abc import ABC, abstractmethod
from typing import Any


class BasePuzzle(ABC):
    """Abstract base class that every puzzle type must inherit from."""

    # Subclasses override these class attributes
    puzzle_name: str = "base"
    puzzle_type: str = "content"  # content | mixed | generated

    #: Which content-pack kind supplies this puzzle's questions/words, if any.
    #: ``None`` means the puzzle is generated rather than drawn from content.
    content_kind: str | None = None

    def __init__(self, difficulty: str = "medium", content: Any = None):
        self.difficulty: str = difficulty
        self.solved: bool = False
        self.data: dict[str, Any] = {}
        # A content pack when one is available; subclasses fall back to the bank
        # embedded in their own module when it is None (see ``pick_content``).
        self.content = content
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

    # --- content-pack access -------------------------------------------------

    def pick_content(self) -> dict[str, Any] | None:
        """One item of this puzzle's content kind, or ``None`` to use the built-in bank.

        Puzzles call this first and fall back to their module-level bank, so the
        game keeps working with no pack present — content migration is therefore
        incremental instead of a big-bang switch.

        A seeded ``self.rng`` makes the draw reproducible (used by the daily
        puzzle); without one the module-level ``random`` is used as before.
        """
        kind = getattr(type(self), "content_kind", None)
        pack = getattr(self, "content", None)
        if not kind or pack is None:
            return None
        return pack.choose(kind, self.difficulty, rng=getattr(self, "rng", None))

    def pick_from(self, options: Any) -> Any:
        """Choose from a built-in bank, honouring a seeded ``self.rng``.

        Built-in banks use the module-level ``random`` directly. Routing the choice
        through here keeps a seeded run deterministic **without** reseeding global
        state, which would leak into every other session in the process.
        """
        return self._rng().choice(options)

    def _rng(self) -> Any:
        """The random source this puzzle draws from: seeded when one was supplied.

        Every built-in bank in the puzzle modules calls ``self._rng()`` instead of
        the module-level ``random``, so "puzzle of the day" can reproduce a puzzle
        exactly without touching process-global state.
        """
        return getattr(self, "rng", None) or random

    def reset(self) -> None:
        """Reset the puzzle to a fresh state."""
        self.solved = False
        self.data = {}
        self._generate()
