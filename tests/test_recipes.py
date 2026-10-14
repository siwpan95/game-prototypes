# -*- coding: utf-8 -*-
"""合成 / 烧炼配方单测（纯数据 + 纯函数，零 GL）。

配方的价值全在"**能被做出来**"：写了配方却永远凑不齐材料，等于死数据。
所以这里的重点是**反向自检**（拿配方自己的输入去合它自己）+ 扣减的**原子性**
（失败不许留下半扣状态）+ `input_options()` 的形状（踩过 `int.split()` 的地方）。

跑：`python -m tests.test_recipes`
"""
from __future__ import annotations

import sys

from tests._util import make_suite

from mcclone3d import blocks as B
from mcclone3d import items as I
from mcclone3d import recipes as R

test, main = make_suite('ALL_RECIPES_TESTS_PASSED', '配方')


def _satisfy(recipe: R.Recipe) -> dict:
    """造一个"刚好够"的假背包：每个槽位给**第一个**可接受物品的足量。

    故意只给"第一个选项"：这样同时也验证了"可替换输入（`a|b`）里的第一个确实能用"。
    """
    inv = {}
    for need, opts in recipe.input_options():
        inv[opts[0]] = inv.get(opts[0], 0) + need
    return inv


@test('配方表契约：id 唯一、kind 合法、数量为正、时间非负')
def t_table_contract():
    ids = [r.id for r in R.RECIPES]
    assert ids, '配方表是空的'
    assert len(ids) == len(set(ids)), f'配方 id 重复：{ids}'
    for r in R.RECIPES:
        assert r.kind in ('craft', 'smelt'), f'{r.id} 的 kind={r.kind!r} 不认识'
        assert r.count >= 1, f'{r.id} 的产出数量 {r.count} 不是正数'
        assert r.time >= 0.0, f'{r.id} 的 time={r.time} 是负数'
        assert r.inputs, f'{r.id} 没有任何输入（凭空产出？）'
        if r.kind == 'smelt':
            assert r.time > 0.0, f'烧炼配方 {r.id} 的 time 必须是正数（否则一帧就出料）'
        else:
            assert r.time == 0.0, f'合成配方 {r.id} 不该有烧炼时间'
    # 按 id 取回的必须是同一个对象（不是拷贝）
    for r in R.RECIPES:
        assert R.recipe_by_id(r.id) is r, f'{r.id} 按 id 取回的不是同一条配方'
    try:
        R.recipe_by_id('no_such_recipe')
    except KeyError:
        pass
    else:
        raise AssertionError('未知配方 id 必须抛 KeyError')


@test('input_options 形状：(数量, [可接受名字...]) —— 这是踩过 int.split() 的地方')
def t_input_options():
    for r in R.RECIPES:
        opts = r.input_options()
        assert isinstance(opts, list) and opts, f'{r.id} 的 input_options 是空的'
        for entry in opts:
            assert isinstance(entry, tuple) and len(entry) == 2, \
                f'{r.id} 的槽位形状不对：{entry!r}（该是 (数量, [名字...])）'
            need, names = entry
            assert isinstance(need, int) and need >= 1, \
                f'{r.id} 的数量位不是正整数：{need!r}（写反了就会 int.split() 当场炸）'
            assert isinstance(names, list) and names, \
                f'{r.id} 的可接受名字不是非空列表：{names!r}'
            for n in names:
                assert isinstance(n, str) and n, f'{r.id} 的名字位不是非空字符串：{n!r}'
                assert n in I.ITEMS_BY_NAME, f'{r.id} 的输入 {n!r} 不在物品表里'
    # 可替换输入要被切开（`coal|charcoal` 是两个选项，不是一个带竖线的名字）
    iron = R.recipe_by_id('iron_ingot')
    opts = iron.input_options()
    assert len(opts) == 2, f'铁锭该是 2 个槽位，实际 {len(opts)}'
    flat = [n for _need, names in opts for n in names]
    assert 'coal' in flat and 'charcoal' in flat, f'可替换输入没切开：{flat}'
    assert not any('|' in n for n in flat), f'名字里还留着竖线（没 split）：{flat}'
    assert sorted(flat) == ['charcoal', 'coal', 'raw_iron'], f'铁锭的输入集合不对：{flat}'


@test('反向自检：每条配方都能被它自己的输入合成出来（防死配方）')
def t_reverse_selfcheck():
    for r in R.RECIPES:
        inv = _satisfy(r)
        assert R.craftable(r, inv), f'{r.id} 用自己刚好够的输入却判"不可合成"：{inv}'
        trial = dict(inv)
        assert R.craft(r, trial) is True, f'{r.id} 判定可合成，扣减阶段却失败（半扣状态）'
        # 产出必须加上
        assert trial.get(r.output, 0) == r.count, \
            f'{r.id} 产出不对：{trial.get(r.output)} vs {r.count}'
        # 每个槽位都必须被**真的扣过**：`_satisfy` 只给第一个选项，所以那个名字必须见底。
        # ⚠ 不能断言"所有输入名都被清空" —— 可替换输入（`coal|charcoal`）只该消耗其中一个，
        #    `_satisfy` 给的是 opts[0]，另一个从来就不在包里，清空与否没有意义。
        for _need, names in r.input_options():
            assert trial.get(names[0], 0) == 0, \
                f'{r.id} 的槽位 {names} 没扣干净，还剩 {trial.get(names[0])}'


