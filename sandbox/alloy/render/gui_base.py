"""
Tkinter GUI 基类 — 通用窗口框架

提供:
    - Styles: 主题样式管理 (dark/light 双主题)
    - BaseWindow: Tkinter 主窗口基类（布局框架）
    - StatusPanel: 状态显示面板 (HP/理智/章节等)
    - TkUtil: Tkinter 工具函数集

从 hell below/shared_core/ 提取并泛化为通用框架。
"""

from __future__ import annotations

import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk
from typing import Any, Callable, Dict, List, Optional, Tuple, Union


# ================================================================
#  调色板 — Dark Theme
# ================================================================

DARK_PALETTE = {
    # 背景
    "BG_DARKEST":   "#0d0d1a",
    "BG_DARK":      "#1a1a2e",
    "BG_MEDIUM":    "#16213e",
    "BG_PANEL":     "#1f2030",
    "BG_INPUT":     "#252540",
    # 文本
    "TEXT_PRIMARY":   "#e0d8c8",
    "TEXT_SECONDARY": "#8a8578",
    "TEXT_DIM":       "#5a5550",
    "TEXT_BRIGHT":    "#ffeedd",
    # 强调色
    "ACCENT_RED":     "#c0392b",
    "ACCENT_ORANGE":  "#e67e22",
    "ACCENT_GOLD":    "#d4a017",
    "ACCENT_PURPLE":  "#8e44ad",
    "ACCENT_BLUE":    "#2980b9",
    "ACCENT_GREEN":   "#27ae60",
    # 状态
    "STATUS_HIGH":    "#2ecc71",
    "STATUS_MED":     "#f39c12",
    "STATUS_LOW":     "#e74c3c",
    "STATUS_SPECIAL": "#8e44ad",
    # 边框
    "BORDER_DARK":    "#2a2a40",
    "BORDER_LIGHT":   "#3a3a55",
    "BORDER_ACCENT":  "#4a3050",
    # 按钮
    "BTN_BG":     "#2a2a45",
    "BTN_HOVER":  "#3a3a60",
    "BTN_ACTIVE": "#4a3070",
    "BTN_TEXT":   "#e0d8c8",
}

# ================================================================
#  调色板 — Light Theme
# ================================================================

LIGHT_PALETTE = {
    "BG_DARKEST":   "#f0f0f0",
    "BG_DARK":      "#ffffff",
    "BG_MEDIUM":    "#e8e8e8",
    "BG_PANEL":     "#f5f5f5",
    "BG_INPUT":     "#ffffff",
    "TEXT_PRIMARY":   "#1a1a2e",
    "TEXT_SECONDARY": "#555555",
    "TEXT_DIM":       "#999999",
    "TEXT_BRIGHT":    "#000000",
    "ACCENT_RED":     "#e74c3c",
    "ACCENT_ORANGE":  "#d35400",
    "ACCENT_GOLD":    "#c09100",
    "ACCENT_PURPLE":  "#8e44ad",
    "ACCENT_BLUE":    "#2980b9",
    "ACCENT_GREEN":   "#27ae60",
    "STATUS_HIGH":    "#2ecc71",
    "STATUS_MED":     "#f39c12",
    "STATUS_LOW":     "#e74c3c",
    "STATUS_SPECIAL": "#8e44ad",
    "BORDER_DARK":    "#cccccc",
    "BORDER_LIGHT":   "#dddddd",
    "BORDER_ACCENT":  "#aaaaaa",
    "BTN_BG":     "#e0e0e0",
    "BTN_HOVER":  "#d0d0d0",
    "BTN_ACTIVE": "#c0c0c0",
    "BTN_TEXT":   "#1a1a2e",
}

# ================================================================
#  字体配置
# ================================================================

FONT_FAMILY_MONO = "Consolas"
FONT_FAMILY_SANS = "Segoe UI"


