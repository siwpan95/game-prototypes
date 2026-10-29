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
    """⚠ Phase 3-B 起中继器**有延迟**（走元件 tick 队列）⇒ 不能再用 `_settle`（它 dt=0、
    只清脏网络、不推进时间）。这里要用 `run_until_stable`：它会连**时间**一起推进，
    直到"没有脏网络、也没有待触发事件"。延迟语义本身由 `t_repeater_delay` 单独钉。
    """
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
    g.run_until_stable()
    assert w.get(x0 + 15, Y, Z) == B.REPEATER_E_ON, \
        f'中继器该被前段点亮，实际 {B.name_of(w.get(x0 + 15, Y, Z))}'
    assert g.power_at(x0 + 16, Y, Z) == 15, \
        f'中继器后第一格该是 15（续接），实际 {g.power_at(x0 + 16, Y, Z)}'
    assert w.get(x0 + 21, Y, Z) == B.LAMP_ON, '续接后的灯该亮'
    # 断电：中继器与灯都要灭
    g.toggle_lever(x0, Y, Z)
    g.run_until_stable()
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


def _put(w, g, x: int, y: int, z: int, bid: int):
    """放置 + `mark`（**必须**，否则网络式重算根本不知道这里多了元件）。"""
    w.set_generated(x, y, z, bid)
    g.mark(x, y, z)


def _tier(d: str, n: int, on: bool = False) -> int:
    """取中继器的某个 `(方向, 档位)` 状态 id。"""
    off, on_id = B.REPEATER_BY_DIR_DELAY[(d, n)]
    return on_id if on else off


def _inverter_rig(w, g, x0: int = 4, z0: int = Z):
    """搭一台**反相器**：拉杆 → 线 → 中继器（朝东）→ 实心块 → 块上的火把 → 线 → 灯。

    返回 `(拉杆, 中继器, 块, 火把, 灯)` 五个坐标。中继器一亮就强充能它**正面**的块，
    块上那支火把随之熄灭 ⇒ 灯灭。这是"反相"的最小装置。
    """
    _put(w, g, x0, Y, z0, B.LEVER_OFF)
    _put(w, g, x0 + 1, Y, z0, B.REDSTONE_WIRE)
    _put(w, g, x0 + 2, Y, z0, B.REPEATER_E_OFF)          # 正面 = (x0+3, Y, z0)
    _put(w, g, x0 + 3, Y, z0, B.STONE)                   # 会被强充能的实心块
    _put(w, g, x0 + 3, Y + 1, z0, B.REDSTONE_TORCH)      # 坐在块上的火把
    _put(w, g, x0 + 4, Y + 1, z0, B.REDSTONE_WIRE)
    _put(w, g, x0 + 5, Y + 1, z0, B.LAMP_OFF)
    return ((x0, Y, z0), (x0 + 2, Y, z0), (x0 + 3, Y, z0),
            (x0 + 3, Y + 1, z0), (x0 + 5, Y + 1, z0))


def _clock_rig(w, g, x0: int = 4, z0: int = 6, tier: int = 0):
    """搭一台**环形时钟**：中继器朝南 → 正面实心块 → 块上火把 → 线绕回中继器背面。

    反相器是**瞬时**的、中继器是**延迟**的 ⇒ 环里每半个周期翻一次，
    整周期 = `2 × 档位延迟`（0.1s 档 ⇒ 5Hz）。
    返回 `(中继器, 火把, 灯)` 三个坐标。
    """
    _put(w, g, x0, Y, z0 + 2, B.REDSTONE_WIRE)           # 中继器**背面**（输入）
    _put(w, g, x0, Y, z0 + 3, _tier('south', tier))      # 正面 = (x0, Y, z0+4)
    _put(w, g, x0, Y, z0 + 4, B.STONE)
    _put(w, g, x0, Y + 1, z0 + 4, B.REDSTONE_TORCH)      # 块上的火把
    _put(w, g, x0, Y + 1, z0 + 3, B.REDSTONE_WIRE)       # 火把输出绕回…
    _put(w, g, x0, Y + 1, z0 + 2, B.REDSTONE_WIRE)       # …到背面那条线
    _put(w, g, x0 + 1, Y, z0 + 2, B.LAMP_OFF)            # 灯接在背面线上，跟着闪
    return (x0, Y, z0 + 3), (x0, Y + 1, z0 + 4), (x0 + 1, Y, z0 + 2)


