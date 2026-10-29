"""The desktop client's daily puzzle and progress.

Two things are checked here that no other test covers:

* **the daily is one puzzle for one date, across clients** — the desktop engine and the
  puzzle service must agree, because two clients disagreeing about "today's puzzle" is
  invisible from inside either one;
* **progress is recorded once** — a puzzle that is already solved must not add a second
  day's record or a second practice game, or a player could inflate a streak by pressing
  enter twice.

The desktop engine is exercised headlessly (SDL dummy driver): it is the same code the
window runs, minus the window.
"""

from __future__ import annotations

import os
import subprocess
import sys
from datetime import date, timedelta
from pathlib import Path

import pytest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from client.engine import Engine  # noqa: E402
from client.events import EventBus  # noqa: E402
from puzzle_service import daily  # noqa: E402
from puzzle_service.service import PuzzleService  # noqa: E402


@pytest.fixture
def engine(tmp_path: Path) -> Engine:
    return Engine(event_bus=EventBus(), lang="zh", profile_path=tmp_path / "profile.json")


def _solve(puzzle):
    """A submission this puzzle accepts as its answer, or ``None`` if it has none.

    Three kinds need more than "read the answer key":

    * the **word ladder** is solved by reaching the target, so the target is returned;
    * the **anagram** and the **colour sequence** are *action-driven*: their
      ``check_answer`` reads state the player builds with clicks
      (``player_letters``, ``player_input``) and ignores the argument entirely, so no
      string can solve them. Returning ``None`` says so instead of pretending;
    * the **anagram** also shows a *scrambled* word, and handing that back is wrong —
      the first version of this helper did exactly that, so one day was silently
      recorded as unsolved and a streak of three read as two.

    A helper that answers wrongly is not a harmless test detail: it changes what the
    test measures.
    """
    data = getattr(puzzle, "data", {}) or {}
    name = type(puzzle).__name__
    if name in ("AnagramPuzzle", "ColorSequencePuzzle"):
        return None
    for key in ("answer", "word", "target", "end"):
        if key in data and not isinstance(data.get(key), (list, dict)):
            return data[key]
    raise AssertionError(f"{name} exposes no answer key")


# ---------------------------------------------------------------------------
# The daily is one puzzle per date, in every client
# ---------------------------------------------------------------------------


def test_the_daily_is_reproducible_for_one_client(engine: Engine) -> None:
    first = engine.start_daily("2026-10-16")
    kind = first.kind
    again = engine.start_daily("2026-10-16")
    assert again.kind == kind
    assert type(again) is type(first)


def test_the_daily_matches_the_service_for_many_dates(engine: Engine) -> None:
    """The check the parity script performs, pinned in the suite.

    A curated eligible-kind list and a *different candidate order* is what actually
    broke this during development: both clients drew from "the registry" but ordered the
    candidates differently, so every date resolved to a different kind and each client
    looked correct on its own.
    """
    service = PuzzleService(language="zh")
    start = date(2026, 10, 1)
    mismatches = []
    for offset in range(21):
        day = (start + timedelta(days=offset)).isoformat()
        from_desktop = engine.start_daily(day).kind
        from_service = service.new_daily("parity", day=day)["kind"]
        if from_desktop != from_service:
            mismatches.append(f"{day}: {from_desktop} != {from_service}")
    assert not mismatches, "desktop and service disagree about the daily:\n" + "\n".join(mismatches)


def test_the_daily_draws_only_from_the_curated_kinds(engine: Engine) -> None:
    """Long sessions and timed-flash kinds are deliberately not dailies."""
    drawn = {
        engine.start_daily((date(2026, 1, 1) + timedelta(days=offset)).isoformat()).kind
        for offset in range(60)
    }
    assert drawn <= set(daily.DAILY_KINDS), f"unexpected daily kind(s): {drawn - set(daily.DAILY_KINDS)}"
    # And the pool is actually used, not accidentally narrowed to one kind.
    assert len(drawn) >= 4, f"the daily only ever produced {drawn}"


