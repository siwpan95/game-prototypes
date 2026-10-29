# -*- coding: utf-8 -*-
"""worldgen.caves — M5 洞穴雕刻（确定性，不修改地形地基）。

CaveCarver：
  - 在 z∈[1, depth-2] 区间程序化挖空（生成 AIR 空腔）。
  - 两种机制结合：① 噪声阈值雕刻（按列结合 BiomeMap.cave_density 调整密度）；
    ② 基于 random.Random(seed) 的虫洞随机游走，生成连通隧道。
  - 绝对保护边界：z=0 地表层与 z=depth-1 岩浆湖层均不被破坏。

确定性来源：仅 PerlinNoise(seed) + random.Random(seed)，禁止全局随机/时间。
"""

from __future__ import annotations

import random

from mcclone.core.block_registry import AIR
from mcclone.core.noise import PerlinNoise
from .biomes import BiomeMap
from . import LAVA_ID


class CaveCarver:
    """洞穴雕刻器（在已生成世界上挖空 subsurface 区间）。"""

    def __init__(self, registry=None, seed: int = 0) -> None:
        """初始化雕刻器。

        参数：
            registry: 方块注册表（当前仅用于语义占位，雕刻不依赖其取值）
            seed: 随机种子（确定性来源）
        """
        self.registry = registry
        self.seed = seed

    def carve(self, world, registry=None, seed: int | None = None,
              density: float = 0.08) -> object:
        """在世界上雕刻洞穴（就地修改，返回同一 world）。

        参数：
            world: 已生成的 BlockWorld（通常先经 BiomeTerrainGenerator 生成）
            registry: 方块注册表（默认用构造时的 registry）
            seed: 随机种子（默认用构造时的 seed）
            density: 基础洞穴密度（0~1，越大空腔越多）；会按列群系做倍率调整

        返回：
            雕刻后的 world（同一实例）
        """
        registry = registry if registry is not None else self.registry
        seed = seed if seed is not None else self.seed
        W, H, D = world.width, world.height, world.depth

        # 层太薄（<3）无法雕刻 subsurface 区间，直接返回。
        if D < 3:
            return world

        biome_map = BiomeMap(W, seed)
        carve_noise = PerlinNoise(seed + 999)     # 洞穴形状噪声（独立派生）
        rng = random.Random(seed)                # 虫洞随机游走

        # ① 噪声阈值雕刻：仅 z∈[1, D-2]，绝不触碰 z=0 与 z=D-1。
        for z in range(1, D - 1):
            for y in range(H):
                for x in range(W):
                    bdens = biome_map.cave_density(biome_map.biome_at(x))
                    # 密度越高阈值越低 → 越容易超过阈值被挖空。
                    threshold = 0.30 - bdens
                    n = carve_noise.fbm(x * 0.12, y * 0.12 + z * 0.18, octaves=3)
                    if n > threshold:
                        world.set(x, y, z, AIR)

        # ② 虫洞随机游走：在 subsurface 区间内生成连通隧道空腔。
        worm_count = max(1, W // 10)
        for _ in range(worm_count):
            cz = rng.randint(1, D - 2)
            cx = rng.randint(0, W - 1)
            cy = rng.randint(0, H - 1)
            length = rng.randint(8, 24)
            for _step in range(length):
                # 以当前点为中心、半径 1 挖空（仍限制在 z∈[1, D-2]）。
                for dx in (-1, 0, 1):
                    for dy in (-1, 0, 1):
                        nz, nx, ny = cz, cx + dx, cy + dy
                        if (1 <= nz <= D - 2 and 0 <= nx < W and 0 <= ny < H):
                            world.set(nx, ny, nz, AIR)
                # 随机走一步，并夹紧在合法 subsurface 区间。
                cz = max(1, min(D - 2, cz + rng.choice((-1, 0, 1))))
                cx = max(0, min(W - 1, cx + rng.choice((-1, 0, 1))))
                cy = max(0, min(H - 1, cy + rng.choice((-1, 0, 1))))

        return world
