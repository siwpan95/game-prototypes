# -*- coding: utf-8 -*-
"""test_m1_camera — Camera 跟随 / 钳制 / 像素↔世界格互逆（headless）。

覆盖：
  - follow 使视口中心对齐目标中心（整数格）
  - clamp_to 把视口钳制进世界（角落不越界）
  - screen_to_world_cell 与 TileWorldRenderer._world_to_screen 互逆
"""

from __future__ import annotations

from mcclone.core.geometry import AABB2D
from mcclone.core.block_world import BlockWorld
from mcclone.core.camera import Camera, TILE_SIZE, HUD_TOP, VIEW_OFFSET_X
from mcclone.render.tile_world_renderer import TileWorldRenderer
from mcclone.core.block_registry import BlockRegistry

# 视口瓦片数（与 main_gui.VIEWPORT_TILES 一致）。
VIEWPORT_TILES = (80, 24)


def _reg():
    reg = BlockRegistry()
    reg.load_defaults()
    return reg


def test_follow_centers_player():
    reg = _reg()
    world = BlockWorld(256, 96)
    vp = AABB2D(0, 0, VIEWPORT_TILES[0] - 1, VIEWPORT_TILES[1] - 1)
    cam = Camera(vp)
    player = AABB2D(128, 48, 129, 50)
    cam.follow(player)
    cam.clamp_to(world.bounds())
    # 视口宽 79，half=39.5；中心 128.5 → min_x = floor(128.5-39.5)=89
    assert cam.viewport.min_x == 89, cam.viewport.min_x
    # 中心应等于玩家中心
    cx = (cam.viewport.min_x + cam.viewport.max_x) / 2.0
    assert abs(cx - 128.5) < 1e-6


def test_clamp_at_corner():
    reg = _reg()
    world = BlockWorld(256, 96)
    bounds = world.bounds()
    vp = AABB2D(0, 0, VIEWPORT_TILES[0] - 1, VIEWPORT_TILES[1] - 1)
    cam = Camera(vp)
    # 玩家在左下角
    player = AABB2D(0, 0, 1, 2)
    cam.follow(player)
    cam.clamp_to(bounds)
    assert cam.viewport.min_x >= 0
    assert cam.viewport.max_x <= bounds.max_x
    assert cam.viewport.min_y >= 0
    assert cam.viewport.max_y <= bounds.max_y


def test_clamp_when_viewport_larger_than_world():
    reg = _reg()
    world = BlockWorld(40, 30)
    bounds = world.bounds()
    vp = AABB2D(0, 0, VIEWPORT_TILES[0] - 1, VIEWPORT_TILES[1] - 1)  # 宽 79 > 40
    cam = Camera(vp)
    cam.follow(AABB2D(0, 0, 1, 1))
    cam.clamp_to(bounds)
    # 视口比世界宽 → 钳制为整个世界
    assert cam.viewport.min_x == bounds.min_x
    assert cam.viewport.max_x == bounds.max_x


def test_screen_world_inverse():
    reg = _reg()
    vp = AABB2D(5, 3, 84, 26)     # 80x24 瓦片
    renderer = TileWorldRenderer(None, reg)
    cam = Camera(AABB2D(vp.min_x, vp.min_y, vp.max_x, vp.max_y))
    tx, ty = 40, 15
    px, py = renderer._world_to_screen(tx, ty, vp)
    # 取瓦片中心像素
    mx, my = px + TILE_SIZE // 2, py + HUD_TOP // 2 + (py - HUD_TOP) % TILE_SIZE + TILE_SIZE // 2
    # 简化：直接用 tile 中心像素
    mx, my = px + TILE_SIZE // 2, py + TILE_SIZE // 2
    wx, wy = cam.screen_to_world_cell(mx, my)
    assert (wx, wy) == (tx, ty), f"互逆失败：({wx},{wy}) != ({tx},{ty})"
