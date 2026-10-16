"""Local play profile: daily results, streaks, and a spoiler-free share card.

What this is for: a daily puzzle is only a habit if yesterday's result still
exists. The service itself stays stateless (any session can be dropped at any
time), so progress lives here — one small JSON file per player, written
atomically, no database and no server-side schedule.

Two rules shape the design:

* **Nothing secret is stored.** A record keeps the day, the kind, whether it was
  solved, the score and the attempt count. It never keeps the answer or the
  puzzle's content, so a save file can be shared, inspected, or committed without
  leaking a solution.
* **A missing or corrupt file is not fatal.** Progress is a convenience: the game
  must still start. A broken file is reported on stderr and treated as empty,
  rather than crashing the service or silently wiping the file.
"""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

__all__ = [
    "DailyRecord",
    "Profile",
    "ProfileStore",
    "default_profile_path",
    "PROFILE_ENV_VAR",
    "share_card",
    "SOLVED_MARK",
    "UNSOLVED_MARK",
]

PROFILE_ENV_VAR = "TEXT_ADVENTURE_PROFILE"

#: Marks used by the share card. Text, not emoji-only, so it survives a paste into
#: anything that mangles emoji and stays readable in a screen reader.
SOLVED_MARK = "✔"
UNSOLVED_MARK = "✘"


def default_profile_path() -> Path:
    """Where a player's progress lives, unless overridden by the environment."""
    override = os.environ.get(PROFILE_ENV_VAR)
    if override:
        return Path(override)
    # `saves/` is already git-ignored, which is what keeps progress out of the repo.
    return Path(__file__).resolve().parents[1] / "saves" / "profile.json"


@dataclass
class DailyRecord:
    """One day's outcome for one player. Deliberately answer-free."""

    day: str
    kind: str
    solved: bool = False
    score: int = 0
    attempts: int = 0
    seconds: float = 0.0

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "DailyRecord":
        return cls(
            day=str(payload.get("day", "")),
            kind=str(payload.get("kind", "")),
            solved=bool(payload.get("solved", False)),
            score=int(payload.get("score", 0) or 0),
            attempts=int(payload.get("attempts", 0) or 0),
            seconds=float(payload.get("seconds", 0.0) or 0.0),
        )


