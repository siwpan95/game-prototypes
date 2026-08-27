# tests/test_panel_rivals.py
# 对手视图（E8）的无头单测：渲染并绑定 do_rival_tick / do_add_rival。
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import _panel_harness as H
from gui.panels.rivals_view import draw_rivals_view
from gui.state import GUIState
from sequences import make_sequence
from rivals import RivalSystem


def _draw(state):
    canvas = H.FakeCanvas(width=580)
    cb = H.make_callbacks(*H.PANEL_CALLBACK_KEYS)
    draw_rivals_view(canvas, state, cb)
    return canvas, cb


@H.test("panel_rivals_renders_and_binds")
def t():
    """对手视图应渲染并正确绑定 do_rival_tick / do_add_rival。"""
    state = H.make_state(character=make_sequence("error", 9))
    state.rival_system = RivalSystem(seed=1)
    state.rival_system.add_rival("fool")
    canvas, cb = _draw(state)
    fired = H.fired_callback_names(canvas, cb)
    H.expect("do_rival_tick" in fired, "应绑定 do_rival_tick")
    H.expect("do_add_rival" in fired, "应绑定 do_add_rival")


@H.test("panel_rivals_empty_state")
def t():
    """无对手时应提示添加对手。"""
    state = H.make_state(character=make_sequence("error", 9))
    state.rival_system = None
    canvas, cb = _draw(state)
    texts = [k.get("text", "") for typ, k in canvas.items if typ == "text"]
    H.expect(any("暂无对手" in t for t in texts), "空状态应提示添加对手")
