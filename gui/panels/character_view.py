"""gui/panels/character_view.py — 角色卡片 / 仪表盘（自由函数版）。

所有渲染逻辑都是无 self 的纯函数：draw_*(canvas, state)。
state 提供 character / old_one_info / fonts；canvas 为任意兼容 tkinter.Canvas 接口的对象
（真实 Canvas 或测试用 FakeCanvas）。这样面板可被完全独立的单元测试覆盖。
"""
from gui.theme import CLR, TAROT_ICONS
from gui.drawing import draw_rounded_rect, draw_gauge, _wrap_text
from uniqueness import SequenceOneCharacteristic
from abilities import effective_abilities


def draw_character_card(canvas, state):
    """绘制角色卡片（自由函数，可直接单测）"""
    c = canvas
    c.delete("all")
    character = state.character
    fonts = state.fonts
    if not character:
        c.create_text(290, 200, text="选择一个途径开始", font=fonts["h2"],
                      fill=CLR["text_dim"])
        return

    ch = character
    w = c.winfo_width() or 580
    pad = 16

    # ── 途径名 + 塔罗 ──
    y = 20
    icon = TAROT_ICONS.get(ch.PATHWAY_KEY, "✦")
    c.create_text(pad, y, text=icon, font=("Segoe UI Emoji", 40), anchor="nw")
    c.create_text(pad+56, y+4, text=ch.PATHWAY_NAME, anchor="nw",
                  font=fonts["h1"], fill=CLR["gold"])
    c.create_text(pad+56, y+36, text=f"塔罗牌：{ch.TAROT}　·　灰雾之上·源堡", anchor="nw",
                  font=fonts["small"], fill=CLR["accent"])
    # ── 考据（E10 沉浸包装）：灰雾之上的低语 ──
    from lore import pathway_lore
    _lore = _wrap_text(pathway_lore(ch.PATHWAY_KEY), 44)
    for i, ln in enumerate(_lore):
        c.create_text(pad+56, y+58 + i*18, text=ln, anchor="nw",
                      font=fonts["tiny"], fill=CLR["text_dim"])
    y += 58 + len(_lore) * 18 + 10

    # ── 序列等级大数字 ──
    draw_rounded_rect(c, pad, y, pad+72, y+60, r=10,
                      fill="#1a1a2e", outline=CLR["gold"])
    c.create_text(pad+36, y+12, text="序列", font=fonts["tiny"], fill=CLR["text_dim"])
    c.create_text(pad+36, y+38, text=str(ch.LEVEL), font=("Noto Sans SC Black", 32), fill=CLR["gold"])

    # 序列名称
    c.create_text(pad+88, y+20, text=ch.SEQUENCE_NAME, anchor="w",
                  font=fonts["h2"], fill=CLR["text_bright"])
    c.create_text(pad+88, y+44, text=f"性别：{ch.gender}", anchor="w",
                  font=fonts["small"], fill=CLR["text_dim"])
    y += 72

    # ── 旧日位阶 / 权柄收集进度 ──
    if ch.LEVEL == 0:
        info = state.old_one_info
        if info:
            pillar = info.get("pillar")
            tier = info.get("tier") or "普通旧日"
            extra = f"｜支柱：{pillar}" if pillar else ""
            c.create_text(pad, y, text=f"★ 旧日位阶：{info['group']}（{tier}）{extra}",
                          anchor="nw", font=fonts["title"], fill=CLR["gold"])
        else:
            c.create_text(pad, y, text="★ 序列0真神 · 可容纳源质晋升旧日",
                          anchor="nw", font=fonts["title"], fill=CLR["gold"])
        y += 26
    elif ch.LEVEL == 1:
        owned = SequenceOneCharacteristic.owned_count(ch.PATHWAY_KEY, ch)
        c.create_text(pad, y, text=f"◆ 权柄收集：序列1特性 {owned}/3｜唯一性待容纳",
                      anchor="nw", font=fonts["small"], fill=CLR["accent3"])
        y += 22

    # ── 诅咒 / 特殊 ──
    if ch._curse or ch._special:
        y += 4
        if ch._curse:
            c.create_text(pad, y, text=f"╬ 诅咒：{ch._curse}", anchor="nw",
                          font=fonts["small"], fill=CLR["accent2"])
            y += 22
        if ch._special:
            c.create_text(pad, y, text=f"✦ 特殊：{ch._special}", anchor="nw",
                          font=fonts["small"], fill=CLR["accent"])
            y += 22
        y += 4

    # ── 分割线 ──
    y += 4
    c.create_line(pad, y, w-pad, y, fill=CLR["border"])
    y += 12

    # ── 能力列表 ──
    c.create_text(pad, y, text="▎超凡能力", anchor="nw",
                  font=fonts["title"], fill=CLR["gold"])
    y += 28
    abilities = ch.abilities
    cols = 3
    col_w = (w - pad*2) // cols
    for i, ab in enumerate(abilities):
        col = i % cols
        row = i // cols
        cx = pad + col * col_w
        cy = y + row * 22
        c.create_text(cx, cy, text=f"◆ {ab}", anchor="nw",
                      font=fonts["small"], fill=CLR["text"])
    y += (len(abilities) // cols + 1) * 22 + 4

    # ── 能力效果（E6）：仅当角色拥有具效果的能力时显示 ──
    eff = effective_abilities(ch)
    if eff:
        y += 2
        c.create_text(pad, y, text="▎能力效果", anchor="nw",
                      font=fonts["title"], fill=CLR["accent"])
        y += 24
        for _name, _desc in eff:
            c.create_text(pad+8, y, text=f"✨ {_name}：{_desc}", anchor="nw",
                          font=fonts["small"], fill=CLR["text_dim"])
            y += 20
        y += 2

    # ── 分割线 ──
    c.create_line(pad, y, w-pad, y, fill=CLR["border"])
    y += 12

    # ── 扮演行为 ──
    c.create_text(pad, y, text="▎扮演行为", anchor="nw",
                  font=fonts["title"], fill=CLR["gold"])
    y += 28
    for i, act in enumerate(ch.act_catalog()):
        done = act in ch.digestion_actions
        mark = "✓" if done else "○"
        color = CLR["accent4"] if done else CLR["text_dim"]
        c.create_text(pad+12, y+i*22, text=f"{mark} {act}", anchor="nw",
                      font=fonts["body"], fill=color)
    y += len(ch.act_catalog()) * 22 + 4

    # ── 晋升仪式（如有） ──
    if ch._ritual:
        y += 4
        c.create_line(pad, y, w-pad, y, fill=CLR["border"])
        y += 12
        c.create_text(pad, y, text="▎晋升仪式（序列5+）", anchor="nw",
                      font=fonts["title"], fill=CLR["accent2"])
        y += 26
        ritual_lines = _wrap_text(ch._ritual, 50)
        for i, rl in enumerate(ritual_lines):
            c.create_text(pad+8, y+i*20, text=rl, anchor="nw",
                          font=fonts["small"], fill=CLR["text"])
        y += len(ritual_lines) * 20

    # 设置滚动区域（底部留白）
    y += 24
    c.configure(scrollregion=(0, 0, w, y))


def draw_gauges(canvas, state):
    """绘制三连仪表盘（自由函数）"""
    c = canvas
    c.delete("all")
    w = c.winfo_width() or 580
    h = 180
    fonts = state.fonts

    ch = state.character
    if not ch:
        return

    # 三个仪表盘均匀分布
    san_color = [CLR["pollution_0"], CLR["pollution_1"], CLR["pollution_2"],
                 CLR["pollution_3"], CLR["pollution_4"]][ch.pollution.level.value]
    gauges = [
        {"label": f"理智 SAN · {ch.pollution.label_cn}",
         "value": ch.pollution.san, "max": 100,
         "colors": [san_color], "text": f"{ch.pollution.san:.0f}\n{ch.pollution.san_status()}"},
        {"label": "锚强度", "value": ch.anchor.strength if ch.anchor else 0, "max": 200,
         "colors": [CLR["accent3"]], "text": f"{ch.anchor.strength:.0f}" if ch.anchor else "—"},
        {"label": "消化进度", "value": ch.digestion_ratio, "max": 1.0,
         "colors": [CLR["accent4"]], "text": f"{ch.digestion_ratio:.0%}"},
    ]

    spacing = w // 3
    for i, g in enumerate(gauges):
        cx = spacing * i + spacing // 2
        cy = h // 2 + 6
        r = 55

        # 标签
        c.create_text(cx, 22, text=g["label"], font=fonts["title"],
                      fill=CLR["gold"], anchor="center")

        # 单色弧形（SAN 为连续值，0–100）
        ratio = min(g["value"] / max(g["max"], 0.01), 1.0)
        extent = int(270 * ratio)
        draw_gauge(c, cx, cy, r, 135, 135+extent, g["colors"][0], width=10)
        draw_gauge(c, cx, cy, r, 135+extent, 405, CLR["border"], width=10)
        c.create_text(cx, cy, text=g["text"], font=fonts["h2"],
                      fill=CLR["text_bright"], anchor="center")
