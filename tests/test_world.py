# -*- coding: utf-8 -*-
"""世界生成与区块存储单测（纯逻辑，零 GL）。

跑：`python -m tests.test_world`
"""
from __future__ import annotations

import sys

from tests._util import make_suite

from mcclone3d import blocks as B
from mcclone3d.world import CHUNK, ChunkedWorld, chunk_key, surface_height

test, main = make_suite('ALL_WORLD_TESTS_PASSED', '世界生成')


@test('确定性：同种子两次生成逐格相同；换种子会变')
def t_deterministic():
    a = ChunkedWorld(1234, 32, 32).generate()
    b = ChunkedWorld(1234, 32, 32).generate()
    c = ChunkedWorld(1235, 32, 32).generate()
    diff = 0
    for x in range(0, 32, 3):
        for y in range(0, 32, 3):
            for z in range(0, 32, 3):
                assert a.get(x, y, z) == b.get(x, y, z), f'({x},{y},{z}) 两次不一致'
                diff += (a.get(x, y, z) != c.get(x, y, z))
    assert diff > 0, '换种子后世界完全没变（噪声没用上？）'


@test('区块覆盖完整：每个需要的区块都生成了（曾因三轴界写错漏掉大半）')
def t_chunks_complete():
    w = ChunkedWorld(7, 32, 32).generate()
    want = (32 // CHUNK) * (32 // CHUNK) * (32 // CHUNK)
    assert len(w.chunks) == want, f'区块数 {len(w.chunks)} != 期望 {want}'
    for x in range(0, 32, 5):
        for z in range(0, 32, 5):
            h = w.surface_at(x, z)
            col = [w.get(x, y, z) for y in range(max(0, h - 4), min(32, h + 2))]
            assert any(b != B.AIR for b in col), f'({x},{z}) 地表附近全是空气'


@test('地层：y=0 是基岩；地表 = 该列高度上的那一格；地下按泥沙石分层')
def t_layers():
    w = ChunkedWorld(99, 32, 32).generate()
    for x in range(0, 32, 6):
        for z in range(0, 32, 6):
            assert w.get(x, 0, z) == B.BEDROCK, f'({x},{z}) 底部不是基岩'
            h = w.surface_at(x, z)
            assert h + 1 < w.height, f'({x},{z}) 地表顶到世界顶'
            # ⚠ 不能断言"地表上面是空气"：树冠会长在地表之上（实测踩过）。
            # 能断言的是"地表那一格不是空气，也不是石头"（石头只出现在地表以下）。
            top = w.get(x, h, z)
            assert top != B.AIR, f'({x},{z}) 地表那一格是空气（h={h}）'
            assert top != B.STONE, f'({x},{z}) 地表那一格是石头（h={h}）'
            if h > w.sea_level + 2:
                # 高地：地表下 1~3 格是泥土（生成规则里的 3 格土层）
                assert w.get(x, h - 1, z) == B.DIRT, \
                    f'({x},{z}) 地表下 1 格是 {B.name_of(w.get(x, h - 1, z))}，期望泥土'
            # ⚠ 不断言"再往下一定是石头"：土层之下还有**矿脉带**（煤/铁），
            # 6 格深处完全可能是矿石（实测踩过）。能断言的是"不再是土/沙"。
            if h > 8:
                deep = w.get(x, h - 6, z)
                assert deep in (B.STONE, B.COAL_ORE, B.IRON_ORE), \
                    f'({x},{z}) 地表下 6 格是 {B.name_of(deep)}，既不是石头也不是矿石'


@test('地表材质口径：地表既不是空气也不是石头（矿石不许长到地表上）')
def t_surface_type():
    """穷举整张地图核对地表材质 —— 这是"矿脉判定必须在土层之后"那条修复的判据。

    先前把矿脉判定写在土层之前，`y == h` 同时满足"地表"与"在矿脉里"，
    于是地表偶尔冒出煤矿/铁矿（实测随机打红"高地表应长草"）。
    """
    for seed, size, height in ((99, 32, 32), (2026, 48, 64), (7, 64, 48)):
        w = ChunkedWorld(seed, size, height).generate()
        sea, snow = w.sea_level, w.snow_line
        for x in range(size):
            for z in range(size):
                h = w.surface_at(x, z)
                assert 1 < h < height - 1, f'({x},{z}) 地表高度越界：{h}'
                top = w.get(x, h, z)
                assert top != B.AIR, f'seed={seed} ({x},{z}) 地表是空气'
                assert top not in (B.COAL_ORE, B.IRON_ORE), \
                    f'seed={seed} ({x},{z}) 地表长出了矿石（{B.name_of(top)}）'
                if h <= sea:
                    assert top in (B.SAND, B.GRAVEL), \
                        f'seed={seed} ({x},{z}) 水下地表是 {B.name_of(top)}'
                elif h >= snow:
                    assert top == B.SNOW, \
                        f'seed={seed} ({x},{z}) 雪线之上地表是 {B.name_of(top)}'
                else:
                    assert top in (B.GRASS, B.SAND), \
                        f'seed={seed} ({x},{z}) 陆地表是 {B.name_of(top)}'


@test('地表高度随世界高度缩放（写死基准会让矮世界变成悬空）')
def t_height_scaling():
    for height in (32, 64, 80, 128):
        hs = [surface_height(x, z, 4242, height)
              for x in range(0, 40, 3) for z in range(0, 40, 3)]
        lo, hi = min(hs), max(hs)
        assert lo >= 3, f'height={height} 地表太低：{lo}'
        assert hi <= height - 3, f'height={height} 地表顶到世界顶：{hi}'
        assert hi - lo >= 2, f'height={height} 地表没有起伏（噪声没生效）'


@test('边界：世界外一律 AIR（所以边界看得见，而不是被隐形墙挡住）')
def t_bounds():
    w = ChunkedWorld(5, 32, 32).generate()
    for p in ((-1, 5, 5), (5, -1, 5), (5, 5, -1), (32, 5, 5), (5, 32, 5), (5, 5, 32)):
        assert w.get(*p) == B.AIR, f'{p} 越界应返回 AIR'


@test('set 记账：改一格进一条增量；改回原值不留痕；越界不记账')
def t_edits():
    w = ChunkedWorld(11, 32, 32).generate()
    assert w.edits == {}
    x, z = 4, 4
    y = w.surface_at(x, z) + 1
    assert w.set(x, y, z, B.STONE) is True
    assert w.edits == {(x, y, z): B.STONE}
    assert w.set(x, y, z, B.STONE) is False, '写同值不算改变'
    assert len(w.edits) == 1
    assert w.set(-1, 0, 0, B.STONE) is False and len(w.edits) == 1, '越界不该记账'
    assert w.set(x, y, z, B.AIR) is True
    assert w.edits[(x, y, z)] == B.AIR


@test('种树：确定性、不把树当玩家增量、树干确实在地表之上')
def t_trees():
    a = ChunkedWorld(31, 64, 64).generate()
    n0 = len(a.edits)
    planted = a.plant_trees()
    assert planted > 0, '一棵树都没种上（散布条件太苛刻？）'
    assert len(a.edits) == n0, '树被记成了玩家增量（应用 set_generated，不是 set）'
    b = ChunkedWorld(31, 64, 64).generate()
    b.plant_trees()
    assert a.block_count(B.LOG) == b.block_count(B.LOG), '两次种树结果不同'
    assert a.block_count(B.LOG) > 0 and a.block_count(B.LEAVES) > 0


@test('水：海平面由世界高度推出，且确有水方块')
def t_water():
    for height in (32, 64):
        w = ChunkedWorld(2026, 64, height).generate()
        assert 0 < w.sea_level < height, f'height={height} 海平面越界：{w.sea_level}'
        assert w.block_count(B.WATER) > 0, f'height={height} 一滴水都没有'
        # 有水的列，水面必须正好在 sea_level（不是"水填到世界顶"）
        cols_with_water = [(x, z) for x in range(0, 64, 4) for z in range(0, 64, 4)
                           if w.get(x, w.sea_level, z) == B.WATER]
        assert cols_with_water, f'height={height} 海平面那一层没有水'
        for (x, z) in cols_with_water[:8]:
            assert w.get(x, w.sea_level + 1, z) == B.AIR, \
                f'海平面之上还有水（({x},{z}) 溢出了）'


@test('chunk_key 与世界/区块索引互换一致')
def t_chunk_key():
    w = ChunkedWorld(3, 32, 32).generate()
    for x in (0, 1, 15, 16, 31):
        for y in (0, 15, 31):
            for z in (0, 16, 31):
                key = chunk_key(x, y, z)
                assert key in w.chunks, f'({x},{y},{z}) 的区块 {key} 不存在'
                assert w.get(x, y, z) is not None


if __name__ == '__main__':
    sys.exit(main())
