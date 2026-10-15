# -*- coding: utf-8 -*-
"""Phase 2-C 洞穴生成单测（纯逻辑，零 GL）。

覆盖：三条护栏（基岩 / 表土保底 / 水下地形整列不挖）、挖空比例的**区间**判据
（既防"调阈值调到没洞"也防"挖成海绵"）、worm 洞口的**存在与可达**、
同种子逐格相同、**惰性分块生成与全量一致**（`ensure_chunk` vs `generate`）、
洞内天光为 0（与 Phase 2-A 光照联动）。

跑：`python -m tests.test_caves`
"""
from __future__ import annotations

import sys
from collections import deque

from tests._util import make_suite

from mcclone3d import blocks as B
from mcclone3d import caves
from mcclone3d.world import CHUNK, ChunkedWorld, surface_height

test, main = make_suite('ALL_CAVES_TESTS_PASSED', '洞穴生成')

SEED, SIZE, HEIGHT = 2026, 64, 64


def _world(seed=SEED, size=SIZE, height=HEIGHT) -> ChunkedWorld:
    return ChunkedWorld(seed, size, height).generate()


# ==================================================================== 护栏
@test('护栏：基岩与 y=1 不被挖（洞底不会打通到世界外）')
def t_bedrock_intact():
    for seed, size, height in ((11, 32, 32), (2026, 64, 64)):
        w = _world(seed, size, height)
        for x in range(size):
            for z in range(size):
                assert w.get(x, 0, z) == B.BEDROCK, f'({x},{z}) 基岩被破坏'
                # y=1 允许有矿石（**钻石带的下界就是 y=1** —— MC 同款），
                # 只不许是"空气"或水
                assert w.get(x, 1, z) not in (B.AIR, B.WATER), \
                    f'({x},1,{z}) 是 {B.name_of(w.get(x, 1, z))}，不该出现'


@test('护栏：表土 3 格不被噪声挖穿（洞顶有岩层，不会一挖塌到天）')
def t_soil_kept():
    w = _world()
    holes = caves.tunnels(w.seed, w.size, w.height, w.sea_level).holes
    for x in range(SIZE):
        for z in range(SIZE):
            h = w.surface_at(x, z)
            if h <= w.sea_level + 1:
                continue                      # 水下/岸边地形本就不进候选带
            for dy in range(0, caves.SOIL_KEEP):
                b = w.get(x, h - dy, z)
                if b != B.AIR:
                    continue
                # 允许是 worm 洞口，但必须是**登记在册**的洞口
                assert (x, z) in holes, \
                    f'({x},{h - dy},{z}) 表土里出现空气却不在 worm 洞口清单'


@test('护栏：水下地形整列不挖（洞里不会有水 —— 本项目没有流体系统）')
def t_underwater_column_untouched():
    w = _world()
    for x in range(SIZE):
        for z in range(SIZE):
            h = w.surface_at(x, z)
            if h > w.sea_level + 1:
                continue                      # 陆地列
            for y in range(1, h + 1):
                assert w.get(x, y, z) != B.AIR or y > h, \
                    f'({x},{y},{z}) 水下/岸边地形里被挖空了'


@test('护栏：洞场对越界坐标安全返回（负数 / 超出世界）')
def t_field_bounds_safe():
    f = caves.CaveField(SEED, SIZE, HEIGHT, 30)
    for (x, y, z) in ((-1, 10, 10), (SIZE + 5, 10, 10), (10, -3, 10),
                      (10, HEIGHT + 5, 10), (10, 10, -7), (10, 10, SIZE + 2)):
        assert f.density(x, y, z) == 0.0, f'({x},{y},{z}) 场外应返回 0'
        assert f.is_cave(x, y, z, 40) is False, f'({x},{y},{z}) 场外不该是洞'


# ==================================================================== 体量
@test('挖空比例落在合理区间（防"调阈值调到没洞"与"挖成海绵"）')
def t_cave_ratio_sane():
    w = _world(2026, 96, 64)
    tot = cav = 0
    for x in range(0, 96, 2):
        for z in range(0, 96, 2):
            h = w.surface_at(x, z)
            if h <= w.sea_level + 1:
                continue
            for y in range(2, min(h - caves.SOIL_KEEP, w.sea_level)):
                tot += 1
                if w.get(x, y, z) == B.AIR:
                    cav += 1
    assert tot > 0, '候选带是空的（sea_level 或地表算错了）'
    ratio = cav / tot
    assert 0.03 <= ratio <= 0.25, \
        f'挖空比例 {ratio * 100:.1f}% 不在 3~25%（阈值 0.74 实测约 10%）'


@test('阈值随深度递减 ⇒ 越深洞穴越密（探针实测深度分布）')
def t_threshold_deeper_denser():
    """`cave_threshold(y, sea) = 基础 + 0.02×(sea-y)/sea`：
    y 越小（越深）项越大 ⇒ **阈值越低越容易挖**。"""
    sea = 30
    deep, shallow = caves.cave_threshold(2, sea), caves.cave_threshold(sea, sea)
    assert deep < shallow, f'深处阈值 {deep} ≥ 浅处 {shallow}（那还怎么"越深越密"）'
    # 每一层都不比浅层更高（单调）
    last = deep
    for y in range(2, sea):
        cur = caves.cave_threshold(y, sea)
        assert cur >= last - 1e-9, f'y={y} 的阈值反而比更深处的低'
        last = cur


