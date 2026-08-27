"""Unit tests for the level editor undo stack (incremental PRD V2, U1-U5).

Covers snapshot pushing for effective edits only (U1), multi-step full-state
restore (U2), the stack depth cap (U3), stack clearing on wholesale loads
(U4) and the silent empty-stack no-op (U5).
"""
import pytest

from doom_game.config import EDITOR_UNDO_DEPTH
from doom_game.core.types import TextureType
from doom_game.editor.level_editor import BRUSHES, LevelEditor
from doom_game.world.level_io import LevelData

BRUSH_BRICK = 0
BRUSH_PLAYER = 4
BRUSH_ENEMY = 5
BRUSH_HEALTH = 6
BRUSH_ERASER = 8


def blank_level_data(width: int = 10, height: int = 10) -> LevelData:
    return LevelData(
        version=1,
        width=width,
        height=height,
        cells=[[0] * width for _ in range(height)],
        player_start={"x": 1.5, "y": 1.5, "angle": 0.0},
        enemies=[],
        pickups=[],
    )


@pytest.fixture
def editor():
    """An editor on a blank 10x10 grid with an empty undo stack."""
    ed = LevelEditor(640, 480)
    ed.load_level_data(blank_level_data())
    assert ed._undo_stack == []
    return ed


def _place(ed, brush_index, gx, gy):
    ed.brush_index = brush_index
    ed._apply_brush(gx, gy)


# --------------------------------------------------------------------------- #
# U1: effective edits push exactly one snapshot; no-ops push nothing
# --------------------------------------------------------------------------- #
class TestUndoStackPushes:
    def test_n_effective_edits_push_n_snapshots(self, editor):
        n = 5
        for i in range(n):
            _place(editor, BRUSH_BRICK, 1 + i, 1)
        assert len(editor._undo_stack) == n

    def test_repeated_same_wall_is_a_no_op(self, editor):
        _place(editor, BRUSH_BRICK, 2, 2)
        _place(editor, BRUSH_BRICK, 2, 2)            # same brush, same cell
        assert len(editor._undo_stack) == 1

    def test_erasing_an_empty_cell_is_a_no_op(self, editor):
        editor._erase(5, 5)                          # nothing there
        assert editor._undo_stack == []

    def test_eraser_brush_on_empty_cell_is_a_no_op(self, editor):
        _place(editor, BRUSH_ERASER, 5, 5)
        assert editor._undo_stack == []

    def test_effective_erase_pushes_one_snapshot(self, editor):
        _place(editor, BRUSH_BRICK, 3, 3)
        editor._erase(3, 3)
        assert len(editor._undo_stack) == 2


# --------------------------------------------------------------------------- #
# U2: multi-step undo restores the full editor state
# --------------------------------------------------------------------------- #
class TestMultiStepUndo:
    def test_three_undos_restore_the_initial_state(self, editor):
        initial = editor._snapshot()

        _place(editor, BRUSH_BRICK, 2, 2)            # 1. place a wall
        _place(editor, BRUSH_ENEMY, 3, 3)            # 2. place an enemy
        editor._erase(2, 2)                          # 3. erase the wall
        assert len(editor._undo_stack) == 3

        for _ in range(3):
            assert editor.undo() is True

        assert editor._snapshot() == initial         # cells + start +
        assert editor.enemies == []                  # enemies + pickups
        assert editor._undo_stack == []

    def test_undo_restores_wall_cell(self, editor):
        _place(editor, BRUSH_BRICK, 4, 4)
        assert editor.world_map.cells[4][4] == TextureType.BRICK
        assert editor.undo() is True
        assert editor.world_map.cells[4][4] is None

    def test_undo_restores_player_start(self, editor):
        before = dict(editor.player_start)
        _place(editor, BRUSH_PLAYER, 6, 6)
        assert editor.player_start == {"x": 6.5, "y": 6.5, "angle": 0.0}
        assert editor.undo() is True
        assert editor.player_start == before

    def test_undo_removes_placed_pickup(self, editor):
        _place(editor, BRUSH_HEALTH, 7, 7)
        assert len(editor.pickups) == 1
        assert editor.undo() is True
        assert editor.pickups == []


# --------------------------------------------------------------------------- #
# U3: depth cap - oldest snapshots are dropped, rest stays undoable
# --------------------------------------------------------------------------- #
class TestUndoDepthCap:
    def test_stack_caps_and_undoes_back_to_edit_ten(self, editor):
        total = EDITOR_UNDO_DEPTH + 10
        state_after_ten = None
        for i in range(total):
            _place(editor, BRUSH_BRICK, 1 + i % 8, 1 + i // 8)
            if i == 9:                               # after the 10th edit
                state_after_ten = editor._snapshot()

        assert len(editor._undo_stack) == EDITOR_UNDO_DEPTH

        undone = 0
        while editor.undo():
            undone += 1
        assert undone == EDITOR_UNDO_DEPTH
        assert editor._snapshot() == state_after_ten


# --------------------------------------------------------------------------- #
# U4: wholesale loads clear the stack
# --------------------------------------------------------------------------- #
class TestLoadClearsStack:
    def test_load_level_data_empties_the_stack(self, editor):
        for i in range(4):
            _place(editor, BRUSH_BRICK, 1 + i, 2)
        assert len(editor._undo_stack) == 4

        editor.load_level_data(blank_level_data())

        assert editor._undo_stack == []
        state = editor._snapshot()
        assert editor.undo() is False                # no cross-file undo
        assert editor._snapshot() == state           # state untouched


# --------------------------------------------------------------------------- #
# U5: empty-stack undo is a silent no-op
# --------------------------------------------------------------------------- #
class TestEmptyStackUndo:
    def test_undo_on_empty_stack_returns_false(self, editor):
        state = editor._snapshot()
        assert editor.undo() is False                # never raises
        assert editor._snapshot() == state

    def test_brush_palette_has_expected_layout(self):
        # Guard the indices this test module relies on.
        assert BRUSHES[BRUSH_BRICK][0] == "Brick"
        assert BRUSHES[BRUSH_PLAYER][0] == "Player"
        assert BRUSHES[BRUSH_ENEMY][0] == "Enemy"
        assert BRUSHES[BRUSH_HEALTH][0] == "Health"
        assert BRUSHES[BRUSH_ERASER][0] == "Eraser"
