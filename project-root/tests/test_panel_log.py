import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# tests/test_panel_log.py
# 事件日志面板（add_log 写 / draw_log 画 分离）的独立单元测试（无头）。
from _panel_harness import (test, expect, run_all, FakeCanvas, make_state)
import gui.panels.log_panel as lp


@test("panel_log_draw_empty")
def t_draw_empty():
    canvas = FakeCanvas(width=320)
    state = make_state(event_log=[])
    lp.draw_log(canvas, state)
    expect(canvas.configs, "空日志也应设置滚动区域")


@test("panel_log_draw_entries")
def t_draw_entries():
    canvas = FakeCanvas(width=320)
    state = make_state(event_log=[
        "[10:00:00] ✅ 晋升成功！",
        "[10:01:00] ⚠ 警告信息",
        "[10:02:00] ❌ 失败信息",
        "[10:03:00] ⬆ 晋升至序列8",
        "[10:04:00] ⚡ 随机事件",
    ])
    lp.draw_log(canvas, state)
    expect(len(canvas.items) > 0, "有日志应渲染文本")


@test("panel_log_add_truncates")
def t_add_truncates():
    state = make_state(event_log=[])
    for i in range(250):
        lp.add_log(state, f"msg {i}")
    expect(len(state.event_log) == 200, f"日志应截断到 200，实际 {len(state.event_log)}")
    expect(state.event_log[0].endswith("msg 50"), "应保留最近 200 条（从 msg 50 起）")


@test("panel_log_add_state_only")
def t_add_state_only():
    # add_log 只改状态、不依赖 canvas；调用方自行决定是否重绘
    state = make_state(event_log=[])
    lp.add_log(state, "hello")
    expect(len(state.event_log) == 1, "add_log 应追加一条")
    expect(state.event_log[0].endswith("hello"), "内容应正确")


if __name__ == "__main__":
    run_all()