def get_default_fonts(local_font: Optional[str] = None) -> Dict[str, tkfont.Font]:
    """创建默认字体集。

    参数：
        local_font: 本地字体别名 / 文件名（见 utils.font 的本地字体系统）。
                     若提供且本地字体可加载，标题 / 按钮等展示角色将使用该
                     手写 / 艺术字体，正文与输入框仍保持等宽可读性。

    返回：
        字体名字典 {"title", "heading", "body", ...}
    """
    fonts: Dict[str, tkfont.Font] = {
        "title":    tkfont.Font(family=FONT_FAMILY_MONO, size=18, weight="bold"),
        "heading":  tkfont.Font(family=FONT_FAMILY_MONO, size=14, weight="bold"),
        "body":     tkfont.Font(family=FONT_FAMILY_MONO, size=11),
        "body_large": tkfont.Font(family=FONT_FAMILY_MONO, size=13),
        "small":    tkfont.Font(family=FONT_FAMILY_MONO, size=9),
        "button":   tkfont.Font(family=FONT_FAMILY_SANS, size=11),
        "input":    tkfont.Font(family=FONT_FAMILY_MONO, size=12),
        "status":   tkfont.Font(family=FONT_FAMILY_MONO, size=10, weight="bold"),
    }

    # 用本地字体替换展示角色（标题/副标题/按钮），保留正文可读性
    if local_font:
        try:
            from alloy.utils.font import load_local_tk_font
            display = load_local_tk_font(18, name=local_font, bold=True)
            if display is not None:
                fonts["title"] = display
                fonts["heading"] = load_local_tk_font(14, name=local_font, bold=True) or fonts["heading"]
                fonts["button"] = load_local_tk_font(12, name=local_font) or fonts["button"]
        except Exception:
            # 本地字体不可用（如无 Tk 环境 / 字体缺失），保持系统字体
            pass

    return fonts


# ================================================================
#  Styles
# ================================================================

class Styles:
    """样式容器 — 统一管理和覆写 UI 样式。

    使用示例:
        # 默认暗色主题
        styles = Styles()

        # 亮色主题
        styles = Styles(theme="light")

        # 自定义覆写
        styles = Styles(overrides={"ACCENT_RED": "#ff0000", "WINDOW_WIDTH": 1200})
    """

    # 需从调色板同步的色值名
    _COLOR_NAMES = [
        "BG_DARKEST", "BG_DARK", "BG_MEDIUM", "BG_PANEL", "BG_INPUT",
        "TEXT_PRIMARY", "TEXT_SECONDARY", "TEXT_DIM", "TEXT_BRIGHT",
        "ACCENT_RED", "ACCENT_ORANGE", "ACCENT_GOLD",
        "ACCENT_PURPLE", "ACCENT_BLUE", "ACCENT_GREEN",
        "STATUS_HIGH", "STATUS_MED", "STATUS_LOW", "STATUS_SPECIAL",
        "BORDER_DARK", "BORDER_LIGHT", "BORDER_ACCENT",
        "BTN_BG", "BTN_HOVER", "BTN_ACTIVE", "BTN_TEXT",
    ]

    # 默认尺寸
    WINDOW_WIDTH = 1100
    WINDOW_HEIGHT = 720
    WINDOW_MIN_WIDTH = 900
    WINDOW_MIN_HEIGHT = 560
    PANEL_LEFT_WIDTH = 680
    PANEL_RIGHT_WIDTH = 380
    PANEL_BOTTOM_HEIGHT = 160
    PADDING_SM = 5
    PADDING_MD = 10
    PADDING_LG = 15

    def __init__(
        self,
        theme: str = "dark",
        overrides: Optional[Dict[str, Any]] = None,
    ):
        """初始化样式。

        参数:
            theme: 主题名 ("dark" 或 "light")
            overrides: 覆写字典，键名对应调色板色值名或尺寸名
        """
        self.theme = theme
        self.overrides = overrides or {}

        # 加载调色板
        palette = DARK_PALETTE if theme == "dark" else LIGHT_PALETTE
        for name in self._COLOR_NAMES:
            value = self.overrides.get(name, palette.get(name, "#000000"))
            setattr(self, name, value)

        # 尺寸
        for size_name in [
            "WINDOW_WIDTH", "WINDOW_HEIGHT",
            "WINDOW_MIN_WIDTH", "WINDOW_MIN_HEIGHT",
            "PANEL_LEFT_WIDTH", "PANEL_RIGHT_WIDTH",
            "PANEL_BOTTOM_HEIGHT",
            "PADDING_SM", "PADDING_MD", "PADDING_LG",
        ]:
            value = self.overrides.get(size_name, getattr(Styles, size_name, 10))
            setattr(self, size_name, value)

        # 字体
        self.fonts = get_default_fonts()

        # 为亮色主题调整按钮样式
        if theme == "light":
            self.fonts = get_default_fonts()

    def switch_theme(self, theme: str):
        """切换主题。

        参数:
            theme: "dark" 或 "light"
        """
        self.__init__(theme=theme, overrides=self.overrides)

    def apply_to_widget(self, widget: tk.Widget, **kwargs):
        """批量设置控件样式。

        参数:
            widget: Tkinter 控件
            **kwargs: bg, fg, font, etc.
        """
        try:
            widget.configure(**kwargs)
        except tk.TclError:
            pass


