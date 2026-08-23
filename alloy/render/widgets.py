"""
游戏 UI 组件 — 从《我的世界》实战沉淀

提供 Tkinter 游戏界面常用组件：
  - GameLogPanel:  可滚动文本日志，带颜色标签
  - StatusBar:     多行状态显示（HP/位置/装备等）
  - QuickCommandBar: 快捷命令按钮组
  - GameInputBar:  带命令历史的输入区

所有组件使用统一的暗色主题配色，可自定义。

使用方式:

    from alloy.render.widgets import (
        GameLogPanel, StatusBar, QuickCommandBar, GameInputBar
    )

    # 日志面板
    log = GameLogPanel(root)
    log.append("欢迎来到游戏！", color="#7ec850")

    # 状态栏
    status = StatusBar(root)
    status.set("hp", "❤️ 生命: 20/20")
    status.set("location", "📍 平原")

    # 快捷命令栏
    cmds = QuickCommandBar(root, [
        ("⛏️ 采集", "gather"),
        ("🎒 背包", "inventory"),
    ], callback=on_command)
"""

from __future__ import annotations

import tkinter as tk
from tkinter import font, scrolledtext
from typing import Any, Callable, Optional


# ═══════════════════════════════════════════════════════════
#  默认配色主题
# ═══════════════════════════════════════════════════════════

class GameTheme:
    """游戏 UI 默认配色。可继承覆盖。"""

    BG_DARK      = "#1a1a1a"
    BG_PANEL     = "#2d2d2d"
    BG_INPUT     = "#3a3a3a"
    FG_PRIMARY   = "#e0e0e0"
    FG_ACCENT    = "#7ec850"
    FG_GOLD      = "#ffaa00"
    FG_RED       = "#ff5555"
    FG_BLUE      = "#55aaff"
    FG_DIM       = "#888888"
    FG_PURPLE    = "#aa55ff"
    BORDER       = "#444444"


# ═══════════════════════════════════════════════════════════
#  GameLogPanel — 可滚动日志面板
# ═══════════════════════════════════════════════════════════

class GameLogPanel:
    """游戏文本日志面板 — 支持颜色标签、自动滚动、行数限制。

    使用方式:

        log = GameLogPanel(root, max_lines=500)
        log.append("系统启动", color="#7ec850")
        log.append("敌人出现了！", color="#ff5555")
    """

    def __init__(
        self,
        parent: tk.Widget,
        max_lines: int = 500,
        font_family: str = "TkDefaultFont",
        font_size: int = 12,
        theme: type[GameTheme] | None = None,
        **kwargs,
    ):
        """
        参数:
            parent: 父容器
            max_lines: 最大保留行数
            font_family: 字体名
            font_size: 字号
            theme: 配色类（None 使用 GameTheme）
            **kwargs: 传递给 ScrolledText 的额外参数
        """
        self.theme = theme or GameTheme
        self._font = font.Font(family=font_family, size=font_size)

        self._widget = scrolledtext.ScrolledText(
            parent,
            wrap=tk.WORD,
            bg=self.theme.BG_PANEL,
            fg=self.theme.FG_PRIMARY,
            insertbackground=self.theme.FG_PRIMARY,
            font=self._font,
            relief=tk.FLAT,
            borderwidth=0,
            padx=12,
            pady=10,
            state=tk.DISABLED,
            **kwargs,
        )

        self._max_lines = max_lines
        self._color_tags: dict[str, str] = {}  # color → tag_name

    @property
    def widget(self) -> scrolledtext.ScrolledText:
        """底层 Tkinter 组件。"""
        return self._widget

    def pack(self, **kwargs) -> None:
        self._widget.pack(**kwargs)

    def grid(self, **kwargs) -> None:
        self._widget.grid(**kwargs)

    def append(self, text: str, color: str | None = None) -> None:
        """追加文本到日志。

        参数:
            text: 文本内容
            color: 可选的颜色（CSS 格式如 "#7ec850"）
        """
        self._widget.configure(state=tk.NORMAL)

        if color:
            tag = self._get_color_tag(color)
            self._widget.insert(tk.END, text + "\n", tag)
        else:
            self._widget.insert(tk.END, text + "\n")

        self._widget.see(tk.END)

        # 限制行数
        lines = int(self._widget.index('end-1c').split('.')[0])
        if lines > self._max_lines:
            self._widget.delete('1.0', f'{lines - self._max_lines}.0')

        self._widget.configure(state=tk.DISABLED)

    def clear(self) -> None:
        """清空日志。"""
        self._widget.configure(state=tk.NORMAL)
        self._widget.delete('1.0', tk.END)
        self._widget.configure(state=tk.DISABLED)

    def _get_color_tag(self, color: str) -> str:
        """获取或创建颜色标签。"""
        if color not in self._color_tags:
            tag_name = f"color_{len(self._color_tags)}"
            self._widget.tag_config(tag_name, foreground=color)
            self._color_tags[color] = tag_name
        return self._color_tags[color]


# ═══════════════════════════════════════════════════════════
#  StatusBar — 游戏状态栏
# ═══════════════════════════════════════════════════════════

