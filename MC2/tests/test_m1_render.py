# -*- coding: utf-8 -*-
"""test_m1_render — 瓦片渲染几何一致性（与 TextWorldRenderer 一致，headless）。

覆盖：
  - TileWorldRenderer.collect_tiles 与 TextWorldRenderer 对同一视口产生
    一致的非空格集合（T-M1-11）。
  - _world_to_screen 公式与坐标映射正确。
"""

from __future__ import annotations

from mcclone.core.geometry import AABB2D
from mcclone.core.block_registry import BlockRegistry, STONE, GRASS, WATER
from mcclone.core.block_world import BlockWorld
from mcclone.render.tile_world_renderer import TileWorldRenderer, TILE_SIZE, HUD_TOP, VIEW_OFFSET_X
from mcclone.render.text_world_renderer import TextWorldRenderer


def _reg():
    reg = BlockRegistry()
    reg.load_defaults()
    return reg


def test_tile_text_geometry_consistent():
    reg = _reg()
    world = BlockWorld(20, 12)
    world.set(2, 3, 0, STONE)
    world.set(5, 7, 0, GRASS)
    world.set(10, 1, 0, WATER)
    world.set(15, 10, 0, STONE)
    vp = AABB2D(0, 0, 19, 11)

    renderer = TileWorldRenderer(None, reg)
    tiles = {(wx, wy) for (wx, wy, _bid) in renderer.collect_tiles(world, vp)}

    text = TextWorldRenderer(reg)
    lines = text.render(world, vp, use_ansi=False).rstrip("\n").split("\n")
    text_cells = set()
    for r, line in enumerate(lines):
        world_y = vp.max_y - r
        for c, ch in enumerate(line):
            if ch != " ":
                world_x = vp.min_x + c
                text_cells.add((world_x, world_y))

    assert tiles == text_cells, (
        f"几何不一致: tile-only={tiles - text_cells}, "
        f"text-only={text_cells - tiles}"
    )


def test_world_to_screen_mapping():
    reg = _reg()
    vp = AABB2D(4, 2, 83, 25)
    renderer = TileWorldRenderer(None, reg)
    tx, ty = 30, 20
    px, py = renderer._world_to_screen(tx, ty, vp)
    expected_c = tx - vp.min_x
    expected_r = vp.max_y - ty
    assert px == VIEW_OFFSET_X + expected_c * TILE_SIZE
    assert py == HUD_TOP + expected_r * TILE_SIZE


def test_world_to_screen_roundtrip_via_camera():
    reg = _reg()
    vp = AABB2D(10, 5, 89, 28)
    renderer = TileWorldRenderer(None, reg)
    from mcclone.core.camera import Camera
    cam = Camera(AABB2D(vp.min_x, vp.min_y, vp.max_x, vp.max_y))
    tx, ty = 50, 18
    px, py = renderer._world_to_screen(tx, ty, vp)
    mx, my = px + TILE_SIZE // 2, py + TILE_SIZE // 2
    wx, wy = cam.screen_to_world_cell(mx, my)
    assert (wx, wy) == (tx, ty)
