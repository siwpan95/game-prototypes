# -*- coding: utf-8 -*-
"""test_m3_worldgen — T-M3-01 多层世界生成（headless，确定性 + 分层结构）。

验收要点：
  - 同 (seed, W, H, depth) 两次生成逐格一致（确定性）。
  - world.depth == WORLD_DEPTH。
  - z=0 沿用 terrain 表层（含 grass/stone/water）；不修改 terrain.py。
  - z=1..2 为 dirt；z>=3 为 stone；底部层含 lava(8)。
"""

from __future__ import annotations

import pytest

from mcclone.core.block_registry import (BlockRegistry, BlockDef,
                             AIR, DIRT, STONE, GRASS, WATER)
from mcclone.core.block_world import BlockWorld
from mcclone.core.noise import PerlinNoise
from mcclone.core.terrain import TerrainGenerator
from mcclone.world.worldgen import MultiLayerGenerator, LAVA_ID, SUBSURFACE_DIRT_LAYERS


def _registry():
    """构造含默认方块 + lava=8 的注册表。"""
    reg = BlockRegistry()
    reg.load_defaults()
    reg.register(BlockDef(LAVA_ID, "lava", "*", "lava",
                          solid=False, transparent=True))
    return reg


def test_worldgen_depth_and_determinism():
    reg = _registry()
    W, H, D = 24, 24, 8
    g = MultiLayerGenerator(reg, 12345)
    w1 = g.generate(W, H, D)
    w2 = g.generate(W, H, D)
    # 深度正确
    assert w1.depth == D
    assert w2.depth == D
    # 逐格一致（仅 random.Random(seed) + PerlinNoise(seed)）
    for z in range(D):
        for y in range(H):
            for x in range(W):
                assert w1.get(x, y, z) == w2.get(x, y, z)


def test_worldgen_surface_uses_terrain():
    """z=0 应等同于直接调用 TerrainGenerator 的输出（间接证明未改动 terrain）。"""
    reg = _registry()
    W, H = 24, 24
    g = MultiLayerGenerator(reg, 777)
    world = g.generate(W, H, 8)
    surface = TerrainGenerator(reg, 777, PerlinNoise(777)).generate(W, H, 1)
    for y in range(H):
        for x in range(W):
            assert world.get(x, y, 0) == surface.get(x, y, 0)


def test_worldgen_subsurface_layers():
    reg = _registry()
    W, H, D = 20, 20, 8
    world = MultiLayerGenerator(reg, 42).generate(W, H, D)
    # z=1..SUBSURFACE_DIRT_LAYERS 为 dirt
    for z in range(1, SUBSURFACE_DIRT_LAYERS + 1):
        for y in range(H):
            for x in range(W):
                assert world.get(x, y, z) == DIRT
    # z=SUBSURFACE_DIRT_LAYERS+1 .. depth-2 为 stone
    for z in range(SUBSURFACE_DIRT_LAYERS + 1, D - 1):
        for y in range(H):
            for x in range(W):
                assert world.get(x, y, z) == STONE


def test_worldgen_bottom_lava_lake():
    reg = _registry()
    W, H, D = 20, 20, 8
    world = MultiLayerGenerator(reg, 99).generate(W, H, D)
    bottom = D - 1
    lava_cells = [(x, y) for x in range(W) for y in range(H)
                  if world.get(x, y, bottom) == LAVA_ID]
    # 确定性兜底保证至少 1 格岩浆（热源）
    assert len(lava_cells) >= 1
    # 同时存在空气腔（LAVA/AIR 交替）
    air_cells = [(x, y) for x in range(W) for y in range(H)
                 if world.get(x, y, bottom) == AIR]
    assert len(air_cells) >= 1


def test_worldgen_does_not_preload_terrain_state():
    """生成器不应污染全局；独立 seed 产出不同的底部岩浆湖（seed 相关）。"""
    reg = _registry()
    w_a = MultiLayerGenerator(reg, 1).generate(16, 16, 8)
    w_b = MultiLayerGenerator(reg, 2).generate(16, 16, 8)
    bottom = 7
    differ = any(w_a.get(x, y, bottom) != w_b.get(x, y, bottom)
                 for x in range(16) for y in range(16))
    assert differ
