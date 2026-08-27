"""gui/panels/brewing_panel.py — 魔药材料 / 酿造面板（自由函数版，E1）。

draw_brewing_panel(canvas, y, state, callbacks) -> int
  - 展示「晋升到下一序列」所需的魔药配方（主材料 + 辅助材料）
  - 用库存标记每份材料 已收集✓ / 未收集✗
  - 提供「🜂 搜寻材料」按钮（callbacks["do_gather"]）模拟世界探索获取材料
  - 返回更新后的 y 坐标，供调用方继续往下排布
闭合回调键："do_gather"
"""
from gui.theme import CLR
from gui.drawing import draw_rounded_rect
from pathways_data import get_potion_formula, get_sequence_data
from gui.helpers import get_pathway_uniqueness  # 复用共享导入风格


def draw_brewing_panel(canvas, y, state, callbacks=None) -> int:
    """绘制魔药材料面板（自由函数，可单测）"""
    c = canvas
    ch = state.character
    fonts = state.fonts
    inv = state.inventory

    c.create_text(12, y, text="魔药材料（下一序列配方）：", anchor="nw",
                  font=fonts["small"], fill=CLR["text_dim"])
    y += 22

    # 已是真神：无需魔药，引导去集齐权柄
    if ch.LEVEL <= 0:
        c.create_text(14, y, text="★ 序列0真神：无需魔药，请于下方集齐权柄晋升旧日",
                      anchor="nw", font=fonts["tiny"], fill=CLR["gold"])
        return y + 22

    target = ch.LEVEL - 1
    seq_to = get_sequence_data(ch.PATHWAY_KEY, target)
    formula = get_potion_formula(ch.PATHWAY_KEY, target)

    # 配方标题
    c.create_text(14, y, text=f"→ 序列{target}《{seq_to['name']}》魔药", anchor="nw",
                  font=fonts["tiny"], fill=CLR["accent"])
    y += 20

    # 主材料
    ok_main = inv.count(formula["main"]) >= 1
    mark = "✓" if ok_main else "✗"
    color = CLR["accent4"] if ok_main else CLR["text_dim"]
    c.create_text(20, y, text=f"{mark} 主材料：{formula['main']}", anchor="nw",
                  font=fonts["small"], fill=color)
    y += 20

    # 辅助材料
    for m in formula["supplementary"]:
        ok = inv.count(m) >= 1
        mark = "✓" if ok else "✗"
        color = CLR["accent4"] if ok else CLR["text_dim"]
        c.create_text(28, y, text=f"{mark} 辅助：{m}", anchor="nw",
                      font=fonts["small"], fill=color)
        y += 20

    # 状态 / 按钮
    ready = inv.has(formula)
    if ready:
        c.create_text(14, y, text="✔ 材料齐备，可晋升！", anchor="nw",
                      font=fonts["tiny"], fill=CLR["accent4"])
        y += 20
    else:
        btn = draw_rounded_rect(c, 10, y, 175, y+28, r=6,
                                fill=CLR["gold_dim"], outline=CLR["gold"])
        txt = c.create_text(92, y+14, text="🜂 搜寻材料（探索）",
                            font=fonts["small"], fill=CLR["text_bright"])
        if callbacks:
            cb = callbacks.get("do_gather")
            if cb:
                c.tag_bind(btn, "<Button-1>", lambda e, cb=cb: cb())
                c.tag_bind(txt, "<Button-1>", lambda e, cb=cb: cb())
        y += 34

    return y
