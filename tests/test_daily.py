"""Daily-puzzle contract: a date picks a puzzle, and that choice is reproducible.

Reproducibility is the whole feature — a "puzzle of the day" that differs between
two players, or between two runs on the same machine, is not a puzzle of the day.
It is also easy to lose: the first attempt at seeding broke exactly here (a static
method kept drawing from process-global ``random``), so these tests check the
property for **every** kind rather than for a sample.
"""

from __future__ import annotations

import json
import random

import pytest

from puzzle_service.registry import get
from puzzle_service.service import PuzzleService, _is_iso_date, _seed_from

DAYS = [
    f"{year}-{month:02d}-{day:02d}"
    for year in (2025, 2026, 2027)
    for month in (1, 3, 5, 7, 9, 11)
    for day in (1, 9, 17, 25)
]


@pytest.fixture()
def service() -> PuzzleService:
    return PuzzleService(language="zh")


def _view_digest(service: PuzzleService, day: str, kind: str | None) -> str:
    rng = random.Random(_seed_from(day))
    snapshot = service.new_puzzle(session_id="d", kind=kind, difficulty="easy", rng=rng)
    # last_result survives from the previous draw inside one session; clearing it
    # keeps the digest about the puzzle rather than about what was played before.
    snapshot.pop("last_result", None)
    snapshot.pop("elapsed", None)
    snapshot.pop("puzzles_started", None)
    return json.dumps(snapshot["view"], sort_keys=True, ensure_ascii=False)


def test_the_same_day_produces_the_same_kind(service):
    picks = {
        service.new_puzzle(session_id="k", rng=random.Random(_seed_from("2026-10-16")))["kind"]
        for _ in range(6)
    }
    assert len(picks) == 1, f"the daily kind is not stable: {picks}"


def test_the_same_day_produces_the_same_puzzle_for_every_kind(service):
    """Every kind, because seeding is threaded through each kind's draws."""
    unstable = []
    for kind in (item["name"] for item in service.list_kinds()):
        first = _view_digest(service, "2026-10-16", kind)
        second = _view_digest(service, "2026-10-16", kind)
        if first != second:
            unstable.append(kind)
    assert not unstable, f"not reproducible under a fixed seed: {unstable}"


def _data_digest(service: PuzzleService, day: str, kind: str) -> str:
    """Identity of the generated *puzzle*, not of its rendering.

    Data, not view: several kinds deliberately hide their state from the view
    (hangman's view never contains the word, colour sequence's view never contains
    the sequence), so comparing views would report "the date has no effect" for
    kinds where it plainly does.
    """
    rng = random.Random(_seed_from(day))
    puzzle = get(kind).create(difficulty="easy", rng=rng)
    data = {
        key: value
        for key, value in puzzle.data.items()
        if not isinstance(value, (set, dict)) and key not in {"player_grid", "player_path"}
    }
    return json.dumps(data, sort_keys=True, ensure_ascii=False, default=str)


def test_different_days_eventually_give_different_puzzles(service):
    """Not every pair must differ (a kind may legitimately repeat), but not all may.

    Asserting a single pair looks like a stronger test and is actually flaky: a
    kind with a small solution space can coincide on two dates.
    """
    stuck = []
    for kind in (item["name"] for item in service.list_kinds()):
        digests = {_data_digest(service, day, kind) for day in DAYS}
        if len(digests) == 1:
            stuck.append(kind)
    assert not stuck, f"the date has no effect on these kinds: {stuck}"


def test_the_view_of_a_daily_puzzle_is_reproducible_even_when_it_hides_state(service):
    """The reproducible/renderable distinction, stated as its own property."""
    for kind in ("hangman", "color_sequence", "memory", "guess_number"):
        first = _view_digest(service, "2026-10-16", kind)
        second = _view_digest(service, "2026-10-16", kind)
        assert first == second, f"{kind}: same day gave two different views"


def test_new_daily_sets_the_day_and_reports_it(service):
    snapshot = service.new_daily(session_id="s", day="2026-10-16")
    assert snapshot["daily"] == {"day": "2026-10-16", "kind": snapshot["kind"]}
    assert snapshot["day"] == "2026-10-16"
    assert snapshot["view"] is not None


def test_new_daily_is_reproducible_across_sessions(service):
    first = service.new_daily(session_id="a", day="2026-10-16")
    second = service.new_daily(session_id="b", day="2026-10-16")
    assert first["kind"] == second["kind"]
    assert json.dumps(first["view"], sort_keys=True) == json.dumps(
        second["view"], sort_keys=True
    )


def test_a_malformed_date_is_refused(service):
    from puzzle_service.service import InvalidAction

    for bad in ("2026-13-01", "16-10-2026", "yesterday", "2026/10/16"):
        with pytest.raises(InvalidAction):
            service.new_daily(session_id="s", day=bad)


def test_the_seed_is_stable_across_processes(service):
    """`hash()` is salted per process; the daily seed must not be.

    A salted seed would give a different puzzle on every restart, which is the
    defect this asserts against.
    """
    import subprocess
    import sys
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [sys.executable, "-c", (
            "import sys; sys.path.insert(0, r'%s');"
            "from puzzle_service.service import _seed_from; print(_seed_from('2026-10-16'))" % root
        )],
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=str(root),
        timeout=120,
    )
    assert result.returncode == 0, result.stderr
    assert int(result.stdout.strip()) == _seed_from("2026-10-16")


def test_an_ordinary_random_puzzle_is_still_random(service):
    """Seeding must not leak: without an rng, two draws should differ sometimes."""
    digests = {
        json.dumps(
            service.new_puzzle(session_id="r", kind="math", difficulty="easy")["view"],
            sort_keys=True,
        )
        for _ in range(30)
    }
    assert len(digests) > 1, "unseeded play looks frozen — a seeded rng leaked into it"


def test_seeded_and_unseeded_draws_do_not_interfere(service):
    """A seeded draw must not change what an unrelated session sees afterwards."""
    import puzzle_service.service as service_module

    first = service_module.random.random()
    service.new_puzzle(session_id="seeded", kind="math", rng=random.Random(1234))
    second = service_module.random.random()
    assert first != second, "the global generator did not advance; it was reseeded"


def test_iso_date_helper():
    assert _is_iso_date("2026-10-16")
    assert not _is_iso_date("2026-2-3")
    assert not _is_iso_date("")
    assert not _is_iso_date(None)
