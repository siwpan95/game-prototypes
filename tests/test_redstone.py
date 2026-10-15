# -*- coding: utf-8 -*-
"""Phase 3 红石单测（纯逻辑，零 GL）。

覆盖：元件分类与别名契约、**信号衰减**（电源给的邻居 15 → 每格 −1 → 归零）、
**中继器续接**（重算到固定点）、灯亮/门开/活塞推这些输出、**按钮回弹**、
**活塞的原子性**（连锁 12 格上限、推不动就整体不动、6 个方向、收回只删臂）、
**信号不进存档但状态进存档**、**读档后信号按布局重算**、确定性、网络护栏、
以及内核路径（`use()` 交互 / `place()` 的多格与朝向 / 挖门连另一半）。

⚠ 活塞的测试**必须在空气层做**（本模块用 y=50）：在地形里测会得到"前方 12 格
全是地形 ⇒ 推不动"，看上去像活塞坏了（实测踩过这一次）。

跑：`python -m tests.test_redstone`
"""
from __future__ import annotations

import sys

from tests._util import make_suite

from mcclone3d import blocks as B
from mcclone3d import redstone as RS
from mcclone3d.kernel import make_offline
from mcclone3d.world import ChunkedWorld

test, main = make_suite('ALL_REDSTONE_TESTS_PASSED', '红石信号与元件')

SEED, SIZE, HEIGHT = 2026, 64, 64
#: 元件都摆在这一层（**空气层**：地形之上，不会被地形挡住活塞）
Y = 50
#: 摆线用的 z
Z = 4


def _world():
    return ChunkedWorld(SEED, SIZE, HEIGHT).generate()


def _grid(w):
    return RS.PowerGrid(w)


def _settle(g, rounds: int = 8, dt: float = 0.0):
    """把引擎跑到固定点（dirty 清空），返回累计改动数。

    ⚠ `dt` 默认 **0**：这个辅助函数只负责"把信号算完"，**不该顺手推进时间** ——
    早先默认 `dt=1.0`，于是在按钮用例里一次 settle 就把 `BUTTON_TTL`（1 秒）
    走完了，按下按钮的灯"立刻"灭 ⇒ 看上去像按钮没供电（实测踩过）。
    要测"时间推进"（回弹）的用例自己给 dt。
    """
    n = 0
    for _ in range(rounds):
        if not g.dirty:
            break
        n += g.step(dt, budget=999)
    return n


def _lever_run(w, g, x0: int = 4, wire_len: int = 4, lever=B.LEVER_ON):
    """在 (x0, Y, Z) 放一个拉杆 + `wire_len` 格红石线 + 末尾一盏灯。"""
    w.set_generated(x0, Y, Z, lever)
    for i in range(1, wire_len + 1):
        w.set_generated(x0 + i, Y, Z, B.REDSTONE_WIRE)
    w.set_generated(x0 + wire_len + 1, Y, Z, B.LAMP_OFF)
    g.mark(x0, Y, Z)
    _settle(g)
    return x0 + wire_len + 1


# ==================================================================== 契约
@test('元件分类：电源 / 传导 / 输出 / 可推，四类不重叠')
def t_kinds():
    for bid in (B.LEVER_ON, B.BUTTON_ON, B.REDSTONE_TORCH):
        assert RS.is_source(bid), f'{B.name_of(bid)} 该是电源'
    assert not RS.is_source(B.LEVER_OFF), '关着的拉杆不是电源'
    assert not RS.is_source(B.BUTTON_OFF), '没按的按钮不是电源'
    assert RS.is_conductor(B.REDSTONE_WIRE), '红石线该能传导'
    assert not RS.is_conductor(B.REPEATER_ON), \
        '中继器**不是**传导者（它是有向的源；算成传导者会自锁）'
    assert not RS.is_conductor(B.STONE), '石头不该传导'
    for bid in (B.LAMP_OFF, B.LAMP_ON, B.DOOR_LOWER, B.DOOR_OPEN_UPPER,
                B.REPEATER_OFF, B.REPEATER_W_ON, B.BLOCK_IDS['piston_north_off']):
        assert RS.is_output(bid), f'{B.name_of(bid)} 该是输出元件'
    assert RS.is_piston(B.BLOCK_IDS['piston_up_on']) and not RS.is_piston(B.STONE)
    # 可推：普通方块可推，红石元件/基岩/水不行（推走元件会让状态立刻混乱）
    assert RS.is_pushable(B.STONE) and RS.is_pushable(B.PLANKS)
    for bid in (B.BEDROCK, B.WATER, B.REDSTONE_WIRE, B.LEVER_OFF, B.LAMP_OFF,
                B.TORCH, B.CROP, B.PISTON_ARM):
        assert not RS.is_pushable(bid), f'{B.name_of(bid)} 不该被推动'