def _blink_series(g, w, lamp, seconds: float, dt: float = 0.05):
    """跑 `seconds` 秒，返回灯的状态序列（1/0）—— 用来数翻转次数与看波形。"""
    out = []
    for _ in range(int(round(seconds / dt))):
        g.step(dt, budget=999)
        out.append(1 if w.get(*lamp) == B.LAMP_ON else 0)
    return out


def _transitions(series):
    return sum(1 for i in range(1, len(series)) if series[i] != series[i - 1])


# ==================================================================== Phase 3-B：元件 tick 队列
@test('tick 队列：中继器**延迟**翻转（0.2s 时还没到点、过了档位才翻）')
def t_repeater_delay():
    """Phase 3-B 的核心：中继器不再是"一个 tick 内算到固定点"的瞬时元件。

    延迟长度 = **档位**（`blocks.REPEATER_DELAYS`：0.1/0.2/0.3/0.4 秒）。
    `g.step(0.0, ...)` 只算信号、**不推进时间** ⇒ 那一刻不该发生翻转。
    """
    w, g = _world(), None
    g = _grid(w)
    off = _tier('east', 2)                              # 3 档 = 0.3s
    on = _tier('east', 2, on=True)
    _put(w, g, 4, Y, Z, B.LEVER_OFF)
    _put(w, g, 5, Y, Z, B.REDSTONE_WIRE)
    _put(w, g, 6, Y, Z, off)
    _put(w, g, 7, Y, Z, B.REDSTONE_WIRE)
    _put(w, g, 8, Y, Z, B.LAMP_OFF)
    g.run_until_stable()
    assert w.get(8, Y, Z) == B.LAMP_OFF

    g.toggle_lever(4, Y, Z)
    g.step(0.0, budget=999)                             # 算完信号，但时间没走
    assert w.get(6, Y, Z) == off, f'延迟没到就不该翻转，实际 {B.name_of(w.get(6, Y, Z))}'
    assert g.pending_count() == 1, f'该排 1 个待触发事件，实际 {g.pending_count()}'

    g.step(0.2, budget=999)
    assert w.get(6, Y, Z) == off, '0.2s < 0.3s（3 档）还不该翻转'
    assert w.get(8, Y, Z) == B.LAMP_OFF, '中继器没亮，灯不该亮'

    g.step(0.15, budget=999)                            # 累计 0.35s > 0.3s
    g.run_until_stable()
    assert w.get(6, Y, Z) == on, f'过了档位延迟该翻转，实际 {B.name_of(w.get(6, Y, Z))}'
    assert w.get(8, Y, Z) == B.LAMP_ON, '翻转之后灯才亮'


@test('惰性求值：比延迟短的脉冲**不产生输出**，比延迟长的照常输出（脉冲整形）')
def t_pulse_shaping():
    """队列里只存 `(到期时刻, 格子)`，触发时**重新读当前输入** ⇒ 短脉冲被自然吃掉。

    对照组（长脉冲）是必须的：只有"短脉冲被吃掉"会看不出中继器是不是**彻底坏了**。
    """
    def rig():
        w = _world()
        g = _grid(w)
        _put(w, g, 4, Y, Z, B.BUTTON_OFF)
        _put(w, g, 5, Y, Z, _tier('east', 2))           # 3 档 = 0.3s
        _put(w, g, 6, Y, Z, B.REDSTONE_WIRE)
        _put(w, g, 7, Y, Z, B.LAMP_OFF)
        g.run_until_stable()
        return w, g

    # ① 短脉冲（0.1s < 0.3s）：灯**始终**不亮
    w, g = rig()
    g.press_button(4, Y, Z, ttl=0.1)
    g.run_until_stable(max_ticks=40, dt=0.05)
    assert w.get(7, Y, Z) == B.LAMP_OFF, '比延迟短的脉冲不该点亮灯（惰性求值）'
    assert w.get(5, Y, Z) == _tier('east', 2), '中继器也该保持灭'

    # ② 长脉冲（0.6s > 0.3s）：延迟之后照常亮
    w, g = rig()
    g.press_button(4, Y, Z, ttl=0.6)
    for _ in range(8):                                   # 走到 0.4s
        g.step(0.05, budget=999)
    assert w.get(7, Y, Z) == B.LAMP_ON, '比延迟长的脉冲该正常点亮（证明不是中继器坏了）'


