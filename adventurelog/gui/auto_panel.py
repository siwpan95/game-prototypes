# -*- coding: utf-8 -*-
"""
自动化状态面板 Mixin — 嵌入式管线进度条（非标签页）

参考 ProgressQuest 布局设计：
- 左侧：6阶段迷你进度条（始终可见）
- 标题栏集成：启停/速度控制按钮
- 底部状态栏：当前活动描述 + 主进度条（类似 PQ 的 "对战 X 年轻的 Y..."）
- 自动切换标签：运行时根据当前阶段自动跳转对应标签页
"""

import tkinter as tk
from tkinter import ttk
import time

from core.config import (
    C_CONTENT_BG, C_PANEL_BG, C_TEXT, C_TEXT_LIGHT, C_TEXT_HINT,
    C_GOLD, C_ACCENT_TEAL, C_ACCENT_RED, C_ACCENT_GREEN,
    C_BTN_PRIMARY, C_BTN_PRIMARY_TEXT,
    C_BTN_DANGER, C_BTN_DANGER_TEXT,
    C_BTN_NORMAL, C_BTN_HOVER, C_BTN_TEXT,
    C_TAB_BAR_BG, C_TAB_ACTIVE, C_TAB_INACTIVE, C_TAB_ACTIVE_TEXT,
    FONT_LABEL, FONT_SMALL, FONT_TINY, FONT_TAB,
)

from gui.progress_bar import (
    CanvasProgressBar, LOG_THEME, BATTLE_THEME,
    EXPLORE_THEME, REST_THEME, SHOP_THEME, RECRUIT_THEME,
)

# ---- 阶段配置 ----
SM_THEMES = {
    "SM_Recruit": RECRUIT_THEME,
    "SM_Shop": SHOP_THEME,
    "SM_Warehouse": RECRUIT_THEME,  # 仓库用棕色系
    "SM_Explore": EXPLORE_THEME,
    "SM_Rest": REST_THEME,
}

SM_ICONS = {
    "SM_Recruit": "🏠",
    "SM_Shop": "🛒",
    "SM_Warehouse": "📦",
    "SM_Explore": "⚔",
    "SM_Rest": "🏨",
}

SM_SHORT_LABELS = {
    "SM_Recruit": "招募",
    "SM_Shop": "购物",
    "SM_Warehouse": "仓库",
    "SM_Explore": "探索",
    "SM_Rest": "休息",
}

# 阶段→对应标签页映射
SM_TO_TAB = {
    "SM_Recruit": "酒馆",
    "SM_Shop": "商店",
    "SM_Warehouse": "仓库",
    "SM_Explore": "郊外",
    "SM_Rest": "旅店",
}


