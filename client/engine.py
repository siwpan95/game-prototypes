"""Game engine: manages state, scoring, and puzzle lifecycle."""

from __future__ import annotations

import time
from typing import Any

from client.domain import GameState
from client.events import EventBus
from client.translations import t
from gameplay_pool import BasePuzzle, PuzzlePicker, RandomPick


def _default_content(language: str):
    """The content pack for *language*, or ``None`` to fall back to built-in banks.

    The desktop client used to draw from banks compiled into its own modules; now it
    plays the same pack as the service and the web client, so all three show the same
    puzzles. A missing or broken pack is reported and the game still runs.
    """
    try:
        from puzzle_service.content import ContentPackError, load_pack

        return load_pack(language=language)
    except ContentPackError as exc:
        print(f"[desktop-client] content pack unusable, using built-in banks: {exc}", flush=True)
        return None


class Engine:
    """Core game engine coordinating puzzles, scoring, and state.

    The engine is language-aware because two of its replies reach the player as text
    ("no active puzzle"); everything else it does — scoring, streaks, timing — is
    language-independent.
    """

    def __init__(self, event_bus: EventBus | None = None, lang: str | None = None,
                 content: Any = None):
        self.lang = lang or messages.DEFAULT_LANGUAGE
        self.state = GameState()
        self.event_bus = event_bus or EventBus()
        self._picker: PuzzlePicker | RandomPick | None = None
        self._current_puzzle: BasePuzzle | None = None
        self._puzzle_start_time: float = 0.0
        self._puzzles_total: int = 0
        # Content pack handed to every puzzle this engine creates, so the desktop
        # client plays the same content as the service and the web client.
        self.content = content if content is not None else _default_content(self.lang)

    # --- Configuration ---

    def configure(self, mode: str, difficulty: str) -> None:
        self.state.mode = mode
        self.state.difficulty = difficulty
        if mode == "random":
            self._picker = RandomPick(difficulty=difficulty)
        else:
            self._picker = PuzzlePicker(mode=mode, difficulty=difficulty)

    # --- Puzzle lifecycle ---

    def start_new_puzzle(self) -> BasePuzzle:
        if self._picker is None:
            self.configure("balanced", "medium")
        assert self._picker is not None
        # The picker takes the language so the puzzle it builds speaks it; the pack
        # is attached the same way the service does it.
        self._current_puzzle = self._picker.pick(lang=self.lang)
        if self.content is not None:
            self._current_puzzle.content = self.content
            if getattr(self._current_puzzle, "content_kind", None):
                self._current_puzzle._generate()
        self._puzzle_start_time = time.time()
        self._puzzles_total += 1
        self.event_bus.publish("puzzle_started", {"puzzle": self._current_puzzle})
        return self._current_puzzle

    def submit_answer(self, answer: Any) -> dict[str, Any]:
        """Submit an answer for the current puzzle. Returns result info."""
        puzzle = self._current_puzzle
        if puzzle is None:
            return {"correct": False, "error": t("msg_no_active_puzzle", self.lang)}

        correct = puzzle.check_answer(answer)
        time_used = time.time() - self._puzzle_start_time

        if correct:
            puzzle.solved = True
            time_bonus = max(0, 5 - int(time_used // 5))
            streak_bonus = min(self.state.streak, 5)
            points = 10 + time_bonus + streak_bonus
            self.state.score += points
            self.state.streak += 1
            self.state.puzzles_solved += 1
            self.event_bus.publish("puzzle_solved", {
                "points": points,
                "time_bonus": time_bonus,
                "streak_bonus": streak_bonus,
                "time_used": time_used,
            })
        else:
            self.state.streak = 0
            self.event_bus.publish("puzzle_wrong", {"answer": answer})

        return {
            "correct": correct,
            "time_used": time_used,
            "score": self.state.score,
            "streak": self.state.streak,
        }

    def skip_puzzle(self) -> None:
        """Skip the current puzzle (breaks streak, no points)."""
        self.state.streak = 0
        self.event_bus.publish("puzzle_skipped", {})

    def get_hint(self) -> str:
        if self._current_puzzle is None:
            return t("msg_no_active_puzzle_hint", self.lang)
        return self._current_puzzle.get_hint()

    # --- State queries ---

    @property
    def current_puzzle(self) -> BasePuzzle | None:
        return self._current_puzzle

    @property
    def elapsed(self) -> float:
        if self._puzzle_start_time == 0:
            return 0.0
        return time.time() - self._puzzle_start_time

    def reset(self) -> None:
        self.state = GameState()
        self._current_puzzle = None
        self._puzzle_start_time = 0.0
        self._puzzles_total = 0
        if self._picker and isinstance(self._picker, PuzzlePicker):
            self._picker.reset_history()
