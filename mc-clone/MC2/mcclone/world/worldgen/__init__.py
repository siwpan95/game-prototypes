# -*- coding: utf-8 -*-
"""worldgen — 多层世界生成（M3，不修改地基 terrain.py）。

导出：
  - MultiLayerGenerator: 生成 depth>1 多层世界（z=0 复用 terrain 地表，
    z>=1 程序化填充 dirt/stone + 底部岩浆湖）。
  - LAVA_ID: 岩浆方块 id（=8）。
  - SUBSURFACE_DIRT_LAYERS: 地表下填 dirt 的层数（默认 2）。

本模块零依赖地基之外的内容；确定性由 PerlinNoise(seed) + random.Random(seed) 保证。
"""

from __future__ import annotations

# M3 世界常量（跨文件统一，见架构 §7.1）。
# 注意：常量需在导入子模块之前定义，子模块通过 `from . import` 引用它们。
LAVA_ID: int = 8
SUBSURFACE_DIRT_LAYERS: int = 2

from .multilayer import MultiLayerGenerator
from .biomes import Biome, BiomeMap, BiomeTerrainGenerator
from .caves import CaveCarver

__all__ = [
    "MultiLayerGenerator", "LAVA_ID", "SUBSURFACE_DIRT_LAYERS",
    "Biome", "BiomeMap", "BiomeTerrainGenerator", "CaveCarver",
]