class StatusBar:
    """游戏状态条 — 管理多个键值对显示，自动刷新。

    使用方式:

        bar = StatusBar(frame, theme=MyTheme)
        bar.add("hp", "❤️ 生命: 20/20", color="#ff5555")
        bar.add("location", "📍 平原")
        bar.update("hp", "❤️ 生命: 15/20")
    """

    def __init__(
        self,
        parent: tk.Widget,
        font_family: str = "TkDefaultFont",
        font_size: int = 12,
        theme: type[GameTheme] | None = None,
    ):
        self.theme = theme or GameTheme
        self._font = font.Font(family=font_family, size=font_size)
        self._parent = parent
        self._labels: dict[str, tk.Label] = {}
        self._frame = tk.Frame(parent, bg=self.theme.BG_PANEL)

    @property
    def widget(self) -> tk.Frame:
        return self._frame

    def pack(self, **kwargs) -> None:
        self._frame.pack(**kwargs)

    def add(self, key: str, text: str, color: str | None = None) -> None:
        """添加一个状态项。

        参数:
            key: 唯一键名（用于后续 update）
            text: 初始文本
            color: 文字颜色
        """
        fg = color or self.theme.FG_PRIMARY
        lbl = tk.Label(
            self._frame, text=text,
            font=self._font, bg=self.theme.BG_PANEL, fg=fg,
            anchor="w",
        )
        lbl.pack(fill=tk.X, padx=10, pady=(3, 0))
        self._labels[key] = lbl

    def update(self, key: str, text: str) -> None:
        """更新指定状态项的文字。"""
        if key in self._labels:
            self._labels[key].config(text=text)

    def remove(self, key: str) -> None:
        """移除状态项。"""
        if key in self._labels:
            self._labels[key].destroy()
            del self._labels[key]

    def clear(self) -> None:
        """清空所有状态项。"""
        for lbl in self._labels.values():
            lbl.destroy()
        self._labels.clear()


# ═══════════════════════════════════════════════════════════
#  QuickCommandBar — 快捷命令按钮栏
# ═══════════════════════════════════════════════════════════

class QuickCommandBar:
    """快捷命令按钮栏 — 一行多按钮，点击触发回调。

    使用方式:

        bar = QuickCommandBar(root, [
            ("⛏️ 采集", "gather"),
            ("🎒 背包", "inventory"),
            ("📊 状态", "status"),
        ], callback=lambda cmd: game.execute(cmd))
    """

    def __init__(
        self,
        parent: tk.Widget,
        buttons: list[tuple[str, str]],
        callback: Callable[[str], None],
        font_family: str = "TkDefaultFont",
        font_size: int = 10,
        theme: type[GameTheme] | None = None,
    ):
        """
        参数:
            parent: 父容器
            buttons: [(显示文本, 命令字符串), ...]
            callback: 按钮点击回调 (命令字符串)
            font_family: 字体名
            font_size: 字号
            theme: 配色类
        """
        self.theme = theme or GameTheme
        self._font = font.Font(family=font_family, size=font_size)
        self._callback = callback

        self._frame = tk.Frame(parent, bg=self.theme.BG_DARK)

        for text, cmd in buttons:
            btn = tk.Button(
                self._frame, text=text,
                font=self._font,
                bg=self.theme.BG_PANEL,
                fg=self.theme.FG_PRIMARY,
                activebackground=self.theme.BG_INPUT,
                activeforeground=self.theme.FG_ACCENT,
                relief=tk.FLAT, bd=1,
                padx=8, pady=3,
                command=lambda c=cmd: self._callback(c),
            )
            btn.pack(side=tk.LEFT, padx=2)

    @property
    def widget(self) -> tk.Frame:
        return self._frame

    def pack(self, **kwargs) -> None:
        self._frame.pack(**kwargs)


# ═══════════════════════════════════════════════════════════
#  GameInputBar — 带命令历史的输入栏
# ═══════════════════════════════════════════════════════════

