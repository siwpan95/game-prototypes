import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# tests/test_panel_pathways.py
# 途径列表 / 全景视图面板的独立单元测试（无头）。
from _panel_harness import (test, expect, run_all, FakeCanvas, make_state,
                            char_seq9, char_seq0, make_callbacks,
                            fired_callback_names, PANEL_CALLBACK_KEYS)
import gui.panels.pathways_view as pv
from pathways_data import PATHWAYS


@test("panel_pathway_list_no_character")
def t_list_no_char():
    canvas = FakeCanvas(width=260)
    state = make_state(character=None)
    cb = make_callbacks(*PANEL_CALLBACK_KEYS)
    pv.draw_pathway_list(canvas, state, cb)
    expect(len(state.pathway_items) == len(PATHWAYS),
           f"应写入全部途径布局，实际 {len(state.pathway_items)}")
    fired = fired_callback_names(canvas, cb)
    expect("select_pathway" in fired, "每条途径应绑定 select_pathway")


@test("panel_pathway_list_with_character")
def t_list_char():
    canvas = FakeCanvas(width=260)
    state = make_state(character=char_seq9())
    cb = make_callbacks(*PANEL_CALLBACK_KEYS)
    pv.draw_pathway_list(canvas, state, cb)
    expect(len(state.pathway_items) == len(PATHWAYS), "应有全部途径布局")
    # 触发所有绑定，验证点击参数都是合法途径 key
    for tag, event, handler in canvas.tag_bind_calls:
        handler(None)
    expect(cb["select_pathway"].called, "select_pathway 应被点击触发")
    for args, _ in cb["select_pathway"].calls:
        expect(args[0] in state.pathway_items, f"点击参数 {args[0]} 应为合法途径")


@test("panel_pathways_view_no_character")
def t_view_no_char():
    canvas = FakeCanvas(width=800, height=600)
    state = make_state(character=None)
    cb = make_callbacks(*PANEL_CALLBACK_KEYS)
    pv.draw_pathways_view(canvas, state, cb)
    fired = fired_callback_names(canvas, cb)
    expect("select_pathway_from_view" in fired, "全景卡片应绑定 select_pathway_from_view")
    expect(len(cb["select_pathway_from_view"].calls) == len(PATHWAYS),
           f"应有 {len(PATHWAYS)} 张卡片点击绑定")


@test("panel_pathways_view_with_character")
def t_view_char():
    canvas = FakeCanvas(width=800, height=600)
    state = make_state(character=char_seq9())
    cb = make_callbacks(*PANEL_CALLBACK_KEYS)
    pv.draw_pathways_view(canvas, state, cb)
    # 22 条途径各 1 张卡片，且都绑定了 select_pathway_from_view
    fired = fired_callback_names(canvas, cb)
    expect("select_pathway_from_view" in fired, "全景卡片应绑定 select_pathway_from_view")
    for args, _ in cb["select_pathway_from_view"].calls:
        expect(args[0] in PATHWAYS, f"{args[0]} 应为合法途径")


if __name__ == "__main__":
    run_all()
