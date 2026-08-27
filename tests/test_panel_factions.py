# tests/test_panel_factions.py
# 阵营社交视图（E7）的无头单测：渲染三大阵营与社交动作，并绑定 do_faction_action。
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import _panel_harness as H
from gui.panels.factions_view import draw_factions_view
from gui.state import GUIState
from sequences import make_sequence
from factions import FACTIONS, ACTIONS


def _draw(state):
    canvas = H.FakeCanvas(width=580)
    cb = H.make_callbacks(*H.PANEL_CALLBACK_KEYS)
    draw_factions_view(canvas, state, cb)
    return canvas, cb


@H.test("panel_factions_renders_and_binds")
def t():
    """阵营视图应渲染所有阵营与动作，并正确绑定 do_faction_action(faction, action)"""
    state = H.make_state(character=make_sequence("error", 9))
    state.factions = {}
    canvas, cb = _draw(state)
    fired = H.fired_callback_names(canvas, cb)
    H.expect("do_faction_action" in fired, "应绑定 do_faction_action")

    calls = cb["do_faction_action"].calls
    H.expect(len(calls) > 0, "do_faction_action 应至少被绑定一次")
    # 每个绑定应传入 (faction_key, action_key) 二元组
    pairs = [(c[0][0], c[0][1]) for c in calls if len(c[0]) >= 2]
    H.expect(len(pairs) == len(calls), "每次绑定都应带 faction+action 参数")
    # 应覆盖至少一个真实阵营与动作
    valid = [(fk, ak) for fk, ak in pairs if fk in FACTIONS and ak in ACTIONS]
    H.expect(len(valid) > 0, "应绑定合法的 阵营+动作 组合")


@H.test("panel_factions_shows_reputation")
def t():
    """阵营视图应显示当前声望数值"""
    state = H.make_state(character=make_sequence("error", 9))
    state.factions = {"tarot": 7, "church": 3, "secret": 0}
    canvas, cb = _draw(state)
    texts = [k.get("text", "") for typ, k in canvas.items if typ == "text"]
    H.expect(any("声望 7" in t for t in texts), "应显示 tarot 声望 7")
    H.expect(any("声望 3" in t for t in texts), "应显示 church 声望 3")


if __name__ == "__main__":
    H.run_all()