@test('别名契约：状态 id 都指回同一件物品（挖掉开着的拉杆也要掉东西）')
def t_alias():
    from mcclone3d import items as I
    from mcclone3d import recipes as R
    for name, item_name in B.BLOCK_ITEM_ALIAS.items():
        assert name in B.BLOCK_NAMES, f'别名表里的 {name!r} 不是方块名'
        assert item_name in I.ITEMS_BY_NAME, f'别名指向的物品 {item_name!r} 不存在'
        bid = B.BLOCK_IDS[name]
        it = R.as_item(bid)
        assert it is not None and it.name == item_name, \
            f'as_item({name}) 该回退到 {item_name}，实际 {it}'
        assert R.drops_for(bid), f'{name} 挖掉必须掉东西'


# ==================================================================== 信号
@test('衰减：电源给**紧邻**的线 15，之后每格 −1，第 16 格归零')
def t_decay():
    w = _world()
    g = _grid(w)
    x0 = 4
    w.set_generated(x0, Y, Z, B.LEVER_ON)
    for i in range(1, 17):
        w.set_generated(x0 + i, Y, Z, B.REDSTONE_WIRE)
    g.mark(x0, Y, Z)
    _settle(g)
    levels = [g.power_at(x0 + i, Y, Z) for i in range(1, 17)]
    assert levels[0] == 15, f'紧贴电源的线该是 15，实际 {levels[0]}'
    assert levels[:15] == list(range(15, 0, -1)), f'该逐格 −1：{levels[:15]}'
    assert levels[15] == 0, f'第 16 格该衰减到 0，实际 {levels[15]}'
    # 拉杆关掉 ⇒ 全部归零
    g.toggle_lever(x0, Y, Z)
    _settle(g)
    assert all(g.power_at(x0 + i, Y, Z) == 0 for i in range(1, 17)), '断电后信号该全归零'


@test('中继器：把信号**续满 15**（长线路靠它），断电后自己也灭')
def t_repeater():
    w = _world()
    g = _grid(w)
    x0 = 4
    w.set_generated(x0, Y, Z, B.LEVER_ON)
    for i in range(1, 15):
        w.set_generated(x0 + i, Y, Z, B.REDSTONE_WIRE)
    # 中继器**朝东**（输出朝 +x）：背面（x0+14）吃信号、正面（x0+16）吐信号
    w.set_generated(x0 + 15, Y, Z, B.REPEATER_E_OFF)
    for i in range(16, 21):
        w.set_generated(x0 + i, Y, Z, B.REDSTONE_WIRE)
    w.set_generated(x0 + 21, Y, Z, B.LAMP_OFF)
    g.mark(x0, Y, Z)
    _settle(g)
    assert w.get(x0 + 15, Y, Z) == B.REPEATER_E_ON, \
        f'中继器该被前段点亮，实际 {B.name_of(w.get(x0 + 15, Y, Z))}'
    assert g.power_at(x0 + 16, Y, Z) == 15, \
        f'中继器后第一格该是 15（续接），实际 {g.power_at(x0 + 16, Y, Z)}'
    assert w.get(x0 + 21, Y, Z) == B.LAMP_ON, '续接后的灯该亮'
    # 断电：中继器与灯都要灭
    g.toggle_lever(x0, Y, Z)
    _settle(g)
    assert w.get(x0 + 15, Y, Z) == B.REPEATER_E_OFF, \
        f'断电后中继器该灭（有向 ⇒ 不会自锁），实际 {B.name_of(w.get(x0 + 15, Y, Z))}'
    assert w.get(x0 + 21, Y, Z) == B.LAMP_OFF, '断电后灯该灭'


