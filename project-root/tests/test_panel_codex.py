# tests/test_panel_codex.py
# 成就 / 图鉴 / 结局视图（E9）的无头单测：渲染成就 / 图鉴 / 结局，并反映解锁状态。
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import _panel_harness as H
from gui.panels.codex_view import draw_codex_view
from gui.state import GUIState
from sequences import make_sequence
from achievements import evaluate_achievements


def _draw(state):
    canvas = H.FakeCanvas(width=580)
    cb = H.make_callbacks(*H.PANEL_CALLBACK_KEYS)
    draw_codex_view(canvas, state, cb)
    return canvas, cb


@H.test("panel_codex_renders")
def t():
    """图鉴视图应渲染成就 / 图鉴 / 结局三段。"""
    state = H.make_state(character=make_sequence("error", 9))
    canvas, _ = _draw(state)
    texts = [k.get("text", "") for typ, k in canvas.items if typ == "text"]
    H.expect(any("成就" in t for t in texts), "应显示成就区")
    H.expect(any("图鉴" in t for t in texts), "应显示图鉴区")
    H.expect(any("命运走向" in t for t in texts), "应显示结局区")


@H.test("panel_codex_shows_unlocked")
def t():
    """已解锁成就应在视图中显示其名。"""
    state = H.make_state(character=make_sequence("error", 9))
    state.character.perform_action("偷窃")
    evaluate_achievements(state)
    canvas, _ = _draw(state)
    texts = [k.get("text", "") for typ, k in canvas.items if typ == "text"]
    H.expect(any("第一步" in t for t in texts), "应显示已解锁的「第一步」")
