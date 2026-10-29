# -*- coding: utf-8 -*-
"""掉落规则单测（纯函数，零 GL）。

Phase 1 把"挖"与"得到"分开了：内核只问 `drops_for(方块, 工具)`。
这里盯三件事：**确定性**（不用 `random`）、**逐条规则**（石头要镐、玻璃白挖）、
以及**覆盖性**（新加了方块却忘了配掉落 ⇒ 这里要响）。

跑：`python -m tests.test_drops`
"""
from __future__ import annotations

import sys

from tests._util import make_suite

from mcclone3d import blocks as B
from mcclone3d import items as I
from mcclone3d import recipes as R

test, main = make_suite('ALL_DROPS_TESTS_PASSED', '掉落规则')

PICK = I.item_by_name('wooden_pickaxe')
SEED_PARTS = (20, 23, 20, 99)


@test('确定性：同 seed_parts 两次调用结果完全相同（不用 random）')
def t_deterministic():
    # 直接盯"随机源"：`recipes` 模块里不许出现 `random` 的用法
    src = open(R.__file__, encoding='utf-8').read()
    assert 'import random' not in src and 'random.' not in src, \
        '掉落规则里出现了 random —— 掉落数量/概率必须可复现（录制、回放、对拍都靠这条）'
    # 同一坐标调两次（含跨调用、跨列表对象）必须一模一样
    for bid in (B.COAL_ORE, B.LEAVES, B.STONE, B.GRASS, B.IRON_ORE):
        a = R.drops_for(bid, PICK, seed_parts=SEED_PARTS)
        b = R.drops_for(bid, PICK, seed_parts=tuple(SEED_PARTS))
        assert a == b, f'{B.name_of(bid)} 两次调用结果不同：{a} vs {b}'
    # 换坐标**应该**能变（否则说明 seed_parts 根本没进哈希 —— "确定性"会退化成"常数"）
    counts = {R.drops_for(B.COAL_ORE, PICK, seed_parts=(x, 10, 10, 5))[0][1]
              for x in range(0, 60)}
    assert counts <= {1, 2}, f'煤矿掉落数量越界：{sorted(counts)}'
    assert len(counts) == 2, f'煤矿掉落数量只有 {sorted(counts)} —— 数量上下限没生效'


@test('石头：带镐掉圆石；徒手一无所获（Phase 1 的核心门槛）')
def t_stone_needs_pick():
    cobble = I.item_by_name('cobble')
    got = R.drops_for(B.STONE, PICK, seed_parts=SEED_PARTS)
    assert got == [(cobble.id, 1)], f'石头+镐该掉 1 个圆石，实际 {got}'
    assert R.drops_for(B.STONE, None) == [], '徒手挖石头居然有掉落（该白挖）'
    # 不对路工具也是白挖（斧/铲/剑都不行）
    for name in ('wooden_axe', 'wooden_shovel', 'wooden_sword'):
        assert R.drops_for(B.STONE, I.item_by_name(name)) == [], \
            f'{name} 挖石头居然有掉落'
    # 三档镐都要掉（等级只影响快慢，不影响掉不掉）
    for name in ('wooden_pickaxe', 'stone_pickaxe', 'iron_pickaxe'):
        assert R.drops_for(B.STONE, I.item_by_name(name)) == [(cobble.id, 1)], \
            f'{name} 挖石头该掉圆石'


@test('玻璃 / 树叶：玻璃永远白挖；树叶只可能偶发掉苹果')
def t_glass_leaves():
    for tool in (None, PICK, I.item_by_name('wooden_sword')):
        assert R.drops_for(B.GLASS, tool) == [], '玻璃挖了就是白挖（MC 同款，只能烧）'
    apple = I.item_by_name('apple')
    # 树叶：单点结果只允许是 [] 或 [(apple, 1)]（不能掉树叶本身，更不能掉别的）
    kinds = set()
    for x in range(0, 120):
        got = R.drops_for(B.LEAVES, None, seed_parts=(x, 5, 5, 7))
        assert got in ([], [(apple.id, 1)]), f'树叶在 x={x} 掉出了 {got}'
        kinds.add(bool(got))
    # 必须**两种都出现过**：否则"偶发"退化成"必掉"或"永不掉"，这条断言就抓不到
    assert kinds == {True, False}, \
        f'树叶的偶发掉落退化成了单一结果（出现过掉落={True in kinds}，没掉落={False in kinds}）'


@test('煤矿石：带镐掉 1~2 个煤，且上下限都被覆盖到')
def t_coal_ore():
    coal = I.item_by_name('coal')
    counts = set()
    for x in range(0, 80):
        got = R.drops_for(B.COAL_ORE, PICK, seed_parts=(x, 12, 12, 3))
        assert len(got) == 1 and got[0][0] == coal.id, f'煤矿该只掉煤，实际 {got}'
        n = got[0][1]
        assert 1 <= n <= 2, f'煤矿掉落数量 {n} 不在 1~2'
        counts.add(n)
    assert counts == {1, 2}, f'煤矿只掉出过 {sorted(counts)} —— 上限/下限没被覆盖'
    assert R.drops_for(B.COAL_ORE, None) == [], '徒手挖煤矿石该白挖'


