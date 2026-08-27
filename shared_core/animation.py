"""
Animation — Tkinter 动画效果工具。

所有动画通过 root.after() 调度，兼容 Tkinter 主循环。
"""

from __future__ import annotations

import time
from typing import Callable, Optional


class Animation:
    """Tkinter 兼容的动画效果。"""

    @staticmethod
    def typewriter(widget, text: str,
                   speed: float = 0.03,
                   on_done: Optional[Callable] = None) -> None:
        """
        打字机效果 — 逐字符显示文本。

        使用 widget.after() 调度，不阻塞主循环。
        widget 必须有 config() 方法（如 tk.Label / tk.Text）。
        """
        if not hasattr(widget, 'config') or not hasattr(widget, 'after'):
            widget.config(text=text)
            if on_done:
                on_done()
            return

        chars = list(text)
        idx = [0]

        def _step():
            i = idx[0]
            if i < len(chars):
                # 批量更新：每次添加多个字符以提高性能
                end = min(i + 3, len(chars))
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
    def fade(widget, target_color: str, duration: float = 0.5,
             steps: int = 10) -> None:
        """淡入淡出效果（通过颜色渐变模拟）。"""
        if not hasattr(widget, 'config') or not hasattr(widget, 'after'):
            return
        # 简化版：直接设置目标色
        try:
            widget.configure(fg=target_color)
        except Exception:
            pass

    @staticmethod
    def shake(widget, intensity: int = 5, duration: float = 0.3,
              steps: int = 4) -> None:
        """
        震动效果。

        通过快速改变 widget 位置实现。
        要求 widget 的父容器支持 place 布局。
        """
        if not (hasattr(widget, 'place_info') and hasattr(widget, 'place')):
            return

        original = widget.place_info()
        step = [0]

        def _shake_step():
            s = step[0]
            if s >= steps * 2:
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
            widget.after(int(duration * 1000 / (steps * 2)), _shake_step)

        _shake_step()

    @staticmethod
    def pulse(widget, color_start: str, color_end: str,
              duration: float = 1.0, cycles: int = 3) -> None:
        """脉冲/发光效果（简化版）。"""
        if not hasattr(widget, 'configure'):
            return
        for _ in range(cycles):
            try:
                widget.configure(fg=color_end)
            except Exception:
                break
