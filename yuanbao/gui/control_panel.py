"""控制面板：开始/暂停/单步/重置与速度调节。"""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable, Dict


class ControlPanel(ttk.Frame):
    """底部控制条。"""

    def __init__(self, master, callbacks: Dict[str, Callable], **kwargs):
        """
        callbacks 需包含键: on_start, on_pause, on_step, on_reset。
        """
        super().__init__(master, **kwargs)
        self.callbacks = callbacks

        self.start_btn = ttk.Button(self, text="▶ 开始", command=callbacks['on_start'])
        self.start_btn.grid(row=0, column=0, padx=4, pady=6)

        self.pause_btn = ttk.Button(self, text="⏸ 暂停", command=callbacks['on_pause'], state='disabled')
        self.pause_btn.grid(row=0, column=1, padx=4, pady=6)

        self.step_btn = ttk.Button(self, text="⏭ 单步", command=callbacks['on_step'])
        self.step_btn.grid(row=0, column=2, padx=4, pady=6)

        self.reset_btn = ttk.Button(self, text="🔄 重置", command=callbacks['on_reset'])
        self.reset_btn.grid(row=0, column=3, padx=4, pady=6)

        ttk.Separator(self, orient='vertical').grid(row=0, column=4, padx=8, sticky='ns')

        ttk.Label(self, text="速度:").grid(row=0, column=5, padx=(4, 2))
        self.speed = tk.DoubleVar(value=4.0)  # 步/秒
        self.speed_scale = ttk.Scale(
            self, from_=1, to=30, variable=self.speed, orient='horizontal', length=140
        )
        self.speed_scale.grid(row=0, column=6, padx=4)
        self.speed_lbl = ttk.Label(self, text="4.0 步/秒", width=10)
        self.speed_lbl.grid(row=0, column=7, padx=4)
        self.speed.trace_add('write', lambda *_: self.speed_lbl.config(text=f"{self.speed.get():.1f} 步/秒"))

    @property
    def interval(self) -> float:
        """当前速度对应的步间隔（秒）。"""
        v = self.speed.get()
        return 1.0 / v if v > 0 else 0.3

    def set_running(self, running: bool) -> None:
        """根据运行状态切换按钮可用性。"""
        self.start_btn.config(state='disabled' if running else 'normal')
        self.pause_btn.config(state='normal' if running else 'disabled')
        self.step_btn.config(state='disabled' if running else 'normal')
        self.reset_btn.config(state='disabled' if running else 'normal')
