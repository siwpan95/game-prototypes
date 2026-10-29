# -*- coding: utf-8 -*-
"""DDA 体素拾取（准星）单测（纯逻辑，零 GL）。

跑：`python -m tests.test_raycast`
"""
from __future__ import annotations

import sys

from tests._util import make_suite

from mcclone3d import blocks as B
from mcclone3d.kernel import REACH, make_offline
from mcclone3d.world import ChunkedWorld

test, main = make_suite('ALL_RAYCAST_TESTS_PASSED', 'DDA 拾取')


def _empty_kernel(seed=99, size=48, height=32):
    """把世界清空成空气，再由测试自己摆方块 —— 射线测试要**精确可控**。"""
    k = make_offline({'seed': seed, 'size': size, 'height': height})
    for x in range(size):
        for z in range(size):
            for y in range(height):
                k.world.set(x, y, z, B.AIR)
    k.world.edits.clear()
    k.flying = True
    k.pos = [20.5, 20.0, 20.5]
    k.vel = [0.0, 0.0, 0.0]
    return k


@test('空世界：什么都瞄不到（返回 None，而不是报假命中）')
def t_empty():
    k = _empty_kernel()
    for pitch in (-89.9, -30.0, 0.0, 30.0, 89.9):
        k.pitch = pitch
        assert k.raycast() is None, f'pitch={pitch} 在空世界里报命中'


@test('正下方命中 + 法向朝上')
def t_down():
    k = _empty_kernel()
    # 眼睛在 y=21.62，默认 reach=5 ⇒ 方块顶面最远只能到 y=16.62，所以摆在 y=20
    # （先前摆 y=15 ⇒ 距离 5.62 > 5，"瞄不到"被误读成"射线坏了"）
    k.world.set(20, 20, 20, B.STONE)
    k.pitch, k.yaw = -89.9, 0.0
    hit = k.raycast()
    assert hit is not None, '正下方有方块却没命中'
    pos, n = hit
    assert pos == (20, 20, 20), pos
    assert n == (0, 1, 0), f'法向应为 +y，实际 {n}'
    # 换个更远的距离，reach 放大后应当仍能命中
    k.world.set(20, 15, 20, B.STONE)
    assert k.raycast(9.0) is not None, '放大 reach 后仍够不到'


@test('正上方命中 + 法向朝下')
def t_up():
    k = _empty_kernel()
    k.world.set(20, 25, 20, B.STONE)
    k.pitch = 89.9
    hit = k.raycast()
    assert hit is not None and hit[1] == (0, -1, 0), hit


@test('四个水平方向都命中，且法向是"来路那一面"')
def t_horizontal():
    from mcclone3d.kernel import EYE_HEIGHT
    # 眼睛在 pos[1] + EYE_HEIGHT ⇒ 占据的格子是 floor(pos[1] + EYE_HEIGHT)。
    # 目标方块必须摆在**眼睛那一格**，法向是**指向观察者**的那一面
    # （先前把期望法向写反了：yaw=0 朝 -z 走，进入面在 +z 侧 ⇒ 法向 (0,0,1)）。
    eye_y = 20 + int(EYE_HEIGHT)
    cases = ((0.0, (0, 0, 1), (20, eye_y, 17)),        # yaw=0 → 朝 -z
             (180.0, (0, 0, -1), (20, eye_y, 23)),
             (-90.0, (-1, 0, 0), (23, eye_y, 20)),     # yaw=-90 → 朝 +x
             (90.0, (1, 0, 0), (17, eye_y, 20)))
    for yaw, expect_n, expect_pos in cases:
        k = _empty_kernel()
        x, y, z = expect_pos
        k.world.set(x, y, z, B.STONE)
        k.yaw, k.pitch = yaw, 0.0
        hit = k.raycast()
        assert hit is not None, f'yaw={yaw} 没命中 {expect_pos}（眼睛在 y={20 + EYE_HEIGHT}）'
        assert hit[0] == expect_pos, f'yaw={yaw} 命中 {hit[0]}，期望 {expect_pos}'
        assert hit[1] == expect_n, f'yaw={yaw} 法向 {hit[1]}，期望 {expect_n}'


@test('薄墙不穿：一格厚的墙正对着必须被挡住（DDA 的意义）')
def t_thin_wall():
    k = _empty_kernel()
    wx = 24
    for y in range(18, 24):
        for z in range(18, 24):
            k.world.set(wx, y, z, B.STONE)
    k.yaw, k.pitch = -90.0, 0.0                    # 朝 +x
    hit = k.raycast()
    assert hit is not None, '一格厚的墙没挡住射线（穿过去了）'
    assert hit[0][0] == wx, f'命中在 {hit[0]}，墙在 x={wx}'


@test('reach 生效：够不着就不命中')
def t_reach():
    k = _empty_kernel()
    k.world.set(20, 15, 20, B.STONE)               # 眼睛在 21.62，距离 ≈6.6
    k.pitch = -89.9
    assert k.raycast() is None, 'REACH=5 不该够到 6.6 格外的方块'
    assert k.raycast(10.0) is not None, 'reach 放大后应该够得到'
    assert abs(k.reach - REACH) < 1e-9


@test('命中最近的那个：两堵墙取近的')
def t_nearest():
    k = _empty_kernel()
    for wx in (22, 26):
        for y in range(18, 24):
            for z in range(18, 24):
                k.world.set(wx, y, z, B.STONE)
    k.yaw, k.pitch = -90.0, 0.0
    hit = k.raycast(20.0)
    assert hit[0][0] == 22, f'命中了远处那堵墙：{hit[0]}'


