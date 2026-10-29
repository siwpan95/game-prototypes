# -*- coding: utf-8 -*-
"""
Canvas 进度条组件 — 带缓动动画与多主题支持
从 zhuangtaiji 整合而来，配色适配探险日志暖色纸卷风格
"""

import tkinter as tk
from dataclasses import dataclass
from typing import Optional, Callable


# ==================== 缓动函数 ====================
def ease_out_quad(t: float) -> float:
    """二次缓出：开始快，结束慢"""
    return 1 - (1 - t) ** 2


def ease_in_out_quad(t: float) -> float:
    """二次缓入缓出"""
    return 2 * t * t if t < 0.5 else 1 - (-2 * t + 2) ** 2 / 2


def ease_out_cubic(t: float) -> float:
    """三次缓出"""
    return 1 - (1 - t) ** 3


EASING_MAP = {
    "linear": lambda t: t,
    "ease_out": ease_out_quad,
    "ease_in_out": ease_in_out_quad,
    "ease_out_cubic": ease_out_cubic,
}


# ==================== 颜色主题 ====================
@dataclass
class BarTheme:
    bar_color: str = "#2A9D8F"       # 默认：青色（探险日志主色调）
    bg_color: str = "#E8DCC8"        # 背景：暖色纸卷
    border_color: str = "#8B7355"    # 边框：木色
    text_color: str = "#4A3728"      # 文字：深棕色
    bar_high: str = "#E9C46A"        # >80% 时变色：金色


# 探险日志专属主题
LOG_THEME = BarTheme()

# 战斗主题（红色系）
BATTLE_THEME = BarTheme(
    bar_color="#E76F51", bg_color="#F4E4D4",
    border_color="#C0392B", text_color="#5D2E2E", bar_high="#F4A261"
)

# 探索主题（蓝色系）
EXPLORE_THEME = BarTheme(
    bar_color="#4A90D9", bg_color="#D6E8F7",
    border_color="#2C5F8A", text_color="#1C3D5A", bar_high="#7FB5E3"
)

# 休息主题（绿色系）
REST_THEME = BarTheme(
    bar_color="#6ABF69", bg_color="#DFF0D8",
    border_color="#3D7A3A", text_color="#2D5A2A", bar_high="#A8D8A6"
)

# 购物主题（金色系）
SHOP_THEME = BarTheme(
    bar_color="#E9C46A", bg_color="#FFF8E7",
    border_color="#B8860B", text_color="#7B5B00", bar_high="#F5D77A"
)

# 招募主题（紫色系）
RECRUIT_THEME = BarTheme(
    bar_color="#9B59B6", bg_color="#EDE1F2",
    border_color="#6C3483", text_color="#4A235A", bar_high="#C39BD3"
)

# 主题映射：根据阶段名称自动选择主题
PHASE_THEMES = {
    "招募": RECRUIT_THEME,
    "购物": SHOP_THEME,
    "探索": EXPLORE_THEME,
    "战斗": BATTLE_THEME,
    "休息": REST_THEME,
    "循环": LOG_THEME,
}


