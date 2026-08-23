# -*- coding: utf-8 -*-
"""worldgen.biomes — M5 群系系统（确定性，不修改 terrain.py）。

Biome：
  - 5 种群系：PLAINS / DESERT / FOREST / TAIGA / OCEAN。
  - BiomeMap：用低频 PerlinNoise 把每个列 x 确定性映射到 Biome；
    提供 biome_at(x) 与 biomes() 迭代，并附带群系相关的方块/高度/洞穴密度类方法。
  - BiomeTerrainGenerator：组合复用 MultiLayerGenerator 填好 z>=1，
    再用群系逻辑覆盖 z=0 地表（含 OCEAN 海洋水体）。

确定性来源：仅 PerlinNoise(seed) + random.Random(seed)，禁止全局随机/时间。
坐标约定同地形：x 向右、y 向上、z 为层（depth）。
"""

from __future__ import annotations

from enum import Enum

from mcclone.core.block_registry import AIR, DIRT, STONE, GRASS, SAND, WATER
from mcclone.core.block_world import BlockWorld
from mcclone.core.noise import PerlinNoise
from . import (MultiLayerGenerator, LAVA_ID, SUBSURFACE_DIRT_LAYERS)


class Biome(Enum):
    """世界群系枚举。"""

    PLAINS = "plains"   # 平原
    DESERT = "desert"   # 沙漠
    FOREST = "forest"   # 森林
    TAIGA = "taiga"     # 针叶林（更高更冷）
    OCEAN = "ocean"     # 海洋（地形低于水位，多水）


class BiomeMap:
    """列级群系映射（确定性）。

    构造时即用低频 PerlinNoise 把每个列 x 映射到 Biome，保证同 (width, seed)
    逐列一致。为在足够宽的世界上稳定产出全部 5 种群系，采用「先采样再归一化
    到 [0,1]，再均分 5 段」的策略（与 terrain.py 的归一化思路一致），从而
    无论噪声实际分布如何，最小/最大列必然落入 OCEAN/DESERT 尾部区间。
    """

    # 5 段归一化阈值（t 由小到大对应低地到高地/干旱）。
    _BANDS = (
        (0.20, Biome.OCEAN),
        (0.40, Biome.TAIGA),
        (0.60, Biome.PLAINS),
        (0.80, Biome.FOREST),
        (1.01, Biome.DESERT),
    )

    def __init__(self, world_width: int, seed: int = 0) -> None:
        """初始化群系映射。

        参数：
            world_width: 世界宽度（列数）
            seed: 随机种子（群系形态来源，确定性）
        """
        self.world_width = world_width
        self.seed = seed
        self._scale = 0.025                      # 低频：每列跨很小噪声步长
        noise = PerlinNoise(seed)                # 群系专用噪声（独立 seed 派生）
        raw = [noise.fbm(x * self._scale, 0.5, octaves=3)
               for x in range(world_width)]
        raw_lo = min(raw) if raw else 0.0
        raw_hi = max(raw) if raw else 1.0
        span = (raw_hi - raw_lo) if raw_hi > raw_lo else 1.0
        self._biomes: list[Biome] = []
        for x in range(world_width):
            t = (raw[x] - raw_lo) / span         # 归一化到 [0,1]
            self._biomes.append(self._band_to_biome(t))

    @classmethod
    def _band_to_biome(cls, t: float) -> Biome:
        """把归一化值 t∈[0,1] 映射到对应群系。"""
        for upper, biome in cls._BANDS:
            if t < upper:
                return biome
        return Biome.DESERT

    def biome_at(self, x: int) -> Biome:
        """返回列 x 的群系（越界按边界列处理）。"""
        if self.world_width == 0:
            return Biome.PLAINS
        x = max(0, min(self.world_width - 1, x))
        return self._biomes[x]

    def biomes(self) -> "list[Biome]":
        """返回所有列的群系列表（按 x 升序）。"""
        return list(self._biomes)

    # ── 群系相关类方法（供生成器复用）──

    @classmethod
    def surface_block(cls, biome: Biome) -> int:
        """返回群系地表的顶层方块 id。

        PLAINS/FOREST/TAIGA → GRASS；DESERT → SAND；OCEAN → GRASS
        （但 OCEAN 实际海底由生成器覆盖为 SAND，见 BiomeTerrainGenerator）。
        """
        if biome is Biome.DESERT:
            return SAND
        return GRASS

    @classmethod
    def subsurface_block(cls, biome: Biome) -> int:
        """返回群系地表下的次表层方块 id（DESERT → SAND，其余 → DIRT）。"""
        if biome is Biome.DESERT:
            return SAND
        return DIRT

    @classmethod
    def height_offset(cls, biome: Biome) -> int:
        """返回群系相对基准高度的水平偏移（整数，单位：格）。

        DESERT/PLAINS 近 0 较平；FOREST 略高；TAIGA 更高；OCEAN 为负（低于水位）。
        """
        return {
            Biome.DESERT: 0,
            Biome.PLAINS: 0,
            Biome.FOREST: 2,
            Biome.TAIGA: 4,
            Biome.OCEAN: -6,
        }[biome]

    @classmethod
    def cave_density(cls, biome: Biome) -> float:
        """返回群系洞穴密度（DESERT 偏高，其余默认）。"""
        if biome is Biome.DESERT:
            return 0.14
        return 0.08


