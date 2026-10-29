# -*- coding: utf-8 -*-
"""
test_block_world — BlockWorld 补充测试（world 模块）。

覆盖：z 维度（depth>1）索引、fill_rect 越界裁剪、整世界序列化保留 depth、
chunk 越界安全、bounds 等。与基础测试互补，避免重复。
"""

from __future__ import annotations

from mcclone.core.geometry import AABB2D

from mcclone.core.block_world import BlockWorld
from mcclone.core.block_registry import AIR, STONE, DIRT


def test_depth_dimension_indexing():
    w = BlockWorld(16, 16, depth=3)
    w.set(1, 1, 2, STONE)
    assert w.get(1, 1, 2) == STONE
    assert w.in_bounds(1, 1, 2) is True
    assert w.in_bounds(1, 1, 3) is False         # z 越界（depth=3 → z∈0..2）
    assert w.get(1, 1, 3) == AIR                  # 越界返回 air


def test_fill_rect_z_layer_isolated():
    w = BlockWorld(16, 16, depth=2)
    w.fill_rect(0, 0, 3, 3, DIRT, z=1)
    for x in range(4):
        for y in range(4):
            assert w.get(x, y, 1) == DIRT
            assert w.get(x, y, 0) == AIR           # 另一层不受影响


def test_fill_rect_out_of_bounds_clipped():
    w = BlockWorld(16, 16)
    w.fill_rect(14, 14, 20, 20, STONE)            # 部分越界
    assert w.get(14, 14, 0) == STONE
    assert w.get(15, 15, 0) == STONE
    assert w.get(16, 16, 0) == AIR                 # 越界部分被静默忽略


def test_to_from_dict_preserves_depth():
    w = BlockWorld(8, 8, depth=4)
    w.set(2, 2, 3, STONE)
    d = w.to_dict()
    assert d["depth"] == 4
    w2 = BlockWorld.from_dict(d)
    assert w2.depth == 4
    assert w2.get(2, 2, 3) == STONE


def test_chunk_out_of_bounds_load_is_safe():
    # chunk 落在世界之外 → 序列化得到全 0 网格，load 后世界不变
    w = BlockWorld(64, 64)
    w.set(0, 0, 0, STONE)
    data = w.serialize_chunk(8, 8, 8)             # ox=64,oy=64 全部越界
    assert all(all(v == 0 for v in row) for row in data["blocks"])
    w.load_chunk(8, 8, 8, data)
    assert w.get(0, 0, 0) == STONE                 # 原有方块不受影响


def test_bounds_reflects_depth_independent_2d():
    w = BlockWorld(64, 24, depth=5)
    b = w.bounds()
    assert isinstance(b, AABB2D)
    assert (b.min_x, b.min_y, b.max_x, b.max_y) == (0, 0, 63, 23)
    assert b.width == 63 and b.height == 23


def test_sparse_air_not_stored():
    w = BlockWorld(10, 10)
    w.set(4, 4, 0, STONE)
    d = w.to_dict()
    assert "4,4,0" in d["blocks"]
    w.set(4, 4, 0, AIR)                            # 设为空气后应从稀疏表移除
    assert "4,4,0" not in w.to_dict()["blocks"]
