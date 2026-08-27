"""Game engine: manages state, scoring, and puzzle lifecycle."""

from __future__ import annotations

import time
from typing import Any

from domain import GameState
from events import EventBus
from gameplay_pool import BasePuzzle, PuzzlePicker, RandomPick


class Engine:
    """Core game engine coordinating puzzles, scoring, and state."""

    def __init__(self, event_bus: EventBus | None = None):
        self.state = GameState()
        self.event_bus = event_bus or EventBus()
        self._picker: PuzzlePicker | RandomPick | None = None
        self._current_puzzle: BasePuzzle | None = None
        self._puzzle_start_time: float = 0.0
        self._puzzles_total: int = 0

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
        self._current_puzzle = self._picker.pick()
        self._puzzle_start_time = time.time()
        self._puzzles_total += 1
        self.event_bus.publish("puzzle_started", {"puzzle": self._current_puzzle})
        return self._current_puzzle

    def submit_answer(self, answer: Any) -> dict[str, Any]:
        """Submit an answer for the current puzzle. Returns result info."""
        puzzle = self._current_puzzle
        if puzzle is None:
            return {"correct": False, "error": "No active puzzle"}

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
            return "No active puzzle"
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
