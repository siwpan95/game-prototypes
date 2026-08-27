"""
Main Window — Tkinter 主窗口（纯 GUI，无 CLI 回退）。

布局:
  +----------------------------------------------+
  |  [Title Bar: 游戏标题 + 章节指示]            |
  +----------------------+-----------------------+
  |                      |   [Status Panel]      |
  |   Story Display     |   Sanity / Corruption |
  |   (scrollable)       |   Chapter / Progress  |
  |                      |                       |
  |                      +-----------------------+
  |                      |   [Info Panel]         |
  |                      |   Imagery / Inventory  |
  +----------------------+-----------------------+
  |   [Choice Buttons / Next / Continue]        |
  +----------------------------------------------+

所有交互通过按钮完成 — 无文本输入框（谜题答案通过
弹出对话框输入，而非命令行）。
"""

from __future__ import annotations

import tkinter as tk
from typing import Any, Callable

from shared_core.styles import Styles, get_fonts
from shared_core.renderer import GameDisplay


class InputPanel:
    """底部输入/选项区域。"""

    def __init__(self, parent: tk.Widget, fonts: dict):
        self.parent = parent
        self.fonts = fonts
        self.s = Styles()
        self._callbacks: dict[str, Callable] = {}

        self.frame = tk.Frame(parent, bg=self.s.BG_PANEL)
        self._btn_frame = tk.Frame(self.frame, bg=self.s.BG_PANEL)

    def show_choices(self, choices: list[dict],
                     on_select: Callable[[int], None]) -> None:
        """显示选项按钮。"""
        self.hide_buttons()
        self._btn_frame.pack(fill="both", expand=True, padx=10, pady=8)
        self._callbacks["choice"] = on_select

        for i, choice in enumerate(choices):
            text = choice.get("text", choice) if isinstance(choice, dict) else str(choice)
            btn = tk.Button(
                self._btn_frame,
                text=text,
                font=self.fonts["button"],
                fg=self.s.BTN_TEXT,
                bg=self.s.BTN_BG,
                activebackground=self.s.BTN_ACTIVE,
                activeforeground=self.s.TEXT_PRIMARY,
                highlightthickness=1,
                highlightbackground=self.s.BORDER_DARK,
                cursor="hand2",
                command=lambda idx=i: self._on_choice(idx),
            )
            btn.pack(side="left", padx=4, pady=4, expand=True, fill="x")

    def _on_choice(self, idx: int) -> None:
        self.hide_buttons()
        cb = self._callbacks.get("choice")
        if cb:
            cb(idx)

    def show_next_button(self, callback: Callable[[], None]) -> None:
        """显示'下一页'按钮。"""
        self.hide_buttons()
        self._btn_frame.pack(fill="both", expand=True, padx=10, pady=8)
        self._callbacks["next"] = callback

        btn = tk.Button(
            self._btn_frame, text="继续 ▶",
            font=self.fonts["button"],
            fg=self.s.BTN_TEXT, bg=self.s.BTN_BG,
            activebackground=self.s.BTN_HOVER,
            cursor="hand2",
            command=self._on_next,
        )
        btn.pack(expand=True)

    def _on_next(self) -> None:
        self.hide_buttons()
        cb = self._callbacks.get("next")
        if cb:
            cb()

    def show_continue_button(self, callback: Callable[[], None]) -> None:
        """显示标题画面的'开始游戏'按钮。"""
        self.hide_buttons()
        self._btn_frame.pack(fill="both", expand=True, padx=10, pady=8)
        self._callbacks["continue"] = callback

        btn = tk.Button(
            self._btn_frame, text="▶ 开始游戏",
            font=self.fonts["heading"],
            fg=self.s.ACCENT_BLOOD, bg=self.s.BTN_BG,
            activebackground=self.s.BTN_ACTIVE,
            cursor="hand2",
            command=self._on_continue,
        )
        btn.pack(expand=True, pady=20)

    def _on_continue(self) -> None:
        self.hide_buttons()
        cb = self._callbacks.get("continue")
        if cb:
            cb()

    def show_quit_button(self) -> None:
        """显示退出按钮。"""
        self.hide_buttons()
        self._btn_frame.pack(fill="both", expand=True, padx=10, pady=8)

        btn = tk.Button(
            self._btn_frame, text="退出游戏",
            font=self.fonts["button"],
            fg=self.s.ACCENT_BLOOD, bg=self.s.BTN_BG,
            cursor="hand2",
            command=lambda: self._callbacks.get("quit", lambda: None)(),
        )
        btn.pack(expand=True, pady=20)

    def hide_input(self) -> None:
        pass  # 不再有文本输入模式

    def hide_buttons(self) -> None:
        for w in self._btn_frame.winfo_children():
            w.destroy()
        self._btn_frame.pack_forget()

    def focus(self) -> None:
        if self.frame.winfo_exists():
            self.frame.focus_set()


