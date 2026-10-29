"""
terrain — 确定性侧视地形生成（无硬依赖）。

提供：
  - TerrainGenerator: 基于 Perlin 噪声生成侧视（2D 文字向）地形。

坐标约定：x 向右，y 向上。同 (seed, width, height) 产出逐格一致。

本模块依赖本地模块：block_registry / block_world / noise。
"""

from __future__ import annotations

from typing import Optional

from mcclone.core.block_registry import (
    AIR, DIRT, GRASS, SAND, STONE, WATER,
    BlockDef, BlockRegistry,
)
from mcclone.core.block_world import BlockWorld
from mcclone.core.noise import PerlinNoise


class TerrainGenerator:
    """侧视地形生成器。

    地层自底向上：stone → dirt → grass；并依据水位填充 water，
    在水位与陆地交界附近铺设 sand（海滩）。
    """

    def __init__(self, registry: BlockRegistry, seed: int = 0,
                 noise: Optional[PerlinNoise] = None) -> None:
        """初始化生成器。

        参数：
            registry: 方块注册表（用于校验方块 id 有效性）
            seed: 随机种子（地形形态来源，确定性）
            noise: 可选外部噪声源；为 None 时用 seed 自建 PerlinNoise
        """
        self.registry = registry
        self.seed = seed
        # 若未提供噪声源，则用 seed 自建（保证确定性）
        self.noise = noise if noise is not None else PerlinNoise(seed)

    def generate(self, width: int, height: int, depth: int = 1) -> BlockWorld:
        """生成侧视地形世界。

        参数：
            width: 世界宽度（列数）
            height: 世界高度（行数）
            depth: 世界层数（默认 1）

        返回：
            填充好的 BlockWorld
        """
        world = BlockWorld(width, height, depth)
        noise = self.noise

        scale = 0.12                                # 噪声采样频率
        min_h = max(2, int(height * 0.30))          # 地表最低高度
        max_h = max(min_h + 1, int(height * 0.80))  # 地表最高高度
        # 水位：取约 50% 高度，确保低洼列可被淹没（冒烟要求「低处有水」）。
        # 注：规格中 water_level「如 25%」为示例值；此处为在较小世界也能出现水面而提高。
        water_level = max(2, int(height * 0.50))    # 水位（y < water_level 为水下）

        # 先采样各列原始噪声，做归一化以保证地表高度铺满 [min_h, max_h]，
        # 避免小幅世界下噪声未达极值而导致地表整体高于水位（无水面）。
        raw_list = [noise.fbm(x * scale, 0.0, octaves=4) for x in range(width)]
        raw_lo = min(raw_list)
        raw_hi = max(raw_list)
        raw_span = (raw_hi - raw_lo) if raw_hi > raw_lo else 1.0

        column_height: list[int] = []
        for x in range(width):
            t = (raw_list[x] - raw_lo) / raw_span     # 归一化到 [0,1]
            h = int(min_h + t * (max_h - min_h))
            h = max(1, min(h, height - 1))
            column_height.append(h)

            # 自底向上填充地层
            for y in range(0, h + 1):
                if y <= h - 3:
                    world.set(x, y, 0, STONE)
                elif y <= h - 1:
                    world.set(x, y, 0, DIRT)
                else:  # y == h
                    world.set(x, y, 0, GRASS)

        # 水位以下填水（仅填充仍为空气的位置）
        for x in range(width):
            for y in range(0, water_level):
                if world.get(x, y, 0) == AIR:
                    world.set(x, y, 0, WATER)

        # 海滩：水位上方一格为 water 且陆地表块是 grass/dirt → 改为 sand
        for x in range(width):
            h = column_height[x]
            if h + 1 < height and world.get(x, h + 1, 0) == WATER:
                top_id = world.get(x, h, 0)
                if top_id in (GRASS, DIRT):
                    world.set(x, h, 0, SAND)

        return world
