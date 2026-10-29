"""Service contract: sessions, scoring, input normalisation, and kind actions."""

from __future__ import annotations

import pytest

from conftest import correct_answer, wrong_answer
from puzzle_service.registry import get
from puzzle_service.service import InvalidAction, InvalidAnswer, PuzzleService

SCORE_WITH_NO_TIME_AND_NO_STREAK = 15  # base 10 + time bonus 5 + streak bonus 0


@pytest.fixture()
def fresh():
    return PuzzleService(language="zh")


def test_a_session_starts_empty(fresh):
    snapshot = fresh.snapshot("s1")
    assert snapshot["view"] is None
    assert snapshot["score"] == 0 and snapshot["streak"] == 0
    assert snapshot["puzzle_id"] is None


def test_starting_a_puzzle_returns_a_view(fresh):
    snapshot = fresh.new_puzzle("s1", kind="math", difficulty="easy")
    assert snapshot["kind"] == "math"
    assert snapshot["puzzle_id"]
    assert snapshot["view"]["kind"] == "math"
    assert snapshot["view"]["nodes"]


def test_choosing_a_kind_by_name_and_when_omitted(fresh):
    """A named kind is honoured; without a name the service picks a valid one.

    The service deliberately samples rather than rotating through its kinds (a
    rotation makes the next kind predictable). So this asserts variety over many
    draws instead of demanding every kind appear in exactly N draws — which is what
    the previous rotation-based version could assert, and why it broke when the
    selection became random.
    """
    named = fresh.new_puzzle("s1", kind="sudoku")
    assert named["kind"] == "sudoku"

    kinds = fresh.list_kinds()
    picks = [fresh.new_puzzle("s1")["kind"] for _ in range(len(kinds) * 4)]
    assert set(picks) <= {item["name"] for item in kinds}
    assert len(set(picks)) >= max(2, len(kinds) // 2), (
        f"selection looks stuck: only {sorted(set(picks))} in {len(picks)} draws"
    )


def test_correct_answer_scores_and_extends_the_streak(fresh):
    fresh.new_puzzle("s1", kind="math", difficulty="easy")
    puzzle = fresh.snapshot("s1")["view"]
    assert puzzle["interaction"] == "text"

    result = fresh.submit("s1", correct_answer(fresh._session("s1").puzzle))
    assert result["correct"] is True
    assert result["score"] == SCORE_WITH_NO_TIME_AND_NO_STREAK
    assert result["streak"] == 1 and result["solved"] == 1
    assert result["points"] == result["time_bonus"] + result["streak_bonus"] + 10


def test_wrong_answer_keeps_the_score_and_resets_the_streak(fresh):
    fresh.new_puzzle("s1", kind="math")
    fresh.submit("s1", correct_answer(fresh._session("s1").puzzle))
    assert fresh.snapshot("s1")["streak"] == 1

    fresh.new_puzzle("s1", kind="math")
    result = fresh.submit("s1", wrong_answer(fresh._session("s1").puzzle))
    assert result["correct"] is False
    assert result["points"] == 0
    assert result["streak"] == 0
    # score is kept: only the streak resets
    assert result["score"] == SCORE_WITH_NO_TIME_AND_NO_STREAK
    assert result["solved"] == 1


def test_a_numeric_answer_may_arrive_as_a_string(fresh):
    """The web client sends form values as text; int kinds must still work."""
    fresh.new_puzzle("s1", kind="math")
    answer = correct_answer(fresh._session("s1").puzzle)
    result = fresh.submit("s1", str(answer))
    assert result["correct"] is True


def test_a_non_numeric_answer_is_a_structured_error_not_a_traceback(fresh):
    fresh.new_puzzle("s1", kind="math")
    with pytest.raises(InvalidAnswer) as excinfo:
        fresh.submit("s1", "not a number")
    assert "integer" in str(excinfo.value)
    # and nothing was scored
    assert fresh.snapshot("s1")["score"] == 0


def test_submitting_without_a_puzzle_is_refused(fresh):
    with pytest.raises(InvalidAction):
        fresh.submit("s1", 1)


def test_actions_are_restricted_to_the_kind_that_declares_them(fresh):
    fresh.new_puzzle("s1", kind="math")
    with pytest.raises(InvalidAction) as excinfo:
        fresh.perform("s1", "reveal", row=0, col=0)
    assert "does not accept action" in str(excinfo.value)