class StatusPanel:
    """右侧状态面板。"""

    # 章节名称映射
    CHAPTER_NAMES = {
        "prologue": "序章",
        "chapter_1": "第一章",
        "chapter_2": "第二章",
        "chapter_3": "第三章",
        "chapter_4": "第四章",
        "chapter_5": "第五章",
        "chapter_6": "第六章",
        "chapter_7": "第七章",
        "chapter_8": "第八章",
        "chapter_9": "第九章",
        "chapter_10": "第十章",
        "epilogue": "尾声",
    }

    # 分支名称映射
    BRANCH_NAMES = {
        "main": "主线",
        "translation": "转译",
        "distance": "远途",
        "multiplication": "增殖",
        "witness": "见证",
        "memory": "记忆",
    }

    @classmethod
    def _localize_chapter(cls, value: str) -> str:
        return cls.CHAPTER_NAMES.get(value, value)

    @classmethod
    def _localize_branch(cls, value: str) -> str:
        return cls.BRANCH_NAMES.get(value, value)

    def __init__(self, parent: tk.Widget, fonts: dict):
        self.parent = parent
        self.fonts = fonts
        self.s = Styles()
        self.frame = tk.Frame(parent, bg=self.s.BG_DARKEST)
        self._build()

    def _build(self) -> None:
        s = self.s
        # 标题
        title = tk.Label(
            self.frame, text="◆ 状态 ◆",
            font=self.fonts["small"], fg=s.TEXT_DIM, bg=s.BG_DARKEST,
        )
        title.pack(pady=(6, 2))

        # 状态标签容器
        self.labels: dict[str, tk.Label] = {}
        status_items = [
            ("sanity", "清晰度: --/--"),
            ("corruption", "浑浊度: --/100"),
            ("chapter", "章节: --"),
            ("puzzles", "谜题: --/--"),
            ("branch", "分支: 主线"),
        ]
        for key, default_text in status_items:
            lbl = tk.Label(
                self.frame, text=default_text,
                font=self.fonts["status"], fg=s.TEXT_SECONDARY, bg=s.BG_DARKEST,
                anchor="w",
            )
            lbl.pack(fill="x", padx=8, pady=1)
            self.labels[key] = lbl

        # 分隔线
        sep = tk.Frame(self.frame, bg=s.BORDER_DARK, height=1)
        sep.pack(fill="x", padx=6, pady=4)

        # 意象/探索标签
        self.info_labels: dict[str, tk.Label] = {}
        info_items = [
            ("imagery", "意象: 0/0"),
            ("room", "位置: --"),
            ("items", "物品: 0"),
        ]
        for key, default_text in info_items:
            lbl = tk.Label(
                self.frame, text=default_text,
                font=self.fonts["status"], fg=s.TEXT_DIM, bg=s.BG_DARKEST,
                anchor="w",
            )
            lbl.pack(fill="x", padx=8, pady=1)
            self.info_labels[key] = lbl

    def update(self, **kwargs) -> None:
        s = self.s
        p = kwargs.get("player") or type('obj', (), {})()

        # 清晰度
        sanity_val = getattr(p, 'sanity', kwargs.get('sanity', '--'))
        max_sanity = getattr(p, 'max_sanity', kwargs.get('max_sanity', '--'))
        if sanity_val != '--':
            ratio = sanity_val / max(max_sanity, 1)
            if ratio > 0.6:
                color = s.STATUS_SANITY_HIGH
            elif ratio > 0.3:
                color = s.STATUS_SANITY_MED
            else:
                color = s.STATUS_SANITY_LOW
            self.labels["sanity"].config(text=f"清晰度: {sanity_val}/{max_sanity}", fg=color)
        else:
            self.labels["sanity"].config(text=f"清晰度: --/--")

        # 浑浊度
        corr = getattr(p, 'corruption', kwargs.get('corruption', '--'))
        if corr != '--':
            self.labels["corruption"].config(text=f"浑浊度: {corr}/100")

        # 章节
        ch = getattr(p, 'current_chapter', None)
        if ch and hasattr(ch, 'value'):
            ch_name = self._localize_chapter(ch.value)
            self.labels["chapter"].config(text=f"章节: {ch_name}")
        elif kwargs.get('chapter'):
            ch_raw = kwargs['chapter']
            ch_name = self._localize_chapter(ch_raw) if isinstance(ch_raw, str) else str(ch_raw)
            self.labels["chapter"].config(text=f"章节: {ch_name}")

        # 谜题
        solved = getattr(p, 'puzzles_solved', kwargs.get('puzzles_solved', 0))
        attempted = getattr(p, 'puzzles_attempted', kwargs.get('puzzles_attempted', 0))
        self.labels["puzzles"].config(text=f"谜题: {solved}/{attempted}")

        # 分支
        branch = kwargs.get('branch', '主线')
        if branch and hasattr(branch, 'value'):
            branch_name = self._localize_branch(branch.value)
        elif isinstance(branch, str):
            branch_name = self._localize_branch(branch)
        else:
            branch_name = str(branch)
        self.labels["branch"].config(text=f"分支: {branch_name}")

        # 意象网络
        inetwork = kwargs.get("imagery_network")
        if inetwork and hasattr(inetwork, 'discovery_count'):
            dc = inetwork.discovery_count
            tn = inetwork.total_nodes
            self.info_labels["imagery"].config(text=f"意象: {dc}/{tn}")

        # 房间
        room = getattr(p, 'current_room', '') or kwargs.get('current_room', '')
        if room:
            self.info_labels["room"].config(text=f"位置: {room}")
        elif kwargs.get('current_room'):
            self.info_labels["room"].config(text=f"位置: {kwargs['current_room']}")

        # 物品
        inv = getattr(p, 'inventory_items', []) or kwargs.get('inventory_items', [])
        self.info_labels["items"].config(text=f"物品: {len(inv)}")


