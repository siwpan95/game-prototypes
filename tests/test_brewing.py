# -*- coding: utf-8 -*-
"""酿造与药水效果单测（纯逻辑 + 内核状态往返）。

跑：`python -m tests.test_brewing`

判据一律**可穷举**：效果查询函数逐个取值对拍、效果表与物品表互相自洽、
效果计时与存档往返逐字段相等。
"""
from __future__ import annotations

import json
import sys

from tests._util import make_suite

from mcclone3d import blocks as B
from mcclone3d import brewing as BW
from mcclone3d import items as I
from mcclone3d import recipes as R
from mcclone3d.kernel import SAVE_VERSION, make_offline

test, main = make_suite('ALL_BREWING_TESTS_PASSED', '酿造与药水')


def _k(**cfg):
    return make_offline(dict({'seed': 17, 'size': 32, 'height': 32,
                              'light': False, 'mobs': False}, **cfg))


# ------------------------------------------------------------------ 表自洽
@test('效果表：名字唯一、种类合法、颜色齐、药水一一对应')
def t_tables():
    assert len(BW.EFFECT_ORDER) == len(set(BW.EFFECT_ORDER))
    assert set(BW.EFFECT_ORDER) == set(BW.EFFECTS)
    for n in BW.EFFECT_ORDER:
        e = BW.EFFECTS[n]
        assert e.kind in ('instant', 'timed'), (n, e.kind)
        assert e.title and len(e.color) == 3, (n, e.title, e.color)
        assert all(0.0 <= c <= 1.0 for c in e.color), (n, e.color)
        if e.kind == 'instant':
            assert e.heal > 0 and e.duration == 0.0, n
        else:
            assert e.duration > 0, n
    assert set(BW.POTION_OF.values()) == set(BW.EFFECTS)
    assert set(BW.POTION_OF) == set(BW.POTION_NAMES)
    for potion in BW.POTION_NAMES:
        assert I.item_by_name(potion).kind == I.KIND_POTION, potion


@test('酿造表：材料/产出一一对应，且材料都是**真的有来源**的物品')
def t_brews():
    ings = [b.ingredient for b in BW.BREWS]
    outs = [b.output for b in BW.BREWS]
    assert len(ings) == len(set(ings)), '同一种材料配了两条配方'
    assert len(outs) == len(set(outs)), '同一种药水有两条来源'
    for b in BW.BREWS:
        assert b.time > 0 and b.count == 1
        assert I.item_by_name(b.ingredient) is not None
        assert I.item_by_name(b.output).kind == I.KIND_POTION
        assert BW.brew_by_ingredient(b.ingredient) is b
        assert BW.brew_by_output(b.output) is b
    assert BW.brew_by_ingredient('no_such') is None
    assert BW.brew_by_output('no_such') is None
    # 材料必须有来源：合成产出、掉落表、或本来就是基础材料（麦子/腐肉从生物来）
    # ⚠ 合成**与烧炼**都算来源：金锭/铁锭是烧出来的（粗金/粗铁才是掉落物）。
    # 只查合成表会误报"金锭是死材料"（实测踩到）。
    obtainable = {r.output for r in R.craft_recipes()}
    obtainable |= {r.output for r in R.smelt_recipes()}
    obtainable |= {row[0] for row in R.DROP_TABLE.values() if row[0]}
    obtainable |= {'rotten_flesh', 'wheat', 'coal'}
    for b in BW.BREWS:
        assert b.ingredient in obtainable, f'{b.ingredient} 没有来源（死材料）'


@test('配方：玻璃瓶与糖都在 `recipes` 里，且数量与常量一致')
def t_recipes():
    n_glass, n_bottle = BW.BOTTLE_FROM_GLASS
    r = R.recipe_by_id('glass_bottle')
    assert r.inputs == {'glass': n_glass} and r.count == n_bottle
    n_wheat, n_sugar = BW.SUGAR_FROM_WHEAT
    r2 = R.recipe_by_id('sugar')
    assert r2.inputs == {'wheat': n_wheat} and r2.count == n_sugar
    # 酿造台的合成与掉落
    assert R.recipe_by_id('brewing_stand').output == 'brewing_stand'
    assert R.DROP_TABLE[B.BREWING_STAND] == ('brewing_stand', 1, 1)
    assert I.item_by_name('brewing_stand').block_id == B.BREWING_STAND
    assert B.MAX_ID == max(B.BLOCKS) == B.BREWING_STAND
    assert sorted(B.BLOCKS) == list(range(1, B.MAX_ID + 1)), 'id 必须连续无空洞'