def test_the_daily_rejects_a_malformed_date(engine: Engine) -> None:
    for bad in ("2026-2-3", "16/10/2026", "today", ""):
        with pytest.raises(ValueError, match="YYYY-MM-DD"):
            engine.start_daily(bad)


def test_the_daily_ignores_a_random_difficulty_choice(engine: Engine) -> None:
    """`random` would consume a draw and give this client a different kind."""
    engine.state.difficulty = "random"
    assert engine.start_daily("2026-10-16").kind == Engine(
        event_bus=EventBus(), lang="zh", remember=False
    ).start_daily("2026-10-16").kind


# ---------------------------------------------------------------------------
# Progress
# ---------------------------------------------------------------------------


def test_solving_the_daily_records_it(engine: Engine, tmp_path: Path) -> None:
    puzzle = engine.start_daily("2026-10-16")
    result = engine.submit_answer(_solve(puzzle))
    assert result["correct"] is True
    assert result["daily"] == "2026-10-16"

    status = engine.daily_status("2026-10-16")
    assert status["played"] is True and status["solved"] is True
    assert status["kind"] == puzzle.kind
    assert status["streak"] == 1
    assert (tmp_path / "profile.json").is_file()


def test_the_daily_streak_counts_consecutive_days(engine: Engine) -> None:
    """The streak is anchored to the last day played, not to the wall clock.

    Anchoring to `today()` would make this test depend on the real date: with fixed
    2026-10 dates and a later "today", the streak is legitimately 0 and the assertion
    would be measuring the calendar rather than the code.

    The days are chosen to be *answerable*: an action-driven kind (anagram, colours)
    cannot be solved through the submit path this test uses, and picking one would test
    the puzzle's input handling rather than the streak.
    """
    solved_days = []
    day = date(2026, 10, 14)
    while len(solved_days) < 3:
        key = day.isoformat()
        puzzle = engine.start_daily(key)
        answer = _solve(puzzle)
        if answer is not None:
            result = engine.submit_answer(answer)
            if result["correct"]:
                solved_days.append(key)
        day += timedelta(days=1)
        assert day < date(2027, 1, 1), "no three answerable consecutive days found"

    anchor = solved_days[-1]
    assert engine.profile_summary(anchor)["current_streak"] == 3, solved_days
    assert engine.profile_summary(anchor)["best_streak"] == 3

    # A gap breaks it: a record well after the run is a streak of one, not of four.
    later = (date.fromisoformat(anchor) + timedelta(days=5)).isoformat()
    engine.start_daily(later)
    answer = _solve(engine.current_puzzle)
    if answer is not None:
        engine.submit_answer(answer)
    assert engine.profile_summary(later)["current_streak"] <= 1
    assert engine.profile_summary(later)["best_streak"] == 3


def test_a_daily_is_recorded_once(engine: Engine) -> None:
    """Pressing enter twice must not invent a second day or a second solve."""
    puzzle = engine.start_daily("2026-10-16")
    engine.submit_answer(_solve(puzzle))
    before = engine.profile_summary()
    engine.submit_answer(_solve(puzzle))
    engine.submit_answer(_solve(puzzle))
    after = engine.profile_summary()
    assert after["total_solved"] == before["total_solved"]
    assert after["days_played"] == before["days_played"] == 1


#: Kinds whose answer is a value this helper can produce. Chosen explicitly rather than
#: drawing at random: a random draw landed on a memory puzzle, whose answer is built
#: with clicks, and the test then measured the draw instead of the recording.
_ANSWERABLE = ("math", "riddle", "guess_number", "hangman", "word_ladder")