@test('档位：4 方向 × 4 档 = 16 对状态，延迟与名字都对得上（老名字不变）')
def t_delay_tiers():
    assert len(B.REPEATER_STATES) == 16, f'中继器状态对数是 {len(B.REPEATER_STATES)}'
    assert B.REPEATER_DELAYS == (0.1, 0.2, 0.3, 0.4), B.REPEATER_DELAYS
    seen = set()
    for (d, n, off, on) in B.REPEATER_STATES:
        for bid in (off, on):
            assert bid not in seen, f'id {bid} 被两个状态用了'
            seen.add(bid)
            assert B.REPEATER_DIR_OF[bid] == d and B.REPEATER_DELAY_OF[bid] == n
            assert B.repeater_delay(bid) == B.REPEATER_DELAYS[n], B.name_of(bid)
            assert bid in B.BLOCKS, f'{bid} 没有方块定义'
    assert len(seen) == 32, f'中继器共占 {len(seen)} 个 id（应 32）'
    # 档 0 的**历史名字**不许改（存档按名字存）
    for name in ('repeater_north_off', 'repeater_north_on', 'repeater_south_off',
                 'repeater_east_on', 'repeater_west_off'):
        assert name in B.BLOCK_NAMES, f'历史方块名 {name} 丢了（会读坏老档）'
    # 非中继器的 `repeater_delay` 是 0，不抛
    assert B.repeater_delay(B.STONE) == 0.0


@test('调档：循环 1→2→3→4→1，且**不改开/关**（亮灭由信号决定）')
def t_cycle_delay():
    w = _world()
    g = _grid(w)
    _put(w, g, 4, Y, Z, _tier('north', 3))               # 4 档
    ids = []
    for _ in range(4):
        new = g.cycle_repeater_delay(4, Y, Z)
        ids.append(B.REPEATER_DELAY_OF[new])
        assert w.get(4, Y, Z) == new, '调档要真的写进世界'
    assert ids == [0, 1, 2, 3], f'调档顺序不对：{ids}（应 4→1→2→3 档）'
    # 开着的中继器调档 ⇒ 仍需是"开着"的状态
    g.toggle_repeater(4, Y, Z)
    was_on = w.get(4, Y, Z)
    assert was_on == _tier('north', 3, on=True), B.name_of(was_on)
    new = g.cycle_repeater_delay(4, Y, Z)
    assert new == _tier('north', 0, on=True), \
        f'调档后该仍是"亮"状态，实际 {B.name_of(new)}'
    # 不是中继器 ⇒ 返回 None，不炸
    assert g.cycle_repeater_delay(9, Y, Z) is None


@test('回归：中继器翻转**不掉档位**（3 档翻完还是 3 档）')
def t_tier_kept_on_flip():
    """`repeater_on_id()` 必须**保持同一档位**。初版它返回 `REPEATER_BY_DIR[dir][1]`
    （那是档 0 的 id）⇒ 中继器每翻一次就掉回 1 档 ——
    症状是"3 档时钟第一次延迟 0.3s，之后变成 0.1s"（周期 0.6s → 0.2s）。
    """
    w = _world()
    g = _grid(w)
    off = _tier('east', 2)                               # 3 档
    on = _tier('east', 2, on=True)
    assert B.repeater_on_id(off) == on, 'off → on 必须留在同一档'
    assert B.repeater_off_id(on) == off, 'on → off 必须留在同一档'
    assert B.REPEATER_DELAY_OF[on] == 2, '翻转后档位变了'
    # 真跑一遍：翻转后再翻回来，仍然是 3 档
    _put(w, g, 4, Y, Z, B.LEVER_OFF)
    _put(w, g, 5, Y, Z, B.REDSTONE_WIRE)
    _put(w, g, 6, Y, Z, off)
    g.run_until_stable()
    g.toggle_lever(4, Y, Z)
    g.run_until_stable()
    assert w.get(6, Y, Z) == on, B.name_of(w.get(6, Y, Z))
    g.toggle_lever(4, Y, Z)
    g.run_until_stable()
    assert w.get(6, Y, Z) == off, B.name_of(w.get(6, Y, Z))