# ------------------------------------------------------------------ 纯函数
@test('speed_mult：取**最大**（不叠乘）、空表为 1.0')
def t_speed():
    assert BW.speed_mult({}) == 1.0
    assert BW.speed_mult(None) == 1.0
    assert abs(BW.speed_mult({'swiftness': 5.0}) - 1.4) < 1e-12
    # 未知名字要被忽略，而不是炸
    assert BW.speed_mult({'swiftness': 1.0, 'nope': 1.0}) == 1.4
    assert BW.speed_mult({'nope': 1.0}) == 1.0


@test('damage_bonus / damage_scale / dot_rate：取最大 / 取最小 / 相加')
def t_combat():
    assert BW.damage_bonus({}) == 0.0
    assert abs(BW.damage_bonus({'strength': 9.0}) - 2.0) < 1e-12
    assert BW.damage_scale({}) == 1.0
    assert abs(BW.damage_scale({'resistance': 9.0}) - 0.6) < 1e-12
    assert BW.dot_rate({}) == 0.0
    assert abs(BW.dot_rate({'poison': 9.0}) - 1.0) < 1e-12
    # 混合：互不串台
    mix = {'swiftness': 1.0, 'strength': 1.0, 'resistance': 1.0, 'poison': 1.0}
    assert abs(BW.speed_mult(mix) - 1.4) < 1e-12
    assert abs(BW.damage_bonus(mix) - 2.0) < 1e-12
    assert abs(BW.damage_scale(mix) - 0.6) < 1e-12
    assert abs(BW.dot_rate(mix) - 1.0) < 1e-12


@test('instant_heal：只有瞬时效果有治疗量')
def t_instant():
    assert abs(BW.instant_heal('healing') - 6.0) < 1e-12
    for n in ('swiftness', 'strength', 'resistance', 'poison', 'nope'):
        assert BW.instant_heal(n) == 0.0, n


@test('active_order / describe_effects：按表顺序、过滤掉 0 与负数')
def t_order():
    got = BW.active_order({'poison': 3.0, 'swiftness': 9.0, 'strength': 0.0})
    assert [n for n, _s in got] == ['swiftness', 'poison'], got
    assert BW.active_order({}) == [] and BW.active_order(None) == []
    assert BW.describe_effects({}) == '无'
    assert BW.describe_effects({'swiftness': 30.0}) == '迅捷 30s'
    assert BW.describe_effects({'swiftness': 30.0, 'poison': 9.4}) == '迅捷 30s · 剧毒 9s'


# ------------------------------------------------------------------ 内核状态
@test('效果计时：按 dt 递减、到点**删掉**（不留 0 值）、与帧率无关')
def t_timer():
    k = _k()
    k.effects = {'swiftness': 1.0}
    for _ in range(60):
        k._potion_step(1 / 60.0)
    assert k.effects == {}, k.effects
    # 三种帧率走到同一结果
    ends = []
    for hz in (30, 60, 120):
        kk = _k()
        kk.effects = {'swiftness': 2.0}
        for _ in range(int(hz * 2.6)):
            kk._potion_step(1.0 / hz)
        ends.append(dict(kk.effects))
    assert ends[0] == ends[1] == ends[2] == {}, ends


@test('喝药水：扣一瓶、效果进表；同类取**较长**的剩余时间（不叠加）')
def t_drink():
    k = _k(creative=False)
    sp = I.item_by_name('swiftness_potion')
    k.give(sp.id, 3)
    k.hotbar[0] = sp.id
    k.select(0)
    assert k.drink() == (True, 'swiftness_potion')
    assert k.inventory.get(sp.id, 0) == 2
    assert abs(k.effects['swiftness'] - 30.0) < 1e-9
    k.effects['swiftness'] = 5.0
    k.drink()
    assert abs(k.effects['swiftness'] - 30.0) < 1e-9, '同类效果应当取较长者'
    assert k.stats['drank'] == 2
    # 不是药水 ⇒ 拒绝（材料/工具都不行）
    k.hotbar[0] = I.item_by_name('sugar').id
    assert k.drink() == (False, None)
    # 喝光之后拒绝
    k.hotbar[0] = sp.id
    k.inventory[sp.id] = 1
    assert k.drink()[0]
    assert k.drink() == (False, 'none_left')


