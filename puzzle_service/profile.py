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
    "KindStats",
    "Profile",
    "ProfileStore",
    "default_profile_path",
    "PROFILE_ENV_VAR",
    "share_card",
    "share_card_svg",
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
class KindStats:
    """Totals for one puzzle kind across free play (non-daily puzzles).

    Separate from the daily records on purpose. A day's record answers "did I do
    today's puzzle"; these answer "how am I doing at crosswords". Mixing them would
    make the streak depend on practice runs, which is not what a streak means.
    """

    kind: str
    played: int = 0
    solved: int = 0
    best_score: int = 0
    total_seconds: float = 0.0

    @property
    def solve_rate(self) -> float:
        return self.solved / self.played if self.played else 0.0

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "KindStats":
        return cls(
            kind=str(payload.get("kind", "")),
            played=int(payload.get("played", 0) or 0),
            solved=int(payload.get("solved", 0) or 0),
            best_score=int(payload.get("best_score", 0) or 0),
            total_seconds=float(payload.get("total_seconds", 0.0) or 0.0),
        )


@dataclass
class Profile:
    """Everything remembered about one player."""

    days: dict[str, DailyRecord] = field(default_factory=dict)
    total_solved: int = 0
    best_streak: int = 0
    kinds: dict[str, KindStats] = field(default_factory=dict)

    # --- recording -----------------------------------------------------------

    def record_kind(
        self, kind: str, *, solved: bool, score: int = 0, seconds: float = 0.0
    ) -> KindStats:
        """Record one finished free-play puzzle of *kind*.

        Only finished puzzles are recorded (a skipped puzzle is not evidence about
        skill), and the best score is kept rather than the latest, so a bad run does
        not erase a good one.
        """
        stats = self.kinds.get(kind) or KindStats(kind=kind)
        stats.played += 1
        if solved:
            stats.solved += 1
        stats.best_score = max(stats.best_score, int(score))
        stats.total_seconds += max(0.0, float(seconds))
        self.kinds[kind] = stats
        return stats

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

    def history(self, limit: int = 14, day: str | None = None) -> list[DailyRecord]:
        """The most recent *limit* days, newest first.

        Listing history is what turns a streak from a number into evidence:
        a player can see which days they played, and a test can check that a
        replay of an old day still resolves to the same puzzle. Without it the
        only way back to a past day was to remember its date from elsewhere.
        """
        anchor = day or date.today().isoformat()
        days = [key for key in sorted(self.days) if key <= anchor]
        return [self.days[key] for key in reversed(days[-max(1, limit):])]

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
            "practice_played": sum(stats.played for stats in self.kinds.values()),
            "practice_solved": sum(stats.solved for stats in self.kinds.values()),
        }

    def kind_summary(self) -> list[dict[str, Any]]:
        """Per-kind free-play totals, weakest first — the order a player needs."""
        rows = [
            {
                "kind": stats.kind,
                "played": stats.played,
                "solved": stats.solved,
                "best_score": stats.best_score,
                "solve_rate": round(stats.solve_rate, 3),
                "average_seconds": round(stats.total_seconds / stats.played, 1)
                if stats.played
                else 0.0,
            }
            for stats in self.kinds.values()
        ]
        return sorted(rows, key=lambda row: (row["solve_rate"], -row["played"], row["kind"]))

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": 2,
            "days": {day: asdict(record) for day, record in sorted(self.days.items())},
            "total_solved": self.total_solved,
            "best_streak": self.best_streak,
            "kinds": {kind: asdict(stats) for kind, stats in sorted(self.kinds.items())},
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
        # A version-1 file has no `kinds`; it loads with empty practice stats rather
        # than being rejected, so an existing player keeps their streak.
        kinds_payload = payload.get("kinds")
        kinds: dict[str, KindStats] = {}
        if isinstance(kinds_payload, dict):
            for kind, entry in kinds_payload.items():
                if isinstance(entry, dict):
                    stats = KindStats.from_dict(entry)
                    stats.kind = stats.kind or str(kind)
                    kinds[str(kind)] = stats
        return cls(
            days=records,
            total_solved=int(payload.get("total_solved", 0) or 0),
            best_streak=int(payload.get("best_streak", 0) or 0),
            kinds=kinds,
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
    key = _card_day(profile, day)
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


def share_card_svg(profile: Profile, day: str | None = None) -> str:
    """A picture version of the share card, as standalone SVG.

    SVG rather than a raster format for two reasons: it needs no dependency and no
    browser to produce, and — because the text stays as ``<text>`` elements — the
    card remains readable by a screen reader and checkable by a test. A PNG export
    would have thrown both away.

    The card shows the same three facts as the text version and nothing else: no
    answer, no puzzle content. The layout is drawn by hand from plain rectangles
    and text, so there is no font or image to ship alongside it.
    """
    key = _card_day(profile, day)
    record = profile.days.get(key)
    solved = bool(record and record.solved)
    accent = "#50c878" if solved else "#dc5050"
    status = "已完成" if solved else ("未完成" if record else "还没玩")
    kind = record.kind if record else "—"
    score = record.score if record else 0
    seconds = f"{record.seconds:.0f}s" if record else "—"
    attempts = record.attempts if record else 0
    streak = profile.current_streak(key) if record else 0

    parts: list[str] = []
    # Every interpolated value is escaped, including the ones inside attributes:
    # a day string arrives from the caller, and an unescaped one could close the
    # attribute and inject markup into the document (caught by a test, 2026-10-16).
    label = _svg_escape(
        f"文字解谜每日一题 {key}，{status}，得分 {score}，连续 {streak} 天，不含谜底"
    )
    parts.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="480" height="260" '
        f'viewBox="0 0 480 260" role="img" aria-label="{label}">'
    )
    parts.append('<rect width="480" height="260" rx="16" fill="#1e1e2e"/>')
    parts.append('<rect x="16" y="16" width="448" height="228" rx="12" fill="#2d2d41"/>')
    parts.append(
        f'<text x="36" y="60" font-family="sans-serif" font-size="20" fill="#ebebf5">'
        f'文字解谜 · 每日一题</text>'
    )
    parts.append(
        f'<text x="36" y="88" font-family="sans-serif" font-size="14" fill="#9a9ab8">'
        f'{_svg_escape(key)}</text>'
    )
    # Status row: a mark plus the word, so the outcome does not depend on colour
    # alone (WCAG 2.2 SC 1.4.1).
    parts.append(f'<circle cx="44" cy="128" r="9" fill="{accent}"/>')
    parts.append(
        f'<text x="62" y="134" font-family="sans-serif" font-size="18" fill="#ebebf5">'
        f'{"✔" if solved else "✘"} {_svg_escape(status)} · {_svg_escape(str(kind))}</text>'
    )
    parts.append(
        f'<text x="36" y="172" font-family="sans-serif" font-size="15" fill="#ebebf5">'
        f'得分 {score} · 用时 {_svg_escape(seconds)} · 尝试 {attempts} 次</text>'
    )
    parts.append(
        f'<text x="36" y="200" font-family="sans-serif" font-size="15" fill="#ebebf5">'
        f'连续 {streak} 天（最佳 {profile.best_streak} 天）</text>'
    )
    parts.append(
        f'<text x="36" y="228" font-family="sans-serif" font-size="12" fill="#9a9ab8">'
        f'本卡片不含谜底，可安全分享</text>'
    )
    parts.append("</svg>")
    return "\n".join(parts)


def _card_day(profile: Profile, day: str | None) -> str:
    """Which day a card is about: the one asked for, else today, else the latest."""
    if day:
        return day
    today = date.today().isoformat()
    if today not in profile.days and profile.days:
        return max(profile.days)
    return today


def _parse_day(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None


def _svg_escape(text: str) -> str:
    """Escape text for XML content. A player's data must not be able to break the card."""
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