# ================================================================
#  StatusPanel — 右面板状态显示
# ================================================================

class StatusPanel:
    """通用状态面板 — 显示 HP/理智/进度/章节等数值。

    使用示例:
        panel = StatusPanel(parent, styles)
        panel.set_fields(["hp", "sanity", "chapter", "progress"])
        panel.update(hp=75, sanity=60, chapter="Chapter 1", progress="3/10")
    """

    def __init__(
        self,
        parent: tk.Widget,
        styles: Styles,
        title: str = "◆ 状态 ◆",
        fields: Optional[List[Tuple[str, str]]] = None,
    ):
        """初始化状态面板。

        参数:
            parent: 父控件
            styles: Styles 实例
            title: 面板标题
            fields: 字段列表 [(key, default_label), ...]
        """
        self.parent = parent
        self.styles = styles
        self.s = styles

        self.frame = tk.Frame(parent, bg=self.s.BG_DARKEST)
        self.labels: Dict[str, tk.Label] = {}
        self._build(title, fields or [])

    def _build(self, title: str, fields: List[Tuple[str, str]]):
        """构建面板 UI。"""
        s = self.s

        # 标题
        title_label = tk.Label(
            self.frame, text=title,
            font=s.fonts["small"], fg=s.TEXT_DIM, bg=s.BG_DARKEST,
        )
        title_label.pack(pady=(6, 2))

        # 字段
        for key, default_text in fields:
            lbl = tk.Label(
                self.frame, text=default_text,
                font=s.fonts["status"], fg=s.TEXT_SECONDARY, bg=s.BG_DARKEST,
                anchor="w",
            )
            lbl.pack(fill="x", padx=8, pady=1)
            self.labels[key] = lbl

        # 分隔线
        sep = tk.Frame(self.frame, bg=s.BORDER_DARK, height=1)
        sep.pack(fill="x", padx=6, pady=4)

    def set_fields(self, fields: List[Tuple[str, str]]):
        """重新设置面板字段（清除旧字段）。

        参数:
            fields: [(key, default_label), ...]
        """
        for lbl in self.labels.values():
            lbl.destroy()
        self.labels.clear()
        # 重新构建（不重建 title）
        for key, default_text in fields:
            lbl = tk.Label(
                self.frame, text=default_text,
                font=self.s.fonts["status"], fg=self.s.TEXT_SECONDARY,
                bg=self.s.BG_DARKEST, anchor="w",
            )
            lbl.pack(fill="x", padx=8, pady=1)
            self.labels[key] = lbl

    def update(self, **kwargs):
        """更新面板字段值。

        参数:
            key=value 对，key 对应 set_fields 时注册的 key。
            特殊处理:
            - hp/max_hp: 自动颜色映射（绿/黄/红）
            - progress: 百分比进度颜色
        """
        s = self.s

        # 特殊字段处理
        if "hp" in kwargs and "max_hp" in kwargs:
            hp_val = kwargs["hp"]
            max_val = kwargs["max_hp"]
            if isinstance(hp_val, (int, float)) and max_val > 0:
                ratio = hp_val / max_val
                if ratio > 0.6:
                    color = s.STATUS_HIGH
                elif ratio > 0.3:
                    color = s.STATUS_MED
                else:
                    color = s.STATUS_LOW
                if "hp" in self.labels:
                    self.labels["hp"].config(
                        text=f"HP: {hp_val}/{max_val}", fg=color
                    )

        # 通用字段
        for key, value in kwargs.items():
            if key in self.labels:
                label = self.labels[key]
                current = label.cget("text")
                # 逗号分隔的格式：更新等号后面的值
                if ":" in current:
                    prefix = current.split(":")[0]
                    new_text = f"{prefix}: {value}"
                else:
                    new_text = str(value)
                label.config(text=new_text)


