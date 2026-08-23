# -*- coding: utf-8 -*-
"""
test_text_renderer — TextWorldRenderer 补充测试（渲染模块）。

覆盖：ANSI 行渲染含转义与行尾 reset、纯 glyph 行、子视口、坐标映射、
空气与注册表缺失 id 的安全回退。与基础测试互补。
"""

from __future__ import annotations

from mcclone.core.geometry import AABB2D

from mcclone.core.block_registry import BlockRegistry, STONE, GRASS, AIR
from mcclone.core.block_world import BlockWorld
from mcclone.render.text_world_renderer import TextWorldRenderer


def _reg():
    reg = BlockRegistry()
    reg.load_defaults()
    return reg


def test_render_line_no_ansi_no_escape():
    reg = _reg()
    w = BlockWorld(64, 24)
    r = TextWorldRenderer(reg)
    line = r.render_line(w, AABB2D(0, 0, 63, 23), 23, use_ansi=False)
    assert "\033[" not in line
    assert len(line) == 64


def test_render_line_ansi_has_escape_and_reset():
    reg = _reg()
    w = BlockWorld(64, 24)
    r = TextWorldRenderer(reg)
    line = r.render_line(w, AABB2D(0, 0, 63, 23), 0, use_ansi=True)
    assert "\033[" in line
    assert line.endswith("\033[0m"), "ANSI 行应以 reset 结尾"


def test_coordinate_mapping_top_row_is_max_y():
    reg = _reg()
    w = BlockWorld(64, 24)
    w.set(10, 23, 0, STONE)                       # world y = 23（顶部）
    r = TextWorldRenderer(reg)
    out = r.render(w, AABB2D(0, 0, 63, 23), use_ansi=False)
    lines = out.rstrip("\n").split("\n")
    assert lines[0][10] == reg.get(STONE).glyph, "第 0 行第 10 列应映射到 world(10,23)"


def test_air_renders_as_space():
    reg = _reg()
    w = BlockWorld(32, 16)
    r = TextWorldRenderer(reg)
    line = r.render_line(w, AABB2D(0, 0, 31, 15), 5, use_ansi=False)
    assert set(line) == {" "}, "全空气行应全为空格"


def test_unknown_block_id_falls_back_to_space():
    reg = _reg()
    w = BlockWorld(32, 16)
    w.set(3, 3, 0, 777)                           # 注册表不存在的 id
    r = TextWorldRenderer(reg)
    line = r.render_line(w, AABB2D(0, 0, 31, 15), 3, use_ansi=False)
    assert line[3] == " ", "未知方块 id 应安全回退为空格"


def test_sub_viewport_render():
    reg = _reg()
    w = BlockWorld(64, 24)
    w.set(30, 20, 0, GRASS)
    vp = AABB2D(20, 18, 39, 22)                   # 子视口 20x5
    r = TextWorldRenderer(reg)
    out = r.render(w, vp, use_ansi=False)
    lines = out.rstrip("\n").split("\n")
    assert len(lines) == 5, "子视口高度应为 5"
    for ln in lines:
        assert len(ln) == 20, "子视口宽度应为 20"
    # world(30,20): r = max_y(22)-20 = 2, c = 30-20 = 10
    assert lines[2][10] == reg.get(GRASS).glyph


def test_render_to_string_line_count():
    reg = _reg()
    w = BlockWorld(40, 30)
    r = TextWorldRenderer(reg)
    out = r.render_to_string(w, AABB2D(0, 0, 39, 29), use_ansi=False)
    lines = out.rstrip("\n").split("\n")
    assert len(lines) == 30
