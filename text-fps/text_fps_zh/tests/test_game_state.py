"""GameState basic state-machine unit tests.

Covers phase/turn advancement, add_log not crashing (incl. non-ASCII / empty
strings), and log truncation at ``max_log_lines``.

Run with pytest (CI):  ``pytest tests/test_game_state.py``
Run without pytest:    ``python tests/run_manual.py``

No pygame / main / ui imports -- GameState is pure Python.
"""
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from core.constants import (
    PHASE_PLAYER_TURN,
    PHASE_ENEMY_TURN,
    PHASE_GAME_OVER,
)
from core.game_state import GameState


def test_gamestate_initial_phase_and_turn():
    gs = GameState()
    assert gs.phase == PHASE_PLAYER_TURN
    assert gs.turn == 0
    assert gs.dirty is True


def test_gamestate_advance_turn():
    gs = GameState()
    gs.turn = 0
    gs.advance_turn()
    assert gs.turn == 1
    gs.advance_turn()
    assert gs.turn == 2
    assert gs.dirty is True


def test_gamestate_phase_transition():
    gs = GameState()
    gs.phase = PHASE_ENEMY_TURN
    assert gs.phase == PHASE_ENEMY_TURN
    gs.phase = PHASE_GAME_OVER
    assert gs.phase == PHASE_GAME_OVER


def test_gamestate_add_log_no_crash():
    gs = GameState()
    gs.add_log("hello world")
    gs.add_log("")                       # empty string must not crash
    gs.add_log("中文日志 should not crash")
    assert len(gs.log) == 3
    assert gs.log[0] == "hello world"
    assert gs.log[-1] == "中文日志 should not crash"
    assert gs.dirty is True


def test_gamestate_log_truncation():
    gs = GameState()
    gs.max_log_lines = 5
    for i in range(12):
        gs.add_log(f"line{i}")
    # Only the most recent max_log_lines entries are kept.
    assert len(gs.log) == 5
    assert gs.log[0] == "line7"   # last 5 of 12 => line7..line11
    assert gs.log[-1] == "line11"
