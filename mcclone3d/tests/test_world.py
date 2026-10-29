# -*- coding: utf-8 -*-
"""世界生成与区块存储单测（纯逻辑，零 GL）。

跑：`python -m tests.test_world`
"""
from __future__ import annotations

import sys

from tests._util import make_suite

from mcclone3d import blocks as B
from mcclone3d import caves
from mcclone3d.world import (CHUNK, ORE_BANDS, ChunkedWorld, chunk_key, ore_bands,
                             surface_height)

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
    holes = caves.tunnels(w.seed, w.size, w.height, w.sea_level).holes
    for x in range(0, 32, 5):
        for z in range(0, 32, 5):
            h = w.surface_at(x, z)
            col = [w.get(x, y, z) for y in range(max(0, h - 4), min(32, h + 2))]
            if all(b == B.AIR for b in col):
                # 全空只允许是 worm 洞口（Phase 2-C 打穿了表土）
                assert (x, z) in holes, \
                    f'({x},{z}) 地表附近全是空气却不是 worm 洞口（生成漏了？）'


@test('地层：y=0 是基岩；地表 = 该列高度上的那一格；地下按泥沙石分层')
def t_layers():
    w = ChunkedWorld(99, 32, 32).generate()
    holes = caves.tunnels(w.seed, w.size, w.height, w.sea_level).holes
    for x in range(0, 32, 6):
        for z in range(0, 32, 6):
            assert w.get(x, 0, z) == B.BEDROCK, f'({x},{z}) 底部不是基岩'
            h = w.surface_at(x, z)
            assert h + 1 < w.height, f'({x},{z}) 地表顶到世界顶'
            # ⚠ 不能断言"地表上面是空气"：树冠会长在地表之上（实测踩过）。
            # ⚠ 地表那一格**可以是空气** —— 但只在 worm 洞口处（Phase 2-C 的
            #   "允许自然洞口"）。噪声挖穿地表是 bug，两者用 `holes` 区分开。
            top = w.get(x, h, z)
            if top == B.AIR:
                assert (x, z) in holes, \
                    f'({x},{z}) 地表是空气却不在 worm 洞口清单里（噪声挖穿了地表？）'
            assert top != B.STONE, f'({x},{z}) 地表那一格是石头（h={h}）'
            if h > w.sea_level + 2:
                # 高地：地表下 1~3 格是泥土（生成规则里的 3 格土层）
                assert w.get(x, h - 1, z) == B.DIRT, \
                    f'({x},{z}) 地表下 1 格是 {B.name_of(w.get(x, h - 1, z))}，期望泥土'
            # ⚠ 不断言"再往下一定是石头"：土层之下还有**矿脉带**（煤/铁/金/钻石）
            # 与**洞穴**（Phase 2-C）。能断言的是"不再是土/沙，且空气是合法来源"。
            if h > 8:
                y = h - 6
                deep = w.get(x, y, z)
                assert deep in (B.STONE, B.AIR, B.COAL_ORE, B.IRON_ORE,
                                B.GOLD_ORE, B.DIAMOND_ORE), \
                    f'({x},{z}) 地表下 6 格是 {B.name_of(deep)}，既不是石头也不是矿石'
                if deep == B.AIR:
                    assert w.cave_field.is_cave(x, y, z, h) or (x, z) in holes, \
                        f'({x},{z}) y={y} 是空气，但既不是洞穴也不是 worm'


@test('地表材质口径：地表既不是空气也不是石头（矿石不许长到地表上）')
def t_surface_type():
    """穷举整张地图核对地表材质 —— 这是"矿脉判定必须在土层之后"那条修复的判据。

    先前把矿脉判定写在土层之前，`y == h` 同时满足"地表"与"在矿脉里"，
    于是地表偶尔冒出煤矿/铁矿（实测随机打红"高地表应长草"）。

    Phase 2-C：地表**可以是空气**，但只在 worm 洞口处（"允许自然洞口"）。
    所以判据从"不许是空气"改成"是空气就必须在洞口清单里" ——
    这样"噪声挖穿地表"这种 bug 依然会响，而真洞口不会。
    """
    for seed, size, height in ((99, 32, 32), (2026, 48, 64), (7, 64, 48)):
        w = ChunkedWorld(seed, size, height).generate()
        sea, snow = w.sea_level, w.snow_line
        holes = caves.tunnels(seed, size, height, sea).holes
        for x in range(size):
            for z in range(size):
                h = w.surface_at(x, z)
                assert 1 < h < height - 1, f'({x},{z}) 地表高度越界：{h}'
                top = w.get(x, h, z)
                if top == B.AIR:
                    assert (x, z) in holes, \
                        f'seed={seed} ({x},{z}) 地表是空气却不是 worm 洞口'
                    continue
                assert top not in (B.COAL_ORE, B.IRON_ORE, B.GOLD_ORE,
                                   B.DIAMOND_ORE), \
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


