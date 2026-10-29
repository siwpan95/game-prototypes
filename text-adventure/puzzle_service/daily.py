"""The puzzle of the day: one date in, one puzzle out.

This lives on its own so that every client computes the same daily puzzle. It used
to be private to the service (``service._seed_from``), which meant a second client
wanting "today's puzzle" had two options: import a private name, or re-derive the
seed — and re-deriving it is how two clients end up showing different puzzles on the
same day while both look correct in isolation.

Determinism rules, both learned the hard way:

* the seed comes from **SHA-256 of the date**, never ``hash()`` — ``hash()`` is
  salted per process, so the daily would differ between runs and machines;
* the date must be spelled exactly ``YYYY-MM-DD`` — ``strptime`` accepts
  ``2026-2-3``, and two spellings of one day would be two different puzzles.
"""

from __future__ import annotations

import hashlib
from datetime import date, datetime

__all__ = ["DAILY_KINDS", "is_iso_date", "seed_from", "today"]


def today() -> str:
    """Today as the canonical ``YYYY-MM-DD`` string."""
    return date.today().strftime("%Y-%m-%d")


def is_iso_date(value: str) -> bool:
    """Strict ``YYYY-MM-DD`` check.

    ``strptime`` alone is too permissive: it happily accepts ``2026-2-3``, which
    would make two spellings of the same day produce two different daily puzzles.
    The round trip rejects anything that is not zero-padded.
    """
    try:
        parsed = datetime.strptime(value, "%Y-%m-%d")
    except (TypeError, ValueError):
        return False
    return parsed.strftime("%Y-%m-%d") == value


def seed_from(day: str) -> int:
    """A stable integer seed for an ISO date (independent of process and platform).

    ``hash()`` is deliberately not used: it is salted per process, so the "puzzle
    of the day" would differ between runs and between machines.
    """
    digest = hashlib.sha256(f"text-adventure:{day}".encode("utf-8")).hexdigest()
    return int(digest[:16], 16)


#: Kinds that may be handed out as the daily puzzle.
#:
#: The daily draws from the *content* kinds, not from all fourteen: several kinds
#: (2048, nonogram, minesweeper) are long sessions, and a daily that can take twenty
#: minutes is a daily people skip. Interaction-style kinds (colours, memory) are
#: excluded for a second reason — a timed flash sequence is a poor fit for a puzzle
#: two players are meant to compare notes about, and "same puzzle for everyone" is
#: the whole point.
DAILY_KINDS: tuple[str, ...] = (
    "math",
    "riddle",
    "crossword",
    "sudoku",
    "guess_number",
    "word_ladder",
    "anagram",
    "pattern",
    "hangman",
)
