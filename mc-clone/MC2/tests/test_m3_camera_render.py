# -*- coding: utf-8 -*-
"""test_m3_camera_render — T-M3-05/06/07 相机/渲染器/玩家 的 Z 维扩展（headless）。

验收要点：
  - Camera.set_z(z, depth) 钳制到 [0, depth-1]；旧 1 参 set_z 不钳制。
  - clamp_z(world) 钳制到 [0, world.depth-1]。
  - screen_to_world_cell 与 _world_to_screen 在任意 z 层互逆（2D 不变）。
  - TileWorldRenderer.collect_tiles(world, vp, z) 按层返回不同集合。
  - Player.try_break/try_place 带 tz 改对应层；tz=0 行为与旧一致。
"""

from __future__ import annotations

import pytest

from mcclone.core.geometry import AABB2D
from mcclone.core.block_registry import (BlockRegistry, BlockDef,
                            AIR, STONE, DIRT, GRASS, WATER)
from mcclone.core.block_world import BlockWorld
from mcclone.core.camera import Camera
from mcclone.render.tile_world_renderer import TileWorldRenderer
from mcclone.player.player import Player
from mcclone.world.worldgen import MultiLayerGenerator, LAVA_ID


def _registry():
    reg = BlockRegistry()
    reg.load_defaults()
    reg.register(BlockDef(LAVA_ID, "lava", "*", "lava",
                          solid=False, transparent=True))
    return reg


# ── T-M3-05 Camera ──
def test_camera_set_z_clamps_with_depth():
    cam = Camera(AABB2D(0, 0, 79, 23))
    cam.set_z(99, 8)
    assert cam.current_z == 7
    cam.set_z(-5, 8)
    assert cam.current_z == 0
    cam.set_z(3, 8)
    assert cam.current_z == 3


def test_camera_set_z_one_arg_no_clamp():
    cam = Camera(AABB2D(0, 0, 79, 23))
    cam.set_z(50)                 # 旧 1 参语义：不钳制
    assert cam.current_z == 50


def test_camera_clamp_z():
    cam = Camera(AABB2D(0, 0, 79, 23))
    cam.current_z = 99
    world = BlockWorld(32, 32, 8)
    cam.clamp_z(world)
    assert cam.current_z == 7


def test_camera_screen_cell_inverse_any_z():
    viewport = AABB2D(0, 0, 79, 23)
    cam = Camera(viewport)
    cam.current_z = 3
    renderer = TileWorldRenderer(None, _registry())
    px, py = renderer._world_to_screen(10, 15, viewport)
    tx, ty = cam.screen_to_world_cell(px, py)
    assert (tx, ty) == (10, 15)


# ── T-M3-06 Renderer 按层 ──
def test_renderer_collect_tiles_by_layer():
    reg = _registry()
    world = MultiLayerGenerator(reg, 123).generate(16, 16, 8)
    viewport = AABB2D(0, 0, 15, 15)
    renderer = TileWorldRenderer(None, reg)
    tiles_z0 = set(renderer.collect_tiles(world, viewport, z=0))
    tiles_z3 = set(renderer.collect_tiles(world, viewport, z=3))
    # z=0（地形）与 z=3（stone 层）应不同
    assert tiles_z0 != tiles_z3
    # z=3 应全为 stone（层内环境一致）
    for (_x, _y, bid) in tiles_z3:
        assert bid == STONE


def test_renderer_render_headless_no_crash():
    reg = _registry()
    world = MultiLayerGenerator(reg, 5).generate(16, 16, 8)
    viewport = AABB2D(0, 0, 15, 15)
    renderer = TileWorldRenderer(None, reg)
    # screen=None：仅遍历验证，不 blit
    renderer.render(world, viewport, overlays=None, z=3)
    # 带 overlays 也不报错（headless 跳过绘制）
    from mcclone.simulation import WorldSim
    sim = WorldSim(world, reg)
    ov = sim.snapshot_overlays(3)
    renderer.render(world, viewport, overlays=ov, z=3,
                    show_temp=True, show_water=True)


# ── T-M3-07 Player tz ──
def test_player_try_break_place_with_tz():
    reg = _registry()
    world = BlockWorld(16, 16, 4)
    world.set(3, 3, 2, STONE)
    p = Player(1.0, 1.0, reg)
    # 破坏 (3,3,2)
    assert p.try_break(world, 3, 3, tz=2) is True
    assert world.get(3, 3, 2) == AIR
    # 放置 (5,5,2)
    p.held_id = DIRT
    assert p.try_place(world, 5, 5, tz=2) is True
    assert world.get(5, 5, 2) == DIRT
    # 默认 tz=0 不改其他层
    assert world.get(5, 5, 0) == AIR


def test_player_try_break_default_tz_is_z0():
    reg = _registry()
    world = BlockWorld(16, 16, 4)
    world.set(3, 3, 0, STONE)
    p = Player(1.0, 1.0, reg)
    # 旧签名（2 参）应作用于 z=0
    assert p.try_break(world, 3, 3) is True
    assert world.get(3, 3, 0) == AIR
    # 其他层不受影响
    assert world.get(3, 3, 2) == AIR