class GameInputBar:
    """游戏命令输入栏 — 支持上下箭头浏览历史。

    使用方式:

        bar = GameInputBar(root, on_submit=lambda cmd: game.execute(cmd))
        bar.focus()
    """

    def __init__(
        self,
        parent: tk.Widget,
        on_submit: Callable[[str], None],
        prompt: str = "> ",
        font_family: str = "TkDefaultFont",
        font_size: int = 13,
        theme: type[GameTheme] | None = None,
    ):
        """
        参数:
            parent: 父容器
            on_submit: 提交回调 (命令字符串)
            prompt: 输入提示符
            font_family: 字体名
            font_size: 字号
            theme: 配色类
        """
        self.theme = theme or GameTheme
        self._font = font.Font(family=font_family, size=font_size)
        self._on_submit = on_submit
        self._history: list[str] = []
        self._history_idx: int = -1

        self._frame = tk.Frame(parent, bg=self.theme.BG_PANEL)

        # 提示符
        tk.Label(
            self._frame, text=prompt,
            font=self._font,
            bg=self.theme.BG_PANEL,
            fg=self.theme.FG_ACCENT,
        ).pack(side=tk.LEFT, padx=(10, 0))

        # 输入框
        self._entry = tk.Entry(
            self._frame,
            font=self._font,
            bg=self.theme.BG_INPUT,
            fg=self.theme.FG_PRIMARY,
            insertbackground=self.theme.FG_ACCENT,
            relief=tk.FLAT,
            borderwidth=0,
        )
        self._entry.pack(side=tk.LEFT, fill=tk.BOTH, expand=True,
                         padx=(5, 10), pady=10)

        # 绑定
        self._entry.bind("<Return>", self._on_enter)
        self._entry.bind("<Up>", self._on_history_up)
        self._entry.bind("<Down>", self._on_history_down)

    @property
    def widget(self) -> tk.Frame:
        return self._frame

    @property
    def entry(self) -> tk.Entry:
        return self._entry

    def pack(self, **kwargs) -> None:
        self._frame.pack(**kwargs)

    def focus(self) -> None:
        """聚焦输入框。"""
        self._entry.focus_set()

    def _on_enter(self, event=None) -> None:
        """回车提交。"""
        cmd = self._entry.get().strip()
        if not cmd:
            return
        self._history.append(cmd)
        self._history_idx = len(self._history)
        self._entry.delete(0, tk.END)
        self._on_submit(cmd)

    def _on_history_up(self, event=None) -> None:
        """上箭头：上一个命令。"""
        if self._history_idx > 0:
            self._history_idx -= 1
            self._entry.delete(0, tk.END)
            self._entry.insert(0, self._history[self._history_idx])

    def _on_history_down(self, event=None) -> None:
        """下箭头：下一个命令或清空。"""
        if self._history_idx < len(self._history) - 1:
            self._history_idx += 1
            self._entry.delete(0, tk.END)
            self._entry.insert(0, self._history[self._history_idx])
        else:
            self._history_idx = len(self._history)
            self._entry.delete(0, tk.END)


# ═══════════════════════════════════════════════════════════
#  GameWindow — 一键游戏窗口（组合上述所有组件）
# ═══════════════════════════════════════════════════════════

class GameWindow:
    """一键游戏窗口 — 组合日志面板、状态栏、输入栏、快捷按钮。

    使用方式:

        window = GameWindow(root, title="我的游戏")
        window.log.append("欢迎！", color="#7ec850")
        window.status.add("hp", "❤️ HP: 20/20")
        window.commands.on_submit = lambda cmd: game.execute(cmd)
    """

    def __init__(
        self,
        root: tk.Tk,
        title: str = "游戏",
        font_family: str = "TkDefaultFont",
        font_size: int = 12,
        theme: type[GameTheme] | None = None,
        buttons: list[tuple[str, str]] | None = None,
    ):
        """
        参数:
            root: Tk 根窗口
            title: 窗口标题
            font_family: 字体名
            font_size: 基础字号
            theme: 配色类
            buttons: 快捷按钮列表 [(文本, 命令), ...]
        """
        self.theme = theme or GameTheme
        self.root = root
        root.title(title)
        root.configure(bg=self.theme.BG_DARK)
        root.geometry("900x680")
        root.minsize(700, 500)

        # ── 标题栏 ──
        title_frame = tk.Frame(root, bg=self.theme.BG_PANEL, height=40)
        title_frame.pack(fill=tk.X)
        title_frame.pack_propagate(False)

        title_font = font.Font(family=font_family, size=font_size + 4, weight="bold")
        tk.Label(
            title_frame, text=title,
            font=title_font, bg=self.theme.BG_PANEL, fg=self.theme.FG_ACCENT,
        ).pack(side=tk.LEFT, padx=15, pady=6)

        # ── 主内容 ──
        main = tk.Frame(root, bg=self.theme.BG_DARK)
        main.pack(fill=tk.BOTH, expand=True, padx=10, pady=(5, 5))

        # 左侧日志
        left = tk.Frame(main, bg=self.theme.BG_DARK)
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.log = GameLogPanel(left, font_family=font_family,
                                font_size=font_size, theme=theme)
        self.log.pack(fill=tk.BOTH, expand=True)

        # 右侧状态
        right = tk.Frame(main, bg=self.theme.BG_DARK, width=240)
        right.pack(side=tk.RIGHT, fill=tk.Y, padx=(8, 0))
        right.pack_propagate(False)
        self.status = StatusBar(right, font_family=font_family,
                                font_size=font_size, theme=theme)
        self.status.pack(fill=tk.X)

        # ── 底部输入栏 ──
        def default_callback(cmd):
            self.log.append(f"> {cmd}", self.theme.FG_ACCENT)

        self.commands = GameInputBar(
            root, on_submit=default_callback,
            font_family=font_family, font_size=font_size + 1, theme=theme,
        )
        self.commands.pack(fill=tk.X, padx=10, pady=(0, 5))

        # ── 快捷按钮 ──
        if buttons:
            self.quickbar = QuickCommandBar(
                root, buttons,
                callback=default_callback,
                font_family=font_family, font_size=font_size - 2, theme=theme,
            )
            self.quickbar.pack(fill=tk.X, padx=10, pady=(0, 10))
        else:
            self.quickbar = None
