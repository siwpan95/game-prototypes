"""gui/panels/codex_view.py — 成就 / 图鉴 / 结局视图（自由函数版，E9）。

自由函数：
  draw_codex_view(canvas, state, callbacks=None)
本视图为只读展示（无回调绑定），汇总：
  - 成就（已解锁 / 未解锁，含进度）
  - 图鉴（已见序列 / 能力 / 事件 / 阵营收集进度）
  - 当前结局走向（evaluate_ending）
"""
from gui.theme import CLR
from achievements import ACHIEVEMENTS, evaluate_ending


def draw_codex_view(canvas, state, callbacks=None):
    """绘制成就 / 图鉴 / 结局视图（自由函数，只读）"""
    c = canvas
    c.delete("all")
    fonts = state.fonts
    w = c.winfo_width() or 580
    y = 20

    c.create_text(16, y, text="📖 成就 · 图鉴 · 结局", anchor="nw",
                  font=fonts["h2"], fill=CLR["gold"])
    y += 36

    # ── 成就 ──
    ach = getattr(state, "achievements", None)
    done, total = (ach.progress() if ach else (0, len(ACHIEVEMENTS)))
    c.create_text(16, y, text=f"▎成就（{done}/{total}）", anchor="nw",
                  font=fonts["title"], fill=CLR["gold"])
    y += 28
    for key, meta in ACHIEVEMENTS.items():
        unlocked = ach.is_unlocked(key) if ach else False
        mark = "🏆" if unlocked else "🔒"
        color = CLR["gold"] if unlocked else CLR["text_dim"]
        c.create_text(20, y, text=f"{mark} {meta['name']} —— {meta['desc']}",
                      anchor="nw", font=fonts["small"], fill=color)
        y += 22
    y += 6

    # ── 图鉴 ──
    codex = getattr(state, "codex", None)
    c.create_text(16, y, text="▎图鉴收集进度", anchor="nw",
                  font=fonts["title"], fill=CLR["gold"])
    y += 28
    if codex is not None:
        seq_n, seq_tot = codex.sequence_progress()
        lines = [
            f"序列：{seq_n}/{seq_tot}",
            f"能力：{len(codex.abilities)} 种",
            f"事件：{len(codex.events)} 个",
            f"阵营：{len(codex.factions)}/3",
        ]
        for i, ln in enumerate(lines):
            c.create_text(20 + i * ((w - 32) // 4), y, text=ln, anchor="nw",
                          font=fonts["small"], fill=CLR["text"])
    else:
        c.create_text(20, y, text="（图鉴尚未初始化）", anchor="nw",
                      font=fonts["small"], fill=CLR["text_dim"])
    y += 30

    # ── 当前结局走向 ──
    c.create_text(16, y, text="▎命运走向（当前）", anchor="nw",
                  font=fonts["title"], fill=CLR["accent"])
    y += 26
    key, title, text = evaluate_ending(state)
    c.create_text(20, y, text=f"✧ {title}", anchor="nw",
                  font=fonts["body"], fill=CLR["text_bright"])
    y += 24
    # 结局描述按宽度折行
    from gui.drawing import _wrap_text
    for i, ln in enumerate(_wrap_text(text, 48)):
        c.create_text(20, y + i * 20, text=ln, anchor="nw",
                      font=fonts["small"], fill=CLR["text_dim"])
    y += len(_wrap_text(text, 48)) * 20 + 12

    c.configure(scrollregion=(0, 0, w, y))
