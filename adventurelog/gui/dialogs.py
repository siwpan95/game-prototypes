# -*- coding: utf-8 -*-
"""弹窗对话框 — 装备管理 / 技能配置 (暖色调)"""

import tkinter as tk
from tkinter import ttk
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.engine import GameEngine

BGP  = "#F5F0E6"
BGC  = "#FAF6EE"
TX   = "#2C1810"
TX2  = "#6B5D4F"
GOLD = "#B8860B"
BTN  = "#2A9D8F"
BTNT = "#FFFFFF"
DGR  = "#E76F51"


def open_equip_dialog(parent: tk.Tk, engine: "GameEngine", refresh_callback):
    from data.loader import get_loader
    loader = get_loader()

    win = tk.Toplevel(parent)
    win.title("装备管理")
    win.geometry("520x440")
    win.configure(bg=BGP)
    win.transient(parent)

    nb = ttk.Notebook(win)
    nb.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

    for i, a in enumerate(engine.party):
        f = tk.Frame(nb, bg=BGC)
        job = loader.jobs.get(a.job_key)
        race = loader.races.get(a.race_key)
        tab_text = f"{job.emoji if job else '?'} {a.name}"
        if a.dead or a.hp <= 0:
            tab_text += " 💀"
        nb.add(f, text=tab_text)

        if a.dead or a.hp <= 0:
            tk.Label(f, text="该冒险者已阵亡，需要旅店休息复活",
                     font=("Microsoft YaHei", 9), bg=BGC, fg=DGR).pack(pady=20)
            continue

        tk.Label(f, text="当前装备", font=("Microsoft YaHei", 11),
                 bg=BGC, fg=GOLD).pack(pady=4)

        for slot, slot_name in [("weapon", "武器"), ("armor", "防具"), ("shield", "盾牌"), ("accessory", "饰品")]:
            eq_name = a.equipment.get(slot)
            row = tk.Frame(f, bg=BGC)
            row.pack(fill=tk.X, padx=10, pady=2)
            if eq_name and eq_name in loader.equipment:
                eq = loader.equipment[eq_name]
                text = f"{slot_name}: {eq_name} ({eq.bonus_text()})"
                tk.Label(row, text=text, font=("Microsoft YaHei", 9),
                         bg=BGC, fg=TX).pack(side=tk.LEFT)
                btn = tk.Button(row, text="卸下", font=("Microsoft YaHei", 9),
                                bg=DGR, fg=BTNT, relief=tk.FLAT,
                                command=lambda s=slot, idx=i: _do_unequip(engine, idx, s, refresh_callback))
                btn.pack(side=tk.RIGHT)
            else:
                tk.Label(row, text=f"{slot_name}: (空)", font=("Microsoft YaHei", 9),
                         bg=BGC, fg=TX2).pack(side=tk.LEFT)

        tk.Label(f, text=f"背包 ({len(engine.inventory)}件)", font=("Microsoft YaHei", 11),
                 bg=BGC, fg=GOLD).pack(pady=(10, 4))

        if not engine.inventory:
            tk.Label(f, text="(空)", font=("Microsoft YaHei", 9),
                     bg=BGC, fg=TX2).pack()
        else:
            for item_name in engine.inventory:
                eq = loader.equipment.get(item_name)
                if eq is None:
                    continue
                row = tk.Frame(f, bg=BGC)
                row.pack(fill=tk.X, padx=10, pady=1)
                text = f"{item_name} ({eq.bonus_text()}) [{eq.slot}]"
                tk.Label(row, text=text, font=("Microsoft YaHei", 9),
                         bg=BGC, fg=TX).pack(side=tk.LEFT)
                btn = tk.Button(row, text="装备", font=("Microsoft YaHei", 9),
                                bg=BTN, fg=BTNT, relief=tk.FLAT,
                                command=lambda it=item_name, idx=i: _do_equip(engine, idx, it, refresh_callback))
                btn.pack(side=tk.RIGHT)


