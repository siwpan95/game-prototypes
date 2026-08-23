"""HUD 顶栏 - 信息面板 + 按钮栏。

监听 ViewModel 事件，实时刷新 分数/时间/剩余/连击/提示次数/洗牌次数。
按钮调用 vm 命令。
"""
from __future__ import annotations

import tkinter as tk
from typing import Callable

from alloy.utils.font import load_local_tk_font
from models.game_state import GameMode
from services.layouts import LayoutKind
from viewmodel.game_viewmodel import GameViewModel


class Hud:
    def __init__(self, parent: tk.Widget, vm: GameViewModel) -> None:
        self.vm = vm
        # 字体统一交给引擎字体工具加载（别名 simhei，由 alloy/fonts/ 托管）
        self.f = load_local_tk_font(10, name="simhei") or ("SimHei", 10)
        self.fb = load_local_tk_font(11, name="simhei", bold=True) or ("SimHei", 11, "bold")
        self.fbig = load_local_tk_font(18, name="simhei", bold=True) or ("SimHei", 18, "bold")

        self.frame = tk.Frame(parent, bg="#2d5016")
        self.frame.pack(fill=tk.X, padx=10, pady=8)

        self._build_stats()
        self._build_buttons()
        self._build_status()

        vm.add_listener(self._on_event)
        self._refresh()

    # ---- 统计面板 ------------------------------------------------
    def _build_stats(self) -> None:
        row = tk.Frame(self.frame, bg="#2d5016")
        row.pack(fill=tk.X)
        self.score_lbl = self._stat(row, "分数", "0", "#fc0")
        self.time_lbl = self._stat(row, "时间", "05:00", "#0cf")
        self.rem_lbl = self._stat(row, "剩余", "144", "#f90")
        self.combo_lbl = self._stat(row, "连击", "0", "#f66")
        self.hint_lbl = self._stat(row, "提示", "3", "#9f6")
        self.shuf_lbl = self._stat(row, "洗牌", "3", "#c9f")

    def _stat(self, parent, title, value, color):
        f = tk.Frame(parent, bg="#1a3009", bd=2, relief=tk.RAISED)
        f.pack(side=tk.LEFT, padx=5, pady=2)
        tk.Label(f, text=title, font=self.fb, bg="#1a3009", fg="white").pack(padx=10, pady=(3, 0))
        lbl = tk.Label(f, text=value, font=self.fbig, bg="#1a3009", fg=color)
        lbl.pack(padx=10, pady=(0, 3))
        return lbl

    # ---- 按钮 ----------------------------------------------------
    def _build_buttons(self) -> None:
        row = tk.Frame(self.frame, bg="#2d5016")
        row.pack(fill=tk.X, pady=(6, 0))
        cfg = dict(font=self.f, bg="#4a752c", fg="white", activebackground="#5a853c",
                   activeforeground="white", bd=2, relief=tk.RAISED, padx=8, pady=3)
        tk.Button(row, text="提示 (H)", command=self.vm.use_hint, **cfg).pack(side=tk.LEFT, padx=3)
        tk.Button(row, text="撤销 (Z)", command=self.vm.undo, **cfg).pack(side=tk.LEFT, padx=3)
        tk.Button(row, text="洗牌 (S)", command=self.vm.shuffle, **cfg).pack(side=tk.LEFT, padx=3)
        tk.Button(row, text="重开 (R)", command=self.vm.restart, **cfg).pack(side=tk.LEFT, padx=3)
        tk.Button(row, text="模式 (M)", command=self.vm.toggle_mode, **cfg).pack(side=tk.LEFT, padx=3)
        tk.Button(row, text="布局 (L)", command=self._cycle_layout, **cfg).pack(side=tk.LEFT, padx=3)
        tk.Button(row, text="暂停 (ESC)", command=self.vm.toggle_pause, **cfg).pack(side=tk.LEFT, padx=3)
        tk.Button(row, text="帮助 (?)", command=self._show_help,
                  bg="#4e2c8a", fg="white", activebackground="#5e3c9a",
                  activeforeground="white", bd=2, relief=tk.RAISED,
                  font=self.f, padx=8, pady=3).pack(side=tk.LEFT, padx=3)

    def _build_status(self) -> None:
        self.status = tk.Label(
            self.frame, text=f"麻将连连看 · {self._mode_status()}",
            font=self.f, bg="#1a3009", fg="white", anchor=tk.W,
        )
        self.status.pack(fill=tk.X, pady=(6, 0))

    def _mode_status(self) -> str:
        if self.vm.state.mode == GameMode.LINK:
            return "连连看 (平面布局)"
        names = {LayoutKind.TURTLE: "乌龟", LayoutKind.PYRAMID: "金字塔",
                 LayoutKind.RECTANGLE: "矩形"}
        return f"上海麻将 ({names.get(self.vm._layout, '自定义')})"

    # ---- 布局切换 ------------------------------------------------
    def _cycle_layout(self) -> None:
        if self.vm.state.mode == GameMode.LINK:
            self._flash("连连看为平面布局，无需切换")
            return
        cur = self.vm._layout
        order = [LayoutKind.TURTLE, LayoutKind.PYRAMID, LayoutKind.RECTANGLE]
        idx = order.index(cur) if cur in order else 0
        nxt = order[(idx + 1) % len(order)]
        self.vm.set_layout(nxt)
        names = {"turtle": "乌龟", "pyramid": "金字塔", "rectangle": "矩形"}
        self._flash(f"布局切换: {names[nxt.value]}")

    # ---- 事件刷新 ------------------------------------------------
    def _on_event(self, ev) -> None:
        if ev.type in ("new_game", "tick", "match", "undo", "shuffle", "hint",
                       "mode_changed", "pause", "resume"):
            self._refresh()
        if ev.type == "reject":
            self._flash(ev.data.get("reason", "无法选择"))
        elif ev.type == "match":
            bd = ev.data.get("breakdown")
            if bd:
                self._flash(f"+{bd.total}  {bd}")
        elif ev.type == "deadlock":
            self._flash("死局! 请洗牌或撤销")
        elif ev.type == "hint_empty":
            self._flash(ev.data.get("reason", "提示用尽"))
        elif ev.type == "shuffle_empty":
            self._flash("洗牌次数用尽")
        elif ev.type == "mode_changed":
            self._flash(f"已进入: {self._mode_status()}")
        elif ev.type == "pause":
            self._flash("已暂停")
        elif ev.type == "resume":
            self._flash("继续")

    def _refresh(self) -> None:
        st = self.vm.state
        self.score_lbl.config(text=str(st.score))
        # 时间
        if st.time_limit > 0:
            tl = int(st.time_left)
            m, s = divmod(tl, 60)
            self.time_lbl.config(text=f"{m:02d}:{s:02d}")
            self.time_lbl.config(fg="#f66" if tl <= 30 else "#0cf")
        else:
            self.time_lbl.config(text="∞")
        self.rem_lbl.config(text=str(st.remaining_tiles))
        self.combo_lbl.config(text=str(st.combo))
        self.hint_lbl.config(text=str(st.hints_left))
        self.shuf_lbl.config(text=str(st.shuffles_left))

    def _flash(self, msg: str) -> None:
        self.status.config(text=msg)

    # ---- 帮助 ----------------------------------------------------
    def _show_help(self) -> None:
        from tkinter import messagebox
        messagebox.showinfo("帮助", (
            "麻将连连看\n\n"
            "【上海麻将】(默认)\n"
            "· 目标: 配对消除全部 144 张牌\n"
            "· 自由牌: 上方无压 且 左右至少一侧露边\n"
            "· 配对: 同名牌; 季(春夏秋冬)任意互配; 花(梅兰菊竹)任意互配\n\n"
            "【连连看】[按 M 切换]\n"
            "· 单层平面布局, 任意两张牌均可先选\n"
            "· 两张相同牌(或同组季/花)若能用不超过 2 个拐弯的折线连通\n"
            "  (路径可绕到棋盘外侧空格), 即可消除\n"
            "· 提示 [H] 会直接标出一对可连通的牌\n\n"
            "· 布局 [L]: 上海麻将下可切换 乌龟 / 金字塔 / 矩形\n\n"
            "快捷键:\n"
            "  H 提示   Z 撤销   S 洗牌   R 重开\n"
            "  M 切模式  L 切布局  ESC 暂停  ? 帮助\n\n"
            "计分: 基础 10/对, 季花 +5, 连击 +2/级, 通关有时间奖励"
        ))
