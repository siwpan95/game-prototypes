"""Session and scoring service: what the Cordis host talks to over JSON-RPC.

This is deliberately free of transport and rendering concerns. It owns:

* which puzzle is active per session, and how long it has been running;
* answer submission, including the scoring rules (time bonus + streak bonus)
  that previously lived in ``engine.py``;
* the kind's mutating actions (``reveal``, ``set_cell``, ``move``, ...);
* snapshots, so a client can re-render without the service holding a socket.

Input normalisation happens here, at the boundary: four kinds coerce with
``int()`` and raise on the wrong type (measured 2026-10-16), so a bad answer
becomes a structured error instead of a traceback on the wire.
"""

from __future__ import annotations

import hashlib
import random
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from puzzle_service import views
from puzzle_service.profile import DailyRecord, ProfileStore
from puzzle_service.registry import PuzzleKind, all_kinds, discover, get

__all__ = ["Session", "PuzzleService", "InvalidAction", "InvalidAnswer"]

MAX_TIME_BONUS = 5
MAX_STREAK_BONUS = 5
BASE_POINTS = 10


class InvalidAction(LookupError):
    """The kind does not accept this action, or the arguments do not fit it."""


class InvalidAnswer(ValueError):
    """The answer could not be normalised for this kind."""


@dataclass
class Session:
    """One running game: the active puzzle plus the score attached to it."""

    session_id: str
    language: str
    score: int = 0
    streak: int = 0
    solved: int = 0
    started: int = 0
    puzzle_id: str | None = None
    kind: PuzzleKind | None = None
    puzzle: Any = None
    started_at: float = 0.0
    last_result: dict[str, Any] = field(default_factory=dict)
    auto_scored: dict[str, Any] | None = None
    #: Set by :meth:`PuzzleService.new_daily` so a client can show which day is in play.
    day: str | None = None
    #: Answer attempts on the active puzzle, so the profile can report effort.
    attempts: int = 0

    @property
    def elapsed(self) -> float:
        if not self.started_at:
            return 0.0
        return time.time() - self.started_at

    @property
    def completed_since_start(self) -> bool:
        """Whether the active puzzle has already been scored in this round."""
        return self.auto_scored is not None or bool(
            getattr(self.puzzle, "solved", False)
        )