# ================================================================
#  BaseWindow — Tkinter 窗口基类
# ================================================================

class BaseWindow:
    """Tkinter 通用窗口基类。

    布局:
        +----------------------------------------------+
        |  [Title Bar: 标题]                            |
        +----------------------------------------------+
        |  [Main Content]  |  [Status Panel (右面板)]   |
        |                   |                            |
        +----------------------------------------------+
        |  [Bottom Panel: 按钮 / 输入]                  |
        +----------------------------------------------+

    使用示例:
        class MyGameWindow(BaseWindow):
            def __init__(self, engine):
                super().__init__(
                    title="My Game",
                    width=1100, height=720,
                    theme="dark",
                )
                self.set_back_callback(self.on_back)
                self._build_content()

            def _build_content(self):
                # 向 self.content_frame 添加控件
                tk.Label(self.content_frame, text="Hello").pack()

            def on_back(self):
                self.shutdown()
    """

    def __init__(
        self,
        title: str = "Allin Engine",
        width: int = 1100,
        height: int = 720,
        min_width: int = 900,
        min_height: int = 560,
        theme: str = "dark",
        font_overrides: Optional[Dict[str, tkfont.Font]] = None,
        show_title_bar: bool = True,
        show_status_panel: bool = True,
        show_bottom_panel: bool = True,
    ):
        """初始化窗口。

        参数:
            title: 窗口标题
            width, height: 窗口尺寸
            min_width, min_height: 最小尺寸
            theme: 主题 ("dark" / "light")
            font_overrides: 字体覆写
            show_title_bar: 是否显示标题栏
            show_status_panel: 是否显示右侧状态面板
            show_bottom_panel: 是否显示底部按钮区
        """
        self._window_title = title
        self._theme = theme
        self._show_title_bar = show_title_bar
        self._show_status_panel = show_status_panel
        self._show_bottom_panel = show_bottom_panel

        # 创建 Tk 根窗口
        self.root = tk.Tk()
        self.root.title(title)
        self.root.configure(bg=DARK_PALETTE["BG_DARKEST"])

        # 样式
        self.styles = Styles(
            theme=theme,
            overrides={
                "WINDOW_WIDTH": width,
                "WINDOW_HEIGHT": height,
                "WINDOW_MIN_WIDTH": min_width,
                "WINDOW_MIN_HEIGHT": min_height,
            },
        )

        # 应用自定义字体
        if font_overrides:
            self.styles.fonts.update(font_overrides)

        self.s = self.styles
        self.fonts = self.styles.fonts
        w, h = self.s.WINDOW_WIDTH, self.s.WINDOW_HEIGHT
        mw, mh = self.s.WINDOW_MIN_WIDTH, self.s.WINDOW_MIN_HEIGHT

        self.root.geometry(f"{w}x{h}")
        self.root.minsize(mw, mh)

        # 回调
        self._back_callback: Optional[Callable[[], None]] = None
        self._quit_callback: Optional[Callable[[], None]] = None
        self._input_callback: Optional[Callable[[str], None]] = None

        # 布局网格
        row = 0
        if show_title_bar:
            row = self._build_title_bar(row)
        row = self._build_main_area(row)
        if show_bottom_panel:
            self._build_bottom_panel(row)

        # 绑定事件
        self._bind_events()

    # ── 子组件构建 ──

    def _build_title_bar(self, row: int) -> int:
        """构建标题栏。返回下一行号。"""
        s = self.s
        top = tk.Frame(
            self.root, bg=s.BG_MEDIUM, height=36,
            highlightbackground=s.BORDER_ACCENT, highlightthickness=1,
        )
        top.grid(row=row, column=0, sticky="ew")
        top.grid_propagate(False)
        self.root.grid_rowconfigure(row, weight=0)

        tk.Label(
            top, text=f"  {self._window_title}",
            font=self.fonts["heading"], fg=s.ACCENT_RED, bg=s.BG_MEDIUM,
        ).pack(side="left", padx=s.PADDING_MD)

        self.title_extra_label = tk.Label(
            top, text="", font=self.fonts["small"], fg=s.TEXT_DIM, bg=s.BG_MEDIUM,
        )
        self.title_extra_label.pack(side="right", padx=s.PADDING_LG)

        # 红色分隔线
        tk.Frame(self.root, bg=s.ACCENT_RED, height=2).grid(
            row=row + 1, column=0, sticky="ew"
        )
        return row + 2

    def _build_main_area(self, row: int) -> int:
        """构建主内容区域。返回下一行号。"""
        s = self.s
        has_right = self._show_status_panel

        self.root.grid_rowconfigure(row, weight=1)
        self.root.grid_columnconfigure(0, weight=1)

        main_frame = tk.Frame(self.root, bg=s.BG_DARKEST)
        main_frame.grid(row=row, column=0, sticky="nsew")
        main_frame.grid_rowconfigure(0, weight=1)
        main_frame.grid_columnconfigure(0, weight=1)
        if has_right:
            main_frame.grid_columnconfigure(1, weight=0)

        # 左：主内容区域
        left = tk.Frame(
            main_frame, bg=s.BG_DARK, width=s.PANEL_LEFT_WIDTH,
            highlightbackground=s.BORDER_DARK, highlightthickness=1,
        )
        left.grid(row=0, column=0, sticky="nsew",
                   padx=(s.PADDING_SM, s.PADDING_SM), pady=s.PADDING_SM)
        left.grid_propagate(False)
        left.grid_rowconfigure(0, weight=1)
        left.grid_columnconfigure(0, weight=1)

        self.content_frame = tk.Frame(left, bg=s.BG_DARK)
        self.content_frame.grid(row=0, column=0, sticky="nsew")
        self.content_frame.grid_rowconfigure(0, weight=1)
        self.content_frame.grid_columnconfigure(0, weight=1)

        # 右：状态面板
        if has_right:
            right = tk.Frame(main_frame, bg=s.BG_DARKEST, width=s.PANEL_RIGHT_WIDTH)
            right.grid(row=0, column=1, sticky="nsew",
                        padx=(0, s.PADDING_SM), pady=s.PADDING_SM)
            right.grid_propagate(False)
            right.grid_rowconfigure(0, weight=1)

            self.status_panel = StatusPanel(
                right, self.styles,
                fields=[
                    ("hp", "HP: --/--"),
                    ("sanity", "理智: --"),
                    ("chapter", "章节: --"),
                    ("progress", "进度: --/--"),
                ],
            )
            self.status_panel.frame.grid(row=0, column=0, sticky="new")

        return row + 1

    def _build_bottom_panel(self, row: int):
        """构建底部按钮面板。"""
        s = self.s
        bottom = tk.Frame(
            self.root, bg=s.BG_PANEL, height=s.PANEL_BOTTOM_HEIGHT,
            highlightbackground=s.BORDER_ACCENT, highlightthickness=1,
        )
        bottom.grid(row=row, column=0, sticky="ew")
        bottom.grid_propagate(False)
        bottom.grid_rowconfigure(0, weight=1)
        bottom.grid_columnconfigure(0, weight=1)

        self.bottom_frame = tk.Frame(bottom, bg=s.BG_PANEL)
        self.bottom_frame.grid(row=0, column=0, sticky="nsew")
        self._button_frames: List[tk.Widget] = []

    # ── 事件绑定 ──

    def _bind_events(self):
        """绑定键盘和窗口事件。"""
        self.root.bind("<Escape>", lambda e: self._on_quit())
        self.root.protocol("WM_DELETE_WINDOW", self._on_quit)

    def _on_quit(self):
        """退出处理。"""
        if self._quit_callback:
            self._quit_callback()
        try:
            self.root.destroy()
        except tk.TclError:
            pass

    # ── 回调设置 ──

    def set_back_callback(self, callback: Callable[[], None]):
        """设置返回/后退回调。

        参数:
            callback: 无参回调函数
        """
        self._back_callback = callback

    def set_quit_callback(self, callback: Callable[[], None]):
        """设置退出回调。

        参数:
            callback: 无参回调函数
        """
        self._quit_callback = callback

    def set_input_callback(self, callback: Callable[[str], None]):
        """设置文本输入回调。

        参数:
            callback: 接收输入字符串的回调
        """
        self._input_callback = callback

    def back(self, callback: Optional[Callable[[], None]] = None):
        """调用返回回调。

        参数:
            callback: 可选的回调（覆盖已设置的回调）
        """
        cb = callback or self._back_callback
        if cb:
            cb()

    # ── 面板交互方法 ──

    def show_buttons(
        self,
        buttons: List[Tuple[str, Callable[[], None]]],
        layout: str = "horizontal",
    ):
        """在底部面板显示按钮。

        参数:
            buttons: [(label, callback), ...]
            layout: "horizontal" 或 "vertical"
        """
        self.clear_buttons()
        s = self.s

        for label, cb in buttons:
            btn = tk.Button(
                self.bottom_frame,
                text=label,
                font=self.fonts["button"],
                fg=s.BTN_TEXT, bg=s.BTN_BG,
                activebackground=s.BTN_HOVER,
                activeforeground=s.TEXT_PRIMARY,
                highlightthickness=1,
                highlightbackground=s.BORDER_DARK,
                cursor="hand2",
                command=cb,
            )
            if layout == "horizontal":
                btn.pack(side="left", padx=4, pady=8, expand=True, fill="x")
            else:
                btn.pack(side="top", padx=10, pady=2, fill="x")
            self._button_frames.append(btn)

    def show_text_input(
        self,
        placeholder: str = "",
        submit_label: str = "确认",
        on_submit: Optional[Callable[[str], None]] = None,
    ):
        """在底部面板显示文本输入框。

        参数:
            placeholder: 占位文字
            submit_label: 确认按钮文字
            on_submit: 提交回调
        """
        self.clear_buttons()
        s = self.s

        input_frame = tk.Frame(self.bottom_frame, bg=s.BG_PANEL)
        input_frame.pack(fill="x", padx=10, pady=8)

        entry = tk.Entry(
            input_frame, font=self.fonts["input"],
            bg=s.BG_INPUT, fg=s.TEXT_PRIMARY,
            insertbackground=s.TEXT_PRIMARY,
            relief="flat",
        )
        entry.insert(0, placeholder)
        entry.pack(side="left", fill="x", expand=True, padx=(0, 8))

        def _submit():
            text = entry.get()
            cb = on_submit or self._input_callback
            if cb:
                cb(text)

        btn = tk.Button(
            input_frame, text=submit_label,
            font=self.fonts["button"],
            fg=s.BTN_TEXT, bg=s.BTN_BG,
            activebackground=s.BTN_HOVER,
            cursor="hand2",
            command=_submit,
        )
        btn.pack(side="right")

        entry.bind("<Return>", lambda e: _submit())
        entry.focus_set()
        self._button_frames.extend([input_frame, entry, btn])

    def clear_buttons(self):
        """清除底部面板所有按钮/控件。"""
        for w in self._button_frames:
            w.destroy()
        self._button_frames.clear()
        # 也清除 bottom_frame 下的所有子控件
        for w in self.bottom_frame.winfo_children():
            w.destroy()

    def show_loading(self, message: str = "Loading..."):
        """在主内容区显示加载提示。

        参数:
            message: 提示文字
        """
        for w in self.content_frame.winfo_children():
            w.destroy()
        tk.Label(
            self.content_frame, text=message,
            font=self.fonts["heading"], fg=self.s.TEXT_DIM,
            bg=self.s.BG_DARK,
        ).pack(expand=True)

    def set_title_extra(self, text: str):
        """设置标题栏右侧额外文字。

        参数:
            text: 文字内容
        """
        if hasattr(self, "title_extra_label"):
            self.title_extra_label.config(text=text)

    def update_status(self, **kwargs):
        """更新右侧状态面板。

        参数:
            key=value 对
        """
        if hasattr(self, "status_panel") and self.status_panel:
            self.status_panel.update(**kwargs)

    # ── 主题 ──

    def switch_theme(self, theme: str):
        """切换窗口主题。

        参数:
            theme: "dark" 或 "light"
        """
        self.styles.switch_theme(theme)
        # 更新根窗口背景
        palette = DARK_PALETTE if theme == "dark" else LIGHT_PALETTE
        self.root.configure(bg=palette["BG_DARKEST"])

    # ── 生命周期 ──

    def run(self):
        """启动 Tkinter 主循环。"""
        self.root.mainloop()

    def shutdown(self):
        """关闭窗口。"""
        try:
            self.root.destroy()
        except tk.TclError:
            pass

    def update_idle(self):
        """刷新待处理事件（用于动画帧更新）。"""
        try:
            self.root.update_idletasks()
            self.root.update()
        except tk.TclError:
            pass


