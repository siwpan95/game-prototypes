"""gui/panels/action_panel.py — 操作面板 / 权柄收集 / 旧日晋升（自由函数版）。

自由函数：
  draw_action_panel(canvas, state, callbacks)
  draw_collection_panel(canvas, y, state, callbacks)   序列1 → 序列0 前置
  draw_old_one_panel(canvas, y, state, callbacks)      序列0 → 旧日
closed-over 的 callbacks 字典键：
  "do_action"              -> 执行扮演行为
  "do_ascend"              -> 晋升 / 聚合晋升序列0
  "do_switch"              -> 途径切换
  "do_random_event"        -> 触发随机事件
  "do_collect_seq1"        -> 争夺序列1特性
  "do_collect_uniqueness"  -> 容纳唯一性
  "do_promote_old_one"     -> 晋升旧日
"""
from gui.theme import CLR
from gui.drawing import draw_rounded_rect, group_key_of
from pathways_data import PATHWAY_GROUPS, get_compatible_pathways, get_pathway
from uniqueness import SequenceOneCharacteristic
from pathway_groups import OldOnePath, FOUR_PILLARS
from gui.helpers import get_pathway_uniqueness
from gui.panels.brewing_panel import draw_brewing_panel


# E5 扮演质量维度：每个行为可选择的贴合度（权重见 sequences.BaseSequence.perform_action）
QUALITY_OPTIONS = [
    ("主动", "active",   CLR["accent4"]),   # 主动贴合扮演 → +1.0
    ("被动", "passive",  CLR["accent3"]),   # 被动剧情选择 → +0.5
    ("背离", "divergent", CLR["accent2"]),  # 背离身份扮演 → -0.5
]


