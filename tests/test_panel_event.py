# tests/test_panel_event.py
# 随机事件浮层（E3）的无头单测：渲染叙事 + 绑定 do_event_choice(选项索引)
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import _panel_harness as H
from gui.panels.event_panel import draw_event_overlay
from sequences import make_sequence


@H.test("panel_event_overlay_renders_and_binds_choices")
def t():
    """浮层应渲染叙事，并为每个选项绑定 do_event_choice(正确索引)"""
    ch = make_sequence("error", 9)
    state = H.make_state(character=ch)
    from events import pick_event
    ev = pick_event(ch, state)
    H.expect(ev is not None, "应能抽取到随机事件")
    state.pending_event = ev
    cb = H.make_callbacks("do_event_choice")
    c = H.FakeCanvas()
    draw_event_overlay(c, state, cb)
    H.expect(len(c.items) > 0, "event overlay 应渲染内容")
    fired = H.fired_callback_names(c, cb)
    H.expect("do_event_choice" in fired, "event overlay 应绑定 do_event_choice")
    # 每个选项都应触发一次，且传入的索引各不相同。
    # 注意：每个选项是「按钮底图 + 文字」两个 canvas item 绑定同一回调，
    # 因此 calls 数 = 选项数×2，这里只关心去重后的索引集合是否完整覆盖。
    indices = [call[0][0] for call in cb["do_event_choice"].calls]
    distinct = sorted(set(indices))
    H.expect(len(distinct) == len(ev["choices"]),
             f"应绑定 {len(ev['choices'])} 个选项，实际去重后 {len(distinct)}")
    H.expect(distinct == list(range(len(ev["choices"]))),
             f"选项索引应覆盖 0..{len(ev['choices'])-1}，实际 {distinct}")


@H.test("panel_event_overlay_no_event_is_noop")
def t():
    """无 pending_event 时浮层应为空操作"""
    ch = make_sequence("error", 9)
    state = H.make_state(character=ch)
    state.pending_event = None
    cb = H.make_callbacks("do_event_choice")
    c = H.FakeCanvas()
    draw_event_overlay(c, state, cb)
    H.expect(len(c.items) == 0, "无事件时浮层不应渲染任何内容")