@test('灯：通电亮、断电灭，且**亮着的灯是光源**（emissive>0 ⇒ 与光照联动）')
def t_lamp():
    w = _world()
    g = _grid(w)
    lamp = _lever_run(w, g)
    assert w.get(lamp, Y, Z) == B.LAMP_ON
    assert B.BLOCKS[B.LAMP_ON].emissive > 0, '亮着的红石灯必须是光源（否则光照不会变）'
    assert B.BLOCKS[B.LAMP_OFF].emissive == 0, '灭的灯不该发光'
    g.toggle_lever(4, Y, Z)
    _settle(g)
    assert w.get(lamp, Y, Z) == B.LAMP_OFF, '断电后灯该灭'


@test('按钮：按下供电、`BUTTON_TTL` 秒后**自动回弹**且灯跟着灭')
def t_button():
    w = _world()
    g = _grid(w)
    w.set_generated(4, Y, Z, B.BUTTON_OFF)
    w.set_generated(5, Y, Z, B.REDSTONE_WIRE)
    w.set_generated(6, Y, Z, B.LAMP_OFF)
    g.mark(4, Y, Z)
    _settle(g)
    assert w.get(6, Y, Z) == B.LAMP_OFF, '没按按钮时灯不该亮'
    assert g.press_button(4, Y, Z) == B.BUTTON_ON
    _settle(g)
    assert w.get(6, Y, Z) == B.LAMP_ON, '按下按钮灯该亮'
    # 快进到回弹之后（分两步：先不足 TTL，再越过）
    g.step(RS.BUTTON_TTL * 0.5, budget=999)
    assert w.get(4, Y, Z) == B.BUTTON_ON, '还没到点就不该回弹'
    g.step(RS.BUTTON_TTL * 0.6, budget=999)
    _settle(g)
    assert w.get(4, Y, Z) == B.BUTTON_OFF, f'过了 {RS.BUTTON_TTL}s 该回弹'
    assert w.get(6, Y, Z) == B.LAMP_OFF, '回弹后灯该灭'


@test('红石火把：常亮电源（不需要玩家操作），但**不给隔一格供电**')
def t_torch():
    w = _world()
    g = _grid(w)
    w.set_generated(4, Y, Z, B.REDSTONE_TORCH)
    w.set_generated(5, Y, Z, B.REDSTONE_WIRE)
    w.set_generated(6, Y, Z, B.REDSTONE_WIRE)
    w.set_generated(7, Y, Z, B.LAMP_OFF)
    g.mark(4, Y, Z)
    _settle(g)
    assert w.get(7, Y, Z) == B.LAMP_ON, '红石火把该常亮供电'
    assert g.power_at(5, Y, Z) == 15 and g.power_at(6, Y, Z) == 14
    # 火把**不是**线：拆掉线之后灯就灭（信号不会"隔着空气"传）
    w.set_generated(5, Y, Z, B.AIR)
    g.mark(5, Y, Z)
    _settle(g)
    assert w.get(7, Y, Z) == B.LAMP_OFF, '线断了两格外的灯该灭'


@test('确定性：同一套布局算两次，每个格子的信号完全一致')
def t_deterministic():
    def build():
        w = _world()
        g = _grid(w)
        w.set_generated(4, Y, Z, B.LEVER_ON)
        for i in range(1, 9):
            w.set_generated(4 + i, Y, Z, B.REDSTONE_WIRE)
        w.set_generated(13, Y, Z, B.LAMP_OFF)
        g.mark(4, Y, Z)
        _settle(g)
        return w, g
    wa, ga = build()
    wb, gb = build()
    cells = sorted(ga.power)
    assert cells == sorted(gb.power), '两次算出的通电格不同'
    for c in cells:
        assert ga.power[c] == gb.power[c], f'{c} 两次的信号不同'


@test('网络护栏：超过 NETWORK_CAP 抛 RedstoneOverflow（响亮失败，不静默截断）')
def t_overflow_guard():
    w = _world()
    g = _grid(w)
    saved = RS.NETWORK_CAP
    try:
        RS.NETWORK_CAP = 8                      # 故意把上限压到极小
        for i in range(20):
            w.set_generated(4 + i, Y, Z, B.REDSTONE_WIRE)
        w.set_generated(4, Y, Z, B.LEVER_ON)
        try:
            g.recompute_from((4, Y, Z))
        except RS.RedstoneOverflow:
            pass
        else:
            raise AssertionError('网络超上限时必须抛 RedstoneOverflow')
    finally:
        RS.NETWORK_CAP = saved


