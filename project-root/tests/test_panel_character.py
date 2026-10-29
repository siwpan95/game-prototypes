import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# tests/test_panel_character.py
# 角色卡片 / 仪表盘面板的独立单元测试（无头）。
from _panel_harness import (test, expect, run_all, FakeCanvas, make_state,
                            char_seq9, char_seq1, char_seq0)
import gui.panels.character_view as cv


@test("panel_character_no_character")
def t_no_character():
    canvas = FakeCanvas()
    state = make_state(character=None)
    cv.draw_character_card(canvas, state)
    expect(len(canvas.items) >= 1, "无角色应至少渲染一行提示")


@test("panel_character_seq9")
def t_seq9():
    canvas = FakeCanvas()
    state = make_state(character=char_seq9())
    cv.draw_character_card(canvas, state)
    expect(len(canvas.items) > 5, "序列9 角色应渲染多行内容")


@test("panel_character_seq1_collection_progress")
def t_seq1():
    canvas = FakeCanvas()
    ch = char_seq1()
    from gui.helpers import get_pathway_uniqueness
    from uniqueness import SequenceOneCharacteristic
    SequenceOneCharacteristic.ensure("error", 1).bind(ch)
    SequenceOneCharacteristic.ensure("error", 2).bind(ch)
    state = make_state(character=ch)
    cv.draw_character_card(canvas, state)
    expect(len(canvas.items) > 5, "序列1 角色应渲染权柄收集进度")


@test("panel_character_seq0_old_one")
def t_seq0():
    canvas = FakeCanvas()
    ch = char_seq0()
    state = make_state(character=ch,
                       old_one_info={"group": "诡秘之主", "pillar": "诡秘之主",
                                     "tier": "支柱级旧日"})
    cv.draw_character_card(canvas, state)
    expect(len(canvas.items) > 5, "序列0 旧日角色应渲染位阶信息")


@test("panel_gauges_all_states")
def t_gauges():
    for ch in (None, char_seq9(), char_seq1(), char_seq0()):
        canvas = FakeCanvas()
        state = make_state(character=ch)
        cv.draw_gauges(canvas, state)
        if ch is None:
            expect(len(canvas.items) == 0, "无角色仪表盘应为空")
        else:
            expect(len(canvas.items) > 0, "有角色应绘制仪表")


@test("panel_character_e6_ability_effects")
def t_e6():
    """E6：拥有具效果能力的角色应渲染『能力效果』区块"""
    ch = char_seq9()
    ch.abilities.append("占卜")
    canvas = FakeCanvas()
    state = make_state(character=ch)
    cv.draw_character_card(canvas, state)
    texts = [k.get("text", "") for typ, k in canvas.items if typ == "text"]
    expect(any("能力效果" in t for t in texts), "应渲染能力效果区块")
    expect(any("占卜" in t for t in texts), "应列出占卜能力效果")


if __name__ == "__main__":
    run_all()