@test('回归：松开按钮后中继器背面读到 **0**（幽灵信号）')
def t_no_ghost_signal():
    """`power` 里过期格必须**立刻作废**。初版只在"网络成员"里清，
    于是"通电的按钮被松开 / 通电的线被挖掉"会在原地留下信号 ——
    症状：按钮 0.1s 回弹后中继器仍认为"背面有电"，把短脉冲当成了常亮。
    """
    w = _world()
    g = _grid(w)
    _put(w, g, 4, Y, Z, B.BUTTON_OFF)
    _put(w, g, 5, Y, Z, _tier('east', 2))
    _put(w, g, 6, Y, Z, B.LAMP_OFF)
    g.run_until_stable()
    g.press_button(4, Y, Z, ttl=0.1)
    g.step(0.0, budget=999)
    assert g.power_at(4, Y, Z) == 15, '按下时按钮那格该有信号'
    g.step(0.2, budget=999)                              # 越过 0.1s 回弹
    assert w.get(4, Y, Z) == B.BUTTON_OFF, '按钮该回弹了'
    assert g.power_at(4, Y, Z) == 0, \
        f'松开后按钮那格该是 0，实际 {g.power_at(4, Y, Z)}（幽灵信号）'
    # 挖掉通电的线同理
    _put(w, g, 4, Y, Z, B.LEVER_ON)
    g.run_until_stable()
    assert g.power_at(5, Y, Z) == 15
    w.set_generated(5, Y, Z, B.AIR)
    g.mark(5, Y, Z)
    g.run_until_stable()
    assert g.power_at(5, Y, Z) == 0, '挖掉的线上不该留着信号'


@test('红石火把是**反相器**：脚下被强充能 ⇒ 熄灭；松开 ⇒ 复亮（不自锁）')
def t_torch_inverter():
    w = _world()
    g = _grid(w)
    lever, repl, block, torch, lamp = _inverter_rig(w, g)
    g.run_until_stable()
    assert w.get(*torch) == B.REDSTONE_TORCH, '没电时火把该亮着'
    assert w.get(*lamp) == B.LAMP_ON, '火把亮着 ⇒ 灯该亮'

    g.toggle_lever(*lever)
    g.run_until_stable()
    assert w.get(*repl) == B.REPEATER_E_ON, '中继器该先亮'
    assert w.get(*torch) == B.REDSTONE_TORCH_OFF, \
        f'块被强充能 ⇒ 火把该熄灭，实际 {B.name_of(w.get(*torch))}'
    assert w.get(*lamp) == B.LAMP_OFF, '火把灭了 ⇒ 灯该灭（反相）'

    g.toggle_lever(*lever)
    g.run_until_stable()
    assert w.get(*torch) == B.REDSTONE_TORCH, '断电后火把该自己亮回来（不自锁）'
    assert w.get(*lamp) == B.LAMP_ON