def _do_equip(engine, idx, item_name, refresh):
    if engine.equip(idx, item_name):
        refresh()


def _do_unequip(engine, idx, slot, refresh):
    if engine.unequip(idx, slot):
        refresh()


def open_skills_dialog(parent: tk.Tk, engine: "GameEngine", refresh_callback):
    from data.loader import get_loader
    loader = get_loader()

    win = tk.Toplevel(parent)
    win.title("技能配置")
    win.geometry("500x420")
    win.configure(bg=BGP)
    win.transient(parent)

    nb = ttk.Notebook(win)
    nb.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

    for i, a in enumerate(engine.party):
        f = tk.Frame(nb, bg=BGC)
        job = loader.jobs.get(a.job_key)
        tab_text = f"{job.emoji if job else '?'} {a.name}"
        nb.add(f, text=tab_text)

        tk.Label(f, text="当前技能:", font=("Microsoft YaHei", 11),
                 bg=BGC, fg=GOLD).pack(pady=4)
        if a.skills:
            for sk_name in a.skills:
                sk = loader.skills.get(sk_name)
                if sk:
                    tk.Label(f, text=f"  {sk_name} — {sk.desc} (MP:{sk.mp_cost} CD:{sk.cooldown})",
                             font=("Microsoft YaHei", 9), bg=BGC, fg=TX).pack(anchor=tk.W)
        else:
            tk.Label(f, text="  (无)", font=("Microsoft YaHei", 9),
                     bg=BGC, fg=TX2).pack(anchor=tk.W)

        tk.Label(f, text="可学技能 (最多4个):", font=("Microsoft YaHei", 11),
                 bg=BGC, fg=GOLD).pack(pady=(10, 4))

        have_blocked = False
        for sk_name, sk in loader.skills.items():
            if sk_name in a.skills:
                continue
            can, reason = sk.can_learn(a, a.job_key)

            row = tk.Frame(f, bg=BGC)
            row.pack(fill=tk.X, padx=10, pady=1)

            base = f"{sk_name} — {sk.desc} (MP:{sk.mp_cost} CD:{sk.cooldown})"
            if can:
                lbl_text = base
                lbl_fg = TX2
            else:
                lbl_text = f"{base}  ❌ {reason}"
                lbl_fg = "#999999"
                have_blocked = True

            tk.Label(row, text=lbl_text, font=("Microsoft YaHei", 8),
                     bg=BGC, fg=lbl_fg, justify=tk.LEFT, anchor=tk.W).pack(side=tk.LEFT, fill=tk.X, expand=True)

            if can:
                btn = tk.Button(row, text="学习", font=("Microsoft YaHei", 9),
                                bg=BTN, fg=BTNT, relief=tk.FLAT,
                                command=lambda n=sk_name, idx=i: _do_learn(engine, idx, n, refresh_callback))
                btn.pack(side=tk.RIGHT, padx=(4, 0))
            else:
                lb = tk.Label(row, text="不可学", font=("Microsoft YaHei", 8),
                              bg=BGC, fg="#BBBBBB")
                lb.pack(side=tk.RIGHT, padx=(4, 0))

        if have_blocked:
            tk.Label(f, text="❌ 灰色技能不满足学习条件", font=("Microsoft YaHei", 8),
                     bg=BGC, fg="#AAAAAA").pack(pady=(6, 0))


def _do_learn(engine, idx, skill_name, refresh):
    a = engine.party[idx]
    if skill_name in a.skills:
        return
    if len(a.skills) >= 4:
        from tkinter import messagebox
        messagebox.showwarning("提示", "最多只能学习4个技能！")
        return

    from data.loader import get_loader
    loader = get_loader()
    sk = loader.skills.get(skill_name)
    if not sk:
        return

    can, reason = sk.can_learn(a, a.job_key)
    if not can:
        from tkinter import messagebox
        messagebox.showwarning("无法学习", f"无法学习 {skill_name}：{reason}")
        return

    a.skills.append(skill_name)
    sk.reset_cd()
    refresh()