@test('45° 斜射：命中的确实是射线穿过的第一格（不是近似采样）')
def t_diagonal():
    k = _empty_kernel()
    k.yaw, k.pitch = -45.0, 0.0                    # 朝 +x/+z 之间
    k.reach = 20.0
    # 沿方向逐格标记，找第一个被标记的格子
    dx, dy, dz = k.look_dir()
    ox, oy, oz = k.eye_pos()
    expect = None
    for i in range(1, 200):
        t = i * 0.05
        gx, gy, gz = int(ox + dx * t), int(oy + dy * t), int(oz + dz * t)
        if (gx, gy, gz) != (int(ox), int(oy), int(oz)):
            expect = (gx, gy, gz)
            break
    k.world.set(*expect, B.STONE)
    hit = k.raycast(20.0)
    assert hit is not None and hit[0] == expect, f'斜射命中 {hit and hit[0]}，期望 {expect}'


@test('起点在方块内部：立刻命中该方块（不跳过）')
def t_inside_block():
    k = _empty_kernel()
    k.world.set(20, 20, 20, B.STONE)
    k.pos = [20.5, 20.0, 20.5]                     # 眼睛 21.62 恰在 y=20 格内？
    k.pitch = -89.9
    hit = k.raycast()
    assert hit is not None, '起点所在格都没命中'
    assert hit[0] == (20, 20, 20), hit


@test('世界边界处不越界取块（越界一律当空气）')
def t_world_edge():
    k = _empty_kernel()
    k.pos = [0.5, 20.0, 0.5]
    k.yaw, k.pitch = -90.0, 0.0                    # 朝 +x，背后是世界外
    assert k.raycast() is None
    k.yaw = 90.0                                   # 朝 -x（世界外）
    assert k.raycast() is None, '朝世界外不该命中任何东西'
    # 靠边放一块**正好在射线路径上**的方块，仍要能命中
    # （眼睛在 y=21.62 ⇒ 占 y=21 那一格；先前测试摆了 y=20，根本不在路径上）
    k.pos = [0.5, 20.0, 0.5]
    k.yaw, k.pitch = -90.0, 0.0
    k.world.set(2, 21, 0, B.STONE)
    hit = k.raycast()
    assert hit is not None and hit[0] == (2, 21, 0), hit


@test('视线向量与 yaw/pitch 一致（0=朝 -z，抬头 pitch 为正）')
def t_look_dir():
    k = _empty_kernel()
    k.yaw, k.pitch = 0.0, 0.0
    dx, dy, dz = k.look_dir()
    assert abs(dx) < 1e-9 and abs(dy) < 1e-9 and abs(dz + 1.0) < 1e-9, (dx, dy, dz)
    k.pitch = 90.0
    assert abs(k.look_dir()[1] - 1.0) < 1e-9, '抬头时 y 分量应为 +1'
    k.pitch = -90.0
    assert abs(k.look_dir()[1] + 1.0) < 1e-9
    for yaw in (0, 45, 90, 180, -135):
        k.yaw, k.pitch = yaw, 0.0
        v = k.look_dir()
        n = sum(c * c for c in v) ** 0.5
        assert abs(n - 1.0) < 1e-9, f'yaw={yaw} 方向向量不是单位长度：{n}'


@test('射线不依赖世界尺寸：站到地表之上，正下方必定命中')
def t_size_independent():
    from mcclone3d.kernel import EYE_HEIGHT
    for size, height in ((32, 32), (48, 32), (64, 48)):
        k = make_offline({'seed': 5, 'size': size, 'height': height})
        k.flying = True
        # 找一列**地表之上确实空着**的格子（树冠会让地表那一格凭空变高——
        # 先前直接取 size//2 那一列就撞上过树，于是"脚下是泥土"的前提不成立）
        col = None
        for x in range(2, size - 2):
            for z in range(2, size - 2):
                h = k.world.surface_at(x, z)
                if not B.is_solid(k.world.get(x, h + 1, z)) \
                        and not B.is_solid(k.world.get(x, h + 2, z)):
                    col = (x, z, h)
                    break
            if col:
                break
        assert col, '找不到空地列（测试前提不成立）'
        x, z, h = col
        k.pos = [x + 0.5, float(min(h + 3, height - 2)), z + 0.5]
        k.pitch = -89.9
        hit = k.raycast()
        assert hit is not None, f'{size}x{height} 正下方居然没命中（地表 y={h}）'
        assert B.is_solid(k.world.get(*hit[0])), f'命中的 {hit[0]} 不是固体方块'
        assert hit[0][0] == x and hit[0][2] == z, f'命中了斜下方的格子：{hit[0]}'
        # ⚠ 这里**不**断言"命中高度离眼睛不远"：选的列可能带树冠，
        # 射线要穿过若干格空气才碰到东西，距离本身没有上界（实测踩过这条误判）


@test('眼睛恰在格边界上时也不能漏格（-0.0 边界的坑）')
def t_exact_boundary():
    k = _empty_kernel()
    k.pos = [20.0, 20.0, 20.0]                     # 三个坐标都是 .0 ⇒ 正好在格边界
    k.pitch = -89.9
    k.world.set(20, 16, 20, B.STONE)
    hit = k.raycast()
    assert hit is not None and hit[0] == (20, 16, 20), f'边界起步漏格：{hit}'
    # 侧向也一样
    k2 = _empty_kernel()
    k2.pos = [20.0, 20.0, 20.0]
    k2.yaw, k2.pitch = 180.0, 0.0                  # 朝 +z
    k2.world.set(20, 21, 24, B.STONE)
    hit2 = k2.raycast(10.0)
    assert hit2 is not None and hit2[0] == (20, 21, 24), f'侧向边界起步漏格：{hit2}'


if __name__ == '__main__':
    sys.exit(main())
