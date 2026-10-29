# -*- coding: utf-8 -*-
"""simulation.cell — 单格模拟状态与温度扩散纯函数（无硬依赖）。

提供：
  - CellState: 单格模拟状态（温度/是否水/是否岩浆/是否 solid）与判定方法。
  - diffuse_step: 温度向邻居均值靠拢的纯函数（钳制到 [lo, hi]）。

纯标准库实现，headless 可断言。确定性：无 RNG、无副作用。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from mcclone.core.geometry import clamp


@dataclass
class CellState:
    """单格模拟状态。"""

    temp: float = 0.0       # 温度（归一化，默认环境 0）
    water: bool = False     # 是否为水
    lava: bool = False      # 是否为岩浆
    solid: bool = True      # 是否为 solid 方块

    def is_fluid(self) -> bool:
        """是否为流体（水 或 岩浆）。"""
        return self.water or self.lava

    def is_heat_source(self) -> bool:
        """是否为热源（岩浆）。"""
        return self.lava


def diffuse_step(center: float, neighbors: Sequence[float],
                 diffusion: float, lo: float = 0.0,
                 hi: float = 1.0) -> float:
    """向邻居均值靠拢一步，返回钳制后的新温度。

    公式：new = center + diffusion * (avg(neighbors) - center)，并钳制到 [lo, hi]。

    参数：
        center: 当前格温度
        neighbors: 邻居温度序列（如 4 邻）
        diffusion: 扩散系数（0..1）
        lo, hi: 钳制区间

    返回：
        新温度（钳制后）
    """
    if not neighbors:
        return clamp(center, lo, hi)
    avg = sum(neighbors) / len(neighbors)
    new = center + diffusion * (avg - center)
    return clamp(new, lo, hi)
