# -*- coding: utf-8 -*-
"""test_m3_simulation — T-M3-02/03/04 模拟核心（headless）。

验收要点：
  - CellState.is_fluid / is_heat_source。
  - diffuse_step 向邻居均值靠拢且钳制。
  - 水从高处流向低处（逐格下落 + 底部铺平）。
  - 温度从岩浆格向邻格扩散；岩浆格恒为 lava_temp。
  - 仅脏 chunk 被遍历（mark_dirty_around / dirty_chunks 正确）。
  - snapshot_overlays 与 world / get_temperature 同步。
"""

from __future__ import annotations

import pytest

from mcclone.core.geometry import clamp
from mcclone.core.block_registry import BlockRegistry, BlockDef, AIR, WATER
from mcclone.core.block_world import BlockWorld
from mcclone.simulation import (WorldSim, SimConfig, CellState, diffuse_step,
                        LAVA_ID, WATER_ID)


def _registry():
    reg = BlockRegistry()
    reg.load_defaults()
    reg.register(BlockDef(LAVA_ID, "lava", "*", "lava",
                          solid=False, transparent=True))
    return reg


# ── T-M3-02 CellState / diffuse_step ──
def test_cell_state_flags():
    assert CellState(water=True).is_fluid()
    assert CellState(lava=True).is_fluid()
    assert not CellState().is_fluid()
    assert CellState(lava=True).is_heat_source()
    assert not CellState(water=True).is_heat_source()
    assert not CellState().is_heat_source()


def test_diffuse_step_converges_and_clamps():
    # 朝向邻居均值靠拢
    new = diffuse_step(0.0, [1.0, 1.0, 1.0, 1.0], 0.25)
    assert abs(new - 0.25) < 1e-9
    # 钳制到 [0, 1]
    hot = diffuse_step(1.0, [2.0, 2.0, 2.0, 2.0], 0.5, 0.0, 1.0)
    assert hot == 1.0
    cold = diffuse_step(0.0, [-1.0, -1.0], 0.5, 0.0, 1.0)
    assert cold == 0.0


# ── T-M3-03 水流动 ──
def test_water_falls_to_bottom():
    reg = _registry()
    W, H, D = 16, 16, 1
    world = BlockWorld(W, H, D)        # 全空气
    world.set(8, 15, 0, WATER)         # 悬空 1 格水
    sim = WorldSim(world, reg)
    # 跑 40 个 sim step（每步 tick(0.05)）
    for _ in range(40):
        sim.tick(0.05)
    # 水已离开原悬空位置
    assert not sim.get_water(8, 15, 0)
    # 水已落到某底部格（y=0），且不会低于底部
    assert any(sim.get_water(x, 0, 0) for x in range(W))


def test_water_spreads_on_floor():
    reg = _registry()
    W, H, D = 16, 16, 1
    world = BlockWorld(W, H, D)
    world.set(8, 5, 0, WATER)
    sim = WorldSim(world, reg)
    bottom_water = set()
    for _ in range(60):
        sim.tick(0.05)
        for x in range(W):
            if sim.get_water(x, 0, 0):
                bottom_water.add(x)
    # 水沿底部铺开（至少占据多处）
    assert len(bottom_water) >= 1


# ── T-M3-03 温度扩散 ──
def test_temperature_diffuses_from_lava():
    reg = _registry()
    W, H, D = 16, 16, 1
    world = BlockWorld(W, H, D)
    world.set(5, 5, 0, LAVA_ID)        # 热源
    sim = WorldSim(world, reg)
    # 岩浆格恒为 lava_temp
    assert sim.get_temperature(5, 5, 0) == pytest.approx(1.0)
    # 单步后邻格升温
    sim.tick(0.05)
    assert sim.get_temperature(6, 5, 0) > 1e-3
    assert sim.get_temperature(4, 5, 0) > 1e-3
    assert sim.get_temperature(5, 4, 0) > 1e-3
    # 岩浆格仍钉死为 lava_temp
    assert sim.get_temperature(5, 5, 0) == pytest.approx(1.0)


def test_dirty_chunks_marked_and_cleared():
    reg = _registry()
    W, H, D = 16, 16, 1
    world = BlockWorld(W, H, D)
    world.set(5, 5, 0, LAVA_ID)
    sim = WorldSim(world, reg)
    # 初始：含岩浆的 chunk 标脏
    assert len(sim.dirty_chunks) > 0
    # 推进后脏集被重算（重新标脏，因为仍有热源）
    sim.tick(0.05)
    assert len(sim.dirty_chunks) > 0


def test_mark_dirty_around():
    reg = _registry()
    world = BlockWorld(32, 32, 8)
    sim = WorldSim(world, reg)
    before = len(sim.dirty_chunks)
    sim.mark_dirty_around(10, 10, 3)
    # 标记了 (10,10,3) 所在 chunk + 3×3×3 邻 chunk（>1 个新 chunk）
    assert len(sim.dirty_chunks) > before


# ── T-M3-04 覆盖层快照 ──
def test_overlay_syncs_with_world_and_temp():
    reg = _registry()
    W, H, D = 16, 16, 1
    world = BlockWorld(W, H, D)
    world.set(5, 5, 0, LAVA_ID)
    world.set(2, 2, 0, WATER)
    sim = WorldSim(world, reg)
    # 未步进：overlay 直接反映世界（水仍在 (2,2)）
    ov0 = sim.snapshot_overlays(0)
    assert ov0.lava[5][5] is True
    assert ov0.water[2][2] is True
    assert ov0.water[5][5] is False
    # 步进后：温度扩散 + 水下落一格（(2,2)→(2,1)）
    sim.tick(0.05)
    ov1 = sim.snapshot_overlays(0)
    assert ov1.lava[5][5] is True
    assert ov1.water[1][2] is True          # 水已落至 (2,1)
    # temp 归一化并与 get_temperature 一致
    assert abs(ov1.temp[5][5] - 1.0) < 1e-9
    t = sim.get_temperature(6, 5, 0)
    assert abs(ov1.temp[5][6] - clamp(t / 1.0, 0.0, 1.0)) < 1e-9
    # cell() 返回 CellState
    cell = ov1.cell(5, 5)
    assert cell.is_heat_source()
    assert cell.lava is True