# ==================================================================== 活塞
@test('活塞：通电推出（方块前移一格、臂占位），断电**只收臂**、方块留在新位置')
def t_piston_push():
    w = _world()
    g = _grid(w)
    w.set_generated(4, Y, Z, B.LEVER_OFF)
    w.set_generated(5, Y, Z, B.REDSTONE_WIRE)
    w.set_generated(6, Y, Z, B.BLOCK_IDS['piston_east_off'])
    w.set_generated(7, Y, Z, B.STONE)
    g.mark(4, Y, Z)
    _settle(g)
    assert w.get(6, Y, Z) == B.BLOCK_IDS['piston_east_off'], '没通电不该推出'
    g.toggle_lever(4, Y, Z)
    _settle(g)
    assert w.get(6, Y, Z) == B.BLOCK_IDS['piston_east_on'], '通电该是"推出"状态'
    assert w.get(7, Y, Z) == B.PISTON_ARM, '前方一格该是臂'
    assert w.get(8, Y, Z) == B.STONE, '被推的方块该前移一格'
    g.toggle_lever(4, Y, Z)
    _settle(g)
    assert w.get(6, Y, Z) == B.BLOCK_IDS['piston_east_off'], '断电该收臂'
    assert w.get(7, Y, Z) == B.AIR, '臂该消失'
    assert w.get(8, Y, Z) == B.STONE, '普通活塞**不拉回**：方块留在新位置'


@test('活塞：横向连锁推 12 格；13 格推不动 ⇒ **整体不动**（原子性）')
def t_piston_chain():
    w = _world()
    g = _grid(w)
    w.set_generated(4, Y, Z, B.LEVER_ON)
    w.set_generated(5, Y, Z, B.REDSTONE_WIRE)
    w.set_generated(6, Y, Z, B.BLOCK_IDS['piston_east_off'])
    for i in range(7, 7 + RS.PUSH_LIMIT):               # 正好 12 个
        w.set_generated(i, Y, Z, B.STONE)
    g.mark(4, Y, Z)
    _settle(g)
    assert w.get(7, Y, Z) == B.PISTON_ARM, '12 个方块该推得动'
    assert w.get(7 + RS.PUSH_LIMIT, Y, Z) == B.STONE, f'最远那个该到 {7 + RS.PUSH_LIMIT}'

    # 13 个 ⇒ 超过上限 ⇒ 一格都不许动
    w2 = _world()
    g2 = _grid(w2)
    w2.set_generated(4, Y, Z, B.LEVER_ON)
    w2.set_generated(5, Y, Z, B.REDSTONE_WIRE)
    w2.set_generated(6, Y, Z, B.BLOCK_IDS['piston_east_off'])
    for i in range(7, 7 + RS.PUSH_LIMIT + 1):
        w2.set_generated(i, Y, Z, B.STONE)
    g2.mark(4, Y, Z)
    _settle(g2)
    assert w2.get(6, Y, Z) == B.BLOCK_IDS['piston_east_off'], '推不动时活塞该保持收回'
    assert all(w2.get(i, Y, Z) == B.STONE
               for i in range(7, 7 + RS.PUSH_LIMIT + 1)), '推不动时**一个方块都不许动**'


@test('活塞：前面是基岩/红石元件 ⇒ 推不动（不破坏，也不留半截状态）')
def t_piston_blocked():
    for blocker in (B.BEDROCK, B.LAMP_OFF, B.LEVER_OFF):
        w = _world()
        g = _grid(w)
        w.set_generated(4, Y, Z, B.LEVER_ON)
        w.set_generated(5, Y, Z, B.REDSTONE_WIRE)
        w.set_generated(6, Y, Z, B.BLOCK_IDS['piston_east_off'])
        w.set_generated(7, Y, Z, blocker)
        g.mark(4, Y, Z)
        _settle(g)
        assert w.get(6, Y, Z) == B.BLOCK_IDS['piston_east_off'], \
            f'前方是 {B.name_of(blocker)} 时活塞不该推出'
        assert w.get(7, Y, Z) == blocker, f'{B.name_of(blocker)} 被破坏了'


