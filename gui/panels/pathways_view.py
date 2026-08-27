"""gui/panels/pathways_view.py — 途径列表 / 全景 / 权柄体系视图（自由函数版）。

自由函数：
  draw_pathway_list(canvas, state, callbacks)      左侧 22 途径列表
  draw_pathways_view(canvas, state, callbacks)     中栏 22 途径全景
closed-over 的 callbacks 字典键：
  "select_pathway"            -> 左侧列表点击某途径
  "select_pathway_from_view"  -> 全景卡片点击某途径
"""
import math
from gui.theme import CLR, TAROT_ICONS
from gui.drawing import draw_rounded_rect, pathway_sort_key
from pathways_data import PATHWAYS, PATHWAY_GROUPS, get_pathway, get_sequence_data


def draw_pathway_list(canvas, state, callbacks=None):
    """绘制左侧途径列表面板；每个条目绑定 callbacks['select_pathway'](pk)"""
    c = canvas
    c.delete("all")
    fonts = state.fonts
    character = state.character

    sorted_keys = sorted(PATHWAYS.keys(), key=pathway_sort_key)
    y = 8
    item_h = 42

    items = {}
    last_group = None
    for pk in sorted_keys:
        p = PATHWAYS[pk]
        gk = p["group"]
        gn = PATHWAY_GROUPS.get(gk, {}).get("name", gk)

        # 组标题
        if gk != last_group:
            y += 2
            c.create_text(16, y+8, text=gn[:12], anchor="w",
                          font=fonts["tiny"], fill=CLR["gold_dim"])
            y += 18
            last_group = gk

        icon = TAROT_ICONS.get(pk, "✦")
        # 背景条
        bg_tag = draw_rounded_rect(c, 6, y, 240, y+item_h, r=6,
                                    fill=CLR["panel_light"], outline="")
        # 图标
        c.create_text(24, y+item_h//2, text=icon, font=("Segoe UI Emoji", 16), anchor="w")
        # 名称
        c.create_text(50, y+10, text=p["name"], anchor="w",
                      font=fonts["body"], fill=CLR["text"])
        # 塔罗牌
        c.create_text(50, y+26, text=f"塔罗：{p['tarot']}", anchor="w",
                      font=fonts["tiny"], fill=CLR["text_dim"])
        # 当前序列指示
        if character and character.PATHWAY_KEY == pk:
            c.create_oval(218, y+12, 234, y+28, fill=CLR["gold"], outline="")
            c.create_text(226, y+item_h//2, text="✦", font=fonts["tiny"], fill="#000")

        items[pk] = (y, item_h)
        # 绑定点击：点击条目背景即选择该途径
        if callbacks:
            c.tag_bind(bg_tag, "<Button-1>",
                       lambda e, k=pk, cb=callbacks["select_pathway"]: cb(k))
        y += item_h + 2

    state.pathway_items = items
    c.configure(scrollregion=(0, 0, 260, y+20))


def draw_pathways_view(canvas, state, callbacks=None):
    """22条途径全景视图"""
    c = canvas
    c.delete("all")
    fonts = state.fonts
    character = state.character
    w = c.winfo_width() or 800
    h = c.winfo_height() or 600

    c.create_text(w//2, 16, text="22 条神之途径 · 序列体系全景",
                  font=fonts["h1"], fill=CLR["gold"])

    sorted_keys = sorted(PATHWAYS.keys(), key=pathway_sort_key)

    # 计算布局
    cols = 6
    rows = math.ceil(len(sorted_keys) / cols)
    cell_w = (w - 40) // cols
    cell_h = min((h - 60) // rows, 180)

    for i, pk in enumerate(sorted_keys):
        col = i % cols
        row = i // cols
        x1 = 16 + col * cell_w
        y1 = 48 + row * cell_h
        x2 = x1 + cell_w - 6
        y2 = y1 + cell_h - 6

        p = PATHWAYS[pk]
        icon = TAROT_ICONS.get(pk, "✦")

        # 卡片背景
        is_active = character and character.PATHWAY_KEY == pk
        bg = CLR["gold_dim"] if is_active else CLR["panel_light"]
        outline = CLR["gold"] if is_active else CLR["border"]
        rect = draw_rounded_rect(c, x1, y1, x2, y2, r=8, fill=bg, outline=outline)

        # 内容
        cx = (x1 + x2) // 2
        c.create_text(cx, y1+14, text=icon, font=("Segoe UI Emoji", 22),
                      fill=CLR["text_bright"])
        c.create_text(cx, y1+44, text=p["name"], font=fonts["title"],
                      fill=CLR["text_bright"])
        c.create_text(cx, y1+66, text=f"塔罗牌：{p['tarot']}", font=fonts["tiny"],
                      fill=CLR["text_dim"])

        # 序列条（9→0，从下往上）
        bar_start = y2 - 10
        bar_h = 6
        for lvl in range(9, -1, -1):
            seq = get_sequence_data(pk, lvl)
            by = bar_start - (9-lvl) * (bar_h+1)
            is_seq = character and character.LEVEL == lvl and is_active
            clr = CLR["gold"] if is_seq else CLR["text_dim"]
            # 画小圆点
            c.create_oval(cx-3, by, cx+3, by+bar_h,
                          fill=clr, outline="")
            if is_seq:
                c.create_text(cx, by-8, text=seq["name"], font=fonts["tiny"],
                              fill=CLR["gold"], anchor="s")

        # 点击事件
        if callbacks:
            c.tag_bind(rect, "<Button-1>",
                       lambda e, k=pk, cb=callbacks["select_pathway_from_view"]: cb(k))