class AutoStatusMixin:
    """嵌入式自动化状态面板。

    不创建独立标签页，而是：
    - 在标题栏右侧嵌入控制按钮（启动/暂停/停止/速度）
    - 在左侧或顶部显示6个迷你进度条指示器
    - 底部增强状态栏：当前活动描述 + 大进度条
    - 运行时自动切换到对应标签页

    依赖宿主类 (ExplorationApp) 提供:
    - self.engine, self.root, self.content_frame, self._tab_content
    - self._log(), self._refresh_all(), _switch_tab(), _bind_hover()
    """

    # ==================== 构建嵌入式UI ====================
    def _build_auto_status_panel(self):
        """在主布局中构建嵌入式自动化面板组件（不含控制按钮，已由 _build_auto_controls 创建）"""

        # ====== 1. 管线迷你进度条区（左侧窄栏）======
        self._auto_sidebar = tk.Frame(self.root, bg="#D4C5A9", width=130)
        self._auto_sidebar.pack(side=tk.LEFT, fill=tk.Y)
        self._auto_sidebar.pack_propagate(False)

        tk.Label(
            self._auto_sidebar, text="自动化\n管线",
            font=("Microsoft YaHei", 8), bg="#D4C5A9", fg=C_TEXT_LIGHT,
            justify=tk.CENTER
        ).pack(pady=(4, 2))

        ttk.Separator(self._auto_sidebar, orient=tk.HORIZONTAL).pack(
            fill=tk.X, padx=4, pady=2)

        # 6个迷你进度条
        self._mini_progress_bars = {}
        self._mini_status_labels = {}

        for sm_name in ["SM_Recruit", "SM_Shop", "SM_Warehouse",
                        "SM_Explore", "SM_Rest"]:
            frame = tk.Frame(self._auto_sidebar, bg="#D4C5A9")
            frame.pack(fill=tk.X, padx=3, pady=1)

            icon = SM_ICONS.get(sm_name, "?")
            label = SM_SHORT_LABELS.get(sm_name, sm_name)

            lbl = tk.Label(frame, text=f"{icon} {label}",
                           font=("Microsoft YaHei", 7),
                           bg="#D4C5A9", fg=C_TEXT_HINT, anchor=tk.W)
            lbl.pack(fill=tk.X)

            self._mini_status_labels[sm_name] = lbl

            # 迷你 Canvas 进度条
            mini_canvas = tk.Canvas(frame, width=120, height=10,
                                    bg="#E8DCC8", highlightthickness=0)
            mini_canvas.pack(pady=1)

            rect = mini_canvas.create_rectangle(0, 0, 0, 10, fill="#BDB09A", outline="")
            pct_text = mini_canvas.create_text(60, 5, text="",
                                               font=("Consolas", 6), fill=C_TEXT_HINT)

            self._mini_progress_bars[sm_name] = {
                "canvas": mini_canvas, "rect": rect, "text": pct_text,
                "frame": frame, "label": lbl,
            }

        # ====== 2. 分隔线 ======
        ttk.Separator(self._auto_sidebar, orient=tk.HORIZONTAL).pack(
            fill=tk.X, padx=4, pady=4)

        # 统计信息（紧凑）
        self._auto_stats_var = tk.StringVar(value="就绪")
        stats_lbl = tk.Label(
            self._auto_sidebar, textvariable=self._auto_stats_var,
            font=("Microsoft YaHei", 7), bg="#D4C5A9", fg=C_TEXT_LIGHT,
            justify=tk.CENTER, wraplength=118
        )
        stats_lbl.pack(pady=2)

        # ====== 3. 标题栏控制按钮注入 ======
        try:
            self._build_auto_controls()
        except Exception:
            self._ctrl_frame = None

        # ====== 4. 底部增强状态栏 ======
        self._build_auto_bottom_bar()

        # ====== 5. 日志面板引用（延迟）=====
        self.auto_engine = None
        self._auto_log_widget = None

    def _build_auto_controls(self):
        """在标题栏右侧嵌入自动化控制按钮"""
        # 控制按钮容器（将在 title_bar 中 pack）
        self._ctrl_frame = tk.Frame(self.root, bg=C_PANEL_BG)
        # 不直接 pack，由调用者在合适位置放置
        # 这里先创建控件，后续在 app.py 中 pack 到 title_bar 右侧

        self._auto_btn_start = tk.Label(
            self._ctrl_frame, text=" ▶自动 ",
            font=("Microsoft YaHei", 9, "bold"),
            bg=C_BTN_PRIMARY, fg=C_BTN_PRIMARY_TEXT,
            padx=8, pady=3, cursor="hand2", relief=tk.FLAT
        )
        self._auto_btn_start.pack(side=tk.LEFT, padx=(0, 3))
        self._auto_btn_start.bind("<Button-1>", lambda e: self._auto_start())
        self._bind_hover(self._auto_btn_start, C_BTN_PRIMARY, "#238B7E")

        self._auto_btn_pause = tk.Label(
            self._ctrl_frame, text=" ⏸ ",
            font=("Microsoft YaHei", 9, "bold"),
            bg=C_BTN_NORMAL, fg=C_BTN_TEXT,
            padx=6, pady=3, cursor="hand2", relief=tk.FLAT
        )
        self._auto_btn_pause.pack(side=tk.LEFT, padx=(0, 3))
        self._auto_btn_pause.bind("<Button-1>", lambda e: self._auto_pause_resume())
        self._bind_hover(self._auto_btn_pause, C_BTN_NORMAL, C_BTN_HOVER)

        self._auto_btn_stop = tk.Label(
            self._ctrl_frame, text=" ⏹ ",
            font=("Microsoft YaHei", 9, "bold"),
            bg=C_BTN_DANGER, fg=C_BTN_DANGER_TEXT,
            padx=6, pady=3, cursor="hand2", relief=tk.FLAT
        )
        self._auto_btn_stop.pack(side=tk.LEFT, padx=(0, 6))
        self._auto_btn_stop.bind("<Button-1>", lambda e: self._auto_stop())
        self._bind_hover(self._auto_btn_stop, C_BTN_DANGER, "#C0392B")

        # 速度
        tk.Label(self._ctrl_frame, text="速:",
                 font=("Microsoft YaHei", 8), bg=C_PANEL_BG,
                 fg=C_TEXT_HINT).pack(side=tk.LEFT)

        self._auto_speed_btns = {}
        for label, mult in [("1×", 0.5), ("2×", 1.0), ("5×", 2.0)]:
            b = tk.Label(self._ctrl_frame, text=label,
                         font=("Consolas", 8, "bold"),
                         bg=C_BTN_NORMAL, fg=C_BTN_TEXT,
                         padx=4, pady=2, cursor="hand2", relief=tk.FLAT)
            b.pack(side=tk.LEFT, padx=1)
            b.bind("<Button-1>", lambda e, m=mult: self._auto_set_speed(m))
            self._bind_hover(b, C_BTN_NORMAL, C_BTN_HOVER)
            self._auto_speed_btns[mult] = b
        self._auto_speed = 1.0
        self._highlight_speed_btn(1.0)

    def _bind_hover(self, widget, normal_bg, hover_bg):
        """绑定 tkinter Label 控件的鼠标悬停背景色切换"""
        def _on_enter(e, w=widget, h=hover_bg):
            w.configure(bg=h)
        def _on_leave(e, w=widget, n=normal_bg):
            w.configure(bg=n)
        widget.bind("<Enter>", _on_enter)
        widget.bind("<Leave>", _on_leave)

    def _build_auto_bottom_bar(self):
        """构建底部增强状态栏（类似 ProgressQuest 的底部活动条）"""
        # 替换原有的简单 bottom_bar 为增强版
        self._auto_bottom_frame = tk.Frame(self.root, bg="#C4B998")
        self._auto_bottom_frame.pack(fill=tk.X, side=tk.BOTTOM)
        self._auto_bottom_frame.pack_propagate(False)

        # 上半部分：当前活动文字
        top_row = tk.Frame(self._auto_bottom_frame, bg="#C4B998")
        top_row.pack(fill=tk.X, padx=8, pady=(4, 0))

        self._auto_activity_var = tk.StringVar(value="准备开始冒险……")
        tk.Label(top_row, textvariable=self._auto_activity_var,
                 font=("Microsoft YaHei", 9),
                 bg="#C4B998", fg=C_TEXT).pack(side=tk.LEFT)

        # 下半部分：大进度条
        bar_row = tk.Frame(self._auto_bottom_frame, bg="#C4B998")
        bar_row.pack(fill=tk.X, padx=8, pady=(2, 4))

        self._main_progress_canvas = tk.Canvas(
            bar_row, height=16, bg="#E8DCC8",
            highlightthickness=1, highlightbackground="#8B7355"
        )
        self._main_progress_canvas.pack(fill=tk.X)

        w_ref = [500]  # 将在渲染后更新实际宽度
        self._main_bar_rect = self._main_progress_canvas.create_rectangle(
            0, 0, 0, 16, fill=C_ACCENT_TEAL, outline=""
        )
        self._main_pct_text = self._main_progress_canvas.create_text(
            250, 8, text="", font=("Consolas", 8, "bold"), fill="#FFFFFF"
        )

        def _on_configure(evt):
            w = evt.width
            w_ref[0] = w
            self._main_progress_canvas.coords(self._main_pct_text, w // 2, 8)
            self._update_main_progress()

        self._main_progress_canvas.bind("<Configure>", _on_configure)
        self._main_bar_width_ref = w_ref

        # 统计文字（右下角）
        self._auto_bottom_stat_var = tk.StringVar(
            value="击杀:0 | 宝物:0 | 循环:0"
        )
        tk.Label(bar_row, textvariable=self._auto_bottom_stat_var,
                 font=("Consolas", 7), bg="#C4B998",
                 fg=C_TEXT_HINT).pack(side=tk.RIGHT, padx=(4, 0))

    # ==================== 迷你进度条更新 ====================
    def _set_mini_progress(self, sm_name: str, pct: int, status: str = ""):
        """更新左侧迷你进度条"""
        if sm_name not in self._mini_progress_bars:
            return
        mb = self._mini_progress_bars[sm_name]
        canvas = mb["canvas"]
        rect = mb["rect"]
        txt = mb["text"]
        lbl = mb["label"]
        cw = canvas.winfo_width() or 120
        ch = 10

        fill_w = max(0, min(cw, int(cw * pct / 100)))
        canvas.coords(rect, 0, 0, fill_w, ch)
        canvas.itemconfig(txt, text=f"{pct}%" if pct > 0 else "")

        # 高亮当前活动的
        theme = SM_THEMES.get(sm_name, LOG_THEME)
        is_active = (hasattr(self, 'auto_engine') and
                     self.auto_engine and
                     self.auto_engine.current_sm_name == sm_name)
        if is_active:
            canvas.configure(bg=theme.bg_color)
            mb["frame"].configure(bg=theme.bar_color)
            lbl.configure(bg=theme.bar_color, fg="#FFFFFF")
        else:
            canvas.configure(bg="#E8DCC8")
            mb["frame"].configure(bg="#D4C5A9")
            lbl.configure(bg="#D4C5A9", fg=(
                C_TEXT if pct >= 100 else C_TEXT_HINT
            ))

        if status:
            pass  # 可扩展 tooltip

    def _reset_all_mini(self):
        """重置所有迷你进度条"""
        for sm_name in self._mini_progress_bars:
            self._set_mini_progress(sm_name, 0)

    # ==================== 主进度条更新 ====================
    def _update_main_progress(self):
        """更新底部大进度条"""
        if not hasattr(self, '_main_progress_canvas'):
            return
        try:
            w = self._main_bar_width_ref[0]
            if not w:
                return
            pct = self._main_progress_value if hasattr(self, '_main_progress_value') else 0
            fill_w = max(0, min(w, int(w * pct / 100)))
            self._main_progress_canvas.coords(
                self._main_bar_rect, 0, 0, fill_w, 16
            )
            color = C_ACCENT_GREEN if pct >= 80 else C_ACCENT_TEAL
            self._main_progress_canvas.itemconfig(self._main_bar_rect, fill=color)
            self._main_progress_canvas.itemconfig(
                self._main_pct_text, text=f"{int(pct)}%"
            )
        except Exception:
            pass

    def _set_main_progress(self, pct: float, activity: str = ""):
        """设置底部主进度条和活动文字"""
        self._main_progress_value = pct
        self._update_main_progress()
        if activity:
            self._auto_activity_var.set(activity)

    # ==================== 控制逻辑 ====================
    def _auto_start(self):
        """启动自动化"""
        if self.engine is None:
            return
        if not hasattr(self, '_auto_btn_start') or self._auto_btn_start is None:
            return

        if not self.engine.party and self.engine.gold < 100:
            self.engine.gold = 200

        from core.auto_engine import AutoEngine

        self.auto_engine = AutoEngine(self)

        # 注入迷你进度条更新回调
        self.auto_engine.progress_bars = self._mini_progress_bars

        # 创建日志 Text 控件
        self._create_auto_log()

        self._reset_all_mini()
        self._set_main_progress(0, "初始化管线…")

        # 启动引擎
        self.auto_engine.start()
        self._auto_update_loop()

        # 按钮状态
        try:
            self._auto_btn_start.configure(text=" ●运行 ", fg=C_TEXT_HINT)
            self._auto_btn_start.unbind("<Button-1>")
            self._auto_btn_start.configure(cursor="arrow")
        except Exception:
            pass

    def _auto_stop(self):
        """停止自动化"""
        if self.auto_engine:
            self.auto_engine.stop()

        if hasattr(self, '_auto_btn_start') and self._auto_btn_start is not None:
            try:
                self._auto_btn_start.configure(text=" ▶自动 ",
                                               fg=C_BTN_PRIMARY_TEXT, cursor="hand2")
                self._auto_btn_start.bind("<Button-1>", lambda e: self._auto_start())
            except Exception:
                pass
        if hasattr(self, '_auto_btn_pause') and self._auto_btn_pause is not None:
            try:
                self._auto_btn_pause.configure(text=" ⏸ ")
            except Exception:
                pass
        self._set_main_progress(0, "已停止")
        if hasattr(self, '_auto_stats_var'):
            self._auto_stats_var.set("已停止")

    def _auto_pause_resume(self):
        """暂停/恢复"""
        if not self.auto_engine:
            return
        paused = self.auto_engine.pause_resume()
        if hasattr(self, '_auto_btn_pause') and self._auto_btn_pause is not None:
            try:
                if paused:
                    self._auto_btn_pause.configure(text=" ▶续 ",
                                                   bg=C_ACCENT_GREEN, fg="#FFFFFF")
                    self._auto_activity_var.set("已暂停")
                else:
                    self._auto_btn_pause.configure(text=" ⏸ ",
                                                   bg=C_BTN_NORMAL, fg=C_BTN_TEXT)
            except Exception:
                pass

    def _auto_set_speed(self, multiplier: float):
        self._auto_speed = multiplier
        self._highlight_speed_btn(multiplier)
        if self.auto_engine and self.auto_engine.running:
            self.auto_engine.set_speed(multiplier)

    def _highlight_speed_btn(self, multiplier: float):
        for mult, btn in self._auto_speed_btns.items():
            if mult == multiplier:
                btn.configure(bg=C_ACCENT_TEAL, fg="#FFFFFF")
            else:
                btn.configure(bg=C_BTN_NORMAL, fg=C_BTN_TEXT)

    # ==================== 日志 ====================
    def _create_auto_log(self):
        """创建自动化日志控件（隐藏式，仅用于记录）"""
        log_frame = tk.Frame(self.root, bd=0)
        # 不显示，纯后台记录用
        self._auto_log_text = tk.Text(
            log_frame, wrap=tk.WORD, font=("Consolas", 8),
            bg="#1E1E1E", fg="#D4D4D4",
            state=tk.DISABLED, height=1, width=1
        )
        self._auto_log_text.tag_configure("auto_start", foreground="#6A9955")
        self._auto_log_text.tag_configure("auto_stop", foreground="#F44747")
        self._auto_log_text.tag_configure("auto_loop", foreground="#569CD6")
        self._auto_log_text.tag_configure("auto_action", foreground="#808080")
        self._auto_log_text.tag_configure("auto_battle", foreground="#DCDCAA")
        self._auto_log_text.tag_configure("auto_highlight", foreground="#4EC9B0")

    # ==================== 定时更新循环 ====================
    def _auto_update_loop(self):
        """定时刷新所有状态显示"""
        if not self.auto_engine or not self.auto_engine.running:
            return

        engine = self.auto_engine

        # 更新左侧迷你进度条
        for sm_name, sm in engine.state_machines.items():
            # 计算该阶段完成百分比
            total_states = len(sm.states)
            finished_states = sum(
                1 for s in sm.states.values()
                if sm.current_state_id == s.get("_final_marker", "")
            )  # 简化：只看是否终态
            if sm.is_finished:
                self._set_mini_progress(sm_name, 100)
            elif engine.current_sm_name == sm_name:
                # 当前正在执行的阶段——从 progress_bar 取值
                bar = engine.progress_bars.get(sm_name)
                if bar and hasattr(bar, 'progress'):
                    self._set_mini_progress(sm_name, int(bar.progress))
            elif sm.current_state_id != list(sm.states.keys())[0]:
                self._set_mini_progress(sm_name, 50)  # 已开始但未完成
            else:
                self._set_mini_progress(sm_name, 0)  # 未开始

        # 高亮当前阶段
        current = engine.current_sm_name
        if current:
            self._set_mini_progress(current,
                                     self._main_progress_value if hasattr(self, '_main_progress_value') else 0)

        # 更新统计
        if engine.paused:
            self._auto_stats_var.set(f"已暂停\n循环:{engine.loop_count}")
        else:
            stats = engine.get_stats()
            self._auto_stats_var.set(
                f"循环:{stats['loop_count']}\n"
                f"战斗:{stats['total_battles']}\n"
                f"金币:{stats['gold']}G"
            )
            self._auto_bottom_stat_var.set(
                f"击杀:{self.engine.total_monsters_killed} | "
                f"宝物:{self.engine.total_treasures_found} | "
                f"循环:{engine.loop_count} | "
                f"用时:{stats['elapsed']}秒"
            )

        # 自动切换标签页
        target_tab = SM_TO_TAB.get(current)
        if target_tab and self._active_tab != target_tab:
            self._switch_tab(target_tab)

        # 更新底部活动文字
        if current and engine.state_machines.get(current):
            content = engine.state_machines[current].current_content
            short_icon = SM_ICONS.get(current, "")
            short_label = SM_SHORT_LABELS.get(current, "")
            self._auto_activity_var.set(f"{short_icon} [{short_label}] {content}")

        self.root.after(800, self._auto_update_loop)
