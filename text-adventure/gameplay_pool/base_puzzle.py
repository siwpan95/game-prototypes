"""Base class for every puzzle, with the language handled once.

This is the M5 convergence point: one implementation of the puzzle logic, with the
language as a parameter instead of a second copy of the package.

What stays compatible with both old builds, on purpose:

* ``puzzle_name`` remains a **class attribute** (the default language's name), so
  anything that reads it off the class still works — and, because the pygame client
  does ``self._puzzle.puzzle_name``, an *instance* attribute of the same name
  shadows it with the right language. That is why no client code had to change.
* ``content_kind`` / ``pick_content`` / ``pick_from`` / ``_rng`` behave exactly as
  before, including the seeded-generator rule for the daily puzzle.
"""

from __future__ import annotations

import random
from abc import ABC, abstractmethod
from typing import Any

from . import messages

__all__ = ["BasePuzzle"]


class BasePuzzle(ABC):
    """Abstract base class that every puzzle type must inherit from."""

    # Subclasses override these class attributes
    puzzle_name: str = "base"
    puzzle_type: str = "content"  # content | mixed | generated

    #: Which content-pack kind supplies this puzzle's questions/words, if any.
    #: ``None`` means the puzzle is generated rather than drawn from content.
    content_kind: str | None = None

    #: Registry id of this kind (used to look the display name up per language).
    kind: str = ""

    def __init__(self, difficulty: str = "medium", content: Any = None,
                 lang: str | None = None, rng: Any = None):
        self.difficulty: str = difficulty
        self.lang: str = messages.normalise_language(lang)
        self.solved: bool = False
        self.data: dict[str, Any] = {}
        # A content pack when one is available; subclasses fall back to the bank
        # embedded in their own module when it is None (see ``pick_content``).
        self.content = content
        self.rng = rng
        if self.kind:
            # Instance attribute shadows the class attribute, so a client that reads
            # `puzzle.puzzle_name` gets this language's name.
            self.puzzle_name = messages.puzzle_name(self.kind, self.lang)
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

    # --- language helpers ----------------------------------------------------

    def msg(self, key: str, **kwargs: Any) -> str:
        """A parameterised message in this puzzle's language."""
        return messages.text(key, self.lang, **kwargs)

    def word(self, key: str) -> str:
        """A static label in this puzzle's language."""
        return messages.label(key, self.lang)

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
        return pack.choose(kind, self.difficulty, rng=self.rng)

    def pick_from(self, options: Any) -> Any:
        """Choose from a built-in bank, honouring a seeded ``self.rng``."""
        return self._rng().choice(options)

    def _rng(self) -> Any:
        """The random source this puzzle draws from: seeded when one was supplied.

        Every built-in bank calls ``self._rng()`` instead of the module-level
        ``random``, so "puzzle of the day" can reproduce a puzzle exactly without
        touching process-global state.
        """
        return self.rng or random

    def reset(self) -> None:
        """Reset the puzzle to a fresh state."""
        self.solved = False
        self.data = {}
        self._generate()