def draw_action_panel(canvas, state, callbacks=None):
    """绘制操作按钮面板（自由函数）"""
    c = canvas
    c.delete("all")
    character = state.character
    if not character:
        return

    ch = character
    fonts = state.fonts
    y = 10

    # ── 扮演行为按钮 ──
    c.create_text(12, y, text="执行扮演行为：", anchor="nw",
                  font=fonts["small"], fill=CLR["text_dim"])
    y += 22

    for act in ch.act_catalog():
        # E5：以累积权重判定该行为是否已「完全消化」（主动一次即满，被动需两次）
        w = ch.action_weight.get(act, 0.0)
        done = w >= 1.0
        bg = CLR["accent4"] if done else CLR["panel_light"]
        fg = "#000" if done else CLR["text"]
        btn = draw_rounded_rect(c, 10, y, 150, y+28, r=6, fill=bg, outline=CLR["border"])
        txt = c.create_text(85, y+14, text=f"{'✓' if done else '▶'} {act}",
                            font=fonts["small"], fill=fg)
        if callbacks:
            # 主按钮 = 主动扮演
            c.tag_bind(btn, "<Button-1>", lambda e, a=act, cb=callbacks["do_action"]: cb(a, "active"))
            c.tag_bind(txt, "<Button-1>", lambda e, a=act, cb=callbacks["do_action"]: cb(a, "active"))

        # 质量维度小标签（E5）：被动 / 背离
        qx = 158
        for qlabel, qkey, qfill in QUALITY_OPTIONS[1:]:
            qp = draw_rounded_rect(c, qx, y, qx+46, y+28, r=5, fill=qfill, outline="")
            qt = c.create_text(qx+23, y+14, text=qlabel, font=fonts["tiny"], fill="#fff")
            if callbacks:
                c.tag_bind(qp, "<Button-1>", lambda e, a=act, q=qkey, cb=callbacks["do_action"]: cb(a, q))
                c.tag_bind(qt, "<Button-1>", lambda e, a=act, q=qkey, cb=callbacks["do_action"]: cb(a, q))
            qx += 50
        y += 34

    y += 6

    # ── 魔药材料（下一序列配方 + 搜寻）──
    y = draw_brewing_panel(c, y, state, callbacks)
    y += 6

    # ── 晋升按钮 ──
    c.create_line(10, y, 320, y, fill=CLR["border"])
    y += 10
    c.create_text(12, y, text="晋升与蜕变：", anchor="nw",
                  font=fonts["small"], fill=CLR["text_dim"])
    y += 24

    if ch.LEVEL > 0:
        next_lvl = ch.LEVEL - 1
        btn_asc = draw_rounded_rect(c, 10, y, 155, y+34, r=8,
                                     fill=CLR["gold_dim"], outline=CLR["gold"])
        txt_asc = c.create_text(82, y+17, text=f"⬆ 晋升至序列{next_lvl}",
                                 font=fonts["body"], fill=CLR["text_bright"])
        if callbacks:
            c.tag_bind(btn_asc, "<Button-1>", lambda e, cb=callbacks["do_ascend"]: cb())
            c.tag_bind(txt_asc, "<Button-1>", lambda e, cb=callbacks["do_ascend"]: cb())

    # 途径切换
    compat_pathways = get_compatible_pathways(ch.PATHWAY_KEY)
    if compat_pathways:
        y += 40
        c.create_text(12, y, text=f"同组可切换途径：", anchor="nw",
                      font=fonts["tiny"], fill=CLR["text_dim"])
        y += 18
        for cpk in compat_pathways[:5]:
            cp = get_pathway(cpk)
            btn_sw = draw_rounded_rect(c, 10, y, 155, y+26, r=6,
                                       fill=CLR["panel_light"], outline=CLR["border"])
            txt_sw = c.create_text(82, y+13, text=f"⇄ {cp['name']}",
                                    font=fonts["small"], fill=CLR["text"])
            if callbacks:
                c.tag_bind(btn_sw, "<Button-1>", lambda e, t=cpk, cb=callbacks["do_switch"]: cb(t))
                c.tag_bind(txt_sw, "<Button-1>", lambda e, t=cpk, cb=callbacks["do_switch"]: cb(t))
            y += 30

    # ── 随机事件按钮 ──
    y += 8
    c.create_line(10, y, 320, y, fill=CLR["border"])
    y += 10
    btn_evt = draw_rounded_rect(c, 10, y, 155, y+28, r=6,
                                fill=CLR["accent2"], outline="")
    txt_evt = c.create_text(82, y+14, text="🎲 触发随机事件",
                             font=fonts["small"], fill="#fff")
    if callbacks:
        c.tag_bind(btn_evt, "<Button-1>", lambda e, cb=callbacks["do_random_event"]: cb())
        c.tag_bind(txt_evt, "<Button-1>", lambda e, cb=callbacks["do_random_event"]: cb())

    # ── 权柄收集 / 旧日晋升（高级机制）──
    y += 8
    c.create_line(10, y, 320, y, fill=CLR["border"])
    y += 10
    c.create_text(12, y, text="权柄收集 · 旧日晋升：", anchor="nw",
                  font=fonts["small"], fill=CLR["text_dim"])
    y += 22

    # 序列1 → 序列0：收集唯一性 + 3 份序列1
    if ch.LEVEL == 1:
        y = draw_collection_panel(c, y, state, callbacks)
    # 序列0 → 旧日：容纳源质 + 相邻途径唯一性
    elif ch.LEVEL == 0:
        y = draw_old_one_panel(c, y, state, callbacks)

    # 设置滚动区域
    c.configure(scrollregion=(0, 0, c.winfo_width() or 340, y + 12))


# ─── 操作逻辑 ───

