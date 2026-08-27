"""gui/panels/factions_view.py — 阵营 / 塔罗会社交视图（自由函数版）。

自由函数：
  draw_factions_view(canvas, state, callbacks)
closed-over 的 callbacks 字典键：
  "do_faction_action"  -> (faction_key, action_key) 执行社交动作
"""
from gui.theme import CLR
from gui.drawing import draw_rounded_rect
from factions import FACTIONS, ACTIONS


def draw_factions_view(canvas, state, callbacks=None):
    """绘制阵营社交视图（自由函数）"""
    c = canvas
    c.delete("all")
    fonts = state.fonts
    w = c.winfo_width() or 580
    y = 20

    c.create_text(16, y, text="🜂 阵营 · 塔罗会社交", anchor="nw",
                  font=fonts["h2"], fill=CLR["gold"])
    y += 36
    c.create_text(16, y,
                  text="在各大势力间经营声望，以声望换取材料、理智与锚之加固。",
                  anchor="nw", font=fonts["small"], fill=CLR["text_dim"])
    y += 28

    factions = state.factions or {}
    for fk, fmeta in FACTIONS.items():
        rep = factions.get(fk, 0)
        # 阵营标题 + 当前声望
        c.create_text(16, y, text=f"{fmeta['label']}　声望 {rep}",
                      anchor="nw", font=fonts["title"], fill=fmeta["color"])
        y += 24
        c.create_text(20, y, text=fmeta["desc"], anchor="nw",
                      font=fonts["small"], fill=CLR["text_dim"])
        y += 22

        # 该阵营可执行的社会动作
        for ak, ameta in ACTIONS.items():
            if ameta["faction"] != fk:
                continue
            affordable = rep >= ameta["cost"]
            fill = CLR["panel_light"] if affordable else CLR["border"]
            fg = CLR["text"] if affordable else CLR["text_dim"]
            btn = draw_rounded_rect(c, 16, y, 16 + 320, y + 30, r=6,
                                    fill=fill, outline=fmeta["color"])
            txt = c.create_text(176, y + 15,
                                text=f"{ameta['label']}（声望-{ameta['cost']}）",
                                font=fonts["small"], fill=fg)
            if callbacks:
                c.tag_bind(btn, "<Button-1>",
                           lambda e, f=fk, a=ak, cb=callbacks["do_faction_action"]: cb(f, a))
                c.tag_bind(txt, "<Button-1>",
                           lambda e, f=fk, a=ak, cb=callbacks["do_faction_action"]: cb(f, a))
            y += 36
        y += 10

    c.configure(scrollregion=(0, 0, w, y))