@dataclass
class Profile:
    """Everything remembered about one player."""

    days: dict[str, DailyRecord] = field(default_factory=dict)
    total_solved: int = 0
    best_streak: int = 0

    # --- recording -----------------------------------------------------------

    def record(self, outcome: DailyRecord) -> DailyRecord:
        """Store (or replace) a day's outcome, keeping the best result for that day."""
        previous = self.days.get(outcome.day)
        if previous is not None:
            # Replaying a day must not lose a solve, and must not double-count it.
            merged = DailyRecord(
                day=outcome.day,
                kind=outcome.kind or previous.kind,
                solved=previous.solved or outcome.solved,
                score=max(previous.score, outcome.score),
                attempts=previous.attempts + outcome.attempts,
                seconds=max(previous.seconds, outcome.seconds),
            )
        else:
            merged = outcome
        self.days[outcome.day] = merged
        self.total_solved = sum(1 for record in self.days.values() if record.solved)
        self.best_streak = max(self.best_streak, self.current_streak(outcome.day))
        return merged

    # --- streaks -------------------------------------------------------------

    def current_streak(self, today: str | None = None) -> int:
        """Consecutive solved days ending today (or yesterday, if today is still open).

        Counting backwards rather than storing a counter means the streak is derived
        from evidence: a missed day breaks it automatically, and editing the save
        file cannot invent a streak that the records do not support.
        """
        anchor = _parse_day(today) or date.today()
        cursor = anchor
        if not (self.days.get(cursor.isoformat()) or {}) or not self._solved_on(cursor):
            # Today may not be played yet: a streak that ended yesterday is still alive.
            cursor = anchor - timedelta(days=1)
        streak = 0
        while self._solved_on(cursor):
            streak += 1
            cursor -= timedelta(days=1)
        return streak

    def _solved_on(self, day: date) -> bool:
        record = self.days.get(day.isoformat())
        return bool(record and record.solved)

    # --- reporting -----------------------------------------------------------

    def share_card(self, day: str | None = None) -> str:
        """A spoiler-free summary of a day — the thing a player pastes to a friend.

        It states the outcome, the streak and the kind, and nothing about the
        puzzle's content: no answer, no words used, no guesses.
        """
        return share_card(self, day)

    def summary(self, today: str | None = None) -> dict[str, Any]:
        return {
            "days_played": len(self.days),
            "total_solved": self.total_solved,
            "current_streak": self.current_streak(today),
            "best_streak": self.best_streak,
            "today": today or date.today().isoformat(),
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": 1,
            "days": {day: asdict(record) for day, record in sorted(self.days.items())},
            "total_solved": self.total_solved,
            "best_streak": self.best_streak,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "Profile":
        days = payload.get("days")
        records: dict[str, DailyRecord] = {}
        if isinstance(days, dict):
            for day, entry in days.items():
                if isinstance(entry, dict):
                    record = DailyRecord.from_dict(entry)
                    record.day = record.day or str(day)
                    records[str(day)] = record
        return cls(
            days=records,
            total_solved=int(payload.get("total_solved", 0) or 0),
            best_streak=int(payload.get("best_streak", 0) or 0),
        )


class ProfileStore:
    """Reads and writes a :class:`Profile`, treating unreadable files as empty."""

    def __init__(self, path: Path | str | None = None):
        self.path = Path(path) if path is not None else default_profile_path()
        self.profile = Profile()
        self.warning: str | None = None
        self.load()

    def load(self) -> Profile:
        self.warning = None
        if not self.path.is_file():
            self.profile = Profile()
            return self.profile
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(payload, dict):
                raise ValueError("profile must be a JSON object")
            self.profile = Profile.from_dict(payload)
        except (json.JSONDecodeError, ValueError, OSError) as exc:
            # Progress is a convenience, not a prerequisite: say what is wrong and
            # continue with an empty profile instead of failing to start. The file is
            # left untouched so the player can inspect it.
            self.warning = f"{self.path}: unusable profile ignored ({type(exc).__name__}: {exc})"
            self.profile = Profile()
        return self.profile

    def save(self) -> None:
        """Write atomically: a crash mid-write must not truncate existing progress."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(self.profile.to_dict(), ensure_ascii=False, indent=2) + "\n"
        handle = tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", newline="\n", dir=self.path.parent,
            prefix=self.path.name, suffix=".tmp", delete=False,
        )
        try:
            with handle:
                handle.write(payload)
            os.replace(handle.name, self.path)
        except OSError as exc:  # pragma: no cover - disk failure
            self.warning = f"could not save profile: {exc}"
            try:
                os.unlink(handle.name)
            except OSError:
                pass


def share_card(profile: Profile, day: str | None = None) -> str:
    """Render the share text for *day* (default: today, else the most recent day)."""
    key = day
    if key is None:
        key = date.today().isoformat()
        if key not in profile.days and profile.days:
            key = max(profile.days)
    header = f"文字解谜 · 每日一题 {key}"
    safe = "（本卡片不含谜底，可安全分享）"
    if key not in profile.days:
        return f"{header}\n今天还没玩（或没有记录）。\n{safe}"

    record = profile.days[key]
    mark = SOLVED_MARK if record.solved else UNSOLVED_MARK
    streak = profile.current_streak(key)
    lines = [
        header,
        f"{mark} {'已完成' if record.solved else '未完成'} · 种类 {record.kind}",
        f"得分 {record.score} · 用时 {record.seconds:.0f}s · 尝试 {record.attempts} 次",
    ]
    if streak:
        lines.append(f"连续 {streak} 天（最佳 {profile.best_streak} 天）")
    # The footer names the property the card is supposed to have, in the card
    # itself: a reader can tell it was designed to be shared without leaking.
    lines.append(safe)
    return "\n".join(lines)


def _parse_day(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None
