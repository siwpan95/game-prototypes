"""gui/panels/event_panel.py — 随机事件浮层（自由函数版，E3）。

draw_event_overlay(canvas, state, callbacks)
  - 在角色视图中央渲染当前 pending_event 的叙事与若干选项按钮
  - 每个选项按钮绑定 callbacks["do_event_choice"](index)
  - 选择后由控制器 _do_event_choice 结算并清除 pending_event
闭合回调键："do_event_choice"
"""
from gui.theme import CLR
from gui.drawing import draw_rounded_rect, _wrap_text


def draw_event_overlay(canvas, state, callbacks=None):
    """绘制随机事件浮层（自由函数，可单测）"""
    c = canvas
    c.delete("all")
    ev = state.pending_event
    fonts = state.fonts
    w = c.winfo_width() or 580
    h = c.winfo_height() or 600

    if not ev:
        return

    # 半透明背板
    pad = 24
    bx, by, bw, bh = pad, 40, w - pad * 2, h - 80
    draw_rounded_rect(c, bx, by, bx + bw, by + bh, r=14,
                      fill=CLR["panel"], outline=CLR["gold"])

    # 标题
    y = by + 18
    c.create_text(bx + 18, y, text=f"🎲 事件 · 《{ev['title']}》", anchor="nw",
                  font=fonts["title"], fill=CLR["gold"])
    y += 34
    c.create_line(bx + 18, y, bx + bw - 18, y, fill=CLR["border"])
    y += 16

    # 叙事（自动换行）
    narrative = ev.get("narrative", "")
    for line in _wrap_text(narrative, 34):
        c.create_text(bx + 18, y, text=line, anchor="nw",
                      font=fonts["body"], fill=CLR["text"])
        y += 24
    y += 14

    # 选项按钮
    choices = ev.get("choices", [])
    for i, ch in enumerate(choices):
        btn = draw_rounded_rect(c, bx + 18, y, bx + bw - 18, y + 46, r=8,
                                fill=CLR["panel_light"], outline=CLR["accent"])
        txt = c.create_text(bx + bw / 2, y + 23, text=f"{i+1}. {ch.get('text')}",
                             font=fonts["body"], fill=CLR["text_bright"], anchor="center")
        if callbacks:
            cb = callbacks.get("do_event_choice")
            if cb:
                c.tag_bind(btn, "<Button-1>", lambda e, idx=i, cb=cb: cb(idx))
                c.tag_bind(txt, "<Button-1>", lambda e, idx=i, cb=cb: cb(idx))
        y += 56

    c.configure(scrollregion=(0, 0, w, max(by + bh, y + 10)))
