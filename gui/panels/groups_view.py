"""gui/panels/groups_view.py — 九大权柄体系视图（自由函数版）。

自由函数：
  draw_groups_view(canvas, state, callbacks)
closed-over 的 callbacks 字典键：
  "on_group_click"  -> 点击某权柄体系卡片
"""
import math
from gui.theme import CLR, TAROT_ICONS
from gui.drawing import draw_rounded_rect
from pathways_data import PATHWAYS, PATHWAY_GROUPS


def draw_groups_view(canvas, state, callbacks=None):
    """九大权柄体系视图"""
    c = canvas
    c.delete("all")
    fonts = state.fonts
    character = state.character
    w = c.winfo_width() or 800
    h = c.winfo_height() or 600

    c.create_text(w//2, 16, text="九大权柄体系 · 旧日位阶",
                  font=fonts["h1"], fill=CLR["gold"])

    groups = list(PATHWAY_GROUPS.items())
    cols = 3
    rows = math.ceil(len(groups) / cols)
    cell_w = (w - 40) // cols
    cell_h = min((h - 60) // rows, 200)

    for i, (gk, gd) in enumerate(groups):
        col = i % cols
        row = i // cols
        x1 = 16 + col * cell_w
        y1 = 48 + row * cell_h
        x2 = x1 + cell_w - 8
        y2 = y1 + cell_h - 8

        # 卡片
        is_pillar = gk in ("god_almighty", "lord_of_mysteries", "eternal_darkness", "root_god")
        bg = "#1a1a3a" if is_pillar else CLR["panel_light"]
        outline = CLR["gold"] if is_pillar else CLR["border"]
        rect = draw_rounded_rect(c, x1, y1, x2, y2, r=10, fill=bg, outline=outline)

        # 支柱标记
        if is_pillar:
            c.create_text(x2-16, y1+10, text="★支柱", font=fonts["tiny"],
                          fill=CLR["gold"], anchor="ne")

        # 标题
        cx = (x1 + x2) // 2
        short_name = gd["name"].split("、")[0][:12]
        c.create_text(cx, y1+14, text=short_name, font=fonts["title"],
                      fill=CLR["gold"])
        c.create_text(cx, y1+34, text=f"源质：{gd['source_quality']}", font=fonts["tiny"],
                      fill=CLR["text_dim"])
        c.create_text(cx, y1+50, text=f"源：{gd['source']}", font=fonts["tiny"],
                      fill=CLR["text_dim"])

        # 途径列表
        cy = y1 + 74
        for pk in gd["pathways"]:
            p = PATHWAYS[pk]
            icon = TAROT_ICONS.get(pk, "✦")
            is_active = character and character.PATHWAY_KEY == pk
            fg = CLR["text_bright"] if is_active else CLR["text"]
            bg_item = CLR["gold_dim"] if is_active else ""
            if bg_item:
                draw_rounded_rect(c, x1+8, cy-2, x2-8, cy+18, r=4,
                                  fill=bg_item, outline="")
            c.create_text(x1+16, cy+8, text=f"{icon} {p['name']} ({p['tarot']})",
                          anchor="nw", font=fonts["body"], fill=fg)
            cy += 22

        # 互换规则
        cy += 4
        at_level = gd["interchange_at"]
        if at_level:
            c.create_text(cx, cy, text=f"可在序列{at_level}互换",
                          font=fonts["tiny"], fill=CLR["accent"])
        else:
            c.create_text(cx, cy, text="独立途径, 不可互换",
                          font=fonts["tiny"], fill=CLR["text_dim"])

        # 绑定点击
        if callbacks:
            c.tag_bind(rect, "<Button-1>",
                       lambda e, g=gk, cb=callbacks["on_group_click"]: cb(g))
