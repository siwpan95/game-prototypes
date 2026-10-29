# -*- coding: utf-8 -*-
"""simulation.overlays — 覆盖层数据结构与构建（温度 tint 值 / 水 / 岩浆）。

提供：
  - LayerOverlay: 某一层 (x,y) 的温度/水/岩浆 2D 网格 + cell(x,y) -> CellState。
  - build_layer_overlay(world, sim, z, cfg): 从世界与模拟读取该层覆盖数据。
  - OverlayBuilder: 类式封装（build_layer_overlay 静态方法）。

tint 公式见 architecture_m3.md §7.5：温度蓝→红渐变 alpha∝t（t 归一化到 [0,1]）。
"""

from __future__ import annotations

from typing import List

from mcclone.core.geometry import clamp
from .cell import CellState


class LayerOverlay:
    """某一 Z 层的覆盖层数据。"""

    def __init__(self, width: int, height: int,
                 temp: List[List[float]],
                 water: List[List[bool]],
                 lava: List[List[bool]]) -> None:
        self.width = width
        self.height = height
        self.temp = temp        # height × width，归一化温度 [0,1]
        self.water = water      # height × width
        self.lava = lava        # height × width

    def cell(self, x: int, y: int) -> CellState:
        """返回 (x,y) 对应的单格模拟状态。"""
        t = self.temp[y][x]
        w = self.water[y][x]
        l = self.lava[y][x]
        return CellState(temp=t, water=w, lava=l, solid=not (w or l))


def build_layer_overlay(world, sim, z: int, cfg) -> LayerOverlay:
    """构建第 z 层的 LayerOverlay。

    参数：
        world: BlockWorld
        sim: WorldSim（提供 get_temperature/get_water/get_lava）
        z: 目标层
        cfg: SimConfig（提供 water_id / lava_id / lava_temp）

    返回：
        LayerOverlay（temp 归一化 clamp(t/lava_temp, 0, 1)）
    """
    w = world.width
    h = world.height
    temp: List[List[float]] = [[0.0] * w for _ in range(h)]
    water: List[List[bool]] = [[False] * w for _ in range(h)]
    lava: List[List[bool]] = [[False] * w for _ in range(h)]
    for y in range(h):
        for x in range(w):
            bid = world.get(x, y, z)
            water[y][x] = (bid == cfg.water_id)
            lava[y][x] = (bid == cfg.lava_id)
            raw = sim.get_temperature(x, y, z)
            temp[y][x] = clamp(raw / cfg.lava_temp, 0.0, 1.0)
    return LayerOverlay(w, h, temp, water, lava)


class OverlayBuilder:
    """覆盖层构建器（类式封装，便于扩展）。"""

    @staticmethod
    def build_layer_overlay(world, sim, z: int, cfg) -> LayerOverlay:
        """等价 build_layer_overlay(world, sim, z, cfg)。"""
        return build_layer_overlay(world, sim, z, cfg)