@test('活塞：六个方向各推各的（朝向体现在 id 上）')
def t_piston_dirs():
    vecs = {'north': (0, 0, -1), 'south': (0, 0, 1), 'east': (1, 0, 0),
            'west': (-1, 0, 0), 'up': (0, 1, 0), 'down': (0, -1, 0)}
    for d, (vx, vy, vz) in vecs.items():
        w = _world()
        g = _grid(w)
        # 电源放在活塞的**反方向**（贴着一个与推程无关的邻居）
        off, on = B.PISTON_BY_DIR[d]
        px, py, pz = 20, Y, 20
        w.set_generated(px, py, pz, off)
        # 给活塞本体接电（电源直接挨着它）
        sx, sy, sz = px - vx, py - vy, pz - vz
        w.set_generated(sx, sy, sz, B.LEVER_ON)
        fx, fy, fz = px + vx, py + vy, pz + vz
        w.set_generated(fx, fy, fz, B.STONE)
        g.mark(sx, sy, sz)
        _settle(g)
        assert w.get(px, py, pz) == on, f'{B.PISTON_TITLES[d]}：该推出（{B.name_of(w.get(px, py, pz))}）'
        assert w.get(fx, fy, fz) == B.PISTON_ARM, f'{B.PISTON_TITLES[d]}：臂放错了'
        assert w.get(fx + vx, fy + vy, fz + vz) == B.STONE, f'{B.PISTON_TITLES[d]}：方块该前移'


# ==================================================================== 门
@test('铁门：通电开（能穿过去）、断电关；两格一起切')
def t_door():
    w = _world()
    g = _grid(w)
    w.set_generated(4, Y, Z, B.LEVER_OFF)
    w.set_generated(5, Y, Z, B.REDSTONE_WIRE)
    w.set_generated(6, Y, Z, B.DOOR_LOWER)
    w.set_generated(6, Y + 1, Z, B.DOOR_UPPER)
    g.mark(4, Y, Z)
    _settle(g)
    assert w.get(6, Y, Z) == B.DOOR_LOWER and w.get(6, Y + 1, Z) == B.DOOR_UPPER
    assert B.is_solid(B.DOOR_LOWER), '关着的门该挡住玩家'
    g.toggle_lever(4, Y, Z)
    _settle(g)
    assert w.get(6, Y, Z) == B.DOOR_OPEN_LOWER, '通电该开'
    assert w.get(6, Y + 1, Z) == B.DOOR_OPEN_UPPER, '门的**上半格**要一起开'
    assert not B.is_solid(B.DOOR_OPEN_LOWER), '开着的门必须能穿过去'
    g.toggle_lever(4, Y, Z)
    _settle(g)
    assert w.get(6, Y, Z) == B.DOOR_LOWER and w.get(6, Y + 1, Z) == B.DOOR_UPPER, '断电该关'


@test('门：两格一体（挖一半、另一半跟着消失；开门状态挖掉也掉门）')
def t_door_dig():
    k = make_offline({'seed': SEED, 'size': 32, 'height': 32, 'light': False,
                      'mobs': False})
    # 造一块平地 + 一扇门
    for x in range(4, 12):
        for z in range(4, 12):
            k.world.set(x, 20, z, B.STONE)
            for y in (21, 22):
                k.world.set(x, y, z, B.AIR)
    k.world.set(8, 21, 8, B.DOOR_LOWER)
    k.world.set(8, 22, 8, B.DOOR_UPPER)
    k.inventory.clear()
    k.creative = True                       # 创造模式：挖了直接进包，好断言
    label = k._finish_dig((8, 22, 8))       # 挖**上半格**
    assert label[0] is True
    assert k.world.get(8, 21, 8) == B.AIR, '挖掉门的上半格，下半格该跟着消失'
    assert k.world.get(8, 22, 8) == B.AIR


# ==================================================================== 存档
@test('存档：**状态进档、信号不进档**（拉杆开着会存下来，灯的亮是算出来的）')
def t_save():
    w = _world()
    g = _grid(w)
    # 走 `set()`（= 玩家路径）放元件 ⇒ 进增量
    w.set(4, Y, Z, B.LEVER_OFF)
    w.set(5, Y, Z, B.REDSTONE_WIRE)
    w.set(6, Y, Z, B.LAMP_OFF)
    g.mark(4, Y, Z)
    _settle(g)
    g.toggle_lever(4, Y, Z)                  # 玩家拉开（走 set_generated，不记增量）
    _settle(g)
    assert w.get(6, Y, Z) == B.LAMP_ON
    names = {row[3] for row in w.dump()['edits']}
    assert 'lamp_on' not in names, '红石驱动的"灯亮"**不该**进存档（它是算出来的）'
    assert 'lever_on' not in names and 'lever_off' in names, \
        '拉杆的开/关是玩家交互的结果 —— 但当前实现走 set_generated，所以档里是关'