def test_acting_without_a_puzzle_is_refused(fresh):
    with pytest.raises(InvalidAction):
        fresh.perform("s1", "reveal", row=0, col=0)


def test_minesweeper_reveal_changes_the_snapshot(fresh):
    snapshot = fresh.new_puzzle("s1", kind="minesweeper")
    grid = next(node for node in snapshot["view"]["nodes"] if node["type"] == "grid")
    assert grid["cells"], "minesweeper grid is empty"
    assert not any(cell["revealed"] for row in grid["cells"] for cell in row)

    after = fresh.perform("s1", "reveal", row=0, col=0)
    reopened = next(node for node in after["view"]["nodes"] if node["type"] == "grid")
    assert reopened["cells"][0][0]["revealed"] is True, "reveal did not mark the cell"


def test_sudoku_set_cell_changes_the_snapshot(fresh):
    fresh.new_puzzle("s1", kind="sudoku")
    # find an empty cell in the player grid
    target = None
    for row in fresh.snapshot("s1")["view"]["nodes"]:
        if row["type"] == "grid":
            for line in row["cells"]:
                for cell in line:
                    if not cell.get("fixed"):
                        target = (cell["row"], cell["col"])
                        break
                if target:
                    break
    assert target, "sudoku puzzle had no editable cell"
    row_index, col_index = target
    after = fresh.perform("s1", "set_cell", row=row_index, col=col_index, num=1)
    grid = next(node for node in after["view"]["nodes"] if node["type"] == "grid")
    assert grid["cells"][row_index][col_index]["value"] == 1


def test_string_coordinates_from_the_wire_are_coerced(fresh):
    fresh.new_puzzle("s1", kind="nonogram")
    after = fresh.perform("s1", "toggle_cell", row="1", col="2")
    grid = next(node for node in after["view"]["nodes"] if node["type"] == "grid")
    assert grid["cells"][1][2]["value"] == 1


def test_action_with_bad_parameters_is_refused(fresh):
    fresh.new_puzzle("s1", kind="minesweeper")
    with pytest.raises(InvalidAction):
        fresh.perform("s1", "reveal", bogus="x")


def test_hint_is_available_and_non_empty(fresh):
    fresh.new_puzzle("s1", kind="math")
    assert fresh.hint("s1").strip()


def test_reset_clears_the_session(fresh):
    fresh.new_puzzle("s1", kind="math")
    fresh.submit("s1", correct_answer(fresh._session("s1").puzzle))
    cleared = fresh.reset("s1")
    assert cleared["score"] == 0 and cleared["streak"] == 0
    assert cleared["view"] is None and cleared["puzzle_id"] is None


def test_sessions_are_isolated(fresh):
    fresh.new_puzzle("a", kind="math")
    fresh.new_puzzle("b", kind="sudoku")
    assert fresh.snapshot("a")["kind"] == "math"
    assert fresh.snapshot("b")["kind"] == "sudoku"
    fresh.submit("a", correct_answer(fresh._session("a").puzzle))
    assert fresh.snapshot("b")["score"] == 0


def test_every_kind_can_be_solved_through_the_service(fresh, kinds):
    """End-to-end contract for all kinds: create → view → solve.

    Kinds answered by acting (``answered_by == "action"``) are driven to their
    winning state and then asked to report it; kinds answered by checking get
    their own expected answer.
    """
    failures: list[str] = []
    for kind in kinds:
        name = kind["name"]
        try:
            fresh.reset("s")
            fresh.new_puzzle("s", kind=name, difficulty="easy")
            puzzle = fresh._session("s").puzzle
            if kind["answered_by"] == "action":
                _drive_to_win(name, puzzle)
                result = fresh.submit("s", None)
            else:
                result = fresh.submit("s", correct_answer(puzzle))
            if not result["correct"]:
                failures.append(f"{name}: correct solve rejected")
        except Exception as exc:  # noqa: BLE001 - report, don't abort the sweep
            failures.append(f"{name}: {type(exc).__name__}: {exc}")
    assert not failures, failures