# ================================================================
#  TkUtil — Tkinter 工具函数
# ================================================================

class TkUtil:
    """Tkinter 静态工具类。"""

    @staticmethod
    def create_scrollable_frame(
        parent: tk.Widget,
        bg: str = "",
        width: int = 0,
        height: int = 0,
    ) -> Tuple[tk.Frame, tk.Canvas]:
        """创建可滚动的 Frame。

        参数:
            parent: 父控件
            bg: 背景色
            width, height: Canvas 尺寸

        返回:
            (internal_frame, canvas)
        """
        canvas = tk.Canvas(parent, bg=bg, highlightthickness=0, width=width, height=height)
        scrollbar = tk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)

        inner = tk.Frame(canvas, bg=bg)
        canvas.create_window(0, 0, anchor="nw", window=inner)

        inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        return inner, canvas

    @staticmethod
    def make_button(
        parent: tk.Widget,
        text: str,
        command: Callable[[], None],
        styles: Styles,
        font_key: str = "button",
        width: int = 0,
        height: int = 0,
    ) -> tk.Button:
        """快速创建样式化按钮。

        参数:
            parent: 父控件
            text: 按钮文字
            command: 点击回调
            styles: Styles 实例
            font_key: 字体名
            width, height: 按钮尺寸

        返回:
            tk.Button 实例
        """
        btn = tk.Button(
            parent, text=text, command=command,
            font=styles.fonts[font_key],
            fg=styles.BTN_TEXT, bg=styles.BTN_BG,
            activebackground=styles.BTN_HOVER,
            activeforeground=styles.TEXT_PRIMARY,
            highlightthickness=1,
            highlightbackground=styles.BORDER_DARK,
            cursor="hand2",
            width=width if width else None,
            height=height if height else None,
        )
        return btn

    @staticmethod
    def show_popup_dialog(
        parent: tk.Tk,
        title: str,
        message: str,
        buttons: Optional[List[Tuple[str, Callable[[], None]]]] = None,
        bg: str = "#1a1a2e",
        fg: str = "#e0d8c8",
    ):
        """显示弹出对话框。

        参数:
            parent: 父窗口
            title: 对话框标题
            message: 消息文本
            buttons: [(label, callback), ...]，默认 [("确定", None)]
            bg, fg: 颜色
        """
        dialog = tk.Toplevel(parent)
        dialog.title(title)
        dialog.configure(bg=bg)
        dialog.transient(parent)
        dialog.grab_set()

        # 居中
        dialog.geometry("400x200")
        dialog.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() - 400) // 2
        y = parent.winfo_y() + (parent.winfo_height() - 200) // 2
        dialog.geometry(f"+{x}+{y}")

        tk.Label(
            dialog, text=message, bg=bg, fg=fg,
            font=tkfont.Font(family=FONT_FAMILY_MONO, size=12),
            wraplength=360, justify="center",
        ).pack(expand=True, pady=20)

        btn_frame = tk.Frame(dialog, bg=bg)
        btn_frame.pack(pady=(0, 16))

        if buttons is None:
            buttons = [("确定", dialog.destroy)]

        for label, cb in buttons:
            cmd = cb if cb else dialog.destroy
            tk.Button(
                btn_frame, text=label, command=cmd,
                bg="#2a2a45", fg=fg, activebackground="#3a3a60",
                cursor="hand2",
            ).pack(side="left", padx=8)
