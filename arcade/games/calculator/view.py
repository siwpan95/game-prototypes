"""
CalculatorView — MVVM View 层
职责：
  - 纯 UI 渲染，不引用 Model，不引用任何业务逻辑。
  - 在 __init__ 接收 ViewModel，调用 vm.on_button(token) 处理点击。
  - 通过 Observable.bind() 绑定 ViewModel 的可观察属性，属性变更时自动刷新。
  - shuffle() 由外部（main.py）调用，View 自己不决定何时 shuffle。

增强版（基于 Alchemia 解密游戏指南）：
  - 双主题：默认深色 + Alchemia 羊皮纸棕（进入 #alch 后切换）
  - 底部状态栏：显示当前模式与已解锁成就数
  - 多行显示：支持 #brute / #page 等多行结果
  - 成就解锁闪烁动画
"""

import tkinter as tk
import random
from typing import Callable

# ─────────────────────────────────────────────────────────────
#  常量
# ─────────────────────────────────────────────────────────────
EMPTY = "□"   # 不可见占位符

BUTTON_TOKENS = [
    "(", ")", "←", "÷",
    "7", "8", "9", "×",
    "4", "5", "6", "-",
    "1", "2", "3", "+",
    "0", ".", "=", EMPTY,
]

ALWAYS_ACTIVE = {"←", "=", EMPTY}

# ── 默认深色主题（原计算器）──
COLORS_DARK = {
    "bg":          "#1e1e2e",
    "display_bg":  "#181825",
    "display_fg":  "#cdd6f4",
    "expr_fg":     "#6c7086",
    "sep_color":   "#313244",
    "btn_num":     "#313244",
    "btn_op":      "#45475a",
    "btn_eq":      "#89b4fa",
    "btn_back":    "#f38ba8",
    "btn_fg":      "#cdd6f4",
    "btn_eq_fg":   "#1e1e2e",
    "btn_dis":     "#2a2a3a",
    "btn_dis_fg":  "#555577",
    "btn_num_hv":  "#3b3b50",
    "btn_op_hv":   "#525368",
    "btn_eq_hv":   "#9cc5fb",
    "btn_back_hv": "#f5a0b4",
    "status_bg":   "#11111b",
    "status_fg":   "#6c7086",
    "ach_fg":      "#f9e2af",
}

# ── Alchemia 羊皮纸主题（进入 #alch 后切换）──
COLORS_ALCHEMIA = {
    "bg":          "#2b1d0e",   # 深棕
    "display_bg":  "#1f1408",   # 更深棕
    "display_fg":  "#e8d5a8",   # 羊皮纸色
    "expr_fg":     "#a08766",   # 浅棕
    "sep_color":   "#5c4220",
    "btn_num":     "#3d2814",
    "btn_op":      "#5c4220",
    "btn_eq":      "#d4a849",   # 金色
    "btn_back":    "#c84630",   # 朱砂
    "btn_fg":      "#e8d5a8",
    "btn_eq_fg":   "#1f1408",
    "btn_dis":     "#2a1d0a",
    "btn_dis_fg":  "#5c4220",
    "btn_num_hv":  "#4d3520",
    "btn_op_hv":   "#6c5230",
    "btn_eq_hv":   "#e8b859",
    "btn_back_hv": "#d85640",
    "status_bg":   "#150c04",
    "status_fg":   "#a08766",
    "ach_fg":      "#ffd700",
}

# 默认使用深色主题
COLORS = COLORS_DARK


