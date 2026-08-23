# -*- coding: utf-8 -*-
"""
test_integration — 端到端集成测试（main 管线）。

覆盖：完整管线 registry → terrain.generate → renderer.render 是否产出
符合视口尺寸的字符画，以及确定性（同 seed 两次产出一致）、包含水面与草地字形。
"""

from __future__ import annotations

import io
import contextlib

from mcclone.core.geometry import AABB2D

import main as main_module
from mcclone.core.block_registry import BlockRegistry, WATER, GRASS
from mcclone.core.block_world import BlockWorld
from mcclone.core.terrain import TerrainGenerator
from mcclone.render.text_world_renderer import TextWorldRenderer


def _build_picture(seed=12345, width=64, height=24):
    reg = BlockRegistry.from_json()
    noise = __import__("mcclone.core.noise", fromlist=["PerlinNoise"]).PerlinNoise(seed)
    gen = TerrainGenerator(reg, seed, noise)
    world = gen.generate(width, height)
    vp = AABB2D(0, 0, width - 1, height - 1)
    renderer = TextWorldRenderer(reg)
    return reg, world, renderer.render(world, vp, use_ansi=False)


def test_pipeline_produces_viewport_sized_picture():
    _, _, picture = _build_picture()
    lines = picture.rstrip("\n").split("\n")
    assert len(lines) == 24
    for i, ln in enumerate(lines):
        assert len(ln) == 64, f"第 {i} 行宽度应为 64"


def test_pipeline_has_water_and_grass_glyphs():
    reg, world, _ = _build_picture()
    water_glyph = reg.get(WATER).glyph
    grass_glyph = reg.get(GRASS).glyph
    found_water = found_grass = False
    for x in range(64):
        for y in range(24):
            bid = world.get(x, y, 0)
            if bid == WATER:
                found_water = True
            if bid == GRASS:
                found_grass = True
    assert found_water, "管线应生成水面"
    assert found_grass, "管线应生成草地"
    assert water_glyph == "~"
    assert grass_glyph == '"'


def test_pipeline_deterministic():
    _, w1, p1 = _build_picture(seed=777)
    _, w2, p2 = _build_picture(seed=777)
    assert w1.to_dict() == w2.to_dict(), "同 seed 两次地形应一致"
    assert p1 == p2, "同 seed 两次渲染应一致"


def test_main_runs_without_error():
    # 捕获 main() 的打印输出，确认不抛异常且产出就绪信息
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        main_module.main()
    out = buf.getvalue()
    assert "就绪" in out, "main() 应输出就绪信息"
    # 至少应画出 24 行
    lines = out.rstrip("\n").split("\n")
    assert len(lines) >= 24
