"""
Renderer — Tkinter 渲染器（游戏文本显示区域）。

负责：
  - 故事文本显示（支持打字机效果）
  - 谜题界面渲染
  - 反馈消息（成功/失败/信息）
  - 结局/游戏结束画面
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk, font as tkfont
from typing import Any, Callable

from shared_core.styles import Styles


class GameDisplay:
    """游戏文本显示区域。"""

    def __init__(self, parent: tk.Widget, fonts: dict):
        self.parent = parent
        self.fonts = fonts
        self.styles = Styles()

        # 主框架
        self.frame = tk.Frame(parent, bg=self.styles.BG_DARK)
        self.frame.grid_rowconfigure(0, weight=1)
        self.frame.grid_columnconfigure(0, weight=1)

        # 文本显示（带滚动条）
        self._build_text_area()

    def _build_text_area(self) -> None:
        s = self.styles
        # 文本 + 滚动条容器
        container = tk.Frame(self.frame, bg=s.BG_DARK)
        container.grid(row=0, column=0, sticky="nsew")
        container.grid_rowconfigure(0, weight=1)
        container.grid_columnconfigure(0, weight=1)

        # 使用 Canvas + Text 实现自动滚动
        self.canvas = tk.Canvas(
            container, bg=s.BG_DARK,
            highlightthickness=0,
        )
        self.canvas.grid(row=0, column=0, sticky="nsew")

        scrollbar = tk.Scrollbar(
            container, orient="vertical", command=self.canvas.yview
        )
        scrollbar.grid(row=0, column=1, sticky="ns")

        self.canvas.configure(yscrollcommand=scrollbar.set)

        # 内部文本框架
        self.text_frame = tk.Frame(self.canvas, bg=s.BG_DARK)
        self.canvas_window = self.canvas.create_window(
            0, 0, anchor="nw", window=self.text_frame
        )

        # 文本标签
        self.content_label = tk.Label(
            self.text_frame, text="", bg=s.BG_DARK,
            fg=s.TEXT_PRIMARY, font=self.fonts["body"],
            justify="left", wraplength=650,
        )
        self.content_label.pack(padx=12, pady=12, anchor="nw")

        # 绑定配置事件以调整滚动区域
        self._bind_resize_events()

    def _bind_resize_events(self) -> None:
        self.text_frame.bind("<Configure>", self._on_frame_configure)
        self.canvas.bind("<Configure>", self._on_canvas_configure)

    def _on_frame_configure(self, event=None) -> None:
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _on_canvas_configure(self, event=None) -> None:
        if hasattr(self, 'canvas_window'):
            self.canvas.itemconfig(self.canvas_window, width=event.width)

    # ========== 显示方法 ==========

    def show_title_screen(self) -> None:
        """显示标题画面。"""
        self.content_label.config(
            text="\n\n\n  地 狱 之 下\n\n  — 按「继续」开始 —",
            font=self.fonts["title"],
            fg=self.styles.ACCENT_BLOOD,
        )

    def show_story_text(self, title: str, text: str, tone: str = "",
                         is_critical: bool = False) -> None:
        """显示故事文本。"""
        color = self.styles.ACCENT_FLAME if is_critical else self.styles.TEXT_PRIMARY
        content = f"\n{title}\n" if title else ""
        if tone:
            content += f"〔{tone}〕\n"
        content += f"\n{text}"
        self.content_label.config(text=content, fg=color, font=self.fonts["body"])
        self.canvas.yview_moveto(0)

    def show_puzzle(self, puzzle_data: Any) -> None:
        """显示谜题。"""
        puzzle = getattr(puzzle_data, 'puzzle', None)
        if puzzle:
            title = getattr(puzzle, 'title', '谜题')
            question = getattr(puzzle, 'question', '')
            desc = getattr(puzzle, 'description', '')
            text = f"\n【{title}】\n{desc}\n\n> {question}\n\n(请输入答案)"
        else:
            pid = puzzle_data.get("puzzle_id", "未知") if isinstance(puzzle_data, dict) else "未知"
            text = f"\n【谜题】\n\n谜题 ID: {pid}\n\n(请输入答案)"
        self.content_label.config(text=text, fg=self.styles.ACCENT_GOLD,
                                    font=self.fonts["puzzle"])
        self.canvas.yview_moveto(0)

    def show_feedback(self, fb_type: str, summary: str,
                       detail: str = "") -> None:
        """显示反馈消息。"""
        colors = {
            "success": self.styles.ACCENT_GREEN,
            "failure": self.styles.ACCENT_BLOOD,
            "info": self.styles.ACCENT_BLUE,
            "warning": self.styles.ACCENT_FLAME,
        }
        color = colors.get(fb_type, self.styles.TEXT_SECONDARY)
        text = f"\n[{summary}]"
        if detail:
            text += f" {detail}"
        self.content_label.config(text=text, fg=color, font=self.fonts["body_large"])

    def show_ending(self, title: str, description: str) -> None:
        """显示结局。"""
        text = f"\n\n\n  ── {title} ──\n\n  {description}\n\n\n  感谢游玩。\n"
        self.content_label.config(text=text, fg=self.styles.ACCENT_PURPLE,
                                    font=self.fonts["ending"])

    def show_game_over(self, reason: str) -> None:
        """显示游戏结束。"""
        text = f"\n\n\n  ▓▓▓ 游戏结束 ▓▓▓\n\n  {reason}\n\n\n"
        self.content_label.config(text=text, fg=self.styles.ACCENT_BLOOD,
                                    font=self.fonts["ending"])

    def clear(self) -> None:
        self.content_label.config(text="")


# 导出别名
Renderer = GameDisplay
