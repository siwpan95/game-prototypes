import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# tests/test_panel_action.py
# 操作面板 / 权柄收集 / 旧日晋升面板的独立单元测试（无头）。
# 重点：在不同角色等级下，面板应渲染正确分支并绑定正确回调。
from _panel_harness import (test, expect, run_all, FakeCanvas, make_state,
                            char_seq9, char_seq1, char_seq0, make_callbacks,
                            fired_callback_names, PANEL_CALLBACK_KEYS)
import gui.panels.action_panel as ap
from gui.helpers import get_pathway_uniqueness
from uniqueness import SequenceOneCharacteristic


def _draw(ch):
    canvas = FakeCanvas(width=340)
    state = make_state(character=ch)
    cb = make_callbacks(*PANEL_CALLBACK_KEYS)
    ap.draw_action_panel(canvas, state, cb)
    return canvas, cb


@test("panel_action_no_character")
def t_no_char():
    canvas, cb = _draw(None)
    expect(len(canvas.tag_bind_calls) == 0, "无角色不应有任何按钮绑定")
    expect(len(canvas.items) == 0, "无角色不应渲染")


@test("panel_action_seq9")
def t_seq9():
    canvas, cb = _draw(char_seq9())
    fired = fired_callback_names(canvas, cb)
    expect("do_action" in fired, "应绑定扮演行为按钮")
    expect("do_ascend" in fired, "序列9 应可晋升（do_ascend）")
    expect("do_random_event" in fired, "应绑定随机事件按钮")
    expect("do_switch" in fired, "error 途径应存在可切换途径（do_switch）")
    # 序列9：普通晋升按钮（btn+txt 共 2 次绑定），无收集/旧日分支
    expect(len(cb["do_ascend"].calls) == 2, f"普通晋升按钮应绑定 2 次，实际 {len(cb['do_ascend'].calls)}")
    expect("do_collect_seq1" not in fired, "序列9 不应绑定 do_collect_seq1")
    expect("do_promote_old_one" not in fired, "序列9 不应绑定 do_promote_old_one")


@test("panel_action_seq1_partial")
def t_seq1_partial():
    ch = char_seq1()
    canvas, cb = _draw(ch)
    fired = fired_callback_names(canvas, cb)
    expect("do_collect_seq1" in fired, "序列1 应绑定 争夺序列1特性")
    expect("do_collect_uniqueness" in fired, "序列1 应绑定 容纳唯一性")
    expect("do_promote_old_one" not in fired, "序列1 不应绑定 晋升旧日")
    # 未集齐：只有普通晋升按钮（2 次），聚合晋升序列0 按钮不出现
    expect(len(cb["do_ascend"].calls) == 2,
           f"未集齐时仅普通晋升按钮(2)，实际 {len(cb['do_ascend'].calls)}")


@test("panel_action_seq1_full_authority")
def t_seq1_full():
    ch = char_seq1()
    u = get_pathway_uniqueness("error")
    u.bind(ch)
    for i in (1, 2, 3):
        SequenceOneCharacteristic.ensure("error", i).bind(ch)
    canvas, cb = _draw(ch)
    fired = fired_callback_names(canvas, cb)
    expect("do_collect_seq1" in fired, "集齐后仍可争夺序列1特性")
    # 集齐后：普通晋升(2) + 聚合晋升序列0(2) = 4 次绑定
    expect(len(cb["do_ascend"].calls) == 4,
           f"集齐后聚合晋升按钮出现，do_ascend 应绑定 4 次，实际 {len(cb['do_ascend'].calls)}")


@test("panel_action_seq0_old_one")
def t_seq0():
    ch = char_seq0()
    canvas, cb = _draw(ch)
    fired = fired_callback_names(canvas, cb)
    expect("do_promote_old_one" in fired, "序列0 应绑定 晋升旧日")
    expect(len(cb["do_promote_old_one"].calls) == 2, "晋升旧日按钮应绑定 2 次(btn+txt)")
    expect("do_ascend" not in fired, "序列0 不应再出现普通晋升 do_ascend")
    expect("do_collect_seq1" not in fired, "序列0 不应出现 争夺序列1特性")


@test("panel_action_e5_quality_pills")
def t_e5():
    """E5：每个扮演行为应渲染主动/被动/背离三种质量按钮，且传入质量参数"""
    ch = char_seq9()
    canvas, cb = _draw(ch)
    fired = fired_callback_names(canvas, cb)
    expect("do_action" in fired, "应绑定扮演行为按钮")
    acts = cb["do_action"].calls
    expect(len(acts) > 0, "do_action 应被绑定至少一次")
    qualities = {a[0][1] for a in acts if len(a[0]) >= 2}
    expect("active" in qualities, "应存在主动质量按钮")
    expect("passive" in qualities, "应存在被动质量按钮")
    expect("divergent" in qualities, "应存在背离质量按钮")


if __name__ == "__main__":
    run_all()