def draw_collection_panel(canvas, y, state, callbacks=None) -> int:
    """绘制『权柄收集』面板（序列1 → 序列0 前置）"""
    c = canvas
    ch = state.character
    pk = ch.PATHWAY_KEY
    fonts = state.fonts
    u = get_pathway_uniqueness(pk)
    if u.owner is None:
        ustate = "空闲（待容纳）"
    elif u.owner is ch:
        ustate = "✔ 你已持有"
    else:
        rival = getattr(u.owner, "SEQUENCE_NAME", "未知")
        ustate = f"⚠ 被 {rival} 持有"
    owned = SequenceOneCharacteristic.owned_count(pk, ch)
    avail = SequenceOneCharacteristic.available_count(pk)

    c.create_text(14, y, text=f"唯一性：{ustate}", anchor="nw",
                  font=fonts["small"], fill=CLR["text"])
    y += 20
    c.create_text(14, y, text=f"序列1特性：你持有 {owned}/3（全局空闲 {avail}）",
                  anchor="nw", font=fonts["small"], fill=CLR["text"])
    y += 26

    # 争夺序列1特性
    btn1 = draw_rounded_rect(c, 10, y, 155, y+28, r=6, fill=CLR["accent2"], outline="")
    t1 = c.create_text(82, y+14, text="⚔ 争夺序列1特性",
                       font=fonts["small"], fill="#fff")
    if callbacks:
        c.tag_bind(btn1, "<Button-1>", lambda e, cb=callbacks["do_collect_seq1"]: cb())
        c.tag_bind(t1, "<Button-1>", lambda e, cb=callbacks["do_collect_seq1"]: cb())
    y += 34

    # 容纳唯一性
    btn2 = draw_rounded_rect(c, 10, y, 155, y+28, r=6, fill=CLR["accent3"], outline="")
    t2 = c.create_text(82, y+14, text="🔒 容纳唯一性",
                       font=fonts["small"], fill="#fff")
    if callbacks:
        c.tag_bind(btn2, "<Button-1>", lambda e, cb=callbacks["do_collect_uniqueness"]: cb())
        c.tag_bind(t2, "<Button-1>", lambda e, cb=callbacks["do_collect_uniqueness"]: cb())
    y += 38

    # 集齐后开放「聚合晋升序列0」
    if u.owner is ch and owned >= 3:
        btn3 = draw_rounded_rect(c, 10, y, 200, y+34, r=8,
                                 fill=CLR["gold_dim"], outline=CLR["gold"])
        t3 = c.create_text(110, y+17, text="⬆ 聚合 · 晋升序列0",
                           font=fonts["body"], fill=CLR["text_bright"])
        if callbacks:
            c.tag_bind(btn3, "<Button-1>", lambda e, cb=callbacks["do_ascend"]: cb())
            c.tag_bind(t3, "<Button-1>", lambda e, cb=callbacks["do_ascend"]: cb())
        y += 42
    else:
        c.create_text(14, y, text="※ 集齐 唯一性 + 3 序列1 后开放序列0晋升",
                      anchor="nw", font=fonts["tiny"], fill=CLR["text_dim"])
        y += 18
    return y


def draw_old_one_panel(canvas, y, state, callbacks=None) -> int:
    """绘制『旧日晋升』面板（序列0 → 旧日）"""
    c = canvas
    ch = state.character
    fonts = state.fonts
    gk = group_key_of(ch.PATHWAY_KEY)
    if not gk:
        c.create_text(14, y, text="⚠ 该途径不属于任何权柄体系，无法晋升旧日",
                      anchor="nw", font=fonts["small"], fill=CLR["accent2"])
        return y + 22
    req = OldOnePath.required_for_old_one(gk)
    is_pillar = gk in FOUR_PILLARS
    tier = "支柱级旧日" if is_pillar else "普通旧日"
    group_name = PATHWAY_GROUPS[gk]["name"]

    c.create_text(14, y, text=f"权柄体系：{group_name}", anchor="nw",
                  font=fonts["small"], fill=CLR["text"])
    y += 20
    c.create_text(14, y, text=f"源质：{req['source_quality']}（{tier}）", anchor="nw",
                  font=fonts["small"], fill=CLR["text"])
    y += 20
    c.create_text(14, y, text=f"需聚合 {len(req['pathways'])} 条途径的唯一性 + 各 3 份序列1",
                  anchor="nw", font=fonts["tiny"], fill=CLR["text_dim"])
    y += 22

    btn = draw_rounded_rect(c, 10, y, 210, y+34, r=8,
                            fill=CLR["gold_dim"], outline=CLR["gold"])
    t = c.create_text(115, y+17, text="🌟 容纳源质 · 晋升旧日",
                      font=fonts["body"], fill=CLR["text_bright"])
    if callbacks:
        c.tag_bind(btn, "<Button-1>", lambda e, cb=callbacks["do_promote_old_one"]: cb())
        c.tag_bind(t, "<Button-1>", lambda e, cb=callbacks["do_promote_old_one"]: cb())
    y += 40
    return y
