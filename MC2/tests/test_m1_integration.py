# -*- coding: utf-8 -*-
"""test_m1_integration — M1 集成冒烟（headless 可跑）。

覆盖：
  - --no-gui 降级路径：复用 main.py 的 ANSI 渲染（in-process，无显示）。
  - GUI 模块导入安全：在无 pygame 环境下 import 各 M1 模块不抛异常。
  - 生成世界 + TileWorldRenderer.collect_tiles 端到端几何集合非空且确定。
"""

from __future__ import annotations

import io
import contextlib

from mcclone.core.block_registry import BlockRegistry, STONE, GRASS
from mcclone.core.block_world import BlockWorld
from mcclone.core.terrain import TerrainGenerator
from mcclone.core.noise import PerlinNoise
from mcclone.render.tile_world_renderer import TileWorldRenderer
from mcclone.core.camera import Camera
from mcclone.core.geometry import AABB2D
from mcclone.player.player import Player

# 视口瓦片数（与 main_gui.VIEWPORT_TILES 一致）。
VIEWPORT_TILES = (80, 24)


def _reg():
    reg = BlockRegistry()
    reg.load_defaults()
    return reg


def test_modules_importable_without_pygame():
    # 这些模块导入期不应依赖 pygame（延迟导入）
    from mcclone import main_gui# noqa: F401
    from mcclone.render import hud# noqa: F401
    from mcclone.input import mouse_input# noqa: F401
    from mcclone.render import tile_world_renderer# noqa: F401
    from mcclone.player import player# noqa: F401
    from mcclone.core import camera# noqa: F401
    from mcclone.core import event_bus# noqa: F401
    assert True


def test_gui_pipeline_collect_tiles_deterministic():
    reg = _reg()
    noise = PerlinNoise(12345)
    gen = TerrainGenerator(reg, 12345, noise)
    world = gen.generate(256, 96, 1)

    vp = AABB2D(0, 0, VIEWPORT_TILES[0] - 1, VIEWPORT_TILES[1] - 1)
    renderer = TileWorldRenderer(None, reg)
    tiles1 = renderer.collect_tiles(world, vp)

    # 确定性：同世界再收集应一致
    tiles2 = renderer.collect_tiles(world, vp)
    assert tiles1 == tiles2

    # 视口底部（y 0..23）必有 stone（地基填充）
    bids = {bid for (_x, _y, bid) in tiles1}
    assert STONE in bids
    assert len(tiles1) > 0

    # 确定性地形整体应含 grass（地表）
    grass_cells = {(x, y) for x in range(world.width) for y in range(world.height)
                   if world.get(x, y, 0) == GRASS}
    assert len(grass_cells) > 0


def test_no_gui_runs():
    """in-process 验证 --no-gui 降级路径（复用 main.py 的 ANSI 渲染，无显示）。

    说明：受管 Python 忽略 PYTHONPATH，故直接在当前进程调用 main_gui.main
    （其 sys.path 已由 _testutil/conftest 注入），避免子进程环境不一致。
    """
    import io
    import contextlib

    from mcclone import main_gui
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = main_gui.main(["--no-gui"])
    assert rc == 0, "main_gui --no-gui 应返回 0"
    assert "就绪" in buf.getvalue(), "应打印就绪信息"


def test_camera_follow_clamp_in_pipeline():
    reg = _reg()
    noise = PerlinNoise(777)
    gen = TerrainGenerator(reg, 777, noise)
    world = gen.generate(256, 96, 1)
    p = Player(128.0, 50.0, reg)
    vp = AABB2D(0, 0, VIEWPORT_TILES[0] - 1, VIEWPORT_TILES[1] - 1)
    cam = Camera(vp)
    cam.follow(p)
    cam.clamp_to(world.bounds())
    assert cam.viewport.min_x >= 0
    assert cam.viewport.max_x <= world.width - 1
    assert cam.viewport.min_y >= 0
    assert cam.viewport.max_y <= world.height - 1
