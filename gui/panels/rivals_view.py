"""gui/panels/rivals_view.py — 对手视图（自由函数版，E8）。

自由函数：
  draw_rivals_view(canvas, state, callbacks)
closed-over 的 callbacks 字典键：
  "do_rival_tick"  推进时间一个 tick（所有对手各推进一步）
  "do_add_rival"   添加一名 AI 对手（控制器自行选择「其它途径」）
"""
from gui.theme import CLR
from gui.drawing import draw_rounded_rect


def draw_rivals_view(canvas, state, callbacks=None):
    """绘制对手视图（自由函数）"""
    c = canvas
    c.delete("all")
    fonts = state.fonts
    w = c.winfo_width() or 580
    y = 20

    c.create_text(16, y, text="⚔ 对手 · 群雄并起", anchor="nw",
                  font=fonts["h2"], fill=CLR["gold"])
    y += 36
    c.create_text(16, y,
                  text="其它途径上的非凡者正随时光推进，争夺唯一性与序列1非凡特性。",
                  anchor="nw", font=fonts["small"], fill=CLR["text_dim"])
    y += 28

    rs = state.rival_system
    if rs is None or rs.count() == 0:
        c.create_text(16, y,
                      text="（暂无对手。点击下方「添加对手」引入一名 AI 非凡者。）",
                      anchor="nw", font=fonts["small"], fill=CLR["text_dim"])
        y += 28
    else:
        for s in rs.status():
            # 对手名 + 途径 + 当前序列
            head = f"{s['name']}　{s['pathway_name']}途径 · 序列{s['level']} {s['sequence_name']}"
            color = CLR["accent2"] if s["owns_uniqueness"] else CLR["text_bright"]
            c.create_text(16, y, text=head, anchor="nw",
                          font=fonts["title"], fill=color)
            y += 24
            # 消化进度 + 是否占住权柄
            claim = "已占住本途径权柄" if s["owns_uniqueness"] else ("已宣示权柄" if s["claimed"] else "争夺中")
            c.create_text(20, y,
                          text=f"消化 {s['digestion']:.0%}　|　{claim}",
                          anchor="nw", font=fonts["small"], fill=CLR["text_dim"])
            y += 26

    y += 6
    # 按钮：推进一 tick
    btn1 = draw_rounded_rect(c, 16, y, 16 + 220, y + 32, r=6,
                             fill=CLR["panel_light"], outline=CLR["gold"])
    t1 = c.create_text(126, y + 16, text="🜂 推进时间（1 tick）",
                       font=fonts["small"], fill=CLR["text_bright"])
    if callbacks:
        c.tag_bind(btn1, "<Button-1>",
                   lambda e, cb=callbacks.get("do_rival_tick"): cb() if cb else None)
        c.tag_bind(t1, "<Button-1>",
                   lambda e, cb=callbacks.get("do_rival_tick"): cb() if cb else None)
    y += 44

    # 按钮：添加对手
    btn2 = draw_rounded_rect(c, 16, y, 16 + 220, y + 32, r=6,
                             fill=CLR["panel_light"], outline=CLR["accent"])
    t2 = c.create_text(126, y + 16, text="➕ 添加一名对手",
                       font=fonts["small"], fill=CLR["text_bright"])
    if callbacks:
        c.tag_bind(btn2, "<Button-1>",
                   lambda e, cb=callbacks.get("do_add_rival"): cb() if cb else None)
        c.tag_bind(t2, "<Button-1>",
                   lambda e, cb=callbacks.get("do_add_rival"): cb() if cb else None)
    y += 44

    c.configure(scrollregion=(0, 0, w, y))
