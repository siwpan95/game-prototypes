# -*- coding: utf-8 -*-
"""玩家物理与碰撞单测（纯逻辑，零 GL）。

跑：`python -m tests.test_physics`
"""
from __future__ import annotations

import sys

from tests._util import make_suite

from mcclone3d import blocks as B
from mcclone3d.kernel import (GRAVITY, JUMP_V, PLAYER_HALF, PLAYER_HEIGHT,
                              WALK_SPEED, make_offline)

test, main = make_suite('ALL_PHYSICS_TESTS_PASSED', '玩家物理')

DT = 1.0 / 60.0


def _flat_world(seed=4242, size=48, height=32):
    """造一块**平台世界**：y=8 一整层石头，其余挖空 —— 物理测试要可控的地面。

    用真实生成的地形做物理测试会让断言依赖种子（"这块恰好不平"就红），
    所以测试自己铺地：**被测的是物理，不是地形**。
    """
    k = make_offline({'seed': seed, 'size': size, 'height': height, 'creative': True})
    for x in range(size):
        for z in range(size):
            for y in range(height):
                k.world.set(x, y, z, B.STONE if y == 8 else B.AIR)
    k.flying = True
    k.pos = [size / 2, 9.0, size / 2]
    k.vel = [0.0, 0.0, 0.0]
    k.step(DT)
    k.flying = False
    k.step(DT)
    # 开局就站在地面上（`grounded` 的判据是"脚下 0.05 格内有固体"）——
    # 不补这一步的话，第一次 `step(..., jump=True)` 会因为没有 grounded 而不起跳，
    # 于是"跳跃"测试测的其实是"原地不动"（实测跳高 0.000 就是这么来的）。
    assert k.grounded, '测试前提：平台世界上应立刻站稳'
    return k


@test('重力：悬空会下落，并停在地面上（不穿地）')
def t_gravity():
    k = _flat_world()
    k.pos[1] = 20.0
    k.grounded = False
    k.vel = [0.0, 0.0, 0.0]
    k.step(DT)
    for _ in range(int(6 * 60)):
        k.step(DT)
        if k.grounded and abs(k.pos[1] - 9.0) < 1e-6:
            break
    assert k.grounded, '6 秒都没落地'
    assert abs(k.pos[1] - 9.0) < 1e-6, f'停在了 {k.pos[1]}，期望地面 9.0'
    assert k.vel[1] == 0.0, f'落地后竖直速度未清零：{k.vel[1]}'
    below = k.world.get(int(k.pos[0]), 8, int(k.pos[2]))
    assert B.is_solid(below), '脚下不是固体'


@test('跳跃高度：起跳能离地，且峰值在 0.9~1.6 格之间（约 1.25 格）')
def t_jump():
    k = _flat_world()
    y0 = k.pos[1]
    k.step(DT, (0.0, 0.0), jump=True)
    peak = y0
    for _ in range(int(3 * 60)):
        k.step(DT)
        peak = max(peak, k.pos[1])
        if k.grounded and k.pos[1] <= y0 + 1e-6:
            break
    h = peak - y0
    assert 0.9 < h < 1.6, f'跳高 {h:.3f} 不在合理区间'
    assert abs(k.pos[1] - y0) < 0.02, f'没落回原高度：{k.pos[1]} vs {y0}'
    # 与解析解对拍：h = v²/(2g)
    analytic = JUMP_V ** 2 / (2 * GRAVITY)
    assert abs(h - analytic) < 0.35, f'跳高 {h:.3f} 与解析解 {analytic:.3f} 差太多'


@test('空中不能二段跳')
def t_no_double_jump():
    k = _flat_world()
    k.step(DT, (0.0, 0.0), jump=True)
    for _ in range(20):
        k.step(DT)
        k.step(DT, (0.0, 0.0), jump=True)          # 空中一直按跳
    assert k.pos[1] > 9.0, '应该在空中'
    peak = k.pos[1]
    for _ in range(int(3 * 60)):
        k.step(DT, (0.0, 0.0), jump=True)
        peak = max(peak, k.pos[1])
        if k.grounded and k.pos[1] <= 9.02:
            break
    assert peak < 9.0 + 1.6, f'空中按跳把自己顶上去了：峰值 {peak:.3f}'


@test('撞墙：正面走向墙不会穿进去（分轴求解）')
def t_wall_no_clip():
    k = _flat_world()
    x = int(k.pos[0]) + 3
    # 墙要**够高够长**：先前只铺 3 高、z 方向 ±3，玩家 14 格的路程直接从墙端绕过去了，
    # 于是断言"没穿墙"在"绕过去"的情况下也会红（测试自己没描述清楚想验什么）。
    for y in (9, 10, 11, 12):
        for z in range(0, k.size):
            k.world.set(x, y, z, B.STONE)
    for _ in range(int(5 * 60)):
        k.step(DT, (1.0, 0.0))
    assert not k._blocked(*k.pos), f'卡进方块里了：{k.pos}'
    assert k.pos[0] < x - PLAYER_HALF + 1e-6, \
        f'穿墙了：x={k.pos[0]:.3f} 墙在 {x}'