@test('铁矿石 / 草 / 泥 / 木：掉对应的东西')
def t_common_blocks():
    cases = ((B.IRON_ORE, PICK, 'raw_iron'),
             (B.GRASS, None, 'dirt'),          # 草方块挖掉掉泥土（MC 同款）
             (B.DIRT, None, 'dirt'),
             (B.SAND, None, 'sand'),
             (B.LOG, None, 'log'),
             (B.PLANKS, None, 'planks'),
             (B.COBBLE, PICK, 'cobble'),
             (B.BRICK, PICK, 'brick'),
             (B.FURNACE, PICK, 'furnace'),
             (B.CRAFTING_TABLE, None, 'crafting_table'),
             (B.GRAVEL, None, 'gravel'),
             (B.SNOW, None, 'snow'))
    for bid, tool, want in cases:
        got = R.drops_for(bid, tool, seed_parts=SEED_PARTS)
        assert got == [(I.item_by_name(want).id, 1)], \
            f'{B.name_of(bid)} 该掉 1 个 {want}，实际 {got}'


@test('无掉落概念的方块：空气 / 水 / 基岩 一律空')
def t_no_drop_blocks():
    for bid in (B.AIR, B.WATER, B.BEDROCK):
        for tool in (None, PICK, I.item_by_name('iron_pickaxe')):
            assert R.drops_for(bid, tool) == [], f'{B.name_of(bid)} 不该有掉落'


@test('覆盖性：每个方块名都在 DROP_TABLE 里，或被 as_item 兜住')
def t_coverage():
    # ① 表里登记过的，掉落物名必须真实存在（防手写错名 ⇒ 到运行时才 KeyError）
    for bid, (name, lo, hi) in R.DROP_TABLE.items():
        assert B.by_id(bid) is not None, f'DROP_TABLE 里有未知方块 id {bid}'
        assert lo <= hi, f'{B.name_of(bid)} 的数量区间反了：{lo}..{hi}'
        if name is not None:
            assert name in I.ITEMS_BY_NAME, \
                f'{B.name_of(bid)} 掉落 {name!r} 不在物品表里（死数据）'
    # ② 每个方块要么在表里、要么能被 as_item 兜住、要么是**没有掉落概念**的。
    #    `water` 是第三种：它没有对应物品、也永远不会被"挖掉"（内核 can_break 就拒），
    #    所以这里显式列出它 —— 而不是把断言放宽成"随便什么都行"。
    NO_DROP = (B.AIR, B.WATER, B.BEDROCK)
    for b in B.all_blocks():
        if b.id in NO_DROP:
            continue
        in_table = b.id in R.DROP_TABLE
        by_item = R.as_item(b.id) is not None
        assert in_table or by_item, \
            f'{b.name}(id={b.id}) 既不在 DROP_TABLE 也没有对应物品 ⇒ 挖了什么都掉不出来'
    # 三种"没有掉落概念"的方块必须真的什么都不掉
    for bid in NO_DROP:
        assert R.drops_for(bid, PICK) == [], f'{B.name_of(bid)} 不该有掉落'
    # ③ 矿石/石类必须在表里显式登记（它们**故意**与同名物品不同：石头→圆石、矿石→材料）
    for bid in (B.STONE, B.COAL_ORE, B.IRON_ORE, B.GRASS):
        assert bid in R.DROP_TABLE, f'{B.name_of(bid)} 的掉落必须显式登记（不能靠同名兜底）'


@test('as_item：方块 → 物品；没物品的方块返回 None（不抛异常）')
def t_as_item():
    for b in B.all_blocks():
        it = R.as_item(b.id)
        if it is None:
            continue
        # 别名登记的格子（如 `lever_on`）指向"关"的那件物品 ⇒ block_id 与它不同
        assert it.id >= I.ITEM_BASE
        assert it.block_id == b.id or B.BLOCK_ITEM_ALIAS.get(b.name) == it.name, \
            f'{b.name} 与物品 {it.name} 的对应关系不合法'
    for bid in (B.WATER, B.BEDROCK, B.COAL_ORE, B.IRON_ORE):
        assert R.as_item(bid) is None, f'{B.name_of(bid)} 不该有对应物品'
    assert R.as_item(B.AIR) is None, '空气不该有对应物品'


@test('output_item：优先同名物品，没有就回退到指定材料')
def t_output_item():
    # 有同名物品的方块：拿到它自己
    it = R.output_item(B.STONE, 'cobble')
    assert it is not None and it.name == 'stone', f'石头该拿到"石头物品"，实际 {it}'
    # 没有同名物品的方块（煤矿石）：回退到指定材料
    it2 = R.output_item(B.COAL_ORE, 'coal')
    assert it2 is not None and it2.name == 'coal', f'煤矿石该回退到煤，实际 {it2}'
    # 回退名写错要当场炸（不许静默返回 None）
    try:
        R.output_item(B.COAL_ORE, 'no_such_item')
    except KeyError:
        pass
    else:
        raise AssertionError('回退名写错必须抛 KeyError')


if __name__ == '__main__':
    sys.exit(main())