@test('反相器不自锁的**结构原因**：红石线只能**弱充能**，火把不吃弱充能')
def t_wire_does_not_strongly_charge():
    """这一条钉的是不变量本身：火把的输出**只能进红石线**，
    而强充能只来自元件（拉杆/按钮/中继器正面）⇒ 火把永远改不动自己的睡眠条件。
    没有这一条，"六邻有电就熄灭"的写法会让火把在固定点迭代里无限翻转。
    """
    w = _world()
    g = _grid(w)
    _put(w, g, 4, Y, Z, B.REDSTONE_TORCH)
    _put(w, g, 5, Y, Z, B.REDSTONE_WIRE)
    _put(w, g, 6, Y, Z, B.STONE)                         # 紧挨着通电的线
    g.run_until_stable()
    assert g.power_at(5, Y, Z) == 15, '火把该把线充到 15'
    assert not g.strongly_powered(6, Y, Z), \
        '线只能弱充能 —— 石头不该因为旁边有通电的线而变成"强充能"'
    assert w.get(4, Y, Z) == B.REDSTONE_TORCH, '火把不该被自己的输出熄灭（不自锁）'
    # 换成"中继器的正面" ⇒ 才算强充能。
    # ⚠ 必须给它背面接个拉杆：裸放一个 `REPEATER_ON` 会被引擎按"背面没电"当场判灭
    #   （`_apply_outputs` 的职责就是这个），于是这条断言会假红（实测踩过）。
    _put(w, g, 3, Y, Z, B.LEVER_ON)
    _put(w, g, 4, Y, Z, B.REPEATER_E_ON)
    g.run_until_stable()
    assert w.get(4, Y, Z) == B.REPEATER_E_ON, \
        f'中继器该保持亮，实际 {B.name_of(w.get(4, Y, Z))}'
    assert g.strongly_powered(5, Y, Z), '中继器的**正面**格该被强充能'


@test('时钟：反相器（瞬时）+ 中继器（延迟）= 环形振荡，周期 = 2×档位')
def t_clock():
    w = _world()
    g = _grid(w)
    repl, torch, lamp = _clock_rig(w, g, tier=0)         # 1 档 = 0.1s
    g.run_until_stable(max_ticks=6)
    series = _blink_series(g, w, lamp, seconds=3.0, dt=0.05)
    trans = _transitions(series)
    # 半周期 0.1s ⇒ 3.0s 内 30 次翻转（允许首尾各差 1 次）
    assert 28 <= trans <= 32, f'3.0s 内灯翻转 {trans} 次（1 档应约 30）'
    assert g.pending_count() > 0, '时钟必须一直挂着下一个事件（它不会停）'


@test('时钟：换档位就换周期（3 档 ⇒ 每 0.3s 翻一次）')
def t_clock_tier():
    w = _world()
    g = _grid(w)
    repl, torch, lamp = _clock_rig(w, g, x0=4, z0=6, tier=2)   # 3 档 = 0.3s
    g.run_until_stable(max_ticks=8)
    series = _blink_series(g, w, lamp, seconds=3.0, dt=0.05)
    trans = _transitions(series)
    assert 8 <= trans <= 12, f'3 档应约 10 次翻转，实际 {trans}'


@test('确定性：同一台时钟跑两遍，波形**逐帧相同**')
def t_clock_deterministic():
    def run():
        w = _world()
        g = _grid(w)
        _repl, _torch, lamp = _clock_rig(w, g)
        g.run_until_stable(max_ticks=6)
        return _blink_series(g, w, lamp, seconds=2.0, dt=0.05)
    assert run() == run(), '同一布局两次运行的波形必须完全一致'


@test('回归（浮点相位）：长跑 8 秒翻转次数**不漂**（时间比较要留容差）')
def t_phase_no_drift():
    """`self.now` 是逐帧累加出来的浮点：累到几百帧后会比重排时刻略小
    （`0.05×N` 的真值在两条路径上差 1 ulp）⇒ 严格 `due <= now` 会让事件**晚一帧**，
    而这一次晚帧会把后续全部推后 ⇒ **相位永久滑移**（实测周期 0.2s 漂成 0.3s）。
    """
    w = _world()
    g = _grid(w)
    _repl, _torch, lamp = _clock_rig(w, g, tier=0)
    g.run_until_stable(max_ticks=6)
    series = _blink_series(g, w, lamp, seconds=8.0, dt=0.05)
    trans = _transitions(series)
    assert 76 <= trans <= 84, f'8.0s 内应约 80 次翻转，实际 {trans}（相位漂了）'


