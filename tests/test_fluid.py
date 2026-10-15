# -*- coding: utf-8 -*-
"""Phase 2-C 第二批 水流单测（纯逻辑，零 GL）。

覆盖：源标记 / **挖穿海床 ⇒ 水灌进洞**（"洞穴与海打通"的实现）/
一次性灌注且**静止**（不震荡）/ 不进存档 / 无水源的列不动 /
遇到已有水就停 / 预算不丢扰动 / 确定性 / 读档后能重新灌。

跑：`python -m tests.test_fluid`
"""
from __future__ import annotations

import sys

from tests._util import make_suite

from mcclone3d import blocks as B
from mcclone3d.fluid import (MAX_FILL, FluidSystem, can_enter, find_source)
from mcclone3d.kernel import make_offline
from mcclone3d.world import ChunkedWorld

test, main = make_suite('ALL_FLUID_TESTS_PASSED', '水流')


def _k(seed=2026, size=128, height=64):
    return make_offline({'seed': seed, 'size': size, 'height': height,
                         'light': False})


def _seabed(k):
    """找一处海底地形列 `(x, z, h)`（`h < sea_level`）。"""
    w = k.world
    sea = w.sea_level
    for x in range(10, w.size - 10):
        for z in range(10, w.size - 10):
            h = w.surface_at(x, z)
            if h < sea:
                return x, z, h
    raise AssertionError('世界里没有海底地形（sea_level 太高？）')


def _dig(k, x, z, h, depth=6, half=0, disturb=True):
    """模拟玩家挖穿海床下方 `depth` 格（`half` 给一个方形范围）。"""
    w = k.world
    for dy in range(0, depth + 1):
        for dx in range(-half, half + 1):
            for dz in range(-half, half + 1):
                w.set_generated(x + dx, h - dy, z + dz, B.AIR)
                if disturb:
                    k.fluid.disturb(w, x + dx, h - dy, z + dz)
    return w


def _run(k, n=8, dt=0.05):
    for _ in range(n):
        k.fluid_step(dt)


# ==================================================================== 源
@test('源标记：生成时的水全部是源，且源不会自己动')
def t_sources_marked():
    k = _k()
    w = k.world
    water = w.block_count(B.WATER)
    assert water > 0, '这个世界没有水（海平面算错了？）'
    assert len(k.fluid.sources) == water, \
        f'源数 {len(k.fluid.sources)} ≠ 水格数 {water}'
    before = w.block_count(B.WATER)
    _run(k, 20)
    assert w.block_count(B.WATER) == before, '源水自己动了（不该）'


@test('源标记用的是 C 层 find（不是逐格遍历）—— 用大世界验时间量级')
def t_mark_sources_is_fast():
    import time
    w = ChunkedWorld(2026, 256, 64).generate()
    t0 = time.perf_counter()
    fs = FluidSystem()
    n = fs.mark_sources(w)
    dt = time.perf_counter() - t0
    assert n == w.block_count(B.WATER), f'源数 {n} ≠ 水格数'
    assert dt < 1.5, f'mark_sources 用了 {dt:.2f}s（逐格遍历会好几秒）'


# ==================================================================== 打通
@test('打通：挖穿海床下方 ⇒ 水沿垂直灌进洞里（洞穴与海连通的实现）')
def t_pour_into_cave():
    k = _k()
    w = k.world
    x, z, h = _seabed(k)
    _dig(k, x, z, h, depth=6)
    _run(k)
    # 洞底那一格必须是水（海在 y=sea，洞在 h 以下）
    assert w.get(x, h - 6, z) == B.WATER, \
        f'洞底 y={h - 6} 是 {B.name_of(w.get(x, h - 6, z))}，水没灌进来'
    # 整根水柱连续（不能是"一格水一格空"）
    for y in range(h - 6, h + 1):
        assert w.get(x, y, z) == B.WATER, f'水柱在 y={y} 断了'
    assert k.fluid.flowing_count() >= 7


@test('灌注是一次性的：一个 tick 内完成，之后完全静止（不震荡）')
def t_pour_converges():
    k = _k()
    w = k.world
    x, z, h = _seabed(k)
    _dig(k, x, z, h, depth=6)
    _run(k, 2)
    settled = k.fluid.flowing_count()
    active = len(k.fluid.active)
    for _ in range(200):
        k.fluid_step(0.05)
    assert k.fluid.flowing_count() == settled, \
        f'200 tick 后水量从 {settled} 变成 {k.fluid.flowing_count()}（还在震荡）'
    assert not k.fluid.active, f'活跃集没清空：{len(k.fluid.active)}'


@test('无水源的列：挖洞不进水（内陆洞穴保持干的）')
def t_no_source_no_water():
    k = _k()
    w = k.world
    # 找一处地表远高于海平面的内陆列
    sea = w.sea_level
    spot = None
    for x in range(10, w.size - 10):
        for z in range(10, w.size - 10):
            h = w.surface_at(x, z)
            if h > sea + 6:
                spot = (x, z, h)
                break
        if spot:
            break
    assert spot, '没有内陆高地'
    x, z, h = spot
    _dig(k, x, z, h, depth=8)
    _run(k)
    assert w.get(x, h - 8, z) != B.WATER, '内陆洞里凭空进水了'