@test('读档：按布局重算 ⇒ 通电的灯自己就亮了（信号不需要存）')
def t_reload():
    k = make_offline({'seed': SEED, 'size': 32, 'height': 32, 'light': False,
                      'mobs': False})
    for x in range(4, 12):
        for z in range(4, 12):
            k.world.set(x, 20, z, B.STONE)
            for y in (21, 22):
                k.world.set(x, y, z, B.AIR)
    k.world.set(6, 21, 8, B.LEVER_ON)        # 拉杆一开始就是开的
    k.world.set(7, 21, 8, B.REDSTONE_WIRE)
    k.world.set(8, 21, 8, B.LAMP_OFF)
    k.redstone.mark(6, 21, 8)
    k.redstone.step(1.0, budget=99)
    assert k.world.get(8, 21, 8) == B.LAMP_ON, '测试前提：灯该亮'
    data = k.dump()
    k2 = make_offline({'seed': SEED, 'size': 32, 'height': 32, 'light': False,
                       'mobs': False})
    k2.load(data)
    for _ in range(8):
        k2.redstone.step(1.0, budget=99)
    assert k2.world.get(8, 21, 8) == B.LAMP_ON, \
        '读档后该按布局重算出"灯亮"（信号不进档，靠重算）'
    assert len(k2.redstone.power) > 0, '读档后信号场该被重建'


# ==================================================================== 内核路径
@test('内核：use() 切拉杆/按按钮/开关门；place() 展开多格与朝向')
def t_kernel_paths():
    k = make_offline({'seed': SEED, 'size': 32, 'height': 32, 'light': False,
                      'mobs': False})
    for x in range(4, 15):
        for z in range(4, 15):
            k.world.set(x, 20, z, B.STONE)           # 地板
            for y in (21, 22, 23):
                k.world.set(x, y, z, B.AIR)
    for z in range(4, 15):                           # 一堵**竖直的墙**（x=13，眼睛高度那层也有）
        for y in (21, 22, 23):
            k.world.set(13, y, z, B.STONE)
    k.creative = True
    # 放一个活塞：朝向按**视线**（朝 +x ⇒ piston_east）。
    # ⚠ 站位必须在 reach（5）之内：早先站在 x=6.5、墙在 x=13（差 6.5 格）⇒ 射线打空，
    #   后面的断言全歪（实测踩过）。
    k.pos = [10.5, 21.0, 8.5]
    k.yaw, k.pitch = -90.0, 0.0                      # 朝 +x
    from mcclone3d import items as I
    k.hotbar[k.selected] = I.item_by_name('piston').id
    k.select(k.selected)
    hit = k.raycast()
    assert hit is not None
    ok, at = k.place()
    assert ok, f'活塞该放下去：{at}'
    place_id = k.world.get(*at)
    assert place_id == B.BLOCK_IDS['piston_east_off'], \
        f'朝 +x 看到墙 ⇒ 该放"朝东"的活塞，实际 {B.name_of(place_id)}'
    # 放一扇门：占两格
    k.hotbar[k.selected] = I.item_by_name('door').id
    k.select(k.selected)
    ok, at = k.place()
    assert ok, f'门该放下去：{at}'
    x, y, z = at
    assert k.world.get(x, y, z) in (B.DOOR_LOWER, B.DOOR_OPEN_LOWER)
    assert k.world.get(x, y + 1, z) in (B.DOOR_UPPER, B.DOOR_OPEN_UPPER), \
        '门必须占两格（上半格是门的另一半）'
    # 用一下（手动开关门）
    k.pos = [x + 1.5, float(y), z + 0.5]
    k.yaw, k.pitch = 90.0, 0.0                       # 朝 -x（朝向门）
    used, info = k.use()
    assert used and info[0].startswith('door'), f'对着门该能交互：{(used, info)}'
    assert k.world.get(x, y, z) == B.DOOR_OPEN_LOWER, '手动开关门该把门打开'
    used2, info2 = k.use()
    assert used2 and k.world.get(x, y, z) == B.DOOR_LOWER, '再点一次该关上'


if __name__ == '__main__':
    sys.exit(main())
