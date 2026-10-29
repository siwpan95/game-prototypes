"""
动画效果工具 — 支持 Tkinter 和 Pygame 双后端

所有动画通过 after() 或帧调度实现，非阻塞。

提供的效果:
    - typewriter: 打字机逐字显示
    - fade:       淡入淡出
    - shake:      震动效果
    - pulse:      脉冲/闪烁效果

从 hell below/shared_core/animation.py 提取并泛化。
"""

from __future__ import annotations

import math
import time
from typing import Any, Callable, Optional, Tuple, Union


# ================================================================
#  Tkinter 动画后端
# ================================================================

class TkAnimation:
    """基于 Tkinter 的动画实现。"""

    @staticmethod
    def typewriter(
        widget,
        text: str,
        speed: float = 0.03,
        on_done: Optional[Callable[[], None]] = None,
        chunk_size: int = 3,
    ) -> None:
        """打字机效果 — 逐字符显示文本。

        参数:
            widget: Tkinter 控件（必须有 cget/config/after 方法）
            text: 要显示的文本
            speed: 每字符延迟（秒）
            on_done: 完成回调
            chunk_size: 每次添加的字符数（提高性能）
        """
        if not all(hasattr(widget, m) for m in ("config", "cget", "after")):
            # 无法动画，直接设置
            if hasattr(widget, "config"):
                widget.config(text=text)
            if on_done:
                on_done()
            return

        chars = list(text)
        idx = [0]

        def _step():
            i = idx[0]
            if i < len(chars):
                end = min(i + chunk_size, len(chars))
                chunk = "".join(chars[i:end])
                current = widget.cget("text") or ""
                widget.config(text=current + chunk)
                idx[0] = end
                widget.after(int(speed * 1000), _step)
            else:
                if on_done:
                    on_done()

        widget.config(text="")
        widget.after(10, _step)

    @staticmethod
    def fade(
        widget,
        target_color: str = "#e0d8c8",
        duration: float = 0.5,
        from_color: str = "#888888",
        steps: int = 15,
    ) -> None:
        """淡入效果 — 从 from_color 渐变到 target_color。

        参数:
            widget: Tkinter 控件（有 configure 方法）
            target_color: 目标前景色
            duration: 持续时间（秒）
            from_color: 起始颜色
            steps: 渐变步数
        """
        if not hasattr(widget, "configure") or not hasattr(widget, "after"):
            return

        try:
            hex_list = []
            from_tuple = _hex_to_rgb(from_color)
            to_tuple = _hex_to_rgb(target_color)
            for step in range(steps + 1):
                t = step / steps
                r = int(from_tuple[0] + (to_tuple[0] - from_tuple[0]) * t)
                g = int(from_tuple[1] + (to_tuple[1] - from_tuple[1]) * t)
                b = int(from_tuple[2] + (to_tuple[2] - from_tuple[2]) * t)
                hex_list.append(f"#{r:02x}{g:02x}{b:02x}")

            idx = [0]

            def _step():
                i = idx[0]
                if i < len(hex_list):
                    try:
                        widget.configure(fg=hex_list[i])
                    except Exception:
                        pass
                    idx[0] = i + 1
                    widget.after(int(duration * 1000 / steps), _step)

            _step()
        except Exception:
            # 回退：直接设置
            try:
                widget.configure(fg=target_color)
            except Exception:
                pass

    @staticmethod
    def shake(
        widget,
        intensity: int = 5,
        duration: float = 0.3,
        steps: int = 6,
    ) -> None:
        """震动效果 — 快速水平位移。

        参数:
            widget: Tkinter 控件（必须有 place_info/place 方法）
            intensity: 震动幅度（像素）
            duration: 持续时间（秒）
            steps: 震动次数
        """
        if not (hasattr(widget, "place_info") and hasattr(widget, "place")):
            return

        try:
            original = widget.place_info()
        except Exception:
            return

        step = [0]
        total_steps = steps * 2  # 来回各一次

        def _shake_step():
            s = step[0]
            if s >= total_steps:
                try:
                    widget.place(**{k: v for k, v in original.items() if v})
                except Exception:
                    pass
                return

            offset = intensity if s % 2 == 0 else -intensity
            x = original.get("x", "0")
            try:
                base_x = int(float(x))
                widget.place(x=base_x + offset)
            except (ValueError, TypeError):
                return

            step[0] = s + 1
            widget.after(int(duration * 1000 / total_steps), _shake_step)

        _shake_step()

    @staticmethod
    def pulse(
        widget,
        color_start: str = "#ffffff",
        color_end: str = "#e67e22",
        duration: float = 1.0,
        cycles: int = 3,
    ) -> None:
        """脉冲效果 — 前景色来回渐变。

        参数:
            widget: Tkinter 控件（有 configure 方法）
            color_start: 起始颜色
            color_end: 脉冲颜色
            duration: 单次脉冲时长（秒）
            cycles: 脉冲循环次数
        """
        if not hasattr(widget, "configure") or not hasattr(widget, "after"):
            return

        cycle = [0]
        total_steps = 10

        def _pulse_step():
            c = cycle[0]
            if c >= cycles * 2:
                return

            progress = (c % 2)  # 0=前往 end, 1=返回 start
            t = progress
            if c % 2 == 0:
                color = _lerp_hex(color_start, color_end, t)
            else:
                color = _lerp_hex(color_end, color_start, t)

            try:
                widget.configure(fg=color)
            except Exception:
                pass

            cycle[0] = c + 1
            widget.after(int(duration * 1000 / total_steps), _pulse_step)

        _pulse_step()


# ================================================================
#  Pygame 动画后端
# ================================================================

