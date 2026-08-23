# -*- coding: utf-8 -*-
"""simulation — M3 模拟层（温度扩散 / 水/岩浆流动 / 覆盖层快照）。

导出：
  - SimConfig: 模拟配置（dataclass，架构 §3）。
  - CellState / diffuse_step: 单格模拟状态与温度扩散纯函数。
  - WorldSim: 温度扩散 + 水/岩浆流动元胞自动机（chunk 级脏标记，≤20Hz）。
  - LayerOverlay / OverlayBuilder / build_layer_overlay: 覆盖层数据结构与构建。

跨文件常量（架构 §7.1）：LAVA_ID / WATER_ID / CHUNK_SIZE / SIM_HZ。
"""

from __future__ import annotations

from dataclasses import dataclass

# ── 模拟配置（架构 §3 / §7.1 / §8）──
@dataclass
class SimConfig:
    """模拟系统数值配置。"""

    chunk_size: int = 16                # 模拟 chunk 边长
    sim_hz: float = 20.0                # 模拟 tick 上限（PRD M3-R8）
    diffusion: float = 0.25             # 温度扩散系数（每 sim tick）
    ambient_temp: float = 0.0           # 环境温度（归一化下限）
    lava_temp: float = 1.0              # 岩浆/热源温度（归一化上限）
    water_id: int = 4                   # 水方块 id
    lava_id: int = 8                    # 岩浆方块 id
    lava_move_interval: int = 4        # 岩浆每 N 个 sim tick 才移动 1 步
    max_temp_alpha: int = 90            # 温度 tint 最大 alpha


# 跨文件常量
LAVA_ID: int = 8
WATER_ID: int = 4
CHUNK_SIZE: int = 16
SIM_HZ: float = 20.0

# 子模块导入（放在常量之后，子模块通过 `from . import SimConfig` 引用）。
from .cell import CellState, diffuse_step                       # noqa: E402
from .world_sim import WorldSim                                # noqa: E402
from .overlays import (                                         # noqa: E402
    LayerOverlay, OverlayBuilder, build_layer_overlay)

__all__ = [
    "SimConfig", "LAVA_ID", "WATER_ID", "CHUNK_SIZE", "SIM_HZ",
    "CellState", "diffuse_step", "WorldSim",
    "LayerOverlay", "OverlayBuilder", "build_layer_overlay",
]