@test('贴墙滑行：斜着撞墙时，切向仍能移动')
def t_slide():
    k = _flat_world()
    x = int(k.pos[0]) + 3
    for y in (9, 10, 11, 12):
        for z in range(0, k.size):
            k.world.set(x, y, z, B.STONE)
    z0 = k.pos[2]
    for _ in range(int(2 * 60)):
        k.step(DT, (1.0, 1.0))                     # 斜向撞墙：法向被挡，切向该继续走
    assert abs(k.pos[2] - z0) > 0.5, f'切向没动（被墙粘住了）：Δz={k.pos[2] - z0:.3f}'
    assert k.pos[0] < x - PLAYER_HALF + 1e-6, \
        f'沿墙滑行时穿墙了：x={k.pos[0]:.3f}（上限 {x - PLAYER_HALF:.2f}）'
    assert not k._blocked(*k.pos), '滑行时卡进了方块'


@test('天花板：往上撞不会穿过')
def t_ceiling():
    k2 = _flat_world()
    for xx in range(int(k2.pos[0]) - 2, int(k2.pos[0]) + 3):
        for zz in range(int(k2.pos[2]) - 2, int(k2.pos[2]) + 3):
            k2.world.set(xx, 11, zz, B.STONE)
    k2.step(DT, (0.0, 0.0), jump=True)
    top = k2.pos[1]
    for _ in range(int(2 * 60)):
        k2.step(DT, (0.0, 0.0), jump=True)
        top = max(top, k2.pos[1])
    assert top < 11.0, f'顶穿了天花板：峰值 {top:.3f}（天花板在 y=11）'
    assert not k2._blocked(*k2.pos), '卡进天花板里了'


@test('落地判定：站在地上时 grounded=True，走出边缘会掉下去')
def t_grounded():
    k = _flat_world(size=32)
    for _ in range(60):
        k.step(DT)
    assert k.grounded, '站在地面上却是 grounded=False'
    # 把脚下一圈挖空 ⇒ 应该掉下去
    px, pz = int(k.pos[0]), int(k.pos[2])
    for dx in (-2, -1, 0, 1, 2):
        for dz in (-2, -1, 0, 1, 2):
            k.world.set(px + dx, 8, pz + dz, B.AIR)
    k.step(DT)
    for _ in range(30):
        k.step(DT)
    assert not k.grounded or k.pos[1] < 9.0, '脚下挖空了却还站在原处'


@test('卡帧保护：单帧 dt 再大也不会瞬移穿墙')
def t_dt_clamp():
    k = _flat_world()
    x = int(k.pos[0]) + 3
    for y in (9, 10, 11):
        for z in range(int(k.pos[2]) - 3, int(k.pos[2]) + 4):
            k.world.set(x, y, z, B.STONE)
    k.step(5.0, (1.0, 0.0))                        # 5 秒的"一帧"
    assert not k._blocked(*k.pos), f'大 dt 把自己扔进墙里：{k.pos}'
    assert k.pos[0] < x - PLAYER_HALF + 1e-6, f'大 dt 穿墙：x={k.pos[0]}'


@test('世界边界：不会走出世界外（也不会掉出世界底）')
def t_bounds():
    k = _flat_world(size=32)
    for _ in range(int(6 * 60)):
        k.step(DT, (1.0, 0.0))
    assert PLAYER_HALF - 1e-6 <= k.pos[0] <= k.size - PLAYER_HALF + 1e-6, \
        f'走出了世界：x={k.pos[0]}'
    k.pos[1] = -5.0
    k.step(DT)
    assert k.pos[1] > 0.0, f'掉出世界底后没有被送回：y={k.pos[1]}'


@test('速度上限：水平速度不超过设定行走速度')
def t_speed():
    k = _flat_world()
    for _ in range(60):
        k.step(DT, (1.0, 0.0))
        assert abs(k.vel[0]) <= WALK_SPEED + 1e-6, f'水平超速：{k.vel[0]}'
        assert k.vel[1] <= JUMP_V + 1e-6, f'竖直超速：{k.vel[1]}'


@test('玩家 AABB 尺寸：比一格窄、比两格矮（否则过不了一格宽的缝）')
def t_aabb():
    assert 0.0 < PLAYER_HALF < 0.5, f'半宽 {PLAYER_HALF} 会让玩家进不了一格通道'
    assert 1.0 < PLAYER_HEIGHT < 2.0, PLAYER_HEIGHT
    k = _flat_world()
    x0, x1, y0, y1, z0, z1 = k._player_boxes(k.pos[0], k.pos[1], k.pos[2])
    assert x1 - x0 <= 1, f'AABB 横向跨了 {x1 - x0 + 1} 格'


if __name__ == '__main__':
    sys.exit(main())
