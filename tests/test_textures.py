# -*- coding: utf-8 -*-
"""程序化贴图与图集几何单测（纯字节，零 GL）。

跑：`python -m tests.test_textures`
"""
from __future__ import annotations

import sys

from tests._util import make_suite

from mcclone3d import textures as T

test, main = make_suite('ALL_TEXTURES_TESTS_PASSED', '程序化贴图')


@test('确定性：同一张贴图两次生成逐字节相同')
def t_deterministic():
    for name in T.ATLAS_TILE_NAMES:
        a, b = T.tile_pixels(name), T.tile_pixels(name)
        assert a == b, f'{name} 两次生成不一致'
        assert len(a) == T.TILE * T.TILE * 4, f'{name} 字节数不对：{len(a)}'


@test('不同贴图内容不同（否则图集里是同一张图重复 N 次）')
def t_distinct():
    seen = {}
    for name in T.ATLAS_TILE_NAMES:
        px = T.tile_pixels(name)
        for other, blob in seen.items():
            assert px != blob, f'{name} 与 {other} 逐像素完全相同'
        seen[name] = px


@test('格号表：名字唯一、顺序即索引、覆盖全部画法')
def t_index():
    assert len(T.ATLAS_TILE_NAMES) == len(set(T.ATLAS_TILE_NAMES))
    assert set(T.ATLAS_TILE_NAMES) == set(T.PAINTERS), '有画法没进图集（或反之）'
    for i, name in enumerate(T.ATLAS_TILE_NAMES):
        assert T.TILE_INDEX[name] == i


@test('未知贴图名必须响亮报错（不许静默给一张空图）')
def t_unknown():
    try:
        T.tile_pixels('no_such_tile')
    except KeyError:
        pass
    else:
        raise AssertionError('未知贴图名必须抛 KeyError')


@test('图集：尺寸、每格落在自己的矩形内、格与格不重叠')
def t_atlas_layout():
    lay = T.LAYOUT
    assert lay.size == lay.cols * T.TILE
    assert lay.rows * lay.cols >= len(T.ATLAS_TILE_NAMES)
    seen = set()
    for name in T.ATLAS_TILE_NAMES:
        x, y, w, h = lay.pixel_rect(name)
        assert w == T.TILE and h == T.TILE
        assert 0 <= x <= lay.size - w and 0 <= y <= lay.size - h
        for cy in range(y, y + h):
            for cx in range(x, x + w):
                assert (cx, cy) not in seen, f'{name} 与别的贴图重叠于 ({cx},{cy})'
                seen.add((cx, cy))


@test('图集字节：每张贴图的像素确实被写到了它自己的矩形里')
def t_atlas_pixels():
    blob = T.build_atlas()
    lay = T.LAYOUT
    assert len(blob) == lay.size * lay.size * 4
    for name in T.ATLAS_TILE_NAMES[:6]:                 # 抽 6 张逐像素核对（全量也行，慢）
        src = T.tile_pixels(name)
        x0, y0, w, h = lay.pixel_rect(name)
        for ty in range(h):
            for tx in range(w):
                di = ((y0 + ty) * lay.size + (x0 + tx)) * 4
                si = (ty * w + tx) * 4
                assert blob[di:di + 4] == src[si:si + 4], \
                    f'{name} 在 ({tx},{ty}) 的像素没写对'


@test('UV 矩形：v 轴与"第 0 行在上"一致（这是最容易搞反的一处）')
def t_uv_orientation():
    lay = T.LAYOUT
    name = T.ATLAS_TILE_NAMES[0]
    x, y, w, h = lay.pixel_rect(name)
    u0, v0, u1, v1 = lay.uv_rect(name)
    assert abs(u0 - x / lay.size) < 1e-9 and abs(u1 - (x + w) / lay.size) < 1e-9
    # 像素矩形在上边（y 小）⇒ UV 的上边（v 大）应为 1 - y/size
    assert abs(v1 - (1.0 - y / lay.size)) < 1e-9, 'v 轴方向反了'
    assert abs(v0 - (1.0 - (y + h) / lay.size)) < 1e-9
    assert v0 < v1


@test('贴图内容有结构（不是一片纯色）—— 逐张贴图至少两种颜色')
def t_not_flat():
    for name in T.ATLAS_TILE_NAMES:
        px = T.tile_pixels(name)
        colors = {px[i:i + 4] for i in range(0, len(px), 4)}
        assert len(colors) >= 2, f'{name} 是纯色（画法没生效？）'


if __name__ == '__main__':
    sys.exit(main())
