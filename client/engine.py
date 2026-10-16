"""Game engine: manages state, scoring, and puzzle lifecycle."""

from __future__ import annotations

import random
import time
from typing import Any

from client.domain import GameState
from client.events import EventBus
from client.translations import t
from gameplay_pool import PUZZLE_CLASSES, BasePuzzle, PuzzlePicker, RandomPick
from puzzle_service import daily
from puzzle_service.registry import daily_kind_names


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
                 content: Any = None, profile_path: Any = None, remember: bool = True):
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
        # Make this client's kinds visible to the shared registry. The registry is
        # what defines the daily puzzle's candidate list and its order, so a client
        # that never registers cannot ask it anything — it gets an empty list and
        # silently falls back to its own idea of the order, which is how the desktop
        # and the service came to disagree about today's puzzle while both looked
        # right alone. Registration is idempotent and per language.
        try:
            from puzzle_service.registry import all_kinds, discover

            if not all_kinds(self.lang):
                discover(self.lang, content=self.content)
        except Exception as exc:  # noqa: BLE001 - progress over pedigree
            print(f"[desktop-client] kind registry unavailable: {exc}", flush=True)
        #: The day the active puzzle belongs to, when it is the puzzle of the day.
        self.day: str | None = None
        #: Progress. Written through the same store the service uses, so a player's
        #: streak is the same number whichever client they open — and the file is the
        #: same one, rather than a second progress file that drifts.
        self.profile_warning: str | None = None
        self.store = None
        if remember:
            from puzzle_service.profile import ProfileStore

            self.store = ProfileStore(profile_path)
            self.profile_warning = self.store.warning

    # --- Progress ------------------------------------------------------------

    @property
    def profile(self):
        return self.store.profile if self.store is not None else None

    def _persist(self) -> None:
        if self.store is not None:
            self.store.save()
            self.profile_warning = self.store.warning

    def profile_summary(self, day: str | None = None) -> dict[str, Any]:
        """Streak and totals, or zeroes when progress is disabled.

        ``day`` anchors the streak (default: today). A live client wants today; a test
        or a replay wants the day it just recorded — otherwise a test using fixed dates
        measures the streak *as of the real clock* and fails for reasons that have
        nothing to do with the code.
        """
        if self.profile is None:
            return {
                "days_played": 0, "total_solved": 0, "current_streak": 0,
                "best_streak": 0, "practice_played": 0, "practice_solved": 0,
                "today": daily.today(), "disabled": True,
            }
        return self.profile.summary(day or daily.today())

    def kind_summary(self) -> list[dict[str, Any]]:
        return self.profile.kind_summary() if self.profile is not None else []

    def history(self, limit: int = 14) -> list[Any]:
        return self.profile.history(limit) if self.profile is not None else []

    def share_card(self, day: str | None = None) -> str:
        if self.profile is None:
            return ""
        return self.profile.share_card(day)

    def daily_status(self, day: str | None = None) -> dict[str, Any]:
        """Whether *day* has been played, for the menu to show before starting."""
        key = day or daily.today()
        record = self.profile.days.get(key) if self.profile is not None else None
        streak = self.profile.current_streak(key) if self.profile is not None else 0
        return {
            "day": key,
            "played": record is not None,
            "solved": bool(record and record.solved),
            "kind": record.kind if record else "",
            "streak": streak,
        }

    # --- Configuration ---

    def configure(self, mode: str, difficulty: str) -> None:
        self.state.mode = mode
        self.state.difficulty = difficulty
        self.day = None
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
        self._prepare(self._current_puzzle)
        self._puzzle_start_time = time.time()
        self._puzzles_total += 1
        self.event_bus.publish("puzzle_started", {"puzzle": self._current_puzzle})
        return self._current_puzzle

    def _prepare(self, puzzle: BasePuzzle) -> None:
        """Attach the content pack and let a content-backed puzzle re-draw from it."""
        if self.content is not None:
            puzzle.content = self.content
            if getattr(puzzle, "content_kind", None):
                puzzle._generate()

    def start_daily(self, day: str | None = None,
                    difficulty: str | None = None) -> BasePuzzle:
        """Start the puzzle of the day: same date in, same puzzle out.

        The seed comes from :mod:`puzzle_service.daily`, the same function the service
        and the terminal client use, so all three show one puzzle for one date. A
        second implementation here is precisely how two clients end up disagreeing
        about "today's puzzle" while each looks right on its own.
        """
        # `None` means "today"; an empty string is a mistake, not a synonym for today.
        # `day or today()` would quietly accept "" and start today's puzzle, which is
        # how a caller passing an empty date from a form gets a plausible wrong answer
        # instead of an error.
        key = daily.today() if day is None else day
        if not daily.is_iso_date(key):
            raise ValueError(t("msg_bad_date", self.lang, day=key))
        level = difficulty or self.state.difficulty or "medium"
        if level == "random":
            level = "medium"
        rng = random.Random(daily.seed_from(key))
        # The kind comes from the seeded stream, so the difficulty must be settled
        # before drawing — otherwise choosing "random" would consume a draw and give
        # this client a different kind than everyone else.
        #
        # The candidate list *and its order* come from the shared registry: the draw
        # indexes into that list, so two clients with different orders would hand out
        # different puzzles for one date while each looked correct in isolation. This
        # is not hypothetical — the desktop and the service did exactly that, and the
        # parity check caught it.
        names = daily_kind_names(self.lang)
        by_name = {cls.kind: cls for cls in PUZZLE_CLASSES}
        candidates = [by_name[name] for name in names if name in by_name]
        if not candidates:  # pragma: no cover - guards a pool/registry mismatch
            raise LookupError(
                f"no daily-eligible puzzle kinds in the pool for {self.lang!r} "
                f"(registry offers {names})"
            )
        puzzle_cls = candidates[rng.randrange(len(candidates))]
        puzzle = puzzle_cls(difficulty=level, rng=rng, lang=self.lang)
        self._prepare(puzzle)
        self._current_puzzle = puzzle
        self.state.difficulty = level
        self.day = key
        self._puzzle_start_time = time.time()
        self._puzzles_total += 1
        self.event_bus.publish("puzzle_started", {"puzzle": puzzle, "daily": key})
        return puzzle

    def new_puzzle_of_kind(self, kind_name: str) -> BasePuzzle:
        """Start a free-play puzzle of a named kind.

        Used by the menu to honour a choice, and by tests that need a specific kind
        instead of whatever the picker draws — a test that draws at random measures the
        draw, not the behaviour it claims to check.
        """
        pool = [cls for cls in PUZZLE_CLASSES if cls.kind == kind_name]
        if not pool:
            raise LookupError(
                f"unknown puzzle kind {kind_name!r}; known: "
                f"{sorted(cls.kind for cls in PUZZLE_CLASSES)}"
            )
        level = self.state.difficulty or "medium"
        if level == "random":
            level = "medium"
        puzzle = pool[0](difficulty=level, lang=self.lang)
        self._prepare(puzzle)
        self._current_puzzle = puzzle
        self.day = None
        self._puzzle_start_time = time.time()
        self._puzzles_total += 1
        self.event_bus.publish("puzzle_started", {"puzzle": puzzle})
        return puzzle

    @property
    def is_daily(self) -> bool:
        return self.day is not None

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

        self._record(puzzle, correct=correct, points=points if correct else 0,
                     seconds=time_used)
        return {
            "correct": correct,
            "time_used": time_used,
            "score": self.state.score,
            "streak": self.state.streak,
            "daily": self.day,
        }

    def _record(self, puzzle: BasePuzzle, *, correct: bool, points: int,
                seconds: float) -> None:
        """Persist the outcome and finish the puzzle so it is recorded once.

        Recording is keyed on the puzzle being unfinished: without that, every extra
        submit on an already-solved puzzle would add another day's record or another
        practice game, and a player could inflate a streak by pressing enter twice.
        """
        if getattr(puzzle, "_recorded", False):
            return
        puzzle._recorded = True  # type: ignore[attr-defined]
        if self.profile is None:
            return
        from puzzle_service.profile import DailyRecord

        kind_name = getattr(puzzle, "kind", type(puzzle).__name__)
        if self.day is not None:
            self.profile.record(
                DailyRecord(
                    day=self.day,
                    kind=kind_name,
                    solved=correct,
                    score=points,
                    attempts=1,
                    seconds=seconds,
                )
            )
        else:
            self.profile.record_kind(
                kind_name, solved=correct, score=points, seconds=seconds
            )
        self._persist()

    def skip_puzzle(self) -> None:
        """Skip the current puzzle (breaks streak, no points, not recorded as effort)."""
        self.state.streak = 0
        self.day = None
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
