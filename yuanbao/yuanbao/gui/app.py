"""GUI 主窗口。

线程模型
--------
``AutoRunner.run_threaded`` 在后台守护线程里跑演化循环，通过回调通知 UI。
tkinter 不是线程安全的，**所有 UI 更新必须回到主线程**，因此回调里统一用
``self.after(0, ...)`` 把刷新调度到主线程事件循环。

控制按钮通过 ``ControlPanel.set_running`` 切换可用状态，避免在运行中误触
"开始/重置"造成多个工作线程并存。
"""
from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk
from typing import Optional

from yuanbao.config import Config
from yuanbao.core.automaton import CellularAutomaton
from yuanbao.core.detector import CNNDetector
from yuanbao.engine.auto_runner import AutoRunner
from yuanbao.cli import build_default_tasks
from yuanbao.gui.grid_canvas import GridCanvas
from yuanbao.gui.control_panel import ControlPanel
from yuanbao.gui.task_panel import TaskPanel


class App(tk.Tk):
    """细胞工厂主窗口。"""

    def __init__(self, config: Optional[Config] = None, *, seed: Optional[int] = None):
        super().__init__()
        self.config_obj = config or Config()
        self.seed = seed
        self.title("🧬 细胞工厂 - 元胞自动机 × CNN 标签任务系统")
        self.resizable(False, False)

        self._build_world()
        self._build_ui()
        self._refresh()

    # ---- 世界构建 ----
    def _build_world(self) -> None:
        self.ca = CellularAutomaton(self.config_obj, seed=self.seed)
        self.detector = CNNDetector(self.config_obj.GRID_SIZE, self.config_obj)
        self.tasks = build_default_tasks()
        self.runner = AutoRunner(self.ca, self.detector, self.tasks)

    # ---- UI 构建 ----
    def _build_ui(self) -> None:
        # 顶部标题栏
        header = ttk.Frame(self)
        header.pack(fill='x', padx=10, pady=(10, 4))
        ttk.Label(
            header, text="🧬 细胞工厂",
            font=('Microsoft YaHei', 16, 'bold'),
        ).pack(side='left')
        self.gen_var = tk.StringVar(value="第 0 代  |  存活 0")
        ttk.Label(
            header, textvariable=self.gen_var,
            font=('Microsoft YaHei', 10),
        ).pack(side='right')

        # 主区域：左画布 + 右任务
        main = ttk.Frame(self)
        main.pack(fill='both', expand=True, padx=10, pady=4)

        self._canvas_host = ttk.Frame(main)
        self._canvas_host.pack(side='left', padx=(0, 10))
        self.canvas = GridCanvas(self._canvas_host, self.ca, cell_size=20)
        self.canvas.pack()

        right = ttk.Frame(main)
        right.pack(side='right', fill='both', expand=True)
        self._task_host = ttk.Frame(right)
        self._task_host.pack(fill='both', expand=True)
        self.task_panel = TaskPanel(self._task_host, self.tasks)

        # 底部控制条
        bottom = ttk.Frame(self)
        bottom.pack(fill='x', padx=10, pady=(4, 10))
        self.control = ControlPanel(bottom, {
            'on_start': self.on_start,
            'on_pause': self.on_pause,
            'on_step': self.on_step,
            'on_reset': self.on_reset,
        })
        self.control.pack()

        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ---- 控制回调 ----
    def on_start(self) -> None:
        if self.runner.all_done:
            messagebox.showinfo("提示", "所有任务已完成，请点击「重置」重新开始。")
            return
        if self.runner.is_running:
            return
        self.control.set_running(True)
        self.runner.run_threaded(
            max_steps=100000,
            interval=self.control.interval,
            on_step=self._on_step_cb,
            on_complete=self._on_complete_cb,
        )

    def on_pause(self) -> None:
        self.runner.stop()
        self.control.set_running(False)

    def on_step(self) -> None:
        if self.runner.is_running or self.runner.all_done:
            return
        self.runner.step()
        self._refresh()

    def on_reset(self) -> None:
        self.runner.stop()
        # 重建世界（新的随机初始状态）
        self._build_world()
        # 重建画布与任务面板（因为引用换了对象）
        self.canvas.destroy()
        self.canvas = GridCanvas(self._canvas_host, self.ca, cell_size=20)
        self.canvas.pack()
        self.task_panel.destroy()
        self.task_panel = TaskPanel(self._task_host, self.tasks)
        self.task_panel.pack(fill='both', expand=True)
        self.control.set_running(False)
        self._refresh()

    # ---- 工作线程 -> 主线程 桥接 ----
    def _on_step_cb(self, n: int, runner: AutoRunner) -> None:
        # 注意：运行中调整速度滑块不会实时生效，需暂停后重新开始。
        # 如需实时调速，可在此把 runner 的 interval 同步进来，但会引入额外锁，
        # 当前简化处理：调速后请按"暂停 -> 开始"。
        self.after(0, self._refresh)

    def _on_complete_cb(self, ok: bool, runner: AutoRunner) -> None:
        self.after(0, lambda: self._on_complete_ui(ok))

    def _on_complete_ui(self, ok: bool) -> None:
        self.control.set_running(False)
        self._refresh()
        if ok:
            messagebox.showinfo("🎉 完成", f"所有任务完成！耗时 {self.runner.step_count} 代。")

    # ---- 刷新 ----
    def _refresh(self) -> None:
        self.canvas.refresh()
        self.task_panel.refresh()
        self.gen_var.set(
            f"第 {self.runner.step_count} 代  |  存活 {self.ca.count_alive()}"
        )

    def _on_close(self) -> None:
        self.runner.stop()
        self.destroy()


def launch_gui() -> None:
    """启动 GUI 主循环。"""
    app = App()
    app.mainloop()


if __name__ == "__main__":
    launch_gui()
