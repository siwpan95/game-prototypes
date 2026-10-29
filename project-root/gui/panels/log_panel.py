"""gui/panels/log_panel.py — 事件日志（自由函数版）。

  add_log(state, msg)      纯状态变更：把一条日志追加到 state.event_log（不触发绘制）
  draw_log(canvas, state)  把 state.event_log 渲染到 canvas（自由函数，可直接单测）

把「写日志」与「画日志」拆开，使控制器/编排层可以只追加不重绘（或按需重绘），
也便于日志逻辑在无 Tk 的单元测试里被覆盖。
"""
import tkinter as tk  # noqa: F401  (保持与 GUI 一致的导入语义；测试会 stub 掉 tk.font.Font)
from tkinter import font as tkfont
from datetime import datetime
from gui.theme import CLR


def add_log(state, msg: str):
    """追加一条日志到 state.event_log（纯状态变更，不触发绘制）"""
    ts = datetime.now().strftime("%H:%M:%S")
    state.event_log.append(f"[{ts}] {msg}")
    if len(state.event_log) > 200:
        state.event_log = state.event_log[-200:]


def draw_log(canvas, state):
    """绘制日志（自由函数，可直接单测）"""
    c = canvas
    c.delete("all")
    fonts = state.fonts
    canvas_w = c.winfo_width() or 320
    max_px = canvas_w - 20  # 右侧留边
    font = tkfont.Font(font=fonts["mono"])
    y = 6
    line_h = 18
    for entry in reversed(state.event_log[-25:]):
        color = CLR["text"]
        if "❌" in entry:
            color = CLR["accent2"]
        elif "✅" in entry or "成功" in entry:
            color = CLR["accent4"]
        elif "⚠" in entry:
            color = CLR["pollution_1"]
        elif "⚡" in entry or "💀" in entry:
            color = CLR["pollution_2"]
        elif "⬆" in entry or "⇄" in entry:
            color = CLR["gold"]
        # 按像素宽度换行
        line = ""
        for ch in entry:
            if font.measure(line + ch) > max_px and line:
                c.create_text(8, y, text=line, anchor="nw",
                              font=fonts["mono"], fill=color)
                y += line_h
                line = ch
            else:
                line += ch
        if line:
            c.create_text(8, y, text=line, anchor="nw",
                          font=fonts["mono"], fill=color)
            y += line_h
    c.configure(scrollregion=(0, 0, canvas_w, max(y + 6, 300)))