class BiomeTerrainGenerator:
    """群系地形生成器（组合复用 MultiLayerGenerator，不修改它）。

    流程：
      ① 调用 MultiLayerGenerator 生成同尺寸世界，取其 z>=1（subsurface + 岩浆湖）。
      ② 用群系逻辑重新生成 z=0 地表：逐列按群系算高度，铺地表/次表层/石头；
         OCEAN 列自海平面到海底填 WATER，海底覆 SAND。
    世界宽高与传入 world 保持一致；确定性由 PerlinNoise(seed) 保证。
    """

    def __init__(self, registry, seed: int = 0,
                 noise: "PerlinNoise | None" = None) -> None:
        """初始化生成器。

        参数：
            registry: 方块注册表
            seed: 随机种子（确定性来源）
            noise: 可选外部噪声源（保留接口，内部另用派生噪声做细节扰动）
        """
        self.registry = registry
        self.seed = seed
        self._noise = noise if noise is not None else PerlinNoise(seed)

    def generate(self, world: BlockWorld, registry=None, seed: int | None = None) -> BlockWorld:
        """在传入的 world 上生成群系世界（保留 z>=1，重写 z=0 地表）。

        参数：
            world: 已按目标宽高创建的空 BlockWorld（会被就地填充）
            registry: 方块注册表（默认用构造时的 registry）
            seed: 随机种子（默认用构造时的 seed）

        返回：
            填充好的 world（与传入对象同一实例）
        """
        registry = registry if registry is not None else self.registry
        seed = seed if seed is not None else self.seed
        W, H, D = world.width, world.height, world.depth

        # ① 组合复用 MultiLayerGenerator：生成同尺寸世界并拷贝 z>=1（不改动它）。
        base = MultiLayerGenerator(registry, seed, self._noise).generate(W, H, D)
        for z in range(1, D):
            for y in range(H):
                for x in range(W):
                    world.set(x, y, z, base.get(x, y, z))

        # ② 群系地表覆盖（z=0）。
        self._generate_surface(world, registry, seed, W, H, D)
        return world

    def _generate_surface(self, world, registry, seed, W, H, D) -> None:
        """逐列生成 z=0 群系地表。"""
        biome_map = BiomeMap(W, seed)
        detail_noise = PerlinNoise(seed + 777)   # 地表细节扰动（独立派生噪声）
        water_level = max(2, int(H * 0.50))      # 与 terrain.py 一致的水位
        base_height = water_level

        for x in range(W):
            biome = biome_map.biome_at(x)
            offset = BiomeMap.height_offset(biome)
            detail = int(detail_noise.fbm(x * 0.08, 3.1, octaves=3) * 3)

            if biome is Biome.OCEAN:
                # 海洋：海底低于水位，保证上方有水体。
                h = max(1, min(water_level - 1, base_height + offset + detail))
            else:
                # 陆地：地表不低于水位（避免旱地浸水）。
                h = max(water_level, min(H - 1, base_height + offset + detail))
            h = max(1, min(H - 1, h))

            surface_id = (SAND if biome is Biome.OCEAN
                          else BiomeMap.surface_block(biome))
            sub_id = BiomeMap.subsurface_block(biome)

            for y in range(0, h + 1):
                if y == h:
                    bid = surface_id
                elif y >= h - SUBSURFACE_DIRT_LAYERS:
                    bid = sub_id
                else:
                    bid = STONE
                world.set(x, y, 0, bid)

            # 海洋：海面以下（海底到水位之间）填水。
            if biome is Biome.OCEAN:
                for y in range(h + 1, water_level):
                    if world.get(x, y, 0) == AIR:
                        world.set(x, y, 0, WATER)