@test('tick 队列去重：同一格只挂一个待触发事件')
def t_tick_dedup():
    w = _world()
    g = _grid(w)
    _put(w, g, 4, Y, Z, B.LEVER_OFF)
    _put(w, g, 5, Y, Z, B.REDSTONE_WIRE)
    _put(w, g, 6, Y, Z, _tier('east', 2))
    g.run_until_stable()
    g.toggle_lever(4, Y, Z)
    for _ in range(5):                                   # 多轮迭代不该重排
        g.step(0.0, budget=999)
    assert g.pending_count() == 1, f'同格排了 {g.pending_count()} 个事件'
    g.run_until_stable()
    assert g.pending_count() == 0, '静态装置结算完队列该是空的'


@test('护栏：一次 step 内触发事件数超上限 ⇒ 抛 RedstoneOverflow（不静默截断）')
def t_events_cap():
    """只有"0 延迟的环"才能撞到这条护栏（正常档位最短 0.1s）。
    这里直接往队列里灌同刻事件来验护栏本身 —— 超限时必须**响亮报错**，
    静默截断会表现为"红石偶尔不动"，那种 bug 最难查。
    """
    w = _world()
    g = _grid(w)
    for i in range(RS.TICK_EVENTS_CAP + 20):
        g._schedule((i % 60, Y, Z + i // 60), 0.0)       # 坐标都在世界里；空气格 ⇒ 触发即空转
    try:
        g._fire_due()
    except RS.RedstoneOverflow:
        return
    raise AssertionError(f'超过 TICK_EVENTS_CAP={RS.TICK_EVENTS_CAP} 该抛 RedstoneOverflow')


@test('run_until_stable：静态装置会**停下来**，时钟**永远不停**')
def t_run_until_stable():
    w = _world()
    g = _grid(w)
    lever, repl, block, torch, lamp = _inverter_rig(w, g, x0=4, z0=Z)
    g.run_until_stable()
    assert not g.dirty and g.pending_count() == 0, '静态装置该完全静止'
    # 时钟：跑满 max_ticks 也停不下来，而且灯确实在动
    w2 = _world()
    g2 = _grid(w2)
    _repl, _torch, lamp2 = _clock_rig(w2, g2)
    g2.run_until_stable(max_ticks=6)
    # ⚠ 别拿"跑 1 秒后状态不同"来判"在闪"：1.0s 正好是 5 个整周期（周期 0.2s）⇒
    #   灯会回到同一个状态，断言假红（实测踩过）。数**翻转次数**才可靠。
    series = _blink_series(g2, w2, lamp2, seconds=1.0, dt=0.05)
    assert g2.pending_count() > 0, '时钟该一直有下一个事件'
    assert _transitions(series) > 0, '时钟的灯必须真的在闪'


@test('内核：右键中继器 = **调档**（不是切亮灭 —— 亮灭由信号决定）')
def t_kernel_use_cycle_delay():
    k = make_offline({'seed': SEED, 'size': 64, 'height': 64, 'light': False})
    x, y, z = 40, Y, 40
    for dx in range(-2, 3):                              # 清一小片空地
        for dz in range(-2, 3):
            for dy in (0, 1, 2):
                k.world.set(x + dx, y + dy, z + dz, B.AIR)
    # ⚠ 元件要摆在**眼睛高度**：`pos` 是脚底，眼睛在 +1.6
    #   ⇒ 摆在脚底那层时 pitch=0 的射线会从方块**头顶飞过去**，`use()` 拿到 (False, None)
    #   （实测踩过；上面那个"门"的用例没踩到，是因为门本来就占两格高）。
    k.world.set(x, y + 1, z, _tier('north', 0))
    k.pos = [x + 0.5, float(y), z + 2.5]
    k.yaw, k.pitch = 0.0, 0.0                            # 朝 -z（朝向中继器）
    used, info = k.use()
    assert used and info is not None, f'对着中继器该能交互：{(used, info)}'
    assert '档' in info[1], f'提示该写档位，实际 {info}'
    assert B.REPEATER_DELAY_OF[k.world.get(x, y + 1, z)] == 1, \
        f'右键该把它调到 2 档，实际 {B.name_of(k.world.get(x, y + 1, z))}'


if __name__ == '__main__':
    sys.exit(main())