@test('酿造：扣料与产出**分开**（装料不给、到点才给），一炉没完不许再装')
def t_brew_kernel():
    k = _k(creative=False)
    wb = I.item_by_name('water_bottle')
    sg = I.item_by_name('sugar')
    k.give(wb.id, 1)          # ⚠ 只给 1 瓶：下面"没水瓶就拒绝"那条判据要靠它
    k.give(sg.id, 2)
    ok, why = k.brew_load('sugar')
    assert ok and k.brewing['output'] == 'swiftness_potion'
    assert k.inventory.get(wb.id, 0) == 0 and k.inventory.get(sg.id, 0) == 1, '装料要扣'
    assert k.inventory.get(I.item_by_name('swiftness_potion').id, 0) == 0, \
        '⚠ 装料那一刻不该给药水（那是"一炉发货两次"的老坑）'
    assert k.brew_load('sugar')[0] is False, '一炉没完不许再装'
    assert k.brew_step(BW.BREW_TIME / 2)[0] == 'brewing'
    assert k.brew_step(BW.BREW_TIME)[0] == 'done'
    assert k.inventory.get(I.item_by_name('swiftness_potion').id, 0) == 1
    assert k.stats['brewed'] == 1
    # 没水瓶 ⇒ 拒绝，且**材料一点不动**
    before = dict(k.inventory)
    assert k.brew_load('sugar')[0] is False
    assert dict(k.inventory) == before, '拒绝时不该扣任何东西'
    # 不认识的材料的报错要说人话
    k.give(wb.id, 1)
    bad = k.brew_load('diamond')
    assert bad[0] is False and '不能用来酿造' in bad[1], bad


@test('装水：必须对着**水**、且手里拿的是玻璃瓶')
def t_fill():
    k = _k(creative=False)
    gb = I.item_by_name('glass_bottle')
    wb = I.item_by_name('water_bottle')
    k.give(gb.id, 1)
    k.hotbar[0] = gb.id
    k.select(0)
    x, z = 8, 8
    y = k.world.surface_at(x, z) + 1
    k.flying = True
    k.pos = [x + 0.5, y + 2.0, z + 0.5]
    k.yaw, k.pitch = 0.0, -90.0
    assert k.fill_bottle() == (False, '要对着水'), '对着地面不该装到水'
    k.world.set(x, y, z, B.WATER)
    ok, _why = k.fill_bottle()
    assert ok and k.inventory.get(wb.id, 0) == 1 and k.inventory.get(gb.id, 0) == 0
    # 手里不是玻璃瓶 ⇒ 拒绝
    k.hotbar[0] = I.item_by_name('sugar').id
    assert k.fill_bottle() == (False, '手里要拿一个玻璃瓶')


@test('存档 v5：效果与"进行中那一炉"往返一致；老档（v4）也能读')
def t_save():
    k = _k(creative=False)
    k.effects = {'swiftness': 12.5, 'poison': 3.25}
    k.give_item('water_bottle', 1)
    k.give_item('sugar', 1)
    k.brew_load('sugar')
    k.brew_step(1.0)
    blob = json.loads(json.dumps(k.dump()))
    assert blob['version'] == 5 == SAVE_VERSION
    p = blob['player']
    assert abs(p['effects']['swiftness'] - 12.5) < 1e-6
    assert p['brewing']['output'] == 'swiftness_potion'
    k2 = _k(creative=False)
    k2.load(blob)
    assert k2.effects == k.effects
    assert k2.brewing == k.brewing
    # v4 老档：没有这两项 ⇒ 默认值，不炸
    old = json.loads(json.dumps(blob))
    old['version'] = 4
    for key in ('effects', 'brewing'):
        old['player'].pop(key, None)
    for key in ('brewed', 'drank'):
        old['player']['stats'].pop(key, None)
    k3 = _k(creative=False)
    k3.load(old)
    assert k3.effects == {} and k3.brewing == {'output': None, 'left': 0.0}
    assert k3.stats['brewed'] == 0 and k3.stats['drank'] == 0
    # 未知效果名 ⇒ 响亮报错（不静默丢掉一条正在生效的药水）
    bad = json.loads(json.dumps(blob))
    bad['player']['effects'] = {'no_such_effect': 5.0}
    k4 = _k(creative=False)
    try:
        k4.load(bad)
    except ValueError:
        pass
    else:
        raise AssertionError('未知效果名应当响亮报错')
    # 存档里"酿好了但还没发"的那一炉：读档**立刻发货**
    k5 = _k(creative=False)
    b2 = json.loads(json.dumps(blob))
    b2['player']['brewing'] = {'output': 'healing_potion', 'left': 0.0}
    k5.load(b2)
    assert k5.brewing == {'output': None, 'left': 0.0}
    assert k5.inventory.get(I.item_by_name('healing_potion').id, 0) == 1


@test('reset：换世界要把效果与酿造台一起清掉（重开一局）')
def t_reset():
    k = _k()
    k.effects = {'swiftness': 20.0}
    k.brewing = {'output': 'poison_potion', 'left': 3.0}
    k.reset(99)
    assert k.effects == {} and k.brewing == {'output': None, 'left': 0.0}


if __name__ == '__main__':
    sys.exit(main())