def _drive_to_win(name: str, puzzle) -> None:
    """Put an action-driven kind into its finished state (measured 2026-10-16)."""
    if name == "2048":
        puzzle.data["board"][0][0] = puzzle.data["target"]
        puzzle._check_win()
    elif name == "anagram":
        puzzle.data["player_letters"] = list(puzzle.data["word"])
    elif name == "memory":
        pairs = puzzle.data["pairs"]
        puzzle.data["pairs_found"] = pairs
        for row in puzzle.data["matched"]:
            for index in range(len(row)):
                row[index] = True
    elif name == "color_sequence":
        puzzle.start_input_phase()
        for color in list(puzzle.data["sequence"]):
            puzzle.press_color(color)
    elif name == "minesweeper":
        # reveal() is the real path: first click is moved off a mine, empty
        # regions cascade, and win is set once every safe cell is open.
        for row in range(puzzle.data["rows"]):
            for col in range(puzzle.data["cols"]):
                if (row, col) not in puzzle.data["mine_positions"]:
                    puzzle.reveal(row, col)
    elif name == "hangman":
        for letter in sorted(set(puzzle.data["word"])):
            puzzle.guess_letter(letter)
    else:
        raise AssertionError(f"{name} is not action-driven")


def test_2048_move_action_reaches_the_puzzle(fresh):
    """A move that can change the board must come back changed.

    The board is random, so a *fixed* direction can be a no-op (all tiles already
    against that wall) and a single-attempt assertion would flake. Trying each
    direction and requiring at least one change tests the same contract without
    assuming a particular starting board.
    """
    fresh.new_puzzle("s1", kind="2048")
    board_before = _board(fresh.snapshot("s1"))

    for direction in ("left", "up", "right", "down"):
        after = fresh.perform("s1", "move", direction=direction)
        if _board(after) != board_before:
            return
    raise AssertionError(
        "no direction changed the board, so the action is being dropped: "
        f"{board_before}"
    )


def _board(snapshot) -> list:
    node = next(n for n in snapshot["view"]["nodes"] if n["type"] == "board")
    return [[cell["value"] for cell in row] for row in node["cells"]]


def test_action_driven_kinds_are_scored_by_acting_not_by_answering(fresh):
    """2048 is solved by its board, not by an answer: acting must score it."""
    fresh.new_puzzle("s1", kind="2048")
    session = fresh._session("s1")
    puzzle = session.puzzle
    target = puzzle.data["target"]
    puzzle.data["board"][0][0] = target
    puzzle._check_win()
    before = session.score

    snapshot = fresh.perform("s1", "move", direction="left")
    assert snapshot["solved"] is True
    assert session.score > before, "completing the board did not award points"
    assert session.auto_scored and session.auto_scored["correct"] is True

    # acting again must not score the same puzzle twice
    scored_once = session.score
    fresh.perform("s1", "move", direction="left")
    assert session.score == scored_once


def test_anagram_is_solved_by_arranging_letters(fresh):
    fresh.new_puzzle("s1", kind="anagram")
    session = fresh._session("s1")
    session.puzzle.data["player_letters"] = list(session.puzzle.data["word"])
    result = fresh.submit("s1", None)
    assert result["correct"] is True
    assert result["score"] == SCORE_WITH_NO_TIME_AND_NO_STREAK


def test_answered_by_is_declared_for_every_kind(kinds):
    """Kinds whose ``check_answer`` reads state instead of its argument."""
    by_action = {kind["name"] for kind in kinds if kind["answered_by"] == "action"}
    assert by_action == {
        "2048",
        "anagram",
        "memory",
        "minesweeper",
        "hangman",
        "color_sequence",
    }
    for kind in kinds:
        assert kind["answered_by"] in {"check", "action"}, kind


def test_manifest_covers_every_kind_the_build_exports(fresh, kinds):
    """A kind with no manifest entry would render with fallback metadata."""
    from puzzle_service.registry import _MANIFEST

    unknown = [kind["name"] for kind in kinds if kind["name"] not in _MANIFEST]
    assert not unknown, f"kinds missing from the manifest: {unknown}"


def test_kind_lookup_and_creation_do_not_share_state(fresh):
    kind = get("sudoku")
    first = kind.create(difficulty="easy")
    second = kind.create(difficulty="easy")
    assert first is not second
    assert first.data is not second.data
