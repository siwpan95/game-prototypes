# -*- coding: utf-8 -*-
"""worldgen.multilayer — 多层世界生成（depth>1，确定性，不修改 terrain.py）。

MultiLayerGenerator：
  - z=0：调用既有 TerrainGenerator 生成侧视地表并拷贝（复用 M1/M2 地形逻辑）。
  - z=1..depth-1：用 random.Random(seed) 程序化填充（dirty/stone + 底部岩浆湖）。
  - 同 (seed, W, H, depth) 逐格一致（仅 PerlinNoise(seed) + random.Random(seed)）。

设计基线（architecture_m3.md §2.4 / T-M3-01）：terrain.py 不可改，故本模块在更高层
组合——地表复用 TerrainGenerator，地下程序化填充，保证模拟稳定与确定性。
"""

from __future__ import annotations

import random

from mcclone.core.block_registry import AIR, DIRT, STONE
from mcclone.core.block_world import BlockWorld
from mcclone.core.terrain import TerrainGenerator
from mcclone.core.noise import PerlinNoise
from . import LAVA_ID, SUBSURFACE_DIRT_LAYERS


class MultiLayerGenerator:
    """多层世界生成器（组合既有 TerrainGenerator，不修改它）。"""

    def __init__(self, registry, seed: int = 0,
                 noise: "PerlinNoise | None" = None) -> None:
        """初始化生成器。

        参数：
            registry: 方块注册表（用于校验方块 id 有效性）
            seed: 随机种子（确定性来源）
            noise: 可选外部噪声源；为 None 时用 seed 自建 PerlinNoise
        """
        self.registry = registry
        self.seed = seed
        # 若未提供噪声源，则用 seed 自建（保证确定性）
        self._noise = noise if noise is not None else PerlinNoise(seed)

    def generate(self, width: int, height: int, depth: int) -> BlockWorld:
        """生成 depth>1 的多层世界。

        参数：
            width, height: 世界宽高（列数 / 行数）
            depth: Z 层数（>=1）

        返回：
            BlockWorld（z=0 为地表，z>=1 为程序化 subsurface + 底部岩浆湖）
        """
        world = BlockWorld(width, height, depth)

        # ① 表层 z=0：复用既有 TerrainGenerator（确定性，同 seed 表现一致）
        surface = TerrainGenerator(
            self.registry, self.seed, self._noise).generate(width, height, 1)
        for x in range(width):
            for y in range(height):
                bid = surface.get(x, y, 0)
                if bid != AIR:
                    world.set(x, y, 0, bid)

        # ② subsurface：random.Random(seed) 程序化填充
        #    z=1..SUBSURFACE_DIRT_LAYERS 填 dirt；其余填 stone（整层实心列）。
        rng = random.Random(self.seed)
        for z in range(1, depth):
            bid = DIRT if z <= SUBSURFACE_DIRT_LAYERS else STONE
            world.fill_rect(0, 0, width - 1, height - 1, bid, z=z)

        # ③ 底部岩浆湖（z=depth-1）：整层填 lava，再按 rng 挖空气腔交替。
        if depth >= 2:
            bottom = depth - 1
            world.fill_rect(0, 0, width - 1, height - 1, LAVA_ID, z=bottom)
            for x in range(width):
                for y in range(height):
                    if rng.random() < 0.5:
                        world.set(x, y, bottom, AIR)
            # 确定性兜底：保证底部层至少含 1 格岩浆（供温度模拟有热源）。
            if not any(world.get(x, y, bottom) == LAVA_ID
                       for x in range(width) for y in range(height)):
                world.set(0, 0, bottom, LAVA_ID)

        return world
