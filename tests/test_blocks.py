# -*- coding: utf-8 -*-
"""方块表与面剔除规则单测（纯逻辑，零 GL）。

跑：`python -m tests.test_blocks`
"""
from __future__ import annotations

import sys

from tests._util import make_suite

from mcclone3d import blocks as B

test, main = make_suite('ALL_BLOCKS_TESTS_PASSED', '方块表')


@test('id 契约：只追加不改号，且 AIR 不在定义表里')
def t_ids():
    ids = sorted(B.BLOCKS)
    assert ids == list(range(1, len(ids) + 1)), f'id 出现断号或重复：{ids}'
    assert B.AIR == 0 and B.AIR not in B.BLOCKS
    assert B.STONE == 1 and B.GRASS == 3, '既有 id 被改动（存档契约会被破坏）'


@test('名字唯一且可双向查找')
def t_names():
    names = [b.name for b in B.all_blocks()]
    assert len(names) == len(set(names)), f'方块名重复：{names}'
    for b in B.all_blocks():
        assert B.by_name(b.name).id == b.id
        assert B.by_id(b.id).name == b.name
    assert B.by_id(B.AIR) is None, '空气不该有定义'
    try:
        B.by_name('no_such_block')
    except KeyError:
        pass
    else:
        raise AssertionError('未知方块名必须抛 KeyError')


@test('贴图：每个方块的每个面都能取到名字，且名字都在贴图表里')
def t_tiles():
    from mcclone3d import textures
    known = set(textures.PAINTERS)
    for b in B.all_blocks():
        for face in B.FACE_ORDER:
            tile = B.tile_for_face(b.id, face)
            assert tile, f'{b.name} 的 {face} 面没有贴图'
            assert tile in known, f'{b.name} 的 {face} 面贴图 {tile!r} 不在贴图表里'


@test('草方块三向贴图：顶/侧/底各不相同（这是"按面声明"的存在理由）')
def t_grass_faces():
    top = B.tile_for_face(B.GRASS, '+y')
    side = B.tile_for_face(B.GRASS, '+z')
    bottom = B.tile_for_face(B.GRASS, '-y')
    assert top == 'grass_top' and side == 'grass_side' and bottom == 'dirt'
    assert len({top, side, bottom}) == 3


@test('剔除规则：不透明邻居挡死；空气不挡；同种透明块互相挡')
def t_face_visible():
    assert B.face_visible(B.STONE, B.DIRT) is False, '不透明邻居必须挡死'
    assert B.face_visible(B.STONE, B.AIR) is True, '空气必须不挡'
    assert B.face_visible(B.WATER, B.WATER) is False, '同种透明块互相挡（否则水面内部全是面）'
    assert B.face_visible(B.GLASS, B.GLASS) is False
    assert B.face_visible(B.WATER, B.GLASS) is True, '异种透明块必须画'
    assert B.face_visible(B.GLASS, B.WATER) is True
    assert B.face_visible(B.WATER, B.STONE) is False, '被石头挡住的侧面不画'


@test('固体/液体/透明度判据：空气算透明，水不算固体')
def t_flags():
    assert B.is_solid(B.STONE) and not B.is_solid(B.AIR)
    assert not B.is_solid(B.WATER) and B.is_liquid(B.WATER)
    assert B.is_transparent(B.AIR) and B.is_transparent(B.WATER)
    assert not B.is_transparent(B.STONE)
    assert B.by_id(B.TORCH).emissive > 0, '火把要自发光'
    assert B.by_id(B.BEDROCK).hardness > 100, '基岩要挖不动'


@test('hotbar 默认项都是合法名字（方块名，或别名表登记的物品名）')
def t_hotbar():
    """⚠ Phase 3 起 hotbar 的名字**不一定是方块名**：`lever` 是物品名，
    它对应 `lever_off`/`lever_on` 两个方块状态（见 `BLOCK_ITEM_ALIAS`）。
    这里不引 items（方块表模块不该依赖物品表），而是拿别名表的值当第二套合法名。
    """
    alias_names = set(B.BLOCK_ITEM_ALIAS.values())
    for name in B.DEFAULT_HOTBAR:
        # ⚠ 不能写 `by_name(name) is not None`：那个函数查不到会**抛 KeyError**
        #   （"配置里写错名字要当场爆"是它的设计），所以用名字表查。
        assert name in B.BLOCK_NAMES or name in alias_names, \
            f'hotbar 里的 {name!r} 既不是方块名，也不在别名表里'
    assert len(B.DEFAULT_HOTBAR) >= 9, 'hotbar 至少 9 格（对应 1-9 键）'


if __name__ == '__main__':
    sys.exit(main())