class InfoPanel:
    """右侧信息面板（意象网络 / 物品列表）。"""

    def __init__(self, parent: tk.Widget, fonts: dict):
        self.parent = parent
        self.fonts = fonts
        self.s = Styles()
        self.frame = tk.Frame(parent, bg=self.s.BG_DARKEST)

        # 列表容器
        self.listbox = tk.Listbox(
            self.frame, font=self.fonts["small"],
            bg=self.s.BG_DARK, fg=self.s.TEXT_PRIMARY,
            selectbackground=self.s.BG_MEDIUM,
            highlightthickness=0,
        )

    def update(self, network: Any = None) -> None:
        """更新信息面板内容（如意象节点列表）。"""
        self.listbox.delete(0, tk.END)
        if not network:
            return
        nodes = getattr(network, 'nodes', {})
        if not nodes:
            return
        for nid, node in sorted(nodes.items()):
            name = getattr(node, 'name', nid)
            disc = "✓" if getattr(node, 'discovered', False) else " "
            self.listbox.insert(tk.END, f"{disc} {name}")


class MainWindow:
    """
    Tkinter 主窗口。

    实现以下接口（供 BaseEngine 调用）：
      - run() / shutdown()
      - show_title_screen() / show_story() / show_choices()
      - show_puzzle() / show_feedback() / show_ending() / show_game_over()
      - update_status(state)
      - set_on_submit(cb) / set_on_choice(cb) / set_on_hint(cb)
      - log(msg)
      - show_next_button(callback) / show_continue_button(callback)
    """

    def __init__(self, engine: Any):
        self.engine = engine

        # 根窗口 — 必须在 Styles (create font) 之前创建
        self.root = tk.Tk()
        game_title = getattr(engine, 'GAME_TITLE', 'Hell Below')
        subtitle = getattr(engine, 'GAME_SUBTITLE', '')
        display_title = f"{game_title} - {subtitle}" if subtitle else game_title
        self.root.title(display_title)
        self.root.configure(bg="#0d0d1a")  # BG_DARKEST

        # 现在 Tk 根窗口已存在，可以安全创建字体
        self.s = Styles(engine.WINDOW_CONFIG if hasattr(engine, 'WINDOW_CONFIG') else {})
        self.root.geometry(f"{self.s.WINDOW_WIDTH}x{self.s.WINDOW_HEIGHT}")
        self.root.minsize(self.s.WINDOW_MIN_WIDTH, self.s.WINDOW_MIN_HEIGHT)
        self.fonts = get_fonts()

        # 布局
        self.root.grid_rowconfigure(2, weight=1)
        self.root.grid_columnconfigure(0, weight=1)

        self._build_ui()
        self._bind_events()

        # 回调引用
        self._submit_cb: Callable | None = None
        self._choice_cb: Callable | None = None
        self._hint_cb: Callable | None = None

    def _build_ui(self) -> None:
        s = self.s
        # Title bar
        self._build_title_bar()
        # Main area
        self._build_main_area()
        # Input area
        self._build_input_area()

    def _build_title_bar(self) -> None:
        s = self.s
        top = tk.Frame(self.root, bg=s.BG_MEDIUM, height=36,
                        highlightbackground=s.BORDER_ACCENT, highlightthickness=1)
        top.grid(row=0, column=0, sticky="ew")
        top.grid_propagate(False)

        title_text = getattr(self.engine, 'GAME_TITLE', 'Hell Below')
        tk.Label(top, text=f"  {title_text}",
                  font=self.fonts["heading"], fg=s.ACCENT_BLOOD, bg=s.BG_MEDIUM
                  ).pack(side="left", padx=s.PADDING_MD)

        self.chapter_label = tk.Label(
            top, text="", font=self.fonts["small"], fg=s.TEXT_DIM, bg=s.BG_MEDIUM
        )
        self.chapter_label.pack(side="right", padx=s.PADDING_LG)

        tk.Frame(self.root, bg=s.ACCENT_BLOOD, height=2).grid(row=1, column=0, sticky="ew")

    def _build_main_area(self) -> None:
        s = self.s
        main_frame = tk.Frame(self.root, bg=s.BG_DARKEST)
        main_frame.grid(row=2, column=0, sticky="nsew")
        main_frame.grid_rowconfigure(0, weight=1)
        main_frame.grid_columnconfigure(0, weight=1)
        main_frame.grid_columnconfigure(1, weight=0)

        # 左：故事区域
        left = tk.Frame(main_frame, bg=s.BG_DARK, width=s.PANEL_LEFT_WIDTH,
                          highlightbackground=s.BORDER_DARK, highlightthickness=1)
        left.grid(row=0, column=0, sticky="nsew",
                   padx=(s.PADDING_SM, s.PADDING_SM), pady=s.PADDING_SM)
        left.grid_propagate(False)
        left.grid_rowconfigure(0, weight=1)
        left.grid_columnconfigure(0, weight=1)

        self.game_display = GameDisplay(left, self.fonts)
        self.game_display.frame.grid(row=0, column=0, sticky="nsew")

        # 右：状态面板
        right = tk.Frame(main_frame, bg=s.BG_DARKEST, width=s.PANEL_RIGHT_WIDTH)
        right.grid(row=0, column=1, sticky="nsew",
                    padx=(0, s.PADDING_SM), pady=s.PADDING_SM)
        right.grid_propagate(False)
        right.grid_rowconfigure(0, weight=0)
        right.grid_rowconfigure(1, weight=1)

        self.inventory_panel = StatusPanel(right, self.fonts)
        self.inventory_panel.frame.grid(row=0, column=0, sticky="ew", pady=(0, s.PADDING_SM))

        self.map_panel = InfoPanel(right, self.fonts)
        self.map_panel.frame.grid(row=1, column=0, sticky="nsew")

    def _build_input_area(self) -> None:
        s = self.s
        bottom = tk.Frame(self.root, bg=s.BG_PANEL, height=s.PANEL_BOTTOM_HEIGHT,
                           highlightbackground=s.BORDER_ACCENT, highlightthickness=1)
        bottom.grid(row=3, column=0, sticky="ew")
        bottom.grid_propagate(False)
        bottom.grid_rowconfigure(0, weight=1)
        bottom.grid_columnconfigure(0, weight=1)

        self.input_panel = InputPanel(bottom, self.fonts)
        self.input_panel.frame.grid(row=0, column=0, sticky="nsew")

    def _bind_events(self) -> None:
        self.root.bind("<Escape>", lambda e: self._on_quit())
        self.root.bind("<Control-h>", lambda e: self.show_hint())
        self.root.bind("<Control-l>", lambda e: self.refresh_status())
        self.root.protocol("WM_DELETE_WINDOW", self._on_quit)

    def _on_quit(self) -> None:
        try:
            if self._submit_cb:
                self._submit_cb("quit")
        finally:
            try:
                self.root.destroy()
            except tk.TclError:
                pass

    # ========== 回调设置 ==========

    def set_on_submit(self, cb: Callable[[str], None]) -> None:
        self._submit_cb = cb

    def set_on_choice(self, cb: Callable[[int], None]) -> None:
        self._choice_cb = cb

    def set_on_hint(self, cb: Callable[[], None]) -> None:
        self._hint_cb = cb

    # ========== UI 更新方法 ==========

    def show_title_screen(self) -> None:
        self.game_display.show_title_screen()
        self.input_panel.show_continue_button(self._on_continue_from_title)

    def _on_continue_from_title(self) -> None:
        self.input_panel.hide_buttons()
        if hasattr(self.engine, 'start_game'):
            self.engine.start_game()

    def show_story(self, content: dict) -> None:
        self.game_display.show_story_text(
            content.get("title", ""),
            content.get("text", ""),
            content.get("tone", ""),
            content.get("critical", False),
        )
        chapter = content.get("chapter", "")
        if chapter:
            self.chapter_label.config(text=str(chapter))

    def show_puzzle(self, puzzle_data: Any) -> None:
        self.game_display.show_puzzle(puzzle_data)

    def show_choices(self, choices: list[dict]) -> None:
        self.input_panel.show_choices(choices, self._on_choice_selected)

    def _on_choice_selected(self, idx: int) -> None:
        self.input_panel.hide_buttons()
        if self._choice_cb:
            self._choice_cb(idx)

    def show_feedback(self, fb_type: str, summary: str, detail: str = "") -> None:
        self.game_display.show_feedback(fb_type, summary, detail)

    def show_ending(self, ending_data: tuple[str, str]) -> None:
        title, desc = ending_data
        self.game_display.show_ending(title, desc)
        self.input_panel.hide_buttons()
        self.input_panel.show_quit_button()

    def show_game_over(self, reason: str) -> None:
        self.game_display.show_game_over(reason)
        self.input_panel.hide_buttons()
        self.input_panel.show_quit_button()

    def update_status(self, state: Any) -> None:
        self.inventory_panel.update(player=getattr(state, 'player', state),
                                     imagery_network=getattr(state, 'imagery_network', None),
                                     branch=getattr(state, 'current_branch', None))
        self.map_panel.update(getattr(state, 'imagery_network', None))

    def show_hint(self) -> None:
        if self._hint_cb:
            self._hint_cb()

    def refresh_status(self) -> None:
        pass

    def show_next_button(self, callback: Callable[[], None]) -> None:
        self.input_panel.show_next_button(callback)

    def show_continue_button(self, callback: Callable[[], None]) -> None:
        self.input_panel.show_continue_button(callback)

    def show_input_mode(self) -> None:
        pass

    def log(self, message: str) -> None:
        self.game_display.show_feedback("info", message)

    def run(self) -> None:
        self.root.mainloop()

    def shutdown(self) -> None:
        try:
            self.root.destroy()
        except tk.TclError:
            pass
