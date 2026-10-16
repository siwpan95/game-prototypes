"""Shared test fixtures.

The suite is headless: it never builds a window and never imports pygame, so it
runs on a build machine. Build selection is passed explicitly to
``bootstrap_import_path`` because both builds export a top-level
``gameplay_pool`` and the first one on ``sys.path`` would shadow the other.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from shared.paths import bootstrap_import_path  # noqa: E402


@pytest.fixture(scope="session")
def zh_root() -> Path:
    root = bootstrap_import_path("zh")
    assert root is not None, "project root not found"
    return root


@pytest.fixture(scope="session")
def service(zh_root):
    from puzzle_service.service import PuzzleService

    return PuzzleService(language="zh")


@pytest.fixture(scope="session")
def kinds(service):
    return service.list_kinds()


def correct_answer(puzzle) -> object:
    """Solve *puzzle* and return whatever its ``check_answer`` expects.

    Three shapes exist (all measured against the build):

    * an answer-bearing key (``answer`` / ``word`` / ``target``) — the literal answer;
    * a grid compared against a solution (crossword, sudoku, nonogram) — the
      player grid is filled in and the answer argument is ignored;
    * a path/state compared against the goal (word ladder) — the goal is placed
      at the end of the player's path.

    Kinds whose completion is a *mutated* state (``answered_by == "action"``) are
    driven by the service tests instead; this helper raises for them so a new
    kind cannot quietly pass without a real solve path.
    """
    data = getattr(puzzle, "data", {}) or {}
    for key in ("answer", "word", "target"):
        if key in data and not isinstance(data.get(key), (list, dict)):
            return data[key]

    solution = data.get("solution")
    player = data.get("player_grid")
    if isinstance(solution, list) and isinstance(player, list):
        for row_index, row in enumerate(solution):
            for col_index, value in enumerate(row):
                player[row_index][col_index] = value
        return None

    grid = data.get("grid")
    if isinstance(grid, list) and isinstance(player, list):
        for row_index, row in enumerate(grid):
            for col_index, value in enumerate(row):
                # None marks a blocked crossword cell; keep it blocked.
                player[row_index][col_index] = value
        return None

    path = data.get("path")
    player_path = data.get("player_path")
    if isinstance(path, list) and isinstance(player_path, list):
        player_path[:] = list(path)
        return None

    raise AssertionError(
        f"{type(puzzle).__name__} has no known solve path: {sorted(data)}"
    )


def wrong_answer(puzzle) -> object:
    """A type-correct answer that cannot be right."""
    data = getattr(puzzle, "data", {}) or {}
    answer = data.get("answer", data.get("target", data.get("word")))
    if isinstance(answer, bool):
        return not answer
    if isinstance(answer, int):
        return 2**31 - 1
    if isinstance(answer, str):
        return answer + "\u0000__wrong__"
    return "__definitely_wrong__"