class PygameAnimation:
    """基于 Pygame 帧计时的动画实现。"""

    @staticmethod
    def typewriter(
        text: str,
        elapsed: float,
        speed: float = 0.03,
        chunk_size: int = 1,
    ) -> str:
        """打字机效果 — 根据已用时间返回已显示文本。

        参数:
            text: 完整文本
            elapsed: 已用时间（秒）
            speed: 每字符延迟（秒）
            chunk_size: 每次添加字符数

        返回:
            当前应显示的文本
        """
        chars_shown = min(len(text), int(elapsed / (speed * chunk_size)) * chunk_size)
        return text[:chars_shown]

    @staticmethod
    def fade_alpha(
        elapsed: float,
        duration: float = 1.0,
        fade_in: bool = True,
    ) -> int:
        """淡入淡出透明度计算。

        参数:
            elapsed: 已用时间（秒）
            duration: 持续时间（秒）
            fade_in: True=淡入, False=淡出

        返回:
            透明度值 (0~255)
        """
        t = min(1.0, max(0.0, elapsed / duration))
        alpha = t if fade_in else (1.0 - t)
        return int(alpha * 255)

    @staticmethod
    def shake_offset(
        elapsed: float,
        duration: float = 0.3,
        intensity: int = 5,
        frequency: float = 30.0,
    ) -> Tuple[float, float]:
        """震动偏移计算。

        参数:
            elapsed: 已用时间（秒）
            duration: 持续时间（秒）
            intensity: 震动幅度（像素）
            frequency: 震动频率（Hz）

        返回:
            (dx, dy) 偏移量
        """
        if elapsed > duration:
            return (0.0, 0.0)

        decay = 1.0 - elapsed / duration
        dx = math.sin(elapsed * frequency * 2 * math.pi) * intensity * decay
        dy = math.cos(elapsed * frequency * 1.7 * math.pi) * intensity * 0.5 * decay
        return (dx, dy)

    @staticmethod
    def pulse_scale(
        elapsed: float,
        duration: float = 1.0,
        min_scale: float = 0.9,
        max_scale: float = 1.1,
    ) -> float:
        """脉冲缩放计算。

        参数:
            elapsed: 已用时间（秒）
            duration: 脉冲周期（秒）
            min_scale: 最小缩放比
            max_scale: 最大缩放比

        返回:
            当前缩放因子
        """
        phase = (elapsed % duration) / duration
        t = (math.sin(phase * 2 * math.pi) + 1) / 2  # 0~1
        return min_scale + (max_scale - min_scale) * t


# ================================================================
#  统一 Animation 类
# ================================================================

class Animation:
    """统一动画入口 — 自动检测后端。

    对 Tkinter: 使用 TkAnimation（after 调度）
    对 Pygame:  使用 PygameAnimation（帧计时）

    用法:
        # Tkinter 模式
        Animation.typewriter(tk_label, "Hello World", speed=0.03)

        # Pygame 模式
        display_text = Animation.typewriter_pg(full_text, elapsed_time)
        alpha = Animation.fade_alpha_pg(elapsed_time, duration=1.0)
    """

    # ── Tkinter 后端 ──

    typewriter = staticmethod(TkAnimation.typewriter)
    fade = staticmethod(TkAnimation.fade)
    shake = staticmethod(TkAnimation.shake)
    pulse = staticmethod(TkAnimation.pulse)

    # ── Pygame 后端 ──

    typewriter_pg = staticmethod(PygameAnimation.typewriter)
    fade_alpha_pg = staticmethod(PygameAnimation.fade_alpha)
    shake_offset_pg = staticmethod(PygameAnimation.shake_offset)
    pulse_scale_pg = staticmethod(PygameAnimation.pulse_scale)

    @staticmethod
    def is_tkinter_backend(widget) -> bool:
        """检测是否为 Tkinter 后端。"""
        return hasattr(widget, "after") and hasattr(widget, "config")

    @staticmethod
    def auto_typewriter(
        widget_or_text: Any,
        text: str = "",
        speed: float = 0.03,
        on_done: Optional[Callable[[], None]] = None,
    ) -> None:
        """自动选择后端的打字机效果。

        如果 widget 支持 Tkinter 协议则使用 Tkinter 后端，
        否则使用 Pygame 协议（需要外部帧计时）。
        """
        if Animation.is_tkinter_backend(widget_or_text):
            TkAnimation.typewriter(widget_or_text, text, speed, on_done)
        else:
            raise ValueError(
                "Pygame 模式的 typewriter 需要外部帧计时，请使用 Animation.typewriter_pg()"
            )


# ================================================================
#  辅助函数
# ================================================================

def _hex_to_rgb(hex_color: str) -> Tuple[int, int, int]:
    """将 #RRGGBB 字符串转为 RGB 元组。"""
    hex_color = hex_color.lstrip("#")
    if len(hex_color) == 3:
        hex_color = "".join(c * 2 for c in hex_color)
    return (
        int(hex_color[0:2], 16),
        int(hex_color[2:4], 16),
        int(hex_color[4:6], 16),
    )


def _lerp_color(a: Tuple[int, int, int], b: Tuple[int, int, int], t: float) -> Tuple[int, int, int]:
    """线性插值两个 RGB 颜色。"""
    t = max(0.0, min(1.0, t))
    return (
        int(a[0] + (b[0] - a[0]) * t),
        int(a[1] + (b[1] - a[1]) * t),
        int(a[2] + (b[2] - a[2]) * t),
    )


def _lerp_hex(a: str, b: str, t: float) -> str:
    """线性插值两个 #RRGGBB 颜色，返回 #RRGGBB 字符串。"""
    ra, ga, ba = _hex_to_rgb(a)
    rb, gb, bb = _hex_to_rgb(b)
    r, g, b = _lerp_color((ra, ga, ba), (rb, gb, bb), t)
    return f"#{r:02x}{g:02x}{b:02x}"
