# -*- coding: utf-8 -*-
"""
固定时间步长游戏循环（Fixed-Timestep Game Loop）
================================================

结合联网调研的游戏引擎架构最佳实践（Gaffer "Fix Your Timestep"、
Game Programming Patterns 的 Game Loop 章节）：

  * 渲染帧率（可变）与物理/逻辑更新（固定）解耦；
  * 用「累加器 (accumulator)」把真实流逝时间切成固定步长 fixed_dt 的若干次
    update，保证逻辑确定性（与帧率无关）；
  * 提供插值因子 alpha 供渲染层做平滑插值，避免高速运动时的抖动；
  * 限制单帧最大处理时间（max_frame_time），防止「死亡螺旋」(spiral of death)
    —— 即卡顿时不断积压固定步导致越算越慢。

`GameEngine` 已内置该循环（见 add_core / advance / run_real_time）。

用法：
    from allin_engine.core.game_loop import FixedTimestepLoop

    loop = FixedTimestepLoop(update_fn, render_fn, fixed_dt=1/60)
    loop.advance(real_dt=0.05)        # 内部可能触发 3 次 update + 1 次 render
    print(loop.stats)
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Callable, Optional


@dataclass
class GameLoopStats:
    """循环运行统计，便于调试与性能观测。"""
    fixed_steps: int = 0          # 累计固定更新次数
    render_calls: int = 0         # 累计渲染次数
    accumulator: float = 0.0      # 当前累加器（秒）
    alpha: float = 0.0            # 最近一次渲染插值因子 [0,1)
    last_real_dt: float = 0.0     # 最近一次 advance 的真实 dt
    total_sim_time: float = 0.0   # 累计模拟时间（秒）


class FixedTimestepLoop:
    """固定时间步长主循环调度器。"""

    def __init__(self, update_fn: Callable[[float], None],
                 render_fn: Optional[Callable[[float], None]] = None,
                 fixed_dt: float = 1.0 / 60.0,
                 max_frame_time: float = 0.25):
        """
        参数：
            update_fn:       固定步长更新回调，签名 (fixed_dt: float) -> None
            render_fn:       渲染回调，签名 (alpha: float) -> None（可选）
            fixed_dt:        固定步长（秒），默认 1/60
            max_frame_time:  单帧最多处理的真实时间，防止死亡螺旋
        """
        self._update = update_fn
        self._render = render_fn
        self.fixed_dt = fixed_dt
        self.max_frame_time = max_frame_time
        self.accumulator: float = 0.0
        self.stats = GameLoopStats()
        self.running: bool = False

    def advance(self, real_dt: float) -> None:
        """推进一个真实时间片段 real_dt（秒）。

        内部按 fixed_dt 切分多次 update，并在最后调用一次 render(alpha)。
        """
        if real_dt > self.max_frame_time:
            real_dt = self.max_frame_time  # 钳制，避免死亡螺旋
        self.stats.last_real_dt = real_dt
        self.accumulator += real_dt

        steps = 0
        while self.accumulator >= self.fixed_dt:
            self._update(self.fixed_dt)
            self.accumulator -= self.fixed_dt
            self.stats.fixed_steps += 1
            self.stats.total_sim_time += self.fixed_dt
            steps += 1

        # 插值因子：渲染在两次固定步之间的位置
        self.stats.alpha = self.accumulator / self.fixed_dt if self.fixed_dt > 0 else 0.0
        self.stats.accumulator = self.accumulator
        if self._render is not None:
            self._render(self.stats.alpha)
            self.stats.render_calls += 1

    def reset(self) -> None:
        """重置累加器与统计（不改变 running 状态）。"""
        self.accumulator = 0.0
        self.stats = GameLoopStats()

    def run_real_time(self, get_time: Optional[Callable[[], float]] = None,
                      stop_when: Optional[Callable[[], bool]] = None) -> None:
        """以真实时钟连续运行（阻塞）。通常仅用于独立程序入口。

        参数：
            get_time:  返回当前时间（秒）的函数，默认 time.monotonic
            stop_when: 返回 True 时停止循环的函数（如检测到退出信号）
        """
        now = get_time or time.monotonic
        last = now()
        self.running = True
        try:
            while self.running:
                t = now()
                frame_dt = t - last
                last = t
                self.advance(frame_dt)
                if stop_when is not None and stop_when():
                    self.running = False
        finally:
            self.running = False