# ==================================================================== worm 洞口
@test('worm 洞口存在且登记在册（地表那一格真的是空气）')
def t_worm_holes_exist():
    idx = caves.tunnels(SEED, SIZE, HEIGHT, 30)
    assert idx.holes, '一条 worm 都没长出来（WORMS_PER_CELL / 游走逻辑坏了？）'
    checked = 0
    w = _world()
    for (x, z), h in list(idx.holes.items()):
        if w.get(x, h, z) != B.AIR:
            continue                      # 洞口被别的地形规则盖住（正常现象）
        checked += 1
        assert w.get(x, h - 1, z) == B.AIR, f'({x},{h},{z}) 洞口下面还是石头'
    assert checked > 0, '登记的洞口一个都不通（地表没被挖穿？）'


@test('从洞口往下能走进洞穴（洪水填充，不灌进天空）')
def t_hole_reaches_cave():
    w = _world()
    holes = caves.tunnels(SEED, SIZE, HEIGHT, 30).holes
    reach = 0
    h_cache: dict = {}

    def _h(x, z):
        if (x, z) not in h_cache:
            h_cache[(x, z)] = w.surface_at(x, z)
        return h_cache[(x, z)]

    for (x, z), _hh in list(holes.items())[:40]:
        h = w.surface_at(x, z)
        start = (x, h - 2, z)
        while start[1] > 1 and w.get(*start) != B.AIR:
            start = (start[0], start[1] - 1, start[2])
        if w.get(*start) != B.AIR:
            continue
        seen = {start}
        q = deque([start])
        deepest = start[1]
        while q:
            cx, cy, cz = q.popleft()
            deepest = min(deepest, cy)
            for d in ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0),
                      (0, 0, 1), (0, 0, -1)):
                n = (cx + d[0], cy + d[1], cz + d[2])
                if n in seen or not (0 <= n[0] < SIZE and 1 < n[1] and 0 <= n[2] < SIZE):
                    continue
                # ⚠ 挡天空用**该列自己的地表高度**，不是海平面：洞口在 y≈34 而
                #   海平面只有 30，用 sea 会把洞口那几层一起挡掉 ⇒ 明明连通的
                #   隧道被判成"不可达"（实测踩过）。
                if n[1] > _h(n[0], n[2]):
                    continue
                if w.get(*n) == B.AIR:
                    seen.add(n)
                    q.append(n)
        if len(seen) > 40:
            reach += 1
            assert deepest < h - caves.SOIL_KEEP, \
                f'({x},{z}) 的洞只通到土层里就停了（没接到洞穴层？）'
    assert reach > 0, '所有洞口都接不到大洞穴（洞与洞之间没连通？）'


# ==================================================================== 确定性
@test('确定性：同种子两次生成洞穴逐格相同；换种子会变')
def t_deterministic():
    a, b = _world(2026, 48, 64), _world(2026, 48, 64)
    c = _world(2027, 48, 64)
    diff_ab = diff_ac = 0
    for x in range(0, 48, 2):
        for z in range(0, 48, 2):
            h = a.surface_at(x, z)
            for y in range(2, min(h - caves.SOIL_KEEP, a.sea_level), 2):
                got, want, other = a.get(x, y, z), b.get(x, y, z), c.get(x, y, z)
                diff_ab += (got != want)
                diff_ac += (got != other)
    assert diff_ab == 0, f'同种子两次生成有 {diff_ab} 格不同'
    assert diff_ac > 0, '换种子后世界一模一样（噪声没起作用？）'


@test('惰性一致：ensure_chunk 单块 == generate 全量（worm 索引必须与顺序无关）')
def t_lazy_chunk_matches_full():
    """`worm` 是全局后处理，若按"生成到哪算到哪"就会不一致 —— 这条钉住它。"""
    full = _world(2026, 48, 64)
    lazy = ChunkedWorld(2026, 48, 64)          # 不调 generate()
    checked = 0
    for cx in range(0, 48 // CHUNK):
        for cy in range(0, 64 // CHUNK):
            for cz in range(0, 48 // CHUNK):
                lazy.ensure_chunk(cx, cy, cz)
                a = bytes(full.chunks[(cx, cy, cz)])
                b = bytes(lazy.chunks[(cx, cy, cz)])
                assert a == b, f'区块 ({cx},{cy},{cz}) 惰性生成与全量不一致'
                checked += 1
    assert checked == (48 // CHUNK) ** 2 * (64 // CHUNK)


# ==================================================================== 与光照联动
@test('洞内天光为 0（洞里是黑的 —— Phase 2-A 的列传播遇不透明即停）')
def t_cave_is_dark():
    w = _world(2026, 48, 64)
    from mcclone3d.light import LightEngine
    le = LightEngine(w)
    le.column_pass_all()
    dark = lit = 0
    for x in range(0, 48, 3):
        for z in range(0, 48, 3):
            h = w.surface_at(x, z)
            if h <= w.sea_level + 1:
                continue
            for y in range(2, min(h - caves.SOIL_KEEP, w.sea_level), 3):
                if w.get(x, y, z) != B.AIR:
                    continue
                if le.sky(x, y, z) == 0:
                    dark += 1
                else:
                    lit += 1
    assert dark > 0, '洞里一处天光都没有？（那洞其实是实心石头）'
    # 洞里**允许**有天光（worm 洞口附近会漏光进去，那是正确的），
    # 但绝大多数洞内格必须是黑的
    assert dark > lit, f'洞内亮格 {lit} 多于黑格 {dark}（洞不够深/漏光太多）'


if __name__ == '__main__':
    sys.exit(main())
