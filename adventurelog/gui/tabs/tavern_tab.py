# -*- coding: utf-8 -*-
"""酒馆标签页 Mixin — 招募冒险者"""

import tkinter as tk
from tkinter import messagebox
import random

from core.config import (
    C_CONTENT_BG, C_TEXT, C_TEXT_LIGHT, C_TEXT_HINT, C_SECTION_TITLE,
    C_ROW_EVEN, C_ROW_ODD, C_ACCENT_TEAL, C_ACCENT_RED, C_GOLD,
    C_BTN_PRIMARY, C_BTN_PRIMARY_TEXT, C_BTN_DANGER, C_BTN_DANGER_TEXT,
    C_SELECTED_BG, FONT_LABEL, FONT_SMALL, FONT_TINY,
    MAX_PARTY_SIZE,
)
from data.loader import get_loader


class TavernTabMixin:
    """酒馆标签页：招募、解雇、掷骰预览"""

    def _build_tavern_tab(self):
        frame = tk.Frame(self.content_frame, bg=C_CONTENT_BG)
        self._tab_content["酒馆"] = frame

        # ---- 顶部标题 ----
        tk.Label(frame, text="🍺 酒馆 — 招募冒险者", font=FONT_LABEL,
                 bg=C_CONTENT_BG, fg=C_SECTION_TITLE).pack(anchor=tk.W, padx=16, pady=(12, 4))

        # 三栏布局
        cols = tk.Frame(frame, bg=C_CONTENT_BG)
        cols.pack(fill=tk.BOTH, expand=True, padx=16, pady=(4, 0))

        # 左栏: 职业列表
        left = tk.Frame(cols, bg=C_CONTENT_BG)
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        tk.Label(left, text="职业", font=FONT_SMALL, bg=C_CONTENT_BG,
                 fg=C_TEXT_LIGHT).pack(anchor=tk.W)
        self._job_list_frame = tk.Frame(left, bg=C_CONTENT_BG)
        self._job_list_frame.pack(fill=tk.BOTH, expand=True)

        # 中栏: 种族 + 属性预览
        mid = tk.Frame(cols, bg=C_CONTENT_BG, width=220)
        mid.pack(side=tk.LEFT, fill=tk.Y, padx=(8, 0))
        mid.pack_propagate(False)

        tk.Label(mid, text="种族", font=FONT_SMALL, bg=C_CONTENT_BG,
                 fg=C_TEXT_LIGHT).pack(anchor=tk.W)
        self._race_list_frame = tk.Frame(mid, bg=C_CONTENT_BG)
        self._race_list_frame.pack(fill=tk.X)

        # 属性预览
        tk.Label(mid, text="", font=FONT_TINY, bg=C_CONTENT_BG).pack(pady=2)  # spacer
        preview_frame = tk.Frame(mid, bg=C_CONTENT_BG)
        preview_frame.pack(fill=tk.X, pady=(4, 0))

        self._preview_vars = {}
        for attr in ["HP", "ATK", "DEF", "SPD", "MP", "TOTAL"]:
            row = tk.Frame(preview_frame, bg=C_CONTENT_BG)
            row.pack(fill=tk.X, pady=1)
            color = C_ACCENT_TEAL if attr != "TOTAL" else C_GOLD
            tk.Label(row, text=f"{attr}:", font=FONT_SMALL, bg=C_CONTENT_BG,
                     fg=C_TEXT_LIGHT, width=6, anchor=tk.E).pack(side=tk.LEFT)
            var = tk.StringVar(value="—")
            tk.Label(row, textvariable=var, font=("Consolas", 11, "bold"),
                     bg=C_CONTENT_BG, fg=color).pack(side=tk.LEFT, padx=(4, 0))
            self._preview_vars[attr] = var

        # 右栏: 招募操作 + 队伍
        right = tk.Frame(cols, bg=C_CONTENT_BG, width=200)
        right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(8, 0))

        name_row = tk.Frame(right, bg=C_CONTENT_BG)
        name_row.pack(fill=tk.X, pady=(0, 4))
        tk.Label(name_row, text="名字:", font=FONT_SMALL,
                 bg=C_CONTENT_BG, fg=C_TEXT_LIGHT).pack(side=tk.LEFT)
        self.recruit_name_var = tk.StringVar()
        name_entry = tk.Entry(name_row, textvariable=self.recruit_name_var,
                              font=FONT_SMALL, width=14)
        name_entry.pack(side=tk.LEFT, padx=(4, 0))

        btn_row = tk.Frame(right, bg=C_CONTENT_BG)
        btn_row.pack(fill=tk.X, pady=(4, 6))

        self._roll_btn = tk.Label(btn_row, text="🎲 重新掷骰",
                                   font=FONT_SMALL, bg="#555555",
                                   fg="white", padx=10, pady=4,
                                   cursor="hand2", relief=tk.FLAT)
        self._roll_btn.pack(side=tk.LEFT, padx=(0, 6))
        self._roll_btn.bind("<Button-1>", lambda e: self._do_roll())
        self._bind_hover(self._roll_btn, "#555555", "#777777")

        recruit_btn = tk.Label(btn_row, text="📜 招募",
                                font=FONT_SMALL, bg=C_BTN_PRIMARY,
                                fg=C_BTN_PRIMARY_TEXT, padx=10, pady=4,
                                cursor="hand2", relief=tk.FLAT)
        recruit_btn.pack(side=tk.LEFT)
        recruit_btn.bind("<Button-1>", lambda e: self._do_recruit())
        self._bind_hover(recruit_btn, C_BTN_PRIMARY, "#238B7E")

        tk.Label(right, text="当前队伍:", font=FONT_SMALL,
                 bg=C_CONTENT_BG, fg=C_TEXT_LIGHT).pack(anchor=tk.W, pady=(4, 2))
        self._tavern_party_frame = tk.Frame(right, bg=C_CONTENT_BG)
        self._tavern_party_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 0))

        # 存储选中状态
        self._selected_job = None
        self._selected_race = "人类"
        self._roll_seed = 0  # 掷骰种子
        self._job_radio_vars = {}
        self._race_radio_vars = {}

    def _refresh_tavern(self):
        """刷新酒馆"""
        loader = get_loader()

        # --- 重建职业列表 ---
        for w in self._job_list_frame.winfo_children():
            w.destroy()
        self._job_radio_vars.clear()

        job_keys = list(loader.jobs.keys())
        if not self._selected_job or self._selected_job not in loader.jobs:
            self._selected_job = job_keys[0] if job_keys else None

        for jk in job_keys:
            job = loader.jobs[jk]
            row = tk.Frame(self._job_list_frame, bg=C_CONTENT_BG, cursor="hand2")
            row.pack(fill=tk.X, pady=1)
            row.job_key = jk

            lbl = tk.Label(row, text=f"  {job.emoji} {job.name}",
                           font=FONT_SMALL, bg=C_CONTENT_BG, fg=C_TEXT,
                           anchor=tk.W, padx=8, pady=4)
            lbl.pack(fill=tk.X)

            row.bind("<Button-1>", lambda e, k=jk: self._select_job(k))
            lbl.bind("<Button-1>", lambda e, k=jk: self._select_job(k))
            self._job_radio_vars[jk] = (row, lbl)

        # --- 重建种族列表 ---
        for w in self._race_list_frame.winfo_children():
            w.destroy()
        self._race_radio_vars.clear()

        race_keys = list(loader.races.keys())
        if self._selected_race not in loader.races:
            self._selected_race = "人类" if "人类" in loader.races else race_keys[0]

        for rk in race_keys:
            race = loader.races[rk]
            row = tk.Frame(self._race_list_frame, bg=C_CONTENT_BG, cursor="hand2")
            row.pack(fill=tk.X, pady=1)
            row.race_key = rk

            # 简短种族信息
            mods = []
            if race.hp_mod: mods.append(f"HP{race.hp_mod:+d}")
            if race.atk_mod: mods.append(f"ATK{race.atk_mod:+d}")
            if race.mp_mod: mods.append(f"MP{race.mp_mod:+d}")
            mod_str = f" ({' '.join(mods)})" if mods else ""

            lbl = tk.Label(row, text=f"  {race.name}{mod_str}",
                           font=FONT_SMALL, bg=C_CONTENT_BG, fg=C_TEXT,
                           anchor=tk.W, padx=8, pady=4)
            lbl.pack(fill=tk.X)

            row.bind("<Button-1>", lambda e, k=rk: self._select_race(k))
            lbl.bind("<Button-1>", lambda e, k=rk: self._select_race(k))
            self._race_radio_vars[rk] = (row, lbl)

        # --- 更新队伍显示 ---
        for w in self._tavern_party_frame.winfo_children():
            w.destroy()

        if not self.engine.party:
            tk.Label(self._tavern_party_frame, text="(空) — 请招募冒险者！",
                     font=FONT_SMALL, bg=C_CONTENT_BG, fg=C_ACCENT_RED).pack(anchor=tk.W)
        else:
            tk.Label(self._tavern_party_frame, text=f"{len(self.engine.party)}/{MAX_PARTY_SIZE}人",
                     font=FONT_SMALL, bg=C_CONTENT_BG, fg=C_TEXT).pack(anchor=tk.W)
            for i, a in enumerate(self.engine.party):
                job = loader.jobs.get(a.job_key)
                row = tk.Frame(self._tavern_party_frame,
                               bg=C_ROW_EVEN if i % 2 == 0 else C_ROW_ODD)
                row.pack(fill=tk.X, pady=1)
                info = (f"  {job.emoji if job else '?'} {a.name}  |  "
                        f"{a.job_key} · {a.race_key}  Lv.{a.level}")
                tk.Label(row, text=info, font=FONT_SMALL, bg=row.cget("bg"),
                         fg=C_TEXT).pack(side=tk.LEFT, padx=8)

                dismiss_btn = tk.Label(row, text="解雇", font=FONT_TINY,
                                        bg=C_BTN_DANGER, fg=C_BTN_DANGER_TEXT,
                                        padx=6, cursor="hand2", relief=tk.FLAT)
                dismiss_btn.pack(side=tk.RIGHT, padx=6)
                dismiss_btn.bind("<Button-1>", lambda e, idx=i: self._do_dismiss(idx))
                self._bind_hover(dismiss_btn, C_BTN_DANGER, "#D65A3F")

        # --- 应用选中状态 ---
        self._apply_selection_styles()
        self._show_preview()

    def _select_job(self, job_key):
        self._selected_job = job_key
        self._apply_selection_styles()
        self._show_preview()

    def _select_race(self, race_key):
        self._selected_race = race_key
        self._apply_selection_styles()
        self._show_preview()

    def _apply_selection_styles(self):
        """更新职业/种族列表的选中样式"""
        for jk, (row, lbl) in self._job_radio_vars.items():
            if jk == self._selected_job:
                row.configure(bg=C_SELECTED_BG)
                lbl.configure(bg=C_SELECTED_BG, fg=C_ACCENT_TEAL)
            else:
                row.configure(bg=C_CONTENT_BG)
                lbl.configure(bg=C_CONTENT_BG, fg=C_TEXT)

        for rk, (row, lbl) in self._race_radio_vars.items():
            if rk == self._selected_race:
                row.configure(bg=C_SELECTED_BG)
                lbl.configure(bg=C_SELECTED_BG, fg=C_ACCENT_TEAL)
            else:
                row.configure(bg=C_CONTENT_BG)
                lbl.configure(bg=C_CONTENT_BG, fg=C_TEXT)

    def _show_preview(self):
        """显示选中职业+种族的组合属性"""
        loader = get_loader()
        job = loader.jobs.get(self._selected_job) if self._selected_job else None
        race = loader.races.get(self._selected_race)

        if job and race:
            base_hp = job.base_hp + race.hp_mod
            base_atk = job.base_atk + race.atk_mod
            base_def = job.base_def + race.def_mod
            base_spd = job.base_spd + race.spd_mod
            base_mp = 50 + race.mp_mod

            # 掷骰微调（±5%）
            random.seed(self._roll_seed)
            hp = base_hp + random.randint(-base_hp // 20, base_hp // 20)
            atk = base_atk + random.randint(-max(1, base_atk // 10), max(1, base_atk // 10))
            def_ = base_def + random.randint(-max(1, base_def // 10), max(1, base_def // 10))
            spd = base_spd + random.randint(-max(1, base_spd // 10), max(1, base_spd // 10))
            mp = base_mp + random.randint(-2, 2)
            total = hp + atk + def_ + spd + mp

            self._preview_vars["HP"].set(str(hp))
            self._preview_vars["ATK"].set(str(atk))
            self._preview_vars["DEF"].set(str(def_))
            self._preview_vars["SPD"].set(str(spd))
            self._preview_vars["MP"].set(str(mp))
            self._preview_vars["TOTAL"].set(str(total))
        else:
            for k in self._preview_vars:
                self._preview_vars[k].set("—")

    def _do_roll(self):
        """重新掷骰"""
        self._roll_seed = random.randint(0, 999999)
        self._show_preview()
        self._set_narrative("🎲 重新掷骰！命运之轮再次转动……")

    def _do_recruit(self):
        if self.engine.exploring:
            return
        name = self.recruit_name_var.get().strip()
        if not name:
            messagebox.showwarning("提示", "请输入冒险者的名字！")
            return
        if not self._selected_job:
            messagebox.showwarning("提示", "请选择职业！")
            return

        # 收集掷骰预览属性
        stat_overrides = {}
        try:
            hp_val = self._preview_vars.get("HP")
            atk_val = self._preview_vars.get("ATK")
            def_val = self._preview_vars.get("DEF")
            spd_val = self._preview_vars.get("SPD")
            mp_val = self._preview_vars.get("MP")
            if hp_val and hp_val.get() not in ("—", ""):
                stat_overrides["hp"] = int(hp_val.get())
            if atk_val and atk_val.get() not in ("—", ""):
                stat_overrides["atk"] = int(atk_val.get())
            if def_val and def_val.get() not in ("—", ""):
                stat_overrides["def"] = int(def_val.get())
            if spd_val and spd_val.get() not in ("—", ""):
                stat_overrides["spd"] = int(spd_val.get())
            if mp_val and mp_val.get() not in ("—", ""):
                stat_overrides["mp"] = int(mp_val.get())
        except (ValueError, AttributeError):
            stat_overrides = {}

        a = self.engine.recruit(name, self._selected_job, self._selected_race, stat_overrides)
        if a is None:
            messagebox.showwarning("提示", f"队伍已满（最多{MAX_PARTY_SIZE}人）！")
            return

        self._log(f"🍺 {name}（{self._selected_job}·{self._selected_race}）加入了队伍！", "header")
        self._set_narrative(f"{name} 加入了冒险队伍，新的传奇开始了！")
        self.recruit_name_var.set("")
        self._roll_seed = random.randint(0, 999999)
        self._refresh_tavern()
        self._refresh_all()

    def _do_dismiss(self, idx):
        if self.engine.exploring:
            return
        if idx < len(self.engine.party):
            name = self.engine.party[idx].name
            if messagebox.askyesno("确认", f"确定要解雇 {name} 吗？\n装备将自动卸下放入背包。"):
                self.engine.dismiss(idx)
                self._log(f"👋 {name} 离开了队伍。")
                self._set_narrative(f"{name} 离开了队伍，独自踏上了新的旅途。")
                self._refresh_tavern()
                self._refresh_all()
