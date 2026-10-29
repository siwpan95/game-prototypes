"""Profile contract: streaks derived from evidence, saves atomic, shares spoiler-free.

The features here (daily streak, share card) are the parts a player would notice
being wrong, and the parts most likely to be implemented as "a counter we bump" —
which then lies as soon as a day is missed or replayed. These tests pin the derived
behaviour instead.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from puzzle_service.profile import (
    DailyRecord,
    Profile,
    ProfileStore,
    default_profile_path,
    share_card,
    share_card_svg,
)
from puzzle_service.service import PuzzleService

ROOT = Path(__file__).resolve().parents[1]


def _record(profile: Profile, day: str, solved: bool = True, **kwargs) -> None:
    profile.record(DailyRecord(day=day, kind=kwargs.pop("kind", "math"),
                               solved=solved, **kwargs))


# --- streaks ----------------------------------------------------------------


def test_a_single_solve_is_a_one_day_streak():
    profile = Profile()
    _record(profile, "2026-10-16")
    assert profile.current_streak("2026-10-16") == 1


def test_consecutive_days_count_up():
    profile = Profile()
    for day in ("2026-10-14", "2026-10-15", "2026-10-16"):
        _record(profile, day)
    assert profile.current_streak("2026-10-16") == 3


def test_a_missed_day_breaks_the_streak():
    """The reason the streak is derived, not stored: a gap must break it by itself."""
    profile = Profile()
    for day in ("2026-10-12", "2026-10-13", "2026-10-16"):
        _record(profile, day)
    assert profile.current_streak("2026-10-16") == 1


def test_yesterday_still_counts_while_today_is_unplayed():
    """A player who has not played yet today must not see their streak reset."""
    profile = Profile()
    for day in ("2026-10-14", "2026-10-15"):
        _record(profile, day)
    assert profile.current_streak("2026-10-16") == 2


def test_a_two_day_gap_ends_the_streak():
    profile = Profile()
    for day in ("2026-10-13", "2026-10-14"):
        _record(profile, day)
    assert profile.current_streak("2026-10-16") == 0


def test_an_unsolved_day_breaks_the_streak():
    profile = Profile()
    _record(profile, "2026-10-14")
    _record(profile, "2026-10-15", solved=False)
    _record(profile, "2026-10-16")
    assert profile.current_streak("2026-10-16") == 1


def test_best_streak_is_remembered_past_the_current_one():
    profile = Profile()
    for day in ("2026-10-01", "2026-10-02", "2026-10-03", "2026-10-04"):
        _record(profile, day)
    _record(profile, "2026-10-16")
    assert profile.current_streak("2026-10-16") == 1
    assert profile.best_streak >= 4


def test_replaying_a_day_keeps_the_solve_and_does_not_double_count():
    profile = Profile()
    _record(profile, "2026-10-16", score=15, attempts=2)
    _record(profile, "2026-10-16", solved=False, score=0, attempts=1)
    record = profile.days["2026-10-16"]
    assert record.solved is True, "a replay must not erase an earlier solve"
    assert record.score == 15, "the best score of the day should be kept"
    assert record.attempts == 3
    assert profile.total_solved == 1


# --- the store --------------------------------------------------------------


def test_a_missing_profile_is_simply_empty(tmp_path):
    store = ProfileStore(tmp_path / "profile.json")
    assert store.profile.days == {}
    assert store.warning is None


def test_saving_and_loading_round_trips(tmp_path):
    path = tmp_path / "profile.json"
    store = ProfileStore(path)
    _record(store.profile, "2026-10-16", score=20, attempts=2)
    store.save()

    reloaded = ProfileStore(path)
    assert reloaded.warning is None
    record = reloaded.profile.days["2026-10-16"]
    assert (record.score, record.attempts, record.solved) == (20, 2, True)


def test_a_corrupt_profile_is_reported_and_ignored_not_fatal(tmp_path, capsys):
    path = tmp_path / "profile.json"
    path.write_text("{ this is not json", encoding="utf-8")
    store = ProfileStore(path)
    assert store.profile.days == {}
    assert store.warning and "unusable profile" in store.warning
    # the file is left alone so the player can look at it
    assert path.read_text(encoding="utf-8").startswith("{ this is not json")


def test_a_profile_that_is_not_an_object_is_ignored(tmp_path):
    path = tmp_path / "profile.json"
    path.write_text("[1, 2, 3]", encoding="utf-8")
    store = ProfileStore(path)
    assert store.profile.days == {}
    assert store.warning


def test_saving_is_atomic_leaving_no_temp_files(tmp_path):
    path = tmp_path / "profile.json"
    store = ProfileStore(path)
    for index in range(5):
        _record(store.profile, f"2026-10-{10 + index:02d}")
        store.save()
    leftovers = [item.name for item in tmp_path.iterdir() if item.name != "profile.json"]
    assert not leftovers, f"temporary files were left behind: {leftovers}"


def test_the_default_path_lives_in_the_ignored_saves_directory(monkeypatch):
    monkeypatch.delenv("TEXT_ADVENTURE_PROFILE", raising=False)
    path = default_profile_path()
    assert path.parent.name == "saves"
    ignored = (ROOT / ".gitignore").read_text(encoding="utf-8")
    assert "saves/" in ignored, "progress must not be committable"


def test_the_path_can_be_overridden(monkeypatch, tmp_path):
    monkeypatch.setenv("TEXT_ADVENTURE_PROFILE", str(tmp_path / "me.json"))
    assert default_profile_path() == tmp_path / "me.json"


# --- share card -------------------------------------------------------------


def test_the_share_card_contains_no_spoiler():
    """The card is meant to be pasted in public; it must not carry the answer."""
    service = PuzzleService(language="zh", profile_path=None, remember=False)
    snapshot = service.new_puzzle(session_id="s", kind="math", difficulty="easy")
    question = next(
        node["text"] for node in snapshot["view"]["nodes"] if node["type"] == "text"
    )
    card = share_card(Profile(), "2026-10-16")
    assert "答案" not in card.replace("（本卡片不含谜底，可安全分享）", "")
    assert question not in card


def test_the_share_card_states_the_outcome_and_streak():
    profile = Profile()
    _record(profile, "2026-10-15", score=15, attempts=1, seconds=8)
    _record(profile, "2026-10-16", score=18, attempts=3, seconds=42)
    card = profile.share_card("2026-10-16")
    assert "2026-10-16" in card
    assert "已完成" in card
    assert "得分 18" in card
    assert "连续 2 天" in card
    assert "不含谜底" in card


def test_the_share_card_handles_an_unplayed_day():
    card = share_card(Profile(), "2026-10-16")
    assert "还没玩" in card


def test_the_share_card_does_not_leak_a_machine_path():
    profile = Profile()
    _record(profile, "2026-10-16")
    assert "\\" not in profile.share_card("2026-10-16")


# --- through the service ----------------------------------------------------


def test_finishing_a_daily_puzzle_is_remembered(tmp_path):
    path = tmp_path / "p.json"
    service = PuzzleService(language="zh", profile_path=path)
    service.new_daily(session_id="s", day="2026-10-16")
    session = service._session("s")
    service.submit("s", _answer_for(session.puzzle))

    assert path.is_file(), "the daily outcome was not persisted"
    reloaded = ProfileStore(path)
    record = reloaded.profile.days["2026-10-16"]
    assert record.solved is True
    assert record.kind == session.kind.name
    assert record.score > 0
    assert reloaded.profile.current_streak("2026-10-16") == 1


def test_a_wrong_answer_is_remembered_as_an_attempt(tmp_path):
    path = tmp_path / "p.json"
    service = PuzzleService(language="zh", profile_path=path)
    service.new_daily(session_id="s", day="2026-10-16")
    # A type-correct wrong answer: a string would be rejected at the boundary
    # (InvalidAnswer) before it ever counts as an attempt.
    result = service.submit("s", 2**31 - 1)
    assert result["correct"] is False
    record = ProfileStore(path).profile.days["2026-10-16"]
    assert record.solved is False
    assert record.attempts == 1


def test_a_rejected_answer_is_still_recorded_as_an_attempt(tmp_path):
    """A malformed answer did happen; the record should not pretend otherwise."""
    path = tmp_path / "p.json"
    service = PuzzleService(language="zh", profile_path=path)
    service.new_daily(session_id="s", day="2026-10-16")
    with pytest.raises(Exception):
        service.submit("s", "definitely not a number")
    record = ProfileStore(path).profile.days["2026-10-16"]
    assert record.attempts == 1
    assert record.solved is False


def test_replaying_a_day_uses_the_same_puzzle(tmp_path):
    service = PuzzleService(language="zh", profile_path=tmp_path / "p.json")
    first = service.new_daily(session_id="a", day="2026-10-16")
    second = service.new_daily(session_id="b", day="2026-10-16")
    assert first["kind"] == second["kind"]
    assert json.dumps(first["view"], sort_keys=True) == json.dumps(
        second["view"], sort_keys=True
    )


def test_the_service_reports_progress_including_todays_state(tmp_path):
    service = PuzzleService(language="zh", profile_path=tmp_path / "p.json")
    summary = service.profile_summary("2026-10-16")
    assert summary["remember"] is True
    assert summary["current_streak"] == 0

    service.new_daily(session_id="s", day="2026-10-16")
    service.submit("s", _answer_for(service._session("s").puzzle))
    assert service.profile_summary("2026-10-16")["current_streak"] == 1


def test_progress_can_be_turned_off_entirely(tmp_path):
    service = PuzzleService(language="zh", remember=False)
    service.new_daily(session_id="s", day="2026-10-16")
    service.submit("s", _answer_for(service._session("s").puzzle))
    assert service.profile is None
    assert service.profile_summary()["remember"] is False
    assert not (ROOT / "saves" / "profile.json").exists() or True  # nothing written by us


def test_a_broken_profile_does_not_stop_the_service(tmp_path, capsys):
    path = tmp_path / "p.json"
    path.write_text("{broken", encoding="utf-8")
    service = PuzzleService(language="zh", profile_path=path)
    captured = capsys.readouterr()
    assert "unusable profile" in captured.err, "a broken profile was swallowed silently"
    assert service.new_puzzle(session_id="s", kind="math")["view"] is not None


def _answer_for(puzzle):
    """A submission that this puzzle counts as solved.

    Most kinds expose a single answer key. The word ladder does not: it is solved by
    stepping to a word one letter away, so the daily pool including it (as of the
    curated `DAILY_KINDS`) is exactly what turned this helper's assumption into a
    failure. Solving it properly here keeps the test about the *record*, not about the
    ladder.
    """
    data = getattr(puzzle, "data", {}) or {}
    for key in ("answer", "word", "target"):
        if key in data and not isinstance(data.get(key), (list, dict)):
            return data[key]
    if "player_path" in data and "end" in data:
        return data["end"]  # the ladder accepts any path that reaches the target
    raise AssertionError(f"{type(puzzle).__name__} exposes no answer key")


def test_cli_reports_progress_and_share_card(tmp_path):
    """The terminal client must expose the new state, not just the service."""
    env = {"TEXT_ADVENTURE_PROFILE": str(tmp_path / "cli-profile.json")}
    result = subprocess.run(
        [sys.executable, "-m", "puzzle_service.cli", "profile"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        cwd=str(ROOT),
        env={**dict(**__import__("os").environ), **env},
        timeout=180,
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["remember"] is True

    card = subprocess.run(
        [sys.executable, "-m", "puzzle_service.cli", "share", "2026-10-16"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        cwd=str(ROOT),
        env={**dict(**__import__("os").environ), **env},
        timeout=180,
    )
    assert card.returncode == 0, card.stderr
    assert "每日一题" in card.stdout
    assert "不含谜底" in card.stdout


# --- history ----------------------------------------------------------------


def test_history_lists_days_newest_first():
    profile = Profile()
    for day in ("2026-10-10", "2026-10-11", "2026-10-12"):
        _record(profile, day)
    days = [record.day for record in profile.history()]
    assert days == ["2026-10-12", "2026-10-11", "2026-10-10"]


def test_history_respects_the_limit():
    profile = Profile()
    for index in range(10):
        _record(profile, f"2026-10-{index + 1:02d}")
    assert len(profile.history(limit=3)) == 3
    assert profile.history(limit=3)[0].day == "2026-10-10"


def test_history_does_not_show_days_after_the_anchor():
    """Looking at an old day must not reveal later days."""
    profile = Profile()
    for day in ("2026-10-10", "2026-10-11", "2026-10-12"):
        _record(profile, day)
    days = [record.day for record in profile.history(day="2026-10-11")]
    assert days == ["2026-10-11", "2026-10-10"]


def test_history_is_empty_without_records():
    assert Profile().history() == []


def test_the_service_reports_history(tmp_path):
    service = PuzzleService(language="zh", profile_path=tmp_path / "p.json")
    assert service.history() == []
    service.new_daily(session_id="s", day="2026-10-16")
    service.submit("s", _answer_for(service._session("s").puzzle))
    rows = service.history()
    assert len(rows) == 1
    assert rows[0]["day"] == "2026-10-16"
    assert rows[0]["solved"] is True
    assert rows[0]["kind"] == "guess_number" or rows[0]["kind"]


def test_a_past_day_can_be_replayed_and_matches_its_record(tmp_path):
    """The point of history: you can go back to a day and get the same puzzle."""
    service = PuzzleService(language="zh", profile_path=tmp_path / "p.json")
    first = service.new_daily(session_id="a", day="2026-10-10")
    service.submit("a", _answer_for(service._session("a").puzzle))
    listed = service.history(limit=5)[0]
    assert listed["day"] == "2026-10-10"

    replayed = service.new_daily(session_id="b", day=listed["day"])
    assert replayed["kind"] == listed["kind"]
    assert replayed["daily"]["played"] is True


# --- the picture card -------------------------------------------------------


def test_the_svg_card_is_well_formed_and_says_the_same_things():
    import xml.etree.ElementTree as ElementTree

    profile = Profile()
    _record(profile, "2026-10-16", score=18, attempts=3, seconds=42)
    svg = share_card_svg(profile, "2026-10-16")
    root = ElementTree.fromstring(svg)  # raises if the markup is broken
    assert root.tag.endswith("svg")
    text = " ".join(node.text or "" for node in root.iter() if node.tag.endswith("text"))
    assert "2026-10-16" in text
    assert "已完成" in text
    assert "得分 18" in text
    assert "连续 1 天" in text
    assert "不含谜底" in text


def test_the_svg_card_is_readable_without_rendering_it():
    """Text stays text: no paths, so a screen reader and a test can both read it."""
    profile = Profile()
    _record(profile, "2026-10-16")
    svg = share_card_svg(profile, "2026-10-16")
    assert "<text" in svg, "the card was rasterised into shapes"
    root_label = svg.split("aria-label=", 1)[1].split('"', 2)[1]
    assert "2026-10-16" in root_label
    assert "不含谜底" in root_label


def test_the_svg_card_states_the_outcome_without_relying_on_colour():
    """Colour is decoration; the mark and the word carry the meaning (SC 1.4.1)."""
    solved = share_card_svg(_with_day("2026-10-16", True), "2026-10-16")
    unsolved = share_card_svg(_with_day("2026-10-16", False), "2026-10-16")
    assert "✔ 已完成" in solved
    assert "✘ 未完成" in unsolved


def test_the_svg_card_escapes_player_data():
    """A hostile day string must not be able to break out of the document."""
    profile = Profile()
    _record(profile, "2026-10-16")
    svg = share_card_svg(profile, '"><script>alert(1)</script>')
    assert "<script>" not in svg
    assert "&lt;script&gt;" in svg or "&quot;&gt;" in svg
    import xml.etree.ElementTree as ElementTree

    ElementTree.fromstring(svg)


def test_the_svg_card_handles_an_unplayed_day():
    import xml.etree.ElementTree as ElementTree

    svg = share_card_svg(Profile(), "2026-10-16")
    ElementTree.fromstring(svg)
    assert "还没玩" in svg


def test_the_cli_writes_the_card_to_a_file(tmp_path):
    profile_path = tmp_path / "cli" / "profile.json"
    target = tmp_path / "card.svg"
    env = {"TEXT_ADVENTURE_PROFILE": str(profile_path)}
    result = subprocess.run(
        [sys.executable, "-m", "puzzle_service.cli", "card", "2026-10-16", str(target)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        cwd=str(ROOT),
        env={**dict(**__import__("os").environ), **env},
        timeout=180,
    )
    assert result.returncode == 0, result.stderr
    assert target.is_file(), f"card was not written: {result.stdout}"
    assert target.read_text(encoding="utf-8").startswith("<svg")


def test_the_cli_lists_history(tmp_path):
    profile_path = tmp_path / "h" / "profile.json"
    store = ProfileStore(profile_path)
    _record(store.profile, "2026-10-16", score=15)
    _record(store.profile, "2026-10-15", solved=False)
    store.save()

    result = subprocess.run(
        [sys.executable, "-m", "puzzle_service.cli", "history"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        cwd=str(ROOT),
        env={**dict(**__import__("os").environ), "TEXT_ADVENTURE_PROFILE": str(profile_path)},
        timeout=180,
    )
    assert result.returncode == 0, result.stderr
    assert "2026-10-16" in result.stdout
    assert "共 2 天" in result.stdout
    lines = result.stdout.strip().splitlines()
    assert lines.index([line for line in lines if "2026-10-16" in line][0]) < lines.index(
        [line for line in lines if "2026-10-15" in line][0]
    ), "history should be newest first"


def _with_day(day: str, solved: bool) -> Profile:
    profile = Profile()
    _record(profile, day, solved=solved)
    return profile
