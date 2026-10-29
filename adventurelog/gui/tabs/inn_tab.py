# -*- coding: utf-8 -*-
"""旅店标签页 Mixin — 角色状态 + 技能配置 + 休息"""

import tkinter as tk
from tkinter import ttk

from core.config import (
    C_CONTENT_BG, C_TEXT, C_TEXT_LIGHT, C_TEXT_HINT, C_SECTION_TITLE,
    C_ROW_EVEN, C_ROW_ODD, C_ACCENT_TEAL, C_ACCENT_RED, C_ACCENT_GREEN,
    C_SEPARATOR,
    C_BTN_NORMAL, C_BTN_HOVER, C_BTN_TEXT, C_BTN_PRIMARY, C_BTN_PRIMARY_TEXT,
    FONT_LABEL, FONT_SMALL, FONT_TINY,
    MAX_PARTY_SIZE, INN_COST,
)
from data.loader import get_loader
from gui import dialogs


class InnTabMixin:
    """旅店标签页：角色状态查看、技能配置、旅店休息"""

    def _build_inn_tab(self):
        frame = tk.Frame(self.content_frame, bg=C_CONTENT_BG)
        self._tab_content["旅店"] = frame

        tk.Label(frame, text="角色状态", font=FONT_LABEL,
                 bg=C_CONTENT_BG, fg=C_SECTION_TITLE).pack(anchor=tk.W, padx=16, pady=(12, 8))

        self._inn_char_frames = []
        for i in range(MAX_PARTY_SIZE):
            char_frame = tk.Frame(frame, bg=C_ROW_EVEN if i % 2 == 0 else C_ROW_ODD,
                                  relief=tk.FLAT, bd=0)
            char_frame.pack(fill=tk.X, padx=16, pady=2)
            self._inn_char_frames.append(char_frame)

        ttk.Separator(frame, orient=tk.HORIZONTAL).pack(fill=tk.X, padx=16, pady=10)

        skill_row = tk.Frame(frame, bg=C_CONTENT_BG)
        skill_row.pack(fill=tk.X, padx=16, pady=(0, 6))
        tk.Label(skill_row, text="配置冒险者的战术技能",
                 font=FONT_SMALL, bg=C_CONTENT_BG, fg=C_TEXT_LIGHT).pack(side=tk.LEFT)

        skill_btn = tk.Label(skill_row, text="  技能配置  ", font=("Microsoft YaHei", 10),
                              bg=C_BTN_NORMAL, fg=C_BTN_TEXT,
                              padx=12, pady=4, cursor="hand2", relief=tk.FLAT)
        skill_btn.pack(side=tk.RIGHT)
        skill_btn.bind("<Button-1>", lambda e: dialogs.open_skills_dialog(
            self.root, self.engine, self._refresh_all))
        self._bind_hover(skill_btn, C_BTN_NORMAL, C_BTN_HOVER)

        ttk.Separator(frame, orient=tk.HORIZONTAL).pack(fill=tk.X, padx=16, pady=6)

        rest_row = tk.Frame(frame, bg=C_CONTENT_BG)
        rest_row.pack(fill=tk.X, padx=16, pady=(4, 12))
        tk.Label(rest_row, text=f"旅店休息 — 消耗 {INN_COST}G，全恢复 HP / MP（包括复活）",
                 font=FONT_SMALL, bg=C_CONTENT_BG, fg=C_TEXT_LIGHT).pack(side=tk.LEFT)

        rest_btn = tk.Label(rest_row, text="  休息  ", font=("Microsoft YaHei", 11, "bold"),
                             bg=C_BTN_PRIMARY, fg=C_BTN_PRIMARY_TEXT,
                             padx=16, pady=6, cursor="hand2", relief=tk.FLAT)
        rest_btn.pack(side=tk.RIGHT)
        rest_btn.bind("<Button-1>", lambda e: self._inn_rest())
        self._bind_hover(rest_btn, C_BTN_PRIMARY, "#238B7E")

    def _refresh_inn(self):
        loader = get_loader()
        for i, f in enumerate(self._inn_char_frames):
            for w in f.winfo_children():
                w.destroy()
            if i >= len(self.engine.party):
                continue

            a = self.engine.party[i]
            job = loader.jobs.get(a.job_key)
            race = loader.races.get(a.race_key)
            job_emoji = job.emoji if job else "?"
            color = job.color if job else C_TEXT
            row_bg = C_ROW_EVEN if i % 2 == 0 else C_ROW_ODD
            f.configure(bg=row_bg)

            if a.dead:
                header = tk.Frame(f, bg=row_bg)
                header.pack(fill=tk.X, padx=10, pady=(6, 2))
                tk.Label(header, text=f"💀 {a.name} — 已阵亡",
                         font=FONT_LABEL, bg=row_bg, fg=C_ACCENT_RED).pack(side=tk.LEFT)
                tk.Label(header, text=f"{a.job_key} · {a.race_key}  Lv.{a.level}",
                         font=FONT_SMALL, bg=row_bg, fg=C_TEXT_LIGHT).pack(side=tk.RIGHT)
                tk.Label(f, text="需要旅店休息或复活卷轴复活", font=FONT_TINY,
                         bg=row_bg, fg=C_ACCENT_RED).pack(anchor=tk.W, padx=10, pady=(0, 6))
                continue

            header = tk.Frame(f, bg=row_bg)
            header.pack(fill=tk.X, padx=10, pady=(6, 2))
            tk.Label(header, text=f"{job_emoji}  {a.name}", font=FONT_LABEL,
                     bg=row_bg, fg=color).pack(side=tk.LEFT)
            tk.Label(header, text=f"{a.job_key} · {a.race_key}  Lv.{a.level}",
                     font=FONT_SMALL, bg=row_bg, fg=C_TEXT_LIGHT).pack(side=tk.RIGHT)

            stats = tk.Frame(f, bg=row_bg)
            stats.pack(fill=tk.X, padx=10, pady=(2, 6))

            full_hp = self.engine._full_hp(a)
            full_atk = self.engine.full_atk(a)
            full_def = self.engine.full_def(a)
            full_spd = self.engine.full_spd(a)

            stat_text = (f"HP: {a.hp}/{full_hp}    "
                         f"MP: {a.mp}/{a.max_mp}    "
                         f"ATK: {full_atk}    "
                         f"DEF: {full_def}    "
                         f"SPD: {full_spd}")
            tk.Label(stats, text=stat_text, font=FONT_SMALL,
                     bg=row_bg, fg=C_TEXT).pack(side=tk.LEFT)

            hp_pct = self.engine.hp_pct(a)
            bar_w = 180
            bar_frame = tk.Frame(f, bg=C_SEPARATOR, height=8, width=bar_w)
            bar_frame.pack(side=tk.RIGHT, padx=(0, 10), pady=6)
            bar_frame.pack_propagate(False)
            fill_color = (C_ACCENT_RED if hp_pct < 0.3 else
                          (C_ACCENT_GREEN if hp_pct > 0.7 else "#E9C46A"))
            tk.Frame(bar_frame, bg=fill_color, height=8,
                     width=int(bar_w * hp_pct)).pack(side=tk.LEFT)

            detail = tk.Frame(f, bg=row_bg)
            detail.pack(fill=tk.X, padx=10, pady=(0, 6))
            eq_parts = []
            for slot, label in [("weapon", "武器"), ("armor", "防具"), ("shield", "盾牌"), ("accessory", "饰品")]:
                eq_name = a.equipment.get(slot)
                if eq_name:
                    eq_parts.append(f"{label}: {eq_name}")
            eq_text = "  |  ".join(eq_parts) if eq_parts else "装备: (无)"
            tk.Label(detail, text=eq_text, font=FONT_TINY,
                     bg=row_bg, fg=C_TEXT_HINT).pack(side=tk.LEFT)
            if a.skills:
                tk.Label(detail, text="技能: " + " · ".join(a.skills), font=FONT_TINY,
                         bg=row_bg, fg=C_TEXT_HINT).pack(side=tk.RIGHT)

            if a.exp_to_next > 0:
                exp_pct = min(1.0, a.exp / a.exp_to_next)
                exp_frame = tk.Frame(f, bg=C_SEPARATOR, height=4, width=bar_w)
                exp_frame.pack(side=tk.RIGHT, padx=(0, 10), pady=(0, 6))
                exp_frame.pack_propagate(False)
                tk.Frame(exp_frame, bg="#7B2D8E", height=4,
                         width=int(bar_w * exp_pct)).pack(side=tk.LEFT)

    def _inn_rest(self):
        if self.engine.exploring:
            return
        if self.engine.inn_rest():
            self._log(f"💤 队伍在旅店休息，消耗 {INN_COST}G，HP/MP 全恢复！阵亡者已复活。")
            self._set_narrative("队伍在旅店洗去一身疲惫，重新精神抖擞。")
            self._switch_tab("旅店")
        else:
            self._log(f"金币不足！休息需要 {INN_COST}G")
        self._refresh_all()
