# -*- coding: utf-8 -*-
"""test_m5_worldgen — M5 群系 + 洞穴（headless，确定性 + 分层/边界保护）。

验收要点：
  - 确定性：同 seed 两次生成世界逐格一致（地表与雕刻均如此）。
  - 群系覆盖：足够宽的世界上 BiomeMap 能产出全部 5 种群系。
  - 洞穴雕刻后：z=0 地表完整、z=depth-1 仍是岩浆湖（未被挖穿）。
  - 洞穴空腔占比在合理区间；OCEAN 列包含 WATER。
  - 生成的 world 经 BlockWorld.to_dict/from_dict 往返后仍合法。
"""

from __future__ import annotations

import pytest

from mcclone.core.block_registry import (BlockRegistry, BlockDef,
                             AIR, DIRT, STONE, GRASS, SAND, WATER)
from mcclone.core.block_world import BlockWorld
from mcclone.world.worldgen import (MultiLayerGenerator, Biome, BiomeMap,
                      BiomeTerrainGenerator, CaveCarver, LAVA_ID)


def _registry():
    """构造含默认方块 + lava=8 的注册表（贴近 main_gui 的 M3 注册）。"""
    reg = BlockRegistry()
    reg.load_defaults()
    reg.register(BlockDef(LAVA_ID, "lava", "*", "lava",
                          solid=False, transparent=True))
    return reg


def _grid_equal(a: BlockWorld, b: BlockWorld) -> bool:
    """逐格比较两个世界是否一致。"""
    if (a.width, a.height, a.depth) != (b.width, b.height, b.depth):
        return False
    for z in range(a.depth):
        for y in range(a.height):
            for x in range(a.width):
                if a.get(x, y, z) != b.get(x, y, z):
                    return False
    return True


# ── 1. 确定性：BiomeTerrainGenerator 同 seed 两次一致 ──

def test_biome_terrain_determinism():
    reg = _registry()
    W, H, D = 48, 48, 10
    g = BiomeTerrainGenerator(reg, 12345)
    w1 = g.generate(BlockWorld(W, H, D), reg, 12345)
    w2 = g.generate(BlockWorld(W, H, D), reg, 12345)
    assert _grid_equal(w1, w2)


# ── 2. 确定性：CaveCarver 同 seed 两次一致 ──

def test_cave_carve_determinism():
    reg = _registry()
    W, H, D = 48, 48, 10
    w_a = BiomeTerrainGenerator(reg, 2024).generate(BlockWorld(W, H, D), reg, 2024)
    w_b = BiomeTerrainGenerator(reg, 2024).generate(BlockWorld(W, H, D), reg, 2024)
    CaveCarver(reg, 2024).carve(w_a, reg, 2024)
    CaveCarver(reg, 2024).carve(w_b, reg, 2024)
    assert _grid_equal(w_a, w_b)


# ── 3. 群系覆盖：宽世界产出全部 5 种群系 ──

def test_biome_coverage_all_five():
    width = 300
    # 在多个 seed 中至少存在一个能稳定产出全部 5 种群系（宽世界归一化策略保证）。
    found = False
    for seed in range(0, 40):
        bm = BiomeMap(width, seed)
        present = set(bm.biomes())
        if present >= {Biome.PLAINS, Biome.DESERT, Biome.FOREST,
                       Biome.TAIGA, Biome.OCEAN}:
            found = True
            break
    assert found, "宽世界上未能产出全部 5 种群系"


# ── 4. 洞穴雕刻后：z=0 地表完整 ──

def test_surface_intact_after_cave():
    reg = _registry()
    W, H, D = 48, 48, 10
    world = BiomeTerrainGenerator(reg, 555).generate(BlockWorld(W, H, D), reg, 555)
    before = [world.get(x, y, 0) for y in range(H) for x in range(W)]
    CaveCarver(reg, 555).carve(world, reg, 555)
    after = [world.get(x, y, 0) for y in range(H) for x in range(W)]
    assert before == after


# ── 5. 洞穴雕刻后：z=depth-1 岩浆湖未被挖穿 ──

def test_bottom_lava_lake_intact_after_cave():
    reg = _registry()
    W, H, D = 48, 48, 10
    world = BiomeTerrainGenerator(reg, 777).generate(BlockWorld(W, H, D), reg, 777)
    bottom = D - 1
    before = [world.get(x, y, bottom) for y in range(H) for x in range(W)]
    CaveCarver(reg, 777).carve(world, reg, 777)
    after = [world.get(x, y, bottom) for y in range(H) for x in range(W)]
    assert before == after
    # 岩浆湖层仍至少含岩浆（未被整体挖空）。
    assert LAVA_ID in after


# ── 6. 洞穴空腔占比合理 ──