@test('灌注遇已有水就停（不覆盖源；水柱不会穿过水继续灌）')
def t_stop_at_existing_water():
    k = _k()
    w = k.world
    x, z, h = _seabed(k)
    # 先在洞底放一格水（模拟已有的积水）
    w.set_generated(x, h - 6, z, B.WATER)
    _dig(k, x, z, h, depth=6)
    _run(k)
    assert w.get(x, h - 6, z) == B.WATER, '已有水被弄掉了'
    # 它下方的格（石头）不该被灌
    assert w.get(x, h - 7, z) == B.STONE, '灌注穿过了石头'


# ==================================================================== 纪律
@test('纪律：流体不写进存档增量（可由「源 + 方块」重算）')
def t_not_in_save_edits():
    k = _k()
    w = k.world
    x, z, h = _seabed(k)
    n0 = len(w.edits)
    _dig(k, x, z, h, depth=6)
    _run(k)
    assert len(w.edits) == n0, f'流体写进了 {len(w.edits) - n0} 条存档增量'
    # 存档里不该出现水（`dump()` 是纯内存口径，不必落盘）
    dumped = k.dump()
    names = {row[3] for row in dumped['world']['edits']}
    assert 'water' not in names, f'存档里有水：{sorted(names)[:6]}'


@test('确定性：同样操作两次，灌注结果逐格相同')
def t_deterministic():
    def once():
        k = _k()
        x, z, h = _seabed(k)
        _dig(k, x, z, h, depth=6, half=1)
        _run(k)
        return tuple(w_bytes(k.world))

    def w_bytes(world):
        return tuple(bytes(world.chunks[key]) for key in sorted(world.chunks))

    a, b = once(), once()
    assert a == b, '两次同样的操作结果不同（水流不是确定性的）'


@test('读档后仍能重新灌注（源重标记 + 洞还在增量里 ⇒ 重灌出同样的水）')
def t_reload_repour():
    k = _k()
    w = k.world
    x, z, h = _seabed(k)
    # ⚠ 这里必须用 **`set`（记增量）** 而不是 `set_generated`：洞要进存档，
    #    否则读档后洞根本没被重建，"水没了"是正确行为而不是 bug（实测踩过）。
    for dy in range(0, 7):
        w.set(x, h - dy, z, B.AIR)
        k.fluid.disturb(w, x, h - dy, z)
    _run(k)
    n1 = k.fluid.flowing_count()
    assert n1 >= 7, f'存档前水量 {n1} 不对'
    data = k.dump()
    k2 = _k()
    k2.load(data)
    n2 = k2.fluid.flowing_count()
    assert n2 == n1, f'读档后水量 {n2} ≠ 存档前 {n1}（读档后没重灌？）'
    assert k2.world.get(x, h - 6, z) == B.WATER, '读档后洞底没有水'


@test('预算：扰动点超预算时不丢（留到下一 tick，且总量不差）')
def t_budget_no_loss():
    k = _k()
    w = k.world
    x, z, h = _seabed(k)
    # 同一列上 5 个扰动点（从洞底往上排），预算只给 2
    for dy in range(0, 5):
        w.set_generated(x, h - dy, z, B.AIR)
        k.fluid.disturb(w, x, h - dy, z)
    total = len(k.fluid.active)
    first = k.fluid.step(w, budget=2)
    left = len(k.fluid.active)
    assert left >= total - 2, f'超预算的扰动点被丢了：{total} → 剩 {left}'
    # 再跑一次（预算放开）⇒ 活跃集必须清空（没有"永远排不完"的情况）
    k.fluid.step(w, budget=64)
    assert not k.fluid.active, '第二轮之后仍有活跃格（预算轮转有问题）'
    assert first > 0, '第一轮一格都没灌（场景前提错：该列上方应有水）'


@test('can_enter：默认只进空气；allow_water=True 才允许水格')
def t_can_enter():
    k = _k()
    w = k.world
    air = (2, 2, w.height - 1)
    w.set_generated(*air, B.AIR)
    assert can_enter(w, *air) is True
    w.set_generated(*air, B.STONE)
    assert can_enter(w, *air) is False
    w.set_generated(*air, B.WATER)
    assert can_enter(w, *air) is False, '水平扩散不该进水格'
    assert can_enter(w, *air, allow_water=True) is True
    assert can_enter(w, 1, w.height + 5, 1) is False, '世界外不该能进水'


@test('find_source：只认同列（找不到返回 None）')
def t_find_source():
    k = _k()
    w = k.world
    x, z, h = _seabed(k)
    sy = find_source(w, k.fluid.sources, x, h, z)
    assert sy is not None and sy > h, f'同列往上没找到水：{sy}'
    assert find_source(w, k.fluid.sources, 3, 1, 3) is None, \
        '内陆最底下凭空找到了水源'


@test('MAX_FILL 是防呆上限（灌注不会跑飞）')
def t_max_fill_guard():
    k = _k()
    w = k.world
    x, z, h = _seabed(k)
    w.set_generated(x, h, z, B.AIR)
    k.fluid.disturb(w, x, h, z)
    n = k.fluid.step(w)
    assert 0 <= n <= MAX_FILL, f'一次灌了 {n} 格，超过上限 {MAX_FILL}'


if __name__ == '__main__':
    sys.exit(main())