def _start_answerable(engine: Engine):
    """Start a free-play puzzle of a kind :func:`_solve` can finish."""
    for kind in _ANSWERABLE:
        puzzle = engine.new_puzzle_of_kind(kind)
        if _solve(puzzle) is not None:
            return puzzle
    raise AssertionError(f"none of {_ANSWERABLE} was answerable")


def test_free_play_records_practice_stats_not_days(engine: Engine) -> None:
    """Practice must not touch the streak: a streak means "did the daily"."""
    engine.configure("balanced", "easy")
    puzzle = _start_answerable(engine)
    assert engine.submit_answer(_solve(puzzle))["correct"] is True

    summary = engine.profile_summary()
    assert summary["practice_played"] == 1
    assert summary["practice_solved"] == 1
    assert summary["days_played"] == 0
    assert summary["current_streak"] == 0

    rows = engine.kind_summary()
    assert rows and rows[0]["kind"] == puzzle.kind and rows[0]["played"] == 1


def test_a_skipped_puzzle_is_not_recorded_as_effort(engine: Engine) -> None:
    engine.configure("balanced", "easy")
    engine.start_new_puzzle()
    engine.skip_puzzle()
    summary = engine.profile_summary()
    assert summary["practice_played"] == 0
    assert engine.is_daily is False


def test_progress_survives_a_restart(tmp_path: Path) -> None:
    """The point of a save file: the streak is still there tomorrow."""
    path = tmp_path / "profile.json"
    first = Engine(event_bus=EventBus(), lang="zh", profile_path=path)
    first.start_daily("2026-10-16")
    first.submit_answer(_solve(first.current_puzzle))

    second = Engine(event_bus=EventBus(), lang="zh", profile_path=path)
    assert second.daily_status("2026-10-16")["solved"] is True
    assert second.profile_summary()["total_solved"] == 1


def test_progress_can_be_disabled() -> None:
    """`remember=False` is for tests and for a throwaway session."""
    engine = Engine(event_bus=EventBus(), lang="zh", remember=False)
    engine.start_daily("2026-10-16")
    engine.submit_answer(_solve(engine.current_puzzle))
    assert engine.profile_summary()["disabled"] is True
    assert engine.share_card() == ""


def test_a_corrupt_profile_does_not_stop_the_game(tmp_path: Path) -> None:
    path = tmp_path / "profile.json"
    path.write_text("{ not json", encoding="utf-8")
    engine = Engine(event_bus=EventBus(), lang="zh", profile_path=path)
    assert engine.profile_warning and "unusable" in engine.profile_warning
    engine.start_daily("2026-10-16")
    assert engine.submit_answer(_solve(engine.current_puzzle))["correct"] is True


def test_the_desktop_and_the_service_share_one_profile_file(tmp_path: Path) -> None:
    """A streak is one number, whichever client the player opens."""
    path = tmp_path / "profile.json"
    engine = Engine(event_bus=EventBus(), lang="zh", profile_path=path)
    engine.start_daily("2026-10-16")
    engine.submit_answer(_solve(engine.current_puzzle))

    service = PuzzleService(language="zh", profile_path=path)
    listed = service.history(limit=5)
    assert listed and listed[0]["day"] == "2026-10-16"
    assert service.profile_summary("2026-10-16")["current_streak"] == 1


def test_the_share_card_is_spoiler_free(engine: Engine) -> None:
    puzzle = engine.start_daily("2026-10-16")
    engine.submit_answer(_solve(puzzle))
    card = engine.share_card("2026-10-16")
    assert "2026-10-16" in card
    answer = str(_solve(engine.current_puzzle))
    assert answer not in card, f"the card leaked the answer {answer!r}"


def test_the_parity_script_agrees() -> None:
    """The script is what a maintainer runs; it must not be the broken one."""
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "check_daily_parity.py"), "--days", "7"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        cwd=str(ROOT),
        timeout=300,
    )
    assert result.returncode == 0, f"{result.stdout}\n{result.stderr}"
    assert "DAILY PARITY PASSED" in result.stdout
