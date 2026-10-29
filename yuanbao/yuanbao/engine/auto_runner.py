"""自动化挂机引擎。

重构要点
--------
原 ``AutoRunner.run`` 直接在循环里 ``print`` 与 ``time.sleep``，把"逻辑"与"展示"
耦合在一起，无法被 GUI 复用。重构后：

* :meth:`AutoRunner.step` 是纯逻辑——演化 CA、检测并收集、更新计数，返回本步信息，
  **没有任何 IO 副作用**；
* :meth:`AutoRunner.run` 阻塞运行（CLI 用），通过 ``on_step`` / ``on_complete``
  回调把展示职责交还调用方；
* :meth:`AutoRunner.run_threaded` 在后台守护线程运行（GUI 用），
  通过回调 + ``self.after(0, ...)`` 线程安全地更新 UI；
* :meth:`AutoRunner.stop` 通过 ``threading.Event`` 优雅停止。

这样 CLI、GUI、未来的 Web 前端都能共享同一份引擎逻辑。
"""
from __future__ import annotations

import sys
import threading
import time
from typing import Callable, List, Optional, Set, Tuple

from yuanbao.core.automaton import CellularAutomaton
from yuanbao.core.detector import CNNDetector
from yuanbao.tasks.task import Task

# 回调类型：(step_count, runner) -> None
StepCallback = Callable[[int, "AutoRunner"], None]
# 回调类型：(all_done, runner) -> None
CompleteCallback = Callable[[bool, "AutoRunner"], None]


class AutoRunner:
    """把元胞自动机演化与任务收集串成自动化循环。"""

    def __init__(self, ca: CellularAutomaton, detector: CNNDetector, tasks: List[Task]):
        self.ca = ca
        self.detector = detector
        self.tasks: List[Task] = tasks
        # 已收集过的细胞位置，避免同一格被反复"收集"造成重复计数
        self.collected_positions: Set[Tuple[int, int]] = set()
        self.step_count: int = 0
        self._stop_flag = threading.Event()
        self._thread: Optional[threading.Thread] = None

    # ---- 状态重置 ----
    def reset(self) -> None:
        self.collected_positions.clear()
        self.step_count = 0
        for t in self.tasks:
            t.reset()
        self._stop_flag.clear()

    # ---- 单步 ----
    def step(self) -> Tuple[bool, List[Tuple[int, int]]]:
        """演化一代并收集匹配细胞。

        Returns
        -------
        (all_done, just_collected)
            all_done: 是否所有任务已完成；
            just_collected: 本步实际收集到的坐标列表。
        """
        self.ca.step()
        grid, tag_grid = self.ca.get_state()
        just_collected: List[Tuple[int, int]] = []

        for task in self.tasks:
            if task.completed:
                continue
            for req in task.requirements:
                if req.done:
                    continue
                matches = self.detector.detect_pattern(grid, tag_grid, req.pattern)
                for pos in matches:
                    if pos in self.collected_positions:
                        continue
                    i, j = pos
                    if self.ca.clear_cell(i, j):
                        self.collected_positions.add(pos)
                        req.collected += 1
                        just_collected.append(pos)
                        if req.done:
                            break

        all_done = all(task.check_completion() for task in self.tasks)
        self.step_count += 1
        return all_done, just_collected

    # ---- 阻塞运行（CLI）----
    def run(
        self,
        max_steps: int = 1000,
        *,
        interval: Optional[float] = None,
        on_step: Optional[StepCallback] = None,
        on_complete: Optional[CompleteCallback] = None,
    ) -> bool:
        """阻塞运行至完成或达到 max_steps。返回是否全部完成。"""
        self._stop_flag.clear()
        if interval is None:
            interval = self.ca.config.STEP_INTERVAL
        for _ in range(max_steps):
            if self._stop_flag.is_set():
                return False
            all_done, _ = self.step()
            if on_step:
                on_step(self.step_count, self)
            if all_done:
                if on_complete:
                    on_complete(True, self)
                return True
            if interval > 0:
                time.sleep(interval)
        if on_complete:
            on_complete(False, self)
        return False

    # ---- 后台线程运行（GUI）----
    def run_threaded(
        self,
        max_steps: int = 100000,
        *,
        interval: Optional[float] = None,
        on_step: Optional[StepCallback] = None,
        on_complete: Optional[CompleteCallback] = None,
    ) -> threading.Thread:
        """在后台守护线程中运行，立即返回线程对象。"""
        self._stop_flag.clear()

        def _worker():
            try:
                self.run(max_steps, interval=interval, on_step=on_step, on_complete=on_complete)
            except Exception as e:  # noqa: BLE001
                print(f"[AutoRunner] error: {e}", file=sys.stderr)

        self._thread = threading.Thread(target=_worker, daemon=True, name="AutoRunner")
        self._thread.start()
        return self._thread

    # ---- 控制 ----
    def stop(self) -> None:
        """请求停止运行（异步，不阻塞）。"""
        self._stop_flag.set()

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    @property
    def all_done(self) -> bool:
        return all(t.completed for t in self.tasks)