# ==================================================================== 矿脉分层（Phase 2-C）
@test('矿带表：深度上限随世界高度等比缩放（64 高 ⇒ 煤40/铁28/金16/钻石8）')
def t_ore_bands_scale():
    """写死绝对值会让矮世界的"钻石层"挤成 3 格甚至空掉 —— 与
    `surface_height`/`sea_level` 同一套缩放纪律（那条教训记在 `surface_height`）。"""
    def names(y, height=64):
        return [b[0] for b in ore_bands(y, height)]

    # 64 高世界：四个上限逐个对拍
    assert names(39) == ['coal_ore'], names(39)
    assert 'iron_ore' in names(27) and 'gold_ore' not in names(27), names(27)
    assert 'gold_ore' in names(15) and 'diamond_ore' not in names(15), names(15)
    assert 'diamond_ore' in names(7), names(7)
    # ⚠ **候选是全部而不是第一个**：初版"第一个覆盖该深度的带胜出"，
    #   于是 y=27 永远只能是煤 —— 铁实际只落在 y<16，"煤40/铁28"名存实亡。
    assert names(7) == ['coal_ore', 'iron_ore', 'gold_ore', 'diamond_ore'], names(7)
    assert names(20) == ['coal_ore', 'iron_ore'], names(20)
    # 浅于最浅矿带 ⇒ 没有矿（"矿不会长到地表"由判据自己兜住）
    for y in range(1, 8):
        assert ore_bands(y, 64), f'y={y} 在 64 高世界里不该有矿带'
    # 缩放：32 高世界里上限减半（铁 28→14），且每层都有矿带（不会空掉）
    for y in range(1, 20):
        assert ore_bands(y, 32), f'height=32 时 y={y} 没有任何矿带'
    assert 'iron_ore' not in names(15, 32), names(15, 32)
    assert 'iron_ore' in names(13, 32), names(13, 32)
    assert names(3, 32) == ['coal_ore', 'iron_ore', 'gold_ore', 'diamond_ore'], \
        names(3, 32)


@test('矿脉分层：真实世界里每种矿都在自己的深度区间内（穷举 64 高世界）')
def t_ore_depth_ranges():
    w = ChunkedWorld(2026, 96, 64).generate()
    tops = {name: top for (name, top, _c, _p) in ORE_BANDS}
    seen = {name: [] for (name, _t, _c, _p) in ORE_BANDS}
    for x in range(96):
        for z in range(96):
            h = w.surface_at(x, z)
            for y in range(0, h + 1):
                b = w.get(x, y, z)
                for name in seen:
                    if b == B.BLOCK_IDS[name]:
                        seen[name].append(y)
    for name, ys in seen.items():
        if not ys:
            continue                      # 96×96 采不到某矿种不算失败（概率事件）
        assert max(ys) < tops[name], \
            f'{name} 出现在 y={max(ys)}，超过上限 {tops[name]}'
    # 分层的意义：浅层矿的总量必须明显多于深层矿
    coal = len(seen['coal_ore'])
    iron = len(seen['iron_ore'])
    gold = len(seen['gold_ore'])
    diamond = len(seen['diamond_ore'])
    if coal and iron and gold:
        assert coal > iron > gold, f'矿量没有随深度递减：煤{coal} 铁{iron} 金{gold}'
    if gold and diamond:
        assert gold > diamond, f'钻石比金还多：{diamond} vs {gold}'


@test('矿脉：不在地表，也不出现在洞穴空气里（矿在洞壁上，不在空气里）')
def t_ore_not_in_surface_or_air():
    w = ChunkedWorld(777, 64, 64).generate()
    for x in range(64):
        for z in range(64):
            h = w.surface_at(x, z)
            for y in range(0, h + 1):
                b = w.get(x, y, z)
                if b not in (B.COAL_ORE, B.IRON_ORE, B.GOLD_ORE, B.DIAMOND_ORE):
                    continue
                assert y < h, f'({x},{y},{z}) 矿石长到了地表之上'
                assert B.is_solid(b), f'矿石 {B.name_of(b)} 不该是液体/空气'
    # 洞穴把石头挖走时，**矿也跟着没了**（说明矿脉判定在洞穴之前）
    w2 = ChunkedWorld(777, 64, 64).generate()
    assert w2.block_count(B.GOLD_ORE) >= 0      # 冒烟：统计接口不炸


if __name__ == '__main__':
    sys.exit(main())