class PuzzleService:
    """Headless puzzle service. One instance per process; sessions multiplexed by id."""

    def __init__(self, language: str = "zh", autodiscover: bool = True,
                 profile_path: Any = None, remember: bool = True):
        self.language = language
        # Content is loaded once per service: a pack read failure is reported here
        # (loudly) rather than swallowed per puzzle, and the game still runs on the
        # banks embedded in the puzzle modules.
        self.content = _load_content()
        if autodiscover and not all_kinds():
            discover(language, content=self.content)
        self._sessions: dict[str, Session] = {}
        self._counter = 0
        # Progress is optional: an unreadable profile is reported and treated as
        # empty rather than stopping the service (see ProfileStore.load).
        self.store = ProfileStore(profile_path) if remember else None
        if self.store is not None and self.store.warning:
            print(f"[puzzle-service] {self.store.warning}", file=sys.stderr)

    # --- profile -------------------------------------------------------------

    @property
    def profile(self):
        return self.store.profile if self.store is not None else None

    def profile_summary(self, day: str | None = None) -> dict[str, Any]:
        if self.profile is None:
            return {"remember": False, "days_played": 0, "total_solved": 0,
                    "current_streak": 0, "best_streak": 0}
        summary = self.profile.summary(day)
        summary["remember"] = True
        return summary

    def share_card(self, day: str | None = None) -> str:
        if self.profile is None:
            return "（未开启进度记录）"
        return self.profile.share_card(day)

    # --- content -------------------------------------------------------------

    def content_summary(self) -> dict[str, Any]:
        if self.content is None:
            return {"source": "built-in banks", "counts": {}}
        summary = self.content.describe()
        summary["source"] = "content pack"
        summary.pop("root", None)  # a machine path has no business crossing the wire
        return summary

    # --- kinds ---------------------------------------------------------------

    def list_kinds(self) -> list[dict[str, Any]]:
        return [kind.public() for kind in all_kinds()]

    # --- sessions ------------------------------------------------------------

    def _session(self, session_id: str) -> Session:
        try:
            return self._sessions[session_id]
        except KeyError:
            session = Session(session_id=session_id, language=self.language)
            self._sessions[session_id] = session
            return session

    def _next_id(self, prefix: str) -> str:
        self._counter += 1
        return f"{prefix}-{self._counter}"

    # --- puzzle lifecycle ----------------------------------------------------

    def new_puzzle(
        self,
        session_id: str = "default",
        kind: str | None = None,
        difficulty: str = "medium",
        rng: Any = None,
    ) -> dict[str, Any]:
        """Start a puzzle, either of a named *kind* or chosen from the registry.

        Args:
            rng: seeded random source. Passing one makes the whole start
                reproducible — which kind is picked *and* its content — because
                both draws go through the same generator.
        """
        session = self._session(session_id)
        if kind is None:
            chooser = rng or random
            pool = all_kinds()
            if not pool:
                raise InvalidAction("no puzzle kinds are registered; call discover() first")
            chosen = chooser.choice(pool)
        else:
            chosen = get(kind)

        session.kind = chosen
        session.puzzle = chosen.create(difficulty=_normalise_difficulty(difficulty), rng=rng)
        session.puzzle_id = self._next_id("p")
        session.started += 1
        session.started_at = time.time()
        session.last_result = {}
        session.auto_scored = None
        # A fresh puzzle starts a fresh attempt count; `new_daily` sets `session.day`
        # *before* calling this, so a day's record keeps its identity while its
        # attempt counter restarts.
        session.attempts = 0
        return self.snapshot(session_id)

    def new_daily(
        self,
        session_id: str = "default",
        day: str | None = None,
        difficulty: str = "medium",
    ) -> dict[str, Any]:
        """Start the puzzle of the day: same date in, same puzzle out.

        Deterministic by construction (a date-derived seed drives both the kind and
        the content), so no server-side schedule or pre-generated list is needed
        and two players on the same day get the same puzzle.
        """
        key = day or datetime.now().strftime("%Y-%m-%d")
        if not _is_iso_date(key):
            raise InvalidAction(f"日期要写成 YYYY-MM-DD，收到 {key!r}")
        rng = random.Random(_seed_from(key))
        # The day is recorded before starting, so the snapshot returned by this
        # call already carries it (setting it afterwards left the first snapshot
        # reporting day=None).
        session = self._session(session_id)
        session.day = key
        snapshot = self.new_puzzle(
            session_id=session_id, kind=None, difficulty=difficulty, rng=rng
        )
        snapshot["daily"] = {"day": key, "kind": snapshot["kind"]}
        if self.profile is not None:
            stored = self.profile.days.get(key)
            snapshot["daily"]["played"] = bool(stored)
            snapshot["profile"] = self.profile_summary(key)
        return snapshot

    def _record_daily(self, session: "Session") -> None:
        """Persist the active daily puzzle's outcome, if there is one to persist."""
        if self.store is None or session.day is None or session.kind is None:
            return
        # `session.solved` counts solves in this session, which is exactly what the
        # day's record wants: solving again on a later day is a different record.
        self.store.profile.record(
            DailyRecord(
                day=session.day,
                kind=session.kind.name,
                solved=session.solved > 0,
                score=session.score,
                attempts=session.attempts,
                seconds=round(session.elapsed, 3),
            )
        )
        self.store.save()

    def submit(self, session_id: str, answer: Any) -> dict[str, Any]:
        """Check *answer* against the active puzzle and apply the scoring rules.

        For an action-driven kind (``answered_by == "action"``) the answer is
        ignored by the puzzle itself: anagram reads the letters the player
        arranged, 2048 reads its board. Submitting is therefore a way to *ask*
        whether the state is finished, and it is scored like any other solve.
        """
        session = self._session(session_id)
        puzzle = session.puzzle
        if puzzle is None:
            raise InvalidAction("no active puzzle in this session")

        time_used = session.elapsed
        session.attempts += 1
        try:
            normalised = self._normalise_answer(session, answer)
            correct = bool(puzzle.check_answer(normalised))
        except (TypeError, ValueError) as exc:
            # Measured behaviour of math/riddle/guess_number/pattern: they coerce
            # with int() and raise instead of returning False. Surface it as a
            # structured error rather than a traceback, and never score it — but the
            # attempt still happened, so the day's record keeps it.
            self._record_daily(session)
            raise InvalidAnswer(
                f"{session.kind.name if session.kind else '?'} rejected the answer: {exc}"
            ) from exc

        if correct:
            puzzle.solved = True
            return self._score(session, time_used)

        session.streak = 0
        outcome: dict[str, Any] = {"correct": False, "points": 0}
        outcome.update(self._scoreboard(session, round(time_used, 3)))
        session.last_result = outcome
        # A wrong answer is progress too: a day played and not solved must show up
        # as such, otherwise "days played" and the attempt count only ever counted
        # successes (found by a test, 2026-10-16).
        self._record_daily(session)
        return outcome

    def perform(self, session_id: str, action: str, **params: Any) -> dict[str, Any]:
        """Run one of the kind's mutating actions, then return the new snapshot.

        Action-driven kinds are scored here: the moment the mutated state says
        the puzzle is finished (2048 reached its tile, memory matched every pair,
        colour sequence replayed in full), the points are awarded exactly once.
        """
        session = self._session(session_id)
        puzzle = session.puzzle
        if puzzle is None or session.kind is None:
            raise InvalidAction("no active puzzle in this session")
        if action not in session.kind.actions:
            raise InvalidAction(
                f"kind {session.kind.name!r} does not accept action {action!r}; "
                f"it accepts {list(session.kind.actions)}"
            )
        method = getattr(puzzle, action, None)
        if not callable(method):
            raise InvalidAction(
                f"kind {session.kind.name!r} declares action {action!r} "
                "but the class does not implement it"
            )
        try:
            result = method(**_coerce_action_kwargs(action, params))
        except TypeError as exc:
            raise InvalidAction(f"{action}: bad parameters ({exc})") from exc

        finished = _is_finished(puzzle)
        if finished and not session.completed_since_start:
            session.auto_scored = self._score(session, session.elapsed)
        snapshot = self.snapshot(session_id)
        if result is not None:
            snapshot["action_result"] = result
        snapshot["solved"] = finished
        return snapshot

    def hint(self, session_id: str) -> str:
        session = self._session(session_id)
        if session.puzzle is None:
            raise InvalidAction("no active puzzle in this session")
        return str(session.puzzle.get_hint())

    def reset(self, session_id: str) -> dict[str, Any]:
        session = self._session(session_id)
        session.score = 0
        session.streak = 0
        session.solved = 0
        session.puzzle = None
        session.kind = None
        session.puzzle_id = None
        session.started = 0
        session.last_result = {}
        session.auto_scored = None
        return self.snapshot(session_id)

    # --- snapshots -----------------------------------------------------------

    def snapshot(self, session_id: str) -> dict[str, Any]:
        """Everything a client needs to render the current state."""
        session = self._session(session_id)
        payload: dict[str, Any] = {
            "session_id": session.session_id,
            "language": session.language,
            "score": session.score,
            "streak": session.streak,
            "solved": session.solved,
            "puzzles_started": session.started,
            "elapsed": round(session.elapsed, 3),
            "puzzle_id": session.puzzle_id,
            "kind": session.kind.name if session.kind else None,
            "last_result": session.last_result,
            "day": session.day,
        }
        if session.puzzle is not None and session.kind is not None:
            payload["view"] = views.build(session.kind, session.puzzle)
        else:
            payload["view"] = None
        return payload

    # --- internals -----------------------------------------------------------

    def _score(self, session: Session, time_used: float) -> dict[str, Any]:
        """Award points for a solve and return the outcome (single place for the rules)."""
        time_bonus = max(0, MAX_TIME_BONUS - int(time_used // 5))
        streak_bonus = min(session.streak, MAX_STREAK_BONUS)
        points = BASE_POINTS + time_bonus + streak_bonus
        session.score += points
        session.streak += 1
        session.solved += 1
        outcome: dict[str, Any] = {
            "correct": True,
            "points": points,
            "time_bonus": time_bonus,
            "streak_bonus": streak_bonus,
        }
        outcome.update(self._scoreboard(session, round(time_used, 3)))
        session.last_result = outcome
        if session.auto_scored is None:
            session.auto_scored = outcome
        self._record_daily(session)
        return outcome

    @staticmethod
    def _scoreboard(session: Session, time_used: float) -> dict[str, Any]:
        return {
            "time_used": time_used,
            "score": session.score,
            "streak": session.streak,
            "solved": session.solved,
        }

    def _normalise_answer(self, session: Session, answer: Any) -> Any:
        """Coerce a wire value (usually a string) into the kind's answer type."""
        if session.kind is None:
            return answer
        wanted = session.kind.answer_type
        if wanted == "int" and isinstance(answer, str):
            text = answer.strip()
            try:
                return int(text)
            except ValueError as exc:
                raise InvalidAnswer(f"expected an integer answer, got {answer!r}") from exc
        return answer


def _normalise_difficulty(difficulty: str) -> str:
    return difficulty if difficulty in {"easy", "medium", "hard"} else "medium"


def _seed_from(day: str) -> int:
    """A stable integer seed for an ISO date (independent of process and platform).

    ``hash()`` is deliberately not used: it is salted per process, so the "puzzle
    of the day" would differ between runs and between machines.
    """
    digest = hashlib.sha256(f"text-adventure:{day}".encode("utf-8")).hexdigest()
    return int(digest[:16], 16)


def _is_iso_date(value: str) -> bool:
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


def _load_content():
    """Load the shipped content pack, announcing a failure instead of hiding it.

    A broken pack must not stop the game — the puzzle modules still carry their own
    banks — but it must not be silent either: a pack that fails validation while
    the game plays on the old content is exactly the "green but wrong" state the
    governance rules forbid.
    """
    from puzzle_service.content import ContentPackError, load_pack

    try:
        return load_pack()
    except ContentPackError as exc:
        print(f"[puzzle-service] content pack unusable, using built-in banks: {exc}", file=sys.stderr)
        return None


def _coerce_action_kwargs(action: str, params: dict[str, Any]) -> dict[str, Any]:
    """Coerce obviously-numeric wire parameters (grid rows/cols/indexes)."""
    numeric = {"row", "col", "idx", "idx1", "idx2", "num"}
    if action == "set_cell":
        numeric = {"row", "col", "num"}
    coerced: dict[str, Any] = {}
    for key, value in params.items():
        if key in numeric and isinstance(value, str):
            try:
                coerced[key] = int(value)
                continue
            except ValueError:
                pass
        coerced[key] = value
    return coerced


def _is_finished(puzzle: Any) -> bool:
    """Kinds signal completion through flags rather than a common interface."""
    for flag in ("win", "game_over", "solved"):
        if getattr(puzzle, flag, False):
            return True
    data = getattr(puzzle, "data", None)
    if isinstance(data, dict) and (data.get("win") or data.get("game_over")):
        return True
    return False