# ==================== 进度条组件 ====================
class CanvasProgressBar:
    """可反复调用的 Canvas 进度条，支持缓动动画与状态机绑定"""

    def __init__(self, parent, width: int = 420, height: int = 28,
                 theme: BarTheme = None, show_percentage: bool = True,
                 label: str = ""):
        self.theme = theme or LOG_THEME
        self.label = label

        # 容器 Frame
        self.container = tk.Frame(parent, bg=self.theme.bg_color)
        self.container.pack(fill=tk.X, padx=10, pady=4)

        # 标签文字
        if label:
            self.label_widget = tk.Label(
                self.container, text=label,
                font=("Microsoft YaHei", 10, "bold"),
                bg=self.theme.bg_color, fg=self.theme.text_color
            )
            self.label_widget.pack(side=tk.TOP, anchor=tk.W, padx=4, pady=(2, 0))

        # Canvas 进度条
        self.canvas = tk.Canvas(
            self.container, width=width, height=height,
            bg=self.theme.bg_color, highlightthickness=0
        )
        self.canvas.pack(pady=4, padx=8)

        self.width = width
        self.height = height

        # 背景圆角框
        self.canvas.create_rectangle(
            1, 1, width, height,
            outline=self.theme.border_color, width=2
        )

        # 进度填充条
        self.bar_rect = self.canvas.create_rectangle(
            2, 2, 2, height - 1,
            fill=self.theme.bar_color, outline=""
        )

        # 百分比文字
        self.show_percentage = show_percentage
        self.text_id = self.canvas.create_text(
            width / 2, height / 2, text="0%",
            font=("Microsoft YaHei", max(9, height // 3), "bold"),
            fill=self.theme.text_color
        ) if show_percentage else None

        # 状态文字（进度条下方）
        self.status_var = tk.StringVar(value="等待启动...")
        self.status_label = tk.Label(
            self.container, textvariable=self.status_var,
            font=("Microsoft YaHei", 8), bg=self.theme.bg_color,
            fg=self.theme.text_color, anchor=tk.W
        )
        self.status_label.pack(fill=tk.X, padx=8, pady=(0, 4))

        # 绑定的状态机
        self.bound_sm = None
        self._progress = 0

        # 动画控制
        self._animating = False
        self._paused = False
        self._on_complete: Optional[Callable] = None

        # 不确定模式
        self._indeterminate = False
        self._indeterminate_dir = 1
        self._indeterminate_pos = 0

    # ==================== 外观更新 ====================
    def set_label(self, label: str):
        """动态更新标签"""
        self.label = label
        if hasattr(self, 'label_widget'):
            self.label_widget.configure(text=label)

    def set_theme(self, theme: BarTheme):
        """动态切换主题"""
        self.theme = theme
        self.canvas.configure(bg=theme.bg_color)
        self.container.configure(bg=theme.bg_color)
        if hasattr(self, 'label_widget'):
            self.label_widget.configure(bg=theme.bg_color, fg=theme.text_color)
        self.status_label.configure(bg=theme.bg_color, fg=theme.text_color)
        if self.text_id:
            self.canvas.itemconfig(self.text_id, fill=theme.text_color)
        # 重绘背景边框
        self.canvas.delete("border")
        self.canvas.create_rectangle(
            1, 1, self.width, self.height,
            outline=theme.border_color, width=2, tags="border"
        )
        self.set_progress(self._progress)  # 刷新颜色

    def set_status(self, text: str):
        """更新状态文字"""
        self.status_var.set(text)

    # ==================== 状态机绑定 ====================
    def bind_state_machine(self, sm_instance):
        """将进度条逻辑上绑定到一个状态机"""
        self.bound_sm = sm_instance
        self.reset()

    # ==================== 进度控制 ====================
    def set_progress(self, percent: float):
        self._progress = max(0, min(percent, 100))
        fill_width = (self._progress / 100) * (self.width - 2)
        color = self.theme.bar_high if self._progress >= 80 else self.theme.bar_color
        self.canvas.itemconfig(self.bar_rect, fill=color)
        self.canvas.coords(self.bar_rect, 2, 2, 2 + fill_width, self.height - 1)
        if self.show_percentage and self.text_id:
            self.canvas.itemconfig(self.text_id, text=f"{int(self._progress)}%")
        self.canvas.update_idletasks()

    def reset(self):
        self.set_progress(0)
        self._animating = False
        self._paused = False
        self._indeterminate = False
        self.status_var.set("等待启动...")

    @property
    def progress(self) -> float:
        return self._progress

    # ==================== 动画 ====================
    def animate(self, step: int = 2, delay: int = 20,
                on_complete: Callable = None, easing: str = "linear"):
        """执行进度条动画（0→100%）"""
        self._animating = True
        self._paused = False
        self._indeterminate = False
        self._on_complete = on_complete
        ease_fn = EASING_MAP.get(easing, EASING_MAP["linear"])

        def _step_forward(raw_step):
            if not self._animating:
                return
            if self._paused:
                self.canvas.after(delay, lambda: _step_forward(raw_step))
                return
            if raw_step <= 100:
                t = raw_step / 100.0
                display = int(ease_fn(t) * 100)
                self.set_progress(display)
                self.canvas.after(delay, lambda: _step_forward(raw_step + step))
            else:
                self.set_progress(100)
                self._animating = False
                if callable(self._on_complete):
                    self._on_complete()

        _step_forward(0)

    def animate_indeterminate(self, delay: int = 15, on_stop: Callable = None):
        """不确定模式：来回弹跳的滑块（表示"等待中"）"""
        self._animating = True
        self._paused = False
        self._indeterminate = True
        self._on_complete = on_stop
        bar_w = self.width * 0.3

        def _bounce():
            if not self._animating:
                return
            if self._paused:
                self.canvas.after(delay, _bounce)
                return
            max_x = (self.width - 2) - bar_w
            self._indeterminate_pos += 3 * self._indeterminate_dir
            if self._indeterminate_pos >= max_x:
                self._indeterminate_pos = max_x
                self._indeterminate_dir = -1
            elif self._indeterminate_pos <= 0:
                self._indeterminate_pos = 0
                self._indeterminate_dir = 1
            self.canvas.coords(
                self.bar_rect,
                2 + self._indeterminate_pos, 2,
                2 + self._indeterminate_pos + bar_w, self.height - 1
            )
            if self.show_percentage and self.text_id:
                self.canvas.itemconfig(self.text_id, text="...")
            self.canvas.update_idletasks()
            self.canvas.after(delay, _bounce)

        _bounce()

    # ==================== 暂停/恢复 ====================
    def pause(self):
        self._paused = True

    def resume(self):
        self._paused = False

    @property
    def is_paused(self) -> bool:
        return self._paused

    @property
    def is_running(self) -> bool:
        return self._animating and not self._paused

    def stop(self):
        """强制终止动画"""
        self._animating = False
        self._paused = False

    # ==================== 布局控制 ====================
    def pack(self, **kwargs):
        self.container.pack(**kwargs)

    def pack_forget(self):
        self.container.pack_forget()

    def destroy(self):
        self.stop()
        self.container.destroy()
