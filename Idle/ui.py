"""
渲染层 — 三区布局：顶栏(纪元+HUD+标签) | 左商店+右面板 | 底栏(装备+声望)
使用本地思源黑体字体。
"""

import tkinter as tk
from tkinter import messagebox, simpledialog
import random
import time
from config import *
from fonts import get_font
from engine.fmt import fmt_num


class GameUI:
    def __init__(self, root: tk.Tk,
                 on_buy, on_click, on_skill, on_prestige, on_hero,
                 on_achievements, on_daily, on_daily_tasks,
                 on_hero_skill, on_golden_click,
                 on_stats, on_save, on_toggle_sound, on_import_done):
        self._on_buy = on_buy
        self._on_click = on_click
        self._on_skill = on_skill
        self._on_prestige = on_prestige
        self._on_hero = on_hero
        self._on_achievements = on_achievements
        self._on_daily = on_daily
        self._on_daily_tasks = on_daily_tasks
        self._on_hero_skill = on_hero_skill
        self._on_golden_click = on_golden_click
        self._on_stats = on_stats
        self._on_save = on_save
        self._on_toggle_sound = on_toggle_sound
        self._on_import_done = on_import_done
        self._active_category = "all"
        self.buy_mode = 1  # 购买数量模式：1 / 10 / 100 / "max"
        self._sound_on = False
        self._mode_btn_ids: dict = {}
        self._util_btn_ids: dict = {}

        self.floaters: list[list] = []

        # ========== 1. 顶栏 ==========
        self._build_top_bar(root)

        # ========== 2. 主体：左商店 + 右面板 ==========
        self._build_main_area(root)

        # ========== 3. 底栏 ==========
        self._build_bottom_bar(root)

        # 所有静态绘制
        self._draw_top_static()
        self._draw_panel_static()
        self._draw_bottom_static()

    # =========================== 构建结构 ===========================

    def _build_top_bar(self, root):
        self.top_cv = tk.Canvas(
            root, width=WINDOW_WIDTH, height=CANVAS_TOP_H,
            bg=COLOR_BG, highlightthickness=0
        )
        self.top_cv.pack(fill=tk.X)

    def _build_main_area(self, root):
        main_frame = tk.Frame(root, bg=COLOR_BG)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # 左：商店
        shop_frame = tk.Frame(main_frame, bg=COLOR_BG)
        shop_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.shop_scroll = tk.Scrollbar(shop_frame, orient=tk.VERTICAL)
        self.shop_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.shop_cv = tk.Canvas(
            shop_frame, bg=COLOR_PANEL, highlightthickness=0,
            yscrollcommand=self.shop_scroll.set
        )
        self.shop_cv.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.shop_scroll.config(command=self.shop_cv.yview)
        self.shop_cv.bind("<MouseWheel>", self._on_mousewheel)

        self._btn_items: dict = {}
        self._visible_keys: set = set()

        # 右：面板
        panel_frame = tk.Frame(main_frame, bg=COLOR_BG, width=PANEL_WIDTH)
        panel_frame.pack(side=tk.RIGHT, fill=tk.Y)
        panel_frame.pack_propagate(False)

        self.panel_cv = tk.Canvas(
            panel_frame, width=PANEL_WIDTH, bg=COLOR_BG, highlightthickness=0
        )
        self.panel_cv.pack(fill=tk.BOTH, expand=True)
        # 面板需要足够高度来画所有内容
        self.panel_cv.config(scrollregion=(0, 0, PANEL_WIDTH, HERO_PANEL_SCROLL_H))

    def _build_bottom_bar(self, root):
        self.bottom_cv = tk.Canvas(
            root, width=WINDOW_WIDTH, height=CANVAS_BOTTOM_H,
            bg="#0c0c1e", highlightthickness=0
        )
        self.bottom_cv.pack(fill=tk.X, side=tk.BOTTOM)

    # =========================== 顶栏绘制 ===========================

    def _draw_top_static(self):
        cv = self.top_cv

        # 纪元进度条
        cv.create_rectangle(
            ERA_BAR_X, ERA_BAR_Y, ERA_BAR_X + ERA_BAR_W, ERA_BAR_Y + ERA_BAR_H,
            fill=COLOR_ERA_BAR_BG, outline="", tags="era_bar_bg"
        )
        cv.create_rectangle(
            ERA_BAR_X, ERA_BAR_Y, ERA_BAR_X, ERA_BAR_Y + ERA_BAR_H,
            fill=COLOR_ERA_BAR_FILL, outline="", tags="era_bar_fill"
        )
        cv.create_text(
            ERA_BAR_X + ERA_BAR_W + 10, ERA_BAR_Y + ERA_BAR_H // 2,
            anchor="w", text="", fill=COLOR_ERA_LABEL,
            font=get_font(10, True), tags="era_label"
        )
        cv.create_text(
            ERA_BAR_X + ERA_BAR_W // 2, ERA_BAR_Y + ERA_BAR_H // 2,
            text="", fill=COLOR_ERA_TEXT, font=get_font(9), tags="era_text"
        )

        # 分类标签
        tab_keys = ["all", "click", "dps", "multiplier", "synergy", "utility", "golden"]
        self._tab_ids = {}
        for i, cat_key in enumerate(tab_keys):
            ci = CATEGORIES.get(cat_key, {"name": cat_key})
            tx = TABS_X + i * TAB_SPACING
            rect = cv.create_rectangle(
                tx, TABS_Y, tx + TAB_W, TABS_Y + TAB_H,
                fill=COLOR_TAB_INACTIVE, outline="",
                tags=(f"tab_{cat_key}", "tabs")
            )
            txt = cv.create_text(
                tx + TAB_W // 2, TABS_Y + TAB_H // 2,
                text=ci["name"], fill=COLOR_TAB_TEXT,
                font=get_font(9), tags=(f"tab_{cat_key}", "tabs")
            )
            self._tab_ids[cat_key] = (rect, txt)
            cv.tag_bind(f"tab_{cat_key}", "<Button-1>",
                        lambda e, k=cat_key: self._set_category(k))
        self._highlight_active_tab()

        # ---- P2：顶栏右侧 — 购买数量模式 + 实用按钮 ----
        mode_defs = [("×1", 1), ("×10", 10), ("×100", 100), ("Max", "max")]
        mx = 640
        for label, m in mode_defs:
            tag = f"mode_{m}"
            rect = cv.create_rectangle(
                mx, 6, mx + 44, 26, fill=COLOR_TAB_INACTIVE, outline="", tags=(tag,))
            txt = cv.create_text(
                mx + 22, 16, text=label, fill=COLOR_TAB_TEXT,
                font=get_font(9), tags=(tag,))
            self._mode_btn_ids[m] = (rect, txt)
            cv.tag_bind(tag, "<Button-1>", lambda e, mm=m: self.set_buy_mode(mm))
            mx += 46

        util_defs = [
            ("📊", self._on_stats), ("💾", self._on_save), ("🔊", self._toggle_sound_btn),
        ]
        ux = 842
        for icon, cb in util_defs:
            tag = f"util_{icon}"
            rect = cv.create_rectangle(
                ux, 6, ux + 30, 26, fill=COLOR_TAB_INACTIVE, outline="", tags=(tag,))
            txt = cv.create_text(
                ux + 15, 16, text=icon, fill=COLOR_TAB_TEXT,
                font=get_font(10), tags=(tag,))
            self._util_btn_ids[icon] = (rect, txt)
            cv.tag_bind(tag, "<Button-1>", lambda e, c=cb: c())
            ux += 34

        self.update_buy_mode()

    def update_era_bar(self, engine):
        era = engine.get_current_era()
        nxt = engine.get_next_era()
        p = engine.get_era_progress()
        w = int(ERA_BAR_W * p)
        self.top_cv.coords("era_bar_fill", ERA_BAR_X, ERA_BAR_Y, ERA_BAR_X + w, ERA_BAR_Y + ERA_BAR_H)
        if nxt:
            self.top_cv.itemconfig("era_label", text=f"{era['name']} → {nxt['name']}")
            self.top_cv.itemconfig("era_text", text=f"{p*100:.0f}%")
        else:
            self.top_cv.itemconfig("era_label", text=f"{era['name']} (最高)")
            self.top_cv.itemconfig("era_text", text="满级")

    def _set_category(self, cat_key: str):
        self._active_category = cat_key
        self._highlight_active_tab()

    def _highlight_active_tab(self):
        for cat_key, (rect, txt) in self._tab_ids.items():
            a = (cat_key == self._active_category)
            self.top_cv.itemconfig(rect, fill=COLOR_TAB_ACTIVE if a else COLOR_TAB_INACTIVE)
            self.top_cv.itemconfig(txt, fill="white" if a else COLOR_TAB_TEXT)

    def set_buy_mode(self, m):
        self.buy_mode = m
        self.update_buy_mode()

    def update_buy_mode(self):
        for m, (rect, txt) in self._mode_btn_ids.items():
            a = (m == self.buy_mode)
            self.top_cv.itemconfig(rect, fill=COLOR_TAB_ACTIVE if a else COLOR_TAB_INACTIVE)
            self.top_cv.itemconfig(txt, fill="white" if a else COLOR_TAB_TEXT)

    def _toggle_sound_btn(self):
        if self._on_toggle_sound:
            self._sound_on = self._on_toggle_sound()
            rect, txt = self._util_btn_ids.get("🔊", (None, None))
            if txt is not None:
                self.top_cv.itemconfig(txt, text="🔊" if self._sound_on else "🔇")

    # =========================== 右面板绘制 ===========================

    def _draw_panel_static(self):
        cv = self.panel_cv

        # Hero
        r = HERO_R
        cv.create_oval(
            HERO_CX - r, HERO_CY - r, HERO_CX + r, HERO_CY + r,
            fill=COLOR_HERO, outline="", tag="hero"
        )
        cv.create_text(HERO_CX, HERO_CY, text="英雄", fill="white",
                       font=get_font(14, True), tag="hero")
        cv.tag_bind("hero", "<Button-1>", self._on_click)
        cv.create_text(HERO_CX, HERO_CY + r + 12, text="",
                       fill=COLOR_GOLDEN_BTN, font=get_font(9, True),
                       tags="golden_timer")

        # 技能按钮（grid 布局）
        self._skill_btn_ids: dict = {}
        for i, sk in enumerate(SKILLS):
            col = i % SKILL_COLS
            row = i // SKILL_COLS
            sx = SKILL_X + col * (SKILL_W + SKILL_GAP_X)
            sy = SKILL_Y + row * (SKILL_H + SKILL_GAP_Y)
            rect = cv.create_rectangle(
                sx, sy, sx + SKILL_W, sy + SKILL_H,
                fill=COLOR_SKILL_COOLDOWN, outline="#555", width=1,
                tags=(f"skill_{sk['key']}", "skills")
            )
            txt = cv.create_text(
                sx + SKILL_W // 2, sy + SKILL_H // 2,
                text=f"{sk['icon']} {sk['name']}", fill="#888",
                font=get_font(8), tags=(f"skill_{sk['key']}", "skills")
            )
            self._skill_btn_ids[sk["key"]] = (rect, txt)
            cv.tag_bind(f"skill_{sk['key']}", "<Button-1>",
                        lambda e, k=sk["key"]: self._on_skill(k))

        # 英雄面板
        self._hero_btn_ids: dict = {}
        self._hero_skill_btn_ids: dict = {}
        for i, h in enumerate(HEROES):
            hy = HERO_PANEL_Y + i * HERO_PANEL_SPACING
            rect = cv.create_rectangle(
                HERO_PANEL_X, hy,
                HERO_PANEL_X + HERO_PANEL_W, hy + HERO_PANEL_H,
                fill="#1a1a3e", outline="#444", width=1,
                tags=(f"hero_{h['key']}", "hero_btns")
            )
            txt = cv.create_text(
                HERO_PANEL_X + 8, hy + HERO_PANEL_H // 2, anchor="w",
                text=f"{h['icon']} {h['name']}", fill="#666",
                font=get_font(9), tags=(f"hero_{h['key']}", "hero_btns")
            )
            self._hero_btn_ids[h["key"]] = (rect, txt, hy)
            cv.tag_bind(f"hero_{h['key']}", "<Button-1>",
                        lambda e, k=h["key"]: self._on_hero("upgrade", k))
            # 英雄主动技能按钮（行右侧）
            sx = HERO_PANEL_X + HERO_PANEL_W - HERO_PANEL_H + 2
            sk = h.get("active_skill")
            if sk:
                srect = cv.create_rectangle(
                    sx, hy + 2, sx + HERO_PANEL_H - 4, hy + HERO_PANEL_H - 2,
                    fill="#333355", outline="#555", width=1,
                    tags=(f"hskill_{h['key']}", "hskill_btns")
                )
                stxt = cv.create_text(
                    sx + (HERO_PANEL_H - 4) // 2, hy + HERO_PANEL_H // 2,
                    text=sk["icon"], fill="#888", font=get_font(9),
                    tags=(f"hskill_{h['key']}", "hskill_btns")
                )
                self._hero_skill_btn_ids[h["key"]] = (srect, stxt, sk)
                cv.tag_bind(f"hskill_{h['key']}", "<Button-1>",
                            lambda e, k=h["key"]: self._on_hero_skill(k))

        # 黄金按钮（默认隐藏，出现时显示在面板右上角）
        self._golden_btn = cv.create_oval(
            PANEL_WIDTH - 46, 8, PANEL_WIDTH - 10, 44,
            fill="#ffaa00", outline="#fff", width=2, state="hidden",
            tags=("golden_btn",)
        )
        self._golden_btn_txt = cv.create_text(
            PANEL_WIDTH - 28, 26, text="", fill="#000", font=get_font(13),
            state="hidden", tags=("golden_btn",)
        )
        cv.tag_bind("golden_btn", "<Button-1>", lambda e: self._on_golden_click())

        # 转生按钮
        cv.create_rectangle(
            PRESTIGE_X, PRESTIGE_Y,
            PRESTIGE_X + PRESTIGE_W, PRESTIGE_Y + PRESTIGE_H,
            fill=COLOR_PRESTIGE_BTN, outline="#fff", width=1,
            tags=("prestige_btn",)
        )
        cv.create_text(
            PRESTIGE_X + PRESTIGE_W // 2, PRESTIGE_Y + PRESTIGE_H // 2,
            text="转生", fill="#000", font=get_font(10, True),
            tags=("prestige_btn",)
        )
        cv.tag_bind("prestige_btn", "<Button-1>", lambda e: self._on_prestige())

    # =========================== 底栏绘制 ===========================

    def _draw_bottom_static(self):
        cv = self.bottom_cv
        cv.create_text(10, EQUIP_PANEL_Y + 2, anchor="w",
                       text="🎒", fill="#888", font=get_font(10),
                       tags="equip_label")

        # 成就 / 每日 / 日常任务 入口按钮
        cv.create_text(40, EQUIP_PANEL_Y + 2, anchor="w",
                       text="🏆", fill="#ffd369", font=get_font(12),
                       tags=("ach_btn",))
        cv.tag_bind("ach_btn", "<Button-1>", lambda e: self._on_achievements())
        cv.create_text(70, EQUIP_PANEL_Y + 2, anchor="w",
                       text="📅", fill="#10b981", font=get_font(12),
                       tags=("daily_btn",))
        cv.tag_bind("daily_btn", "<Button-1>", lambda e: self._on_daily())
        cv.create_text(100, EQUIP_PANEL_Y + 2, anchor="w",
                       text="📋", fill="#0ea5e9", font=get_font(12),
                       tags=("dailytask_btn",))
        cv.tag_bind("dailytask_btn", "<Button-1>", lambda e: self._on_daily_tasks())

        self._equip_tids: list = []
        self._prestige_status_tid: int = 0
        self._event_banner_tid: int = 0

    # =========================== 面板刷新 ===========================

    def update_skill_buttons(self, engine):
        cv = self.panel_cv
        for key, (rect, txt) in self._skill_btn_ids.items():
            cd = engine.get_skill_cooldown(key)
            ar = engine.get_skill_active_remaining(key)
            sk = engine.get_skill_info(key)
            era_ok = engine.is_era_unlocked(sk["era"]) if sk else False
            if not era_ok:
                c, l, tc = COLOR_LOCKED, f"🔒 {sk['name']}", COLOR_LOCKED_TEXT
            elif ar > 0:
                c, l, tc = COLOR_SKILL_ACTIVE, f"{sk['icon']} {int(ar)}s", "white"
            elif cd > 0:
                c, l, tc = COLOR_SKILL_COOLDOWN, f"{sk['icon']} {int(cd)}s", "#888"
            else:
                c, l, tc = COLOR_SKILL_READY, f"{sk['icon']} {sk['name']}", "white"
            cv.itemconfig(rect, fill=c)
            cv.itemconfig(txt, text=l, fill=tc)

    def update_hero_panel(self, engine):
        cv = self.panel_cv
        for key, (rect, txt, hy) in self._hero_btn_ids.items():
            hdef = engine.get_hero_info(key)
            hstate = engine.get_hero_state(key)
            lv = hstate["level"]
            if lv <= 0:
                cost = hdef["unlock_gold"]
                label = f"{hdef['icon']} {hdef['name']}  招募 {self._fmt_gold(cost)}"
                cf, ct = "#1a1a3e", "#888"
            else:
                cost = engine.get_hero_upgrade_cost(key)
                if lv >= hdef["max_level"]:
                    label = f"{hdef['icon']} {hdef['name']}  {lv}级 满级"
                    cf, ct = "#1a1a3e", "#ffd369"
                else:
                    label = f"{hdef['icon']} {hdef['name']}  {lv}级 → {self._fmt_gold(cost)}"
                    can = engine.state.gold >= cost
                    cf = COLOR_BTN_BG if can else "#1a1a3e"
                    ct = COLOR_BTN_TEXT if can else "#888"
            cv.itemconfig(rect, fill=cf)
            cv.itemconfig(txt, text=label, fill=ct)

    def update_hero_skill_buttons(self, engine):
        cv = self.panel_cv
        for key, (rect, txt, sk) in self._hero_skill_btn_ids.items():
            hstate = engine.get_hero_state(key)
            if hstate["level"] <= 0:
                cv.itemconfig(rect, fill="#222", outline="#333")
                cv.itemconfig(txt, text="🔒", fill="#444")
                continue
            cd = engine.get_hero_skill_cooldown(key)
            ar = engine.get_hero_skill_active_remaining(key)
            if ar > 0:
                c, t, tc = COLOR_SKILL_ACTIVE, f"{int(ar)}s", "white"
            elif cd > 0:
                c, t, tc = COLOR_SKILL_COOLDOWN, f"{int(cd)}s", "#888"
            else:
                c, t, tc = COLOR_SKILL_READY, sk["icon"], "white"
            cv.itemconfig(rect, fill=c)
            cv.itemconfig(txt, text=t, fill=tc)

    def update_golden_button(self, engine):
        cv = self.panel_cv
        if engine.golden_button_visible:
            cv.itemconfig(self._golden_btn, state="normal")
            cv.itemconfig(self._golden_btn_txt, state="normal")
            v = engine.golden_variant
            icon = v["icon"] if v else "✨"
            cv.itemconfig(self._golden_btn_txt, text=icon)
        else:
            cv.itemconfig(self._golden_btn, state="hidden")
            cv.itemconfig(self._golden_btn_txt, state="hidden")
        # 增益提示（含变体名/剩余）
        if engine.golden_buff_active and engine.golden_variant:
            vt = f"✨{engine.golden_variant['name']} {engine.golden_buff_remaining:.0f}s"
        else:
            vt = ""
        cv.itemconfig("golden_timer", text=vt)

    def update_event_banner(self, engine):
        cv = self.top_cv
        ev = engine.get_active_event()
        cv.delete("event_banner")
        if ev:
            cv.create_text(
                400, 30, anchor="w",
                text=f"🎊 {ev['icon']} {ev['name']} · {max(0,int(engine.state.event_remaining))}s",
                fill="#ffd369", font=get_font(10, True),
                tags="event_banner"
            )

    def update_golden_timer(self, remaining: float, active: bool):
        t = f"增益: {remaining:.0f}s" if active else ""
        self.panel_cv.itemconfig("golden_timer", text=t)

    # =========================== 装备底栏 ===========================

    def update_equipment_bar(self, engine):
        cv = self.bottom_cv
        for tid in self._equip_tids:
            cv.delete(tid)
        self._equip_tids = []

        eqs = engine.get_equipment()
        show = eqs[-EQUIP_MAX_SHOW:] if len(eqs) > EQUIP_MAX_SHOW else eqs
        slot_icon = {s["key"]: s["icon"] for s in EQUIPMENT_SLOTS}
        for i, eq in enumerate(show):
            ex = 30 + i * (EQUIP_ITEM_W + EQUIP_SPACING)
            icon = slot_icon.get(eq.get("slot", ""), "")
            aff = len(eq.get("affixes", []))
            label = f"{icon}{eq['name']} +{eq['bonus']}"
            if aff:
                label += f"·{aff}词"
            tid = cv.create_text(
                ex, EQUIP_PANEL_Y + 2, anchor="w",
                text=label,
                fill=eq["color"], font=get_font(8)
            )
            self._equip_tids.append(tid)

        pts = engine.state.prestige_points
        ch = engine.get_active_challenge()
        status = ""
        if ch:
            status = f"  |  {ch['name']}"
            if ch.get("time_limit"):
                status += f" {max(0,int(ch['time_limit']-(time.time()-engine.state.challenge_start_time)))}s"
        cv.delete("prestige_bottom")
        cv.create_text(
            WINDOW_WIDTH - 10, EQUIP_PANEL_Y + 2, anchor="e",
            text=f"声望: {pts}{status}", fill=COLOR_PRESTIGE_BTN,
            font=get_font(9, True), tags="prestige_bottom"
        )

    # =========================== HUD ===========================

    def draw_hud(self, gold: float, dps: float):
        cv = self.top_cv
        cv.create_text(HUD_X, HUD_Y_GOLD, anchor="nw",
                       text=f"金币：{self._fmt_gold(gold)}",
                       fill=COLOR_GOLD, font=get_font(13, True), tags="hud_gold")
        cv.create_text(HUD_X, HUD_Y_DPS, anchor="nw",
                       text=f"产出：{self._fmt_dps(dps)}/s",
                       fill=COLOR_DPS, font=get_font(10), tags="hud_dps")

    def refresh_hud(self, gold: float, dps: float):
        self.top_cv.itemconfig("hud_gold", text=f"金币：{self._fmt_gold(gold)}")
        self.top_cv.itemconfig("hud_dps", text=f"产出：{self._fmt_dps(dps)}/s")

    # =========================== 商店 ===========================

    def draw_shop_buttons(self, engine):
        self._clear_shop()
        visible = engine.get_visible_upgrades(self._active_category)
        self._visible_keys = {d.key for d in visible}
        h = max(len(visible) * SHOP_SPACING + SHOP_SCROLL_PADDING, 10)
        self.shop_cv.config(scrollregion=(0, 0, SHOP_W + SHOP_SCROLL_PADDING, h))
        for i, d in enumerate(visible):
            y = SHOP_Y0 + i * SHOP_SPACING
            qty = engine.state.upgrades.get(d.key, 0)
            cost = d.get_cost(qty)
            af = engine.state.gold >= cost
            ok = engine.check_prerequisite(d) and engine.is_era_unlocked(d.era)
            self._draw_one_btn(d.key, d, qty, cost, af, ok, y)

    def _draw_one_btn(self, key, d, qty, cost, af, ok, y):
        ci = CATEGORIES.get(d.category, {})
        cc = ci.get("color", COLOR_BTN_OUT)
        if not ok:
            fb, ft, oc = COLOR_LOCKED, COLOR_LOCKED_TEXT, "#444"
        elif af:
            fb, ft, oc = COLOR_BTN_BG, COLOR_BTN_TEXT, cc
        else:
            fb, ft, oc = "#2a2a3e", "#666", "#444"

        rect = self.shop_cv.create_rectangle(
            SHOP_X, y, SHOP_X + SHOP_W, y + SHOP_H,
            fill=fb, outline=oc, width=1,
            tags=(f"btn_{key}", "shop_btn")
        )
        label = self._make_btn_label(d, qty, cost)
        if not ok:
            label += f" [{d.era}]"
        txt = self.shop_cv.create_text(
            SHOP_X + SHOP_W // 2, y + SHOP_H // 2,
            text=label, fill=ft, font=get_font(9),
            tags=(f"txt_{key}", "shop_btn")
        )
        self.shop_cv.create_rectangle(
            SHOP_X, y, SHOP_X + 4, y + SHOP_H,
            fill=cc, outline="", tags="shop_btn"
        )
        self._btn_items[key] = (rect, txt)
        cb = lambda e, k=key: self._on_buy(k)
        self.shop_cv.tag_bind(f"btn_{key}", "<Button-1>", cb)
        self.shop_cv.tag_bind(f"txt_{key}", "<Button-1>", cb)

    def refresh_shop_buttons(self, engine):
        for key, (rect, txt) in list(self._btn_items.items()):
            d = engine.get_def(key)
            if d is None:
                continue
            qty = engine.state.upgrades.get(key, 0)
            cost = d.get_cost(qty)
            af = engine.state.gold >= cost
            ok = engine.check_prerequisite(d) and engine.is_era_unlocked(d.era)
            fb = COLOR_LOCKED if not ok else (COLOR_BTN_BG if af else "#2a2a3e")
            ft = COLOR_LOCKED_TEXT if not ok else (COLOR_BTN_TEXT if af else "#666")
            self.shop_cv.itemconfig(rect, fill=fb)
            label = self._make_btn_label(d, qty, cost)
            if not ok:
                label += f" [{d.era}]"
            self.shop_cv.itemconfig(txt, text=label, fill=ft)

    def refresh_shop_if_needed(self, engine):
        v = {d.key for d in engine.get_visible_upgrades(self._active_category)}
        if v != self._visible_keys:
            self.draw_shop_buttons(engine)

    # =========================== 浮动飘字 ===========================

    def spawn_float(self, text: str):
        x = FLOAT_BASE_X + random.randint(-FLOAT_OFFSET_RANGE, FLOAT_OFFSET_RANGE)
        tid = self.panel_cv.create_text(
            x, FLOAT_BASE_Y, text=text,
            fill=COLOR_FLOAT, font=get_font(11, True)
        )
        self.floaters.append([tid, 0.0, FLOAT_BASE_Y])

    def update_floaters(self, dt: float):
        for f in self.floaters[:]:
            f[1] += dt
            tid, age, by = f
            if age > FLOAT_LIFETIME:
                self.panel_cv.delete(tid)
                self.floaters.remove(f)
            else:
                self.panel_cv.coords(tid, self.panel_cv.coords(tid)[0], by - FLOAT_SPEED * age)

    # =========================== 对话框 ===========================

    def show_prestige_dialog(self, engine) -> bool:
        """转生预览对话框：展示可获声望与可购项，返回是否确认。"""
        pv = engine.get_prestige_preview()
        win = tk.Toplevel()
        win.title("转生预览")
        win.geometry("380x460")
        win.configure(bg=COLOR_BG)
        win.resizable(False, False)

        tk.Label(win, text="🔄 转生预览", bg=COLOR_BG, fg=COLOR_GOLD,
                 font=get_font(15, True)).pack(pady=(12, 2))

        ov = (f"当前声望:  {fmt_num(pv['current_points'])}\n"
              f"转生将获得:  {fmt_num(pv['gain'])}\n"
              f"转生后合计:  {fmt_num(pv['will_have'])}")
        tk.Label(win, text=ov, bg=COLOR_BG, fg="white",
                 font=get_font(11), justify="left").pack(pady=8)

        tk.Label(win, text="— 声望商店可购项 —", bg=COLOR_BG, fg=COLOR_GOLD,
                 font=get_font(11, True)).pack(pady=(4, 2))

        if pv["buyable"]:
            txt = tk.Text(win, bg=COLOR_PANEL, fg="white", relief="flat",
                          font=get_font(10), wrap="none", cursor="arrow",
                          height=12)
            txt.tag_config("ok", foreground="#10b981")
            txt.tag_config("no", foreground="#888888")
            sb = tk.Scrollbar(win, command=txt.yview)
            txt.configure(yscrollcommand=sb.set)
            for p in pv["buyable"]:
                tag = "ok" if p["affordable"] else "no"
                mark = "✔ " if p["affordable"] else "✖ "
                txt.insert("end", f"{mark}{p['name']}  —  {p['cost']} 声望\n", tag)
            txt.configure(state="disabled")
            txt.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(10, 0), pady=4)
            sb.pack(side=tk.RIGHT, fill=tk.Y, pady=4)
        else:
            tk.Label(win, text="（暂无更多可购项）", bg=COLOR_BG, fg="#888888",
                     font=get_font(10)).pack(pady=10)

        result = {"ok": False}

        def confirm():
            result["ok"] = True
            win.destroy()

        btns = tk.Frame(win, bg=COLOR_BG)
        btns.pack(pady=(6, 12))
        tk.Button(btns, text="取消", command=win.destroy,
                  bg="#444444", fg="white", font=get_font(11),
                  width=10, relief="flat").pack(side=tk.LEFT, padx=8)
        tk.Button(btns, text="确认转生", command=confirm,
                  bg=COLOR_GOLD, fg="#1a1a1a", font=get_font(11, True),
                  width=12, relief="flat").pack(side=tk.LEFT, padx=8)

        win.grab_set()
        win.wait_window()
        return result["ok"]

    def show_challenge_dialog(self, engine) -> str | None:
        chs = engine.get_challenges()
        lines = [f"{i+1}. {c['name']} (x{c.get('prestige_mult',1):.1f}) — {c['tip']}"
                 for i, c in enumerate(chs)]
        r = simpledialog.askstring("挑战",
            "\n".join(lines) + f"\n\n编号 (1-{len(chs)})：")
        if r and r.isdigit():
            i = int(r) - 1
            if 0 <= i < len(chs):
                return chs[i]["key"]
        return None

    def show_prestige_shop(self, engine):
        pus = engine.get_prestige_upgrades()
        lines = [f"  {p['name']}: {engine.state.prestige_upgrades.get(p['key'],0)}级/"
                 f"{p['max_level']} ({p['cost']}声望/级)" for p in pus]
        messagebox.showinfo("声望商店",
            f"声望: {engine.state.prestige_points}\n\n" + "\n".join(lines))

    # =========================== 成就面板 ===========================

    def show_achievements(self, engine):
        win = tk.Toplevel()
        win.title("成就")
        win.geometry("440x540")
        win.configure(bg=COLOR_BG)
        win.resizable(False, False)

        done, total = engine.achievement_progress()
        head = tk.Label(win, text=f"成就进度  {done}/{total}",
                        bg=COLOR_BG, fg=COLOR_GOLD, font=get_font(13, True))
        head.pack(pady=(10, 4))

        txt = tk.Text(win, bg=COLOR_PANEL, fg="white", relief="flat",
                      font=get_font(10), wrap="none", cursor="arrow")
        txt.tag_config("unlocked", foreground="#10b981")
        txt.tag_config("locked", foreground="#888888")
        txt.tag_config("reward", foreground="#ffd369")
        sb = tk.Scrollbar(win, command=txt.yview)
        txt.configure(yscrollcommand=sb.set)
        txt.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(10, 0), pady=6)
        sb.pack(side=tk.RIGHT, fill=tk.Y, pady=6)

        for a in engine.get_achievements():
            tag = "unlocked" if a["unlocked"] else "locked"
            mark = "✔ " if a["unlocked"] else "✖ "
            line = f"{mark}{a['icon']} {a['name']}  —  {a['desc']}\n"
            line += f"    奖励: {a['reward']}\n\n"
            txt.insert("end", line, tag)
        txt.configure(state="disabled")

    # =========================== 每日面板 ===========================

    def show_daily(self, engine):
        status = engine.get_daily_status()
        win = tk.Toplevel()
        win.title("每日奖励")
        win.geometry("360x240")
        win.configure(bg=COLOR_BG)
        win.resizable(False, False)

        tk.Label(win, text="📅 每日登录奖励", bg=COLOR_BG, fg=COLOR_GOLD,
                 font=get_font(13, True)).pack(pady=(12, 4))
        streak_lbl = tk.Label(win, text="", bg=COLOR_BG, fg="white",
                              font=get_font(12))
        streak_lbl.pack(pady=2)
        prev_lbl = tk.Label(win, text="", bg=COLOR_BG, fg="#aaa",
                            font=get_font(10))
        prev_lbl.pack(pady=2)

        def refresh():
            st = engine.get_daily_status()
            if st["claimed_today"]:
                streak_lbl.configure(text=f"今日已领取 · 连击 {st['streak']} 天")
            else:
                streak_lbl.configure(text=f"当前连击 {st['streak']} 天"
                                            f"（满 7 天额外 +1 声望）")
            prev_lbl.configure(
                text=f"下次领取约可得 {self._fmt_gold(st['preview'])} 金币"
            )
            btn.configure(state="disabled" if st["claimed_today"] else "normal")

        def claim():
            res = engine.claim_daily()
            if isinstance(res, str):
                messagebox.showinfo("每日奖励", res)
                return
            msg = (f"领取成功！连击 {res['streak']} 天\n"
                   f"获得 {self._fmt_gold(res['gold'])} 金币")
            if res["bonus_prestige"]:
                msg += "\n额外 +1 声望（满 7 天奖励）"
            messagebox.showinfo("每日奖励", msg)
            refresh()

        btn = tk.Button(win, text="领取", command=claim,
                        bg=COLOR_BTN_BG, fg="white", font=get_font(11, True),
                        activebackground="#0f3460", relief="flat", width=14)
        btn.pack(pady=10)
        refresh()

    # =========================== 日常任务面板 ===========================

    def show_daily_tasks(self, engine):
        win = tk.Toplevel()
        win.title("日常任务")
        win.geometry("420x460")
        win.configure(bg=COLOR_BG)
        win.resizable(False, False)

        tk.Label(win, text="📋 每日任务", bg=COLOR_BG, fg=COLOR_GOLD,
                 font=get_font(13, True)).pack(pady=(12, 2))
        tk.Label(win, text="每日 0 点刷新，完成后领取奖励", bg=COLOR_BG,
                 fg="#aaa", font=get_font(9)).pack(pady=(0, 6))

        frame = tk.Frame(win, bg=COLOR_BG)
        frame.pack(fill=tk.BOTH, expand=True, padx=10)

        def refresh():
            for w in list(frame.children.values()):
                w.destroy()
            for t in engine.get_daily_tasks():
                row = tk.Frame(frame, bg=COLOR_PANEL)
                row.pack(fill=tk.X, pady=3, padx=2)
                head = tk.Frame(row, bg=COLOR_PANEL)
                head.pack(fill=tk.X)
                mark = "✔" if t["claimed"] else ("✓" if t["complete"] else "○")
                tk.Label(head, text=f"{mark} {t['name']}", bg=COLOR_PANEL,
                         fg="#10b981" if t["claimed"] else "white",
                         font=get_font(11, True), anchor="w").pack(side=tk.LEFT)
                rw = t["reward"]
                rtxt = f"+{rw['value']}声望" if rw["type"] == "prestige" else f"+{rw['value']}金"
                tk.Label(head, text=rtxt, bg=COLOR_PANEL, fg=COLOR_GOLD,
                         font=get_font(9)).pack(side=tk.RIGHT)
                tk.Label(row, text=f"{t['desc']}  ({t['progress']}/{t['target']})",
                         bg=COLOR_PANEL, fg="#aaa", font=get_font(9),
                         anchor="w").pack(fill=tk.X)
                prog = tk.Frame(row, bg="#0c0c1e", height=6)
                prog.pack(fill=tk.X, pady=(2, 0))
                frac = min(1.0, t["progress"] / t["target"])
                tk.Frame(prog, bg=COLOR_SKILL_READY, width=int(380 * frac),
                         height=6).pack(side=tk.LEFT)
                if not t["claimed"]:
                    btxt = "领取" if t["complete"] else "未完成"
                    b = tk.Button(row, text=btxt, command=lambda k=t["key"]: do_claim(k),
                                 bg=COLOR_BTN_BG, fg="white", font=get_font(9),
                                 relief="flat", state="normal" if t["complete"] else "disabled")
                    b.pack(pady=(3, 0))

        def do_claim(key):
            res = engine.claim_daily_task(key)
            if isinstance(res, str):
                messagebox.showinfo("日常任务", res)
                return
            messagebox.showinfo("日常任务", f"完成「{res['name']}」！")
            refresh()

        refresh()

    def show_achievement_toast(self, name):
        win = tk.Toplevel()
        win.title("")
        win.overrideredirect(True)
        win.geometry("260x54")
        try:
            x = self.top_cv.winfo_rootx() + WINDOW_WIDTH // 2 - 130
            y = self.top_cv.winfo_rooty() + 80
            win.geometry(f"+{x}+{y}")
        except Exception:
            pass
        f = tk.Frame(win, bg="#1a1a3e", highlightbackground="#ffd369",
                     highlightthickness=1)
        f.pack(fill=tk.BOTH, expand=True)
        tk.Label(f, text="🏆 成就解锁", bg="#1a1a3e", fg="#ffd369",
                 font=get_font(11, True)).pack(pady=(4, 0))
        tk.Label(f, text=name, bg="#1a1a3e", fg="white",
                 font=get_font(12, True)).pack(pady=(2, 6))
        win.after(2600, win.destroy)

    # =========================== 统计面板 ===========================

    @staticmethod
    def _fmt_playtime(sec):
        sec = int(sec)
        h = sec // 3600
        m = (sec % 3600) // 60
        s = sec % 60
        if h:
            return f"{h}小时{m}分"
        if m:
            return f"{m}分{s}秒"
        return f"{s}秒"

    def show_stats(self, engine):
        s = engine.state
        win = tk.Toplevel()
        win.title("统计")
        win.geometry("360x430")
        win.configure(bg=COLOR_BG)
        win.resizable(False, False)

        tk.Label(win, text="📊 游戏统计", bg=COLOR_BG, fg=COLOR_GOLD,
                 font=get_font(13, True)).pack(pady=(12, 6))

        rows = [
            ("总点击", f"{s.stats['clicks']:,}"),
            ("游戏时长", self._fmt_playtime(s.play_time)),
            ("累计获得金币", self._fmt_gold(s.lifetime_gold)),
            ("历史总收益", self._fmt_gold(s.total_gold)),
            ("掉落装备", f"{s.stats['drops']:,}"),
            ("转生次数", f"{s.stats['prestiges']:,}"),
            ("完成挑战", f"{s.stats['challenges']:,}"),
            ("购买升级", f"{s.stats['total_upgrades']:,}"),
            ("声望点数", f"{s.prestige_points:,}"),
        ]
        f = tk.Frame(win, bg=COLOR_BG)
        f.pack(fill=tk.X, padx=16)
        for k, v in rows:
            r = tk.Frame(f, bg=COLOR_BG)
            r.pack(fill=tk.X, pady=2)
            tk.Label(r, text=k, bg=COLOR_BG, fg="#aaa", font=get_font(10),
                     anchor="w").pack(side=tk.LEFT)
            tk.Label(r, text=v, bg=COLOR_BG, fg="white", font=get_font(10, True),
                     anchor="e").pack(side=tk.RIGHT)

        head = tk.Frame(win, bg=COLOR_BG)
        head.pack(fill=tk.X, padx=16, pady=(10, 2))
        tk.Label(head, text="纪元首达", bg=COLOR_BG, fg=COLOR_GOLD,
                 font=get_font(11, True), anchor="w").pack(side=tk.LEFT)
        if s.era_first_times:
            for i, t in sorted(s.era_first_times.items()):
                if 0 <= i < len(ERAS):
                    r = tk.Frame(win, bg=COLOR_BG)
                    r.pack(fill=tk.X, padx=16)
                    tk.Label(r, text=ERAS[i]["name"], bg=COLOR_BG, fg="#aaa",
                             font=get_font(9), anchor="w").pack(side=tk.LEFT)
                    tk.Label(r, text=self._fmt_playtime(time.time() - t) + "前",
                             bg=COLOR_BG, fg="#888", font=get_font(9),
                             anchor="e").pack(side=tk.RIGHT)
        else:
            tk.Label(win, text="（尚无）", bg=COLOR_BG, fg="#666",
                     font=get_font(9)).pack(padx=16, anchor="w")

    # =========================== 存档导出/导入 ===========================

    def show_save_dialog(self, engine):
        win = tk.Toplevel()
        win.title("存档")
        win.geometry("420x340")
        win.configure(bg=COLOR_BG)
        win.resizable(False, False)

        tk.Label(win, text="💾 存档导出 / 导入", bg=COLOR_BG, fg=COLOR_GOLD,
                 font=get_font(13, True)).pack(pady=(12, 6))

        tk.Label(win, text="导出（复制下方字符串备份）", bg=COLOR_BG, fg="#aaa",
                 font=get_font(9)).pack(pady=(4, 2))
        exp = tk.Text(win, height=4, bg=COLOR_PANEL, fg="white",
                      font=get_font(9), wrap="none")
        exp.insert("end", engine.export_save())
        exp.configure(state="disabled")
        exp.pack(fill=tk.X, padx=16)

        def copy():
            try:
                win.clipboard_clear()
                win.clipboard_append(engine.export_save())
                messagebox.showinfo("存档", "已复制到剪贴板")
            except Exception:
                pass

        tk.Button(win, text="复制导出字符串", command=copy, bg=COLOR_BTN_BG,
                  fg="white", font=get_font(10), relief="flat").pack(pady=4)

        tk.Label(win, text="导入（粘贴上方字符串）", bg=COLOR_BG, fg="#aaa",
                 font=get_font(9)).pack(pady=(6, 2))
        imp = tk.Text(win, height=4, bg=COLOR_PANEL, fg="white",
                      font=get_font(9), wrap="none")
        imp.pack(fill=tk.X, padx=16)

        def do_import():
            txt = imp.get("1.0", "end").strip()
            if not txt:
                messagebox.showinfo("存档", "请粘贴导出字符串")
                return
            try:
                engine.import_save(txt)
                engine.save()
                messagebox.showinfo("存档", "导入成功！")
                if self._on_import_done:
                    self._on_import_done()
                win.destroy()
            except Exception as ex:
                messagebox.showinfo("存档", f"导入失败：{ex}")

        tk.Button(win, text="导入", command=do_import, bg=COLOR_BTN_BG,
                  fg="white", font=get_font(10), relief="flat").pack(pady=4)

    # =========================== 内部 ===========================

    def _clear_shop(self):
        self.shop_cv.delete("shop_btn")
        self._btn_items.clear()
        self._visible_keys.clear()

    def _make_btn_label(self, d, qty, cost):
        l = d.description_tpl.replace("{cost}", self._fmt_gold(cost))
        l = l.replace("{qty}", str(qty))
        if self.buy_mode != 1:
            l += f" ×{self.buy_mode}"
        if d.per_second > 0:
            l += f" (+{self._fmt_dps(d.per_second)}/s)"
            nxt = None
            for count, _ in MILESTONE_STEPS:
                if qty < count:
                    nxt = count
                    break
            l += f" 🎯{qty}/{nxt}" if nxt is not None else " 🎯MAX"
        return l

    def _on_mousewheel(self, event):
        self.shop_cv.yview_scroll(-1 * (event.delta // 120), "units")

    @staticmethod
    def _fmt_gold(v):
        return f"{int(v):,}" if v < 1e15 else GameUI._fmt_big(v)

    @staticmethod
    def _fmt_dps(v):
        return GameUI._fmt_big(v)

    @staticmethod
    def _fmt_big(v):
        if v < 1e15: return f"{int(v):,}"
        if v < 1e308: return f"{v:.1e}"
        q = 0
        while v > 1e308: q += 1; v //= 1e308
        b, s = f"{v:.1e}".split("e+")
        return f"{b}e+{GameUI._fmt_big(int(s)+308*q)}"