class CalculatorView(tk.Frame):
    """
    MVVM View：

    - 接收 ViewModel，绑定可观察属性。
    - 按钮点击调用 vm.on_button(token)。
    - shuffle() 供外部调用以打乱按钮布局。
    - 监听 crypto_mode 切换主题（普通模式 / Alchemia 模式）。
    """

    GRID_COLS  = 4
    BTN_FONT   = ("Consolas", 16, "bold")
    DISP_FONTS = [
        ("Consolas", 30, "bold"),   # 0-6  字符
        ("Consolas", 24, "bold"),   # 7-9  字符
        ("Consolas", 18, "bold"),   # 10-15 字符
        ("Consolas", 12, "bold"),   # 16+  字符 / 多行
    ]
    EXPR_FONT   = ("Consolas", 13)
    STATUS_FONT = ("Consolas", 9)

    def __init__(self, master: tk.Tk, viewmodel):
        super().__init__(master, bg=COLORS["bg"])
        self._vm      = viewmodel
        self._buttons: dict[str, tk.Button] = {}
        self._order   = BUTTON_TOKENS[:]
        self._disp_var = tk.StringVar(value="0")
        self._expr_var = tk.StringVar(value="")
        self._status_var = tk.StringVar(value="普通模式 | 成就: 0")
        self._theme   = "dark"
        self._ach_flash_count = 0
        self._build_display()
        self._build_status_bar()
        self._build_buttons()
        self._bind_viewmodel()

    # ── 绑定 ViewModel 可观察属性 ─────────────────────────────────
    def _bind_viewmodel(self) -> None:
        """将 ViewModel 的 Observable 属性绑定到 View 更新方法。"""
        self._vm.display_text.bind(self._on_display_text)
        self._vm.expression_text.bind(self._on_expression_text)
        self._vm.char_limit.bind(self._on_limits_change)
        self._vm.digit_limit.bind(self._on_limits_change)
        self._vm.crypto_mode.bind(self._on_crypto_mode_change)
        self._vm.achievement.bind(self._on_achievement_change)

    def _on_display_text(self, text: str) -> None:
        # 处理多行文本
        display_text = text or "0"
        self._disp_var.set(display_text)
        # 计算行数
        line_count = display_text.count("\n") + 1
        if line_count > 1:
            font = self.DISP_FONTS[3]  # 多行用最小字体
            # 限制显示行数（防止过长）
            if line_count > 8:
                lines = display_text.split("\n")
                display_text = "\n".join(lines[:8]) + f"\n... (共 {line_count} 行)"
                self._disp_var.set(display_text)
        else:
            font = self._scale_font(display_text)
        self._disp_label.config(font=font)

    def _on_expression_text(self, text: str) -> None:
        self._expr_var.set(text)

    def _on_limits_change(self, _: bool) -> None:
        # 任一限制标志变更，重新评估按钮状态
        self._update_button_states(
            self._vm.char_limit.value,
            self._vm.digit_limit.value,
        )

    def _on_crypto_mode_change(self, mode: str) -> None:
        """当密码学模式变化时，更新状态栏。"""
        self._update_status_bar()

    def _on_achievement_change(self, ach_id: str) -> None:
        """成就解锁时，触发显示闪烁。"""
        if not ach_id:
            return
        self._ach_flash_count = 6  # 闪烁 6 次
        self._flash_achievement()
        self._update_status_bar()

    def _flash_achievement(self) -> None:
        """闪烁状态栏以提示成就解锁。"""
        if self._ach_flash_count <= 0:
            self._update_status_bar()
            return
        # 交替金色/普通色
        if self._ach_flash_count % 2 == 0:
            self._status_label.config(fg=COLORS["ach_fg"])
        else:
            self._status_label.config(fg=COLORS["status_fg"])
        self._ach_flash_count -= 1
        self.after(300, self._flash_achievement)

    # ── 字体自适应 ─────────────────────────────────────────────
    def _scale_font(self, text: str):
        n = len(text)
        if n <= 6:
            return self.DISP_FONTS[0]
        if n <= 9:
            return self.DISP_FONTS[1]
        if n <= 15:
            return self.DISP_FONTS[2]
        return self.DISP_FONTS[3]

    # ── 显示区构建 ────────────────────────────────────────────
    def _build_display(self):
        disp_frame = tk.Frame(self, bg=COLORS["display_bg"])
        disp_frame.grid(row=0, column=0, columnspan=self.GRID_COLS,
                        sticky="ew", padx=10, pady=10)

        self._expr_label = tk.Label(
            disp_frame, textvariable=self._expr_var,
            bg=COLORS["display_bg"], fg=COLORS["expr_fg"],
            font=self.EXPR_FONT, anchor="e",
            padx=16, pady=0,
        )
        self._expr_label.pack(fill="x", pady=(12, 0))

        # 显示区支持多行（wraplength + justify）
        self._disp_label = tk.Label(
            disp_frame, textvariable=self._disp_var,
            bg=COLORS["display_bg"], fg=COLORS["display_fg"],
            font=self.DISP_FONTS[0], anchor="e",
            padx=16, pady=0,
            wraplength=300, justify="right",
        )
        self._disp_label.pack(fill="x", pady=(2, 14))

        sep = tk.Frame(self, bg=COLORS["sep_color"], height=1)
        sep.grid(row=1, column=0, columnspan=self.GRID_COLS,
                 sticky="ew", padx=10, pady=6)

        self.columnconfigure(list(range(self.GRID_COLS)), weight=1)

    # ── 底部状态栏 ────────────────────────────────────────────
    def _build_status_bar(self):
        self._status_label = tk.Label(
            self,
            textvariable=self._status_var,
            bg=COLORS["status_bg"], fg=COLORS["status_fg"],
            font=self.STATUS_FONT, anchor="w",
            padx=10, pady=4,
        )
        # 状态栏放在最底部（按钮区之后）
        # 实际位置在 _build_buttons 后通过 grid row 调整
        self._status_label.grid(row=99, column=0, columnspan=self.GRID_COLS,
                                sticky="ew", padx=0, pady=(6, 0))

    def _update_status_bar(self) -> None:
        """更新状态栏文字：显示当前模式 + 成就数。"""
        mode = self._vm.crypto_mode.value or ""
        if mode == "alchemia" or self._vm.alchemia_active:
            mode_str = "🔮 Alchemia 解密模式"
        elif mode:
            mode_map = {
                "caesar":     "凯撒密码",
                "rot13":      "ROT13",
                "atbash":     "Atbash 倒序",
                "vigenere":   "维吉尼亚",
                "porta":      "Porta 密码",
                "trithemius": "Trithemius",
                "selenus":    "Selenus",
                "brute":      "凯撒爆破",
                "hash":       "哈希",
                "key":        "密钥生成",
                "salt":       "盐值生成",
                "password":   "密码哈希",
                "xor":        "异或加密",
                "base64":     "Base64",
                "fibonacci":  "斐波那契移位",
                "sieve":      "素数筛",
                "golden":     "黄金均值",
                "gematria":   "Gematria",
                "antikythera":"古希腊历法",
                "mirror":     "镜像 (As above)",
                "alchemy":    "炼金符号",
                "page":       "Alchemia 页码",
                "finalkey":   "最终密钥",
                "alchemia":   "Alchemia 总入口",
            }
            mode_str = f"🔐 {mode_map.get(mode, mode)}"
        else:
            mode_str = "普通模式"

        ach_count = len(self._vm.get_achievements())
        self._status_var.set(f"{mode_str} | 成就: {ach_count}/10")

    # ── 按钮颜色辅助 ──────────────────────────────────────────
    @staticmethod
    def _is_empty(token: str) -> bool:
        return token == EMPTY

    def _normal_colors(self, token: str):
        if self._is_empty(token):
            return COLORS["bg"], COLORS["bg"]
        if token == "=":
            return COLORS["btn_eq"], COLORS["btn_eq_fg"]
        if token == "←":
            return COLORS["btn_back"], COLORS["btn_fg"]
        if token in ("+", "-", "×", "÷", "(", ")"):
            return COLORS["btn_op"], COLORS["btn_fg"]
        return COLORS["btn_num"], COLORS["btn_fg"]

    def _hover_colors(self, token: str):
        if self._is_empty(token):
            return COLORS["bg"], COLORS["bg"]
        if token == "=":
            return COLORS["btn_eq_hv"], COLORS["btn_eq_fg"]
        if token == "←":
            return COLORS["btn_back_hv"], COLORS["btn_fg"]
        if token in ("+", "-", "×", "÷", "(", ")"):
            return COLORS["btn_op_hv"], COLORS["btn_fg"]
        return COLORS["btn_num_hv"], COLORS["btn_fg"]

    # ── 悬停事件 ──────────────────────────────────────────────
    def _on_enter(self, btn: tk.Button, token: str) -> None:
        if self._is_empty(token):
            return
        if str(btn.cget("state")) != "disabled":
            hbg, _ = self._hover_colors(token)
            btn.config(bg=hbg)

    def _on_leave(self, btn: tk.Button, token: str) -> None:
        if self._is_empty(token):
            return
        if str(btn.cget("state")) != "disabled":
            nbg, _ = self._normal_colors(token)
            btn.config(bg=nbg)

    # ── 按钮构建 ──────────────────────────────────────────────
    def _build_buttons(self):
        for w in self._buttons.values():
            w.destroy()
        self._buttons.clear()
        for idx, token in enumerate(self._order):
            r, c      = divmod(idx, self.GRID_COLS)
            bg, fg    = self._normal_colors(token)
            is_empty  = self._is_empty(token)
            btn = tk.Button(
                self,
                text="" if is_empty else token,
                bg=bg, fg=fg,
                activebackground=bg if is_empty else fg,
                activeforeground=fg if is_empty else bg,
                font=self.BTN_FONT,
                width=5, height=2,
                relief="flat",
                borderwidth=0,
                cursor="arrow" if is_empty else "hand2",
                takefocus=0,
                state="disabled" if is_empty else "normal",
                command=(lambda t=token: self._vm.on_button(t)) if not is_empty else None,
            )
            btn.grid(row=r + 2, column=c, padx=4, pady=4, sticky="nsew")
            if not is_empty:
                btn.bind("<Enter>", lambda e, b=btn, t=token: self._on_enter(b, t))
                btn.bind("<Leave>", lambda e, b=btn, t=token: self._on_leave(b, t))
            self._buttons[token] = btn
        total_rows = 2 + (len(self._order) + self.GRID_COLS - 1) // self.GRID_COLS
        for row in range(2, total_rows + 1):
            self.rowconfigure(row, weight=1)

    # ── 按钮 shuffle ──────────────────────────────────────────
    def shuffle(self) -> None:
        """由外部（main.py）在收到 shuffle 信号后调用。"""
        random.shuffle(self._order)
        self._regrid()

    def _regrid(self) -> None:
        for btn in self._buttons.values():
            btn.grid_forget()
        for idx, token in enumerate(self._order):
            r, c = divmod(idx, self.GRID_COLS)
            self._buttons[token].grid(row=r + 2, column=c,
                                       padx=4, pady=4, sticky="nsew")

    # ── 按钮状态（启用 / 禁用） ───────────────────────────────
    def _update_button_states(self, char_limit: bool, digit_limit: bool) -> None:
        for token, btn in self._buttons.items():
            if self._is_empty(token):
                continue
            if token in ALWAYS_ACTIVE:
                self._restore(btn, token)
                continue
            if char_limit or (digit_limit and (token.isdigit() or token == ".")):
                btn.config(
                    bg=COLORS["btn_dis"],
                    fg=COLORS["btn_dis_fg"],
                    state="disabled",
                    cursor="arrow",
                )
            else:
                self._restore(btn, token)

    def _restore(self, btn: tk.Button, token: str) -> None:
        bg, fg = self._normal_colors(token)
        btn.config(bg=bg, fg=fg, state="normal", cursor="hand2")