@test('每条配方的产出与输入名字都在物品表里（防死数据/拼写错）')
def t_names_exist():
    for r in R.RECIPES:
        assert r.output in I.ITEMS_BY_NAME, \
            f'{r.id} 的产出 {r.output!r} 不在物品表里（永远做不出来的死配方）'
        for need, names in r.input_options():
            for n in names:
                assert n in I.ITEMS_BY_NAME, f'{r.id} 的输入 {n!r} 不在物品表里'
    # `recipes_for()` 必须能把配方反向查回来（UI 的"这个能做什么"）
    for r in R.RECIPES:
        back = R.recipes_for(I.item_by_name(r.output).id)
        assert r in back, f'{r.id} 不能被 recipes_for({r.output}) 查到'


@test('craft 失败时背包一点不动（原子性，半扣状态的回归测试）')
def t_craft_atomic():
    # ① 材料完全不够
    inv = {'log': 0}
    before = dict(inv)
    assert R.craft(R.recipe_by_id('planks_from_log'), inv) is False
    assert inv == before, f'失败却动了背包：{before} → {inv}'
    # ② 材料"看着够、实际不够"：这条是半扣状态的真回归样本 ——
    #    石镐要 cobble×3 + stick×2，只给 3 个 cobble 就能过第一个槽，
    #    第二个槽（木棍）要不到 ⇒ 必须整条回滚。
    inv2 = {'cobble': 3}
    before2 = dict(inv2)
    assert R.craftable(R.recipe_by_id('stone_pickaxe'), inv2) is False, \
        '缺木棍却判成可合成（判定漏了槽位）'
    assert R.craft(R.recipe_by_id('stone_pickaxe'), inv2) is False
    assert inv2 == before2, f'失败却把材料扣掉了（半扣状态）：{before2} → {inv2}'
    # ③ 空背包：任何 craft 配方都必须安静地失败，且不动背包
    for r in R.craft_recipes():
        inv3 = {}
        assert R.craft(r, inv3) is False, f'{r.id} 在空背包上居然合成成功'
        assert inv3 == {}, f'{r.id} 在空背包上改了背包：{inv3}'
    # ④ 两个槽位要同一种物品、总量只够一个槽位 —— 经典的半扣陷阱
    #    （假配方：planks×2 + planks×2 = 4，只给 3 个）
    twin = R.Recipe('twin_trap', 'craft', {'planks': 2, 'log|planks': 2}, 'stick', 1)
    inv4 = {'planks': 3}
    assert R.craft(twin, inv4) is False, '两个槽位都要木板、只够一处，却合成成功了'
    assert inv4 == {'planks': 3}, f'半扣状态：{inv4}'


@test('craftable 逐条穷举：少一个材料就必须判否')
def t_craftable_exhaustive():
    for r in R.craft_recipes():
        full = _satisfy(r)
        assert R.craftable(r, full) is True, f'{r.id} 满材料判否'
        # 逐个槽位各减 1 ⇒ 必须判否（这条覆盖"每个槽位都被真的检查了"）
        for need, names in r.input_options():
            short = dict(full)
            short[names[0]] = short[names[0]] - 1
            assert R.craftable(r, short) is False, \
                f'{r.id} 少了 1 个 {names[0]} 却仍判可合成'


@test('可替换输入：任一选项满足即可（coal 或 charcoal 都能烧铁）')
def t_alternatives():
    iron = R.recipe_by_id('iron_ingot')
    assert R.craftable(iron, {'raw_iron': 1, 'coal': 1}) is True
    assert R.craftable(iron, {'raw_iron': 1, 'charcoal': 1}) is True
    assert R.craftable(iron, {'raw_iron': 1}) is False
    assert R.craftable(iron, {'raw_iron': 1, 'coal': 0}) is False, '数量为 0 不算满足'
    for inv in ({'raw_iron': 1, 'coal': 1}, {'raw_iron': 1, 'charcoal': 1}):
        trial = dict(inv)
        assert R.craft(iron, trial) is True
        assert trial.get('iron_ingot') == 1, f'烧铁产出不对：{trial}'


@test('hotbar 默认项在两套号段里都能查到（配置树写名字，两边都得认）')
def t_hotbar_names():
    for name in B.DEFAULT_HOTBAR:
        assert name in I.ITEMS_BY_NAME, f'默认 hotbar 的 {name!r} 不在物品表里'
        assert B.by_name(name) is not None, f'默认 hotbar 的 {name!r} 不是合法方块名'


if __name__ == '__main__':
    sys.exit(main())
