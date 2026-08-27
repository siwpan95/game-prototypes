import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# tests/test_panel_groups.py
# 九大权柄体系视图面板的独立单元测试（无头）。
from _panel_harness import (test, expect, run_all, FakeCanvas, make_state,
                            char_seq9, make_callbacks, fired_callback_names,
                            PANEL_CALLBACK_KEYS)
import gui.panels.groups_view as gv
from pathways_data import PATHWAY_GROUPS


@test("panel_groups_no_character")
def t_no_char():
    canvas = FakeCanvas(width=800, height=600)
    state = make_state(character=None)
    cb = make_callbacks(*PANEL_CALLBACK_KEYS)
    gv.draw_groups_view(canvas, state, cb)
    fired = fired_callback_names(canvas, cb)
    expect("on_group_click" in fired, "9 大权柄体系应绑定 on_group_click")
    expect(len(cb["on_group_click"].calls) == len(PATHWAY_GROUPS),
           f"应绑定 {len(PATHWAY_GROUPS)} 个体系")


@test("panel_groups_with_character")
def t_char():
    canvas = FakeCanvas(width=800, height=600)
    state = make_state(character=char_seq9())
    cb = make_callbacks(*PANEL_CALLBACK_KEYS)
    gv.draw_groups_view(canvas, state, cb)
    fired_callback_names(canvas, cb)
    expect(cb["on_group_click"].calls, "应有 9 个体系点击绑定")
    for args, _ in cb["on_group_click"].calls:
        expect(args[0] in PATHWAY_GROUPS, f"{args[0]} 应为合法体系 key")


if __name__ == "__main__":
    run_all()
