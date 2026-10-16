"""View-model contract: every kind renders, and no view leaks the solution."""

from __future__ import annotations

import json

import pytest

from puzzle_service import views
from puzzle_service.registry import get

MUTATING_NODE_TYPES = {"grid", "sequence", "keyboard", "colors", "board"}


def _view_for(service, kind_name: str) -> dict:
    kind = get(kind_name)
    puzzle = kind.create(difficulty="easy")
    return views.build(kind, puzzle)


def test_every_registered_kind_has_a_view_builder(service, kinds):
    missing = [k["name"] for k in kinds if k["name"] not in views.registered()]
    assert not missing, f"kinds without a dedicated view builder: {missing}"


def test_every_kind_produces_a_json_serialisable_view(service, kinds):
    for kind in kinds:
        view = _view_for(service, kind["name"])
        payload = json.dumps(view)  # raises on sets, classes, tuples-as-keys
        assert payload
        assert view["nodes"], f"{kind['name']}: view has no nodes"
        assert view["actions"], f"{kind['name']}: view declares no actions"
        assert "submit" in view["actions"] and "hint" in view["actions"]


def test_interaction_types_match_the_view(service, kinds):
    for kind in kinds:
        view = _view_for(service, kind["name"])
        node_types = {node["type"] for node in view["nodes"]}
        assert "text" in node_types, f"{kind['name']}: no prompt text in view"
        if kind["interaction"] in {"grid", "sequence", "keyboard", "colors", "board"}:
            assert node_types & MUTATING_NODE_TYPES, (
                f"{kind['name']}: interaction {kind['interaction']} has no interactive node"
            )


def test_answer_fields_declare_their_type(service, kinds):
    for kind in kinds:
        view = _view_for(service, kind["name"])
        for node in view["nodes"]:
            if node["type"] == "field":
                assert node["answer_type"] == kind["answer_type"], kind["name"]


def test_grid_views_send_cells_that_carry_their_own_coordinates(service):
    for kind_name in ("crossword", "sudoku", "minesweeper", "nonogram", "memory"):
        view = _view_for(service, kind_name)
        grid = next(node for node in view["nodes"] if node["type"] == "grid")
        assert grid["action"], f"{kind_name}: interactive grid without an action"
        for row_index, row in enumerate(grid["cells"]):
            for col_index, cell in enumerate(row):
                assert cell["row"] == row_index and cell["col"] == col_index, kind_name


def test_views_never_contain_the_solution(service):
    """A client must not be able to read the answer out of its own payload."""
    sudoku = _view_for(service, "sudoku")
    solution = get("sudoku").create(difficulty="easy").data["solution"]
    payload = json.dumps(sudoku)
    assert json.dumps(solution) not in payload, "sudoku view leaked its solution"

    crossword = get("crossword").create(difficulty="easy")
    words = [entry["word"] for entry in crossword.data["words"]]
    crossword_payload = json.dumps(_view_for(service, "crossword"))
    leaked = [word for word in words if word and word in crossword_payload]
    assert not leaked, f"crossword view leaked words: {leaked}"


def test_hangman_keyboard_reports_letter_state(service):
    kind = get("hangman")
    puzzle = kind.create(difficulty="easy")
    view = views.build(kind, puzzle)
    keyboard = next(node for node in view["nodes"] if node["type"] == "keyboard")
    assert len(keyboard["keys"]) == 26
    assert {key["state"] for key in keyboard["keys"]} == {"unused"}

    puzzle.guess_letter("a")
    view = views.build(kind, puzzle)
    keyboard = next(node for node in view["nodes"] if node["type"] == "keyboard")
    states = {key["letter"].lower(): key["state"] for key in keyboard["keys"]}
    assert states["a"] in {"correct", "wrong"}
    assert sum(1 for state in states.values() if state != "unused") == 1


def test_unknown_interaction_fails_loudly(service):
    from puzzle_service.registry import PuzzleKind

    class Weird:
        puzzle_type = "content"

    kind = PuzzleKind(name="weird", cls=Weird, title="Weird", interaction="telepathy")
    with pytest.raises(NotImplementedError):
        views.build(kind, Weird())