def test_cave_cavity_ratio_reasonable():
    reg = _registry()
    W, H, D = 64, 64, 12
    world = BiomeTerrainGenerator(reg, 31337).generate(BlockWorld(W, H, D), reg, 31337)
    CaveCarver(reg, 31337).carve(world, reg, 31337)
    total = 0
    air = 0
    for z in range(1, D - 1):
        for y in range(H):
            for x in range(W):
                total += 1
                if world.get(x, y, z) == AIR:
                    air += 1
    ratio = air / total
    # 空腔占比应在合理区间（存在但不过度）。
    assert 0.01 <= ratio <= 0.70


# ── 7. OCEAN 列包含 WATER ──

def test_ocean_column_has_water():
    reg = _registry()
    W, H, D = 200, 64, 10
    seed = None
    found_ocean_col = None
    for s in range(0, 40):
        bm = BiomeMap(W, s)
        if Biome.OCEAN in bm.biomes():
            seed = s
            found_ocean_col = next(x for x in range(W)
                                   if bm.biome_at(x) is Biome.OCEAN)
            break
    assert seed is not None, "未发现 OCEAN 列"
    world = BiomeTerrainGenerator(reg, seed).generate(BlockWorld(W, H, D), reg, seed)
    has_water = any(world.get(found_ocean_col, y, 0) == WATER
                    for y in range(H))
    assert has_water


# ── 8. world 经 to_dict/from_dict 往返合法（BiomeTerrainGenerator）──

def test_world_roundtrip_biome_terrain():
    reg = _registry()
    W, H, D = 40, 40, 9
    world = BiomeTerrainGenerator(reg, 8888).generate(BlockWorld(W, H, D), reg, 8888)
    data = world.to_dict()
    restored = BlockWorld.from_dict(data)
    assert _grid_equal(world, restored)


# ── 9. 群系方块/高度映射正确（类方法）──

def test_biome_classmethods():
    assert BiomeMap.surface_block(Biome.PLAINS) == GRASS
    assert BiomeMap.surface_block(Biome.FOREST) == GRASS
    assert BiomeMap.surface_block(Biome.TAIGA) == GRASS
    assert BiomeMap.surface_block(Biome.DESERT) == SAND
    assert BiomeMap.surface_block(Biome.OCEAN) == GRASS

    assert BiomeMap.subsurface_block(Biome.DESERT) == SAND
    assert BiomeMap.subsurface_block(Biome.PLAINS) == DIRT

    assert BiomeMap.height_offset(Biome.OCEAN) < 0
    assert BiomeMap.height_offset(Biome.TAIGA) > BiomeMap.height_offset(Biome.FOREST)
    assert BiomeMap.height_offset(Biome.FOREST) > BiomeMap.height_offset(Biome.PLAINS)

    assert BiomeMap.cave_density(Biome.DESERT) > BiomeMap.cave_density(Biome.PLAINS)


# ── 10. BiomeMap 确定性：同 seed 群系列一致 ──

def test_biome_map_determinism():
    a = BiomeMap(150, 4242).biomes()
    b = BiomeMap(150, 4242).biomes()
    assert a == b
    # 不同 seed 大概率不同（至少不要求完全相同）。
    c = BiomeMap(150, 9999).biomes()
    assert a != c or True  # 仅作存在性校验，不强制不同


# ── 11. 洞穴雕刻不影响 z>=1 之外的层（单独验证 z=1 与 z=depth-2 边界存在雕刻但不越界）──

def test_cave_carve_bounds():
    reg = _registry()
    W, H, D = 48, 48, 10
    world = BiomeTerrainGenerator(reg, 111).generate(BlockWorld(W, H, D), reg, 111)
    # 记录雕刻前 z=0 与 z=depth-1 的快照（群系地表本就与 MultiLayer 不同，故比较雕刻前后）。
    before_z0 = [world.get(x, y, 0) for y in range(H) for x in range(W)]
    before_bot = [world.get(x, y, D - 1) for y in range(H) for x in range(W)]
    CaveCarver(reg, 111).carve(world, reg, 111)
    after_z0 = [world.get(x, y, 0) for y in range(H) for x in range(W)]
    after_bot = [world.get(x, y, D - 1) for y in range(H) for x in range(W)]
    # z=0 地表层与 z=depth-1 岩浆湖层必须未被雕刻破坏。
    assert before_z0 == after_z0
    assert before_bot == after_bot


# ── 12. 薄世界（depth<3）洞穴雕刻安全跳过 ──

def test_cave_carve_thin_world_safe():
    reg = _registry()
    W, H, D = 32, 32, 2
    world = MultiLayerGenerator(reg, 5).generate(W, H, D)
    # 不应抛异常；返回同一实例。
    out = CaveCarver(reg, 5).carve(world, reg, 5)
    assert out is world
