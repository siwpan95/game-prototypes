# tests/test_panel_brewing.py
# 魔药材料面板（E1）的无头单测：渲染 + 绑定 do_gather
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import _panel_harness as H
from gui.panels.brewing_panel import draw_brewing_panel
from gui.panels.action_panel import draw_action_panel
from sequences import make_sequence


@H.test("panel_brewing_renders_and_binds_gather")
def t():
    """未集齐材料时：应渲染配方并绑定『搜寻材料』按钮（do_gather）"""
    ch = make_sequence("error", 9)
    state = H.make_state(character=ch)
    cb = H.make_callbacks("do_gather")
    c = H.FakeCanvas()
    draw_brewing_panel(c, 10, state, cb)
    H.expect(len(c.items) > 0, "brewing panel 应渲染内容")
    fired = H.fired_callback_names(c, cb)
    H.expect("do_gather" in fired, "brewing panel 应绑定 do_gather")


@H.test("panel_brewing_shows_ready_when_materials_present")
def t():
    """材料齐备时：不显示搜寻按钮，且状态为已就绪"""
    ch = make_sequence("error", 9)
    state = H.make_state(character=ch)
    from pathways_data import get_potion_formula
    formula = get_potion_formula(ch.PATHWAY_KEY, 8)
    for m in [formula["main"]] + formula["supplementary"]:
        state.inventory.add(m, 1)
    cb = H.make_callbacks("do_gather")
    c = H.FakeCanvas()
    draw_brewing_panel(c, 10, state, cb)
    fired = H.fired_callback_names(c, cb)
    H.expect("do_gather" not in fired, "材料齐备后不应再绑定搜寻按钮")


@H.test("panel_brewing_integrated_in_action_panel")
def t():
    """action_panel 应内嵌 brewing 段落（含 do_gather 绑定）"""
    ch = make_sequence("error", 9)
    state = H.make_state(character=ch)
    cb = H.make_callbacks("do_action", "do_ascend", "do_switch",
                          "do_random_event", "do_gather")
    c = H.FakeCanvas()
    draw_action_panel(c, state, cb)
    fired = H.fired_callback_names(c, cb)
    H.expect("do_gather" in fired, "action_panel 应内嵌并绑定 do_gather")


@H.test("panel_brewing_god_has_no_potion")
def t():
    """序列0真神：不应显示魔药配方，应引导去集齐权柄"""
    ch = make_sequence("error", 0)
    state = H.make_state(character=ch)
    cb = H.make_callbacks("do_gather")
    c = H.FakeCanvas()
    draw_brewing_panel(c, 10, state, cb)
    fired = H.fired_callback_names(c, cb)
    H.expect("do_gather" not in fired, "真神无需魔药，不应绑定搜寻按钮")
