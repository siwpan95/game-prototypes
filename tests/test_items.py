# -*- coding: utf-8 -*-
"""物品 / 工具 / 挖掘规则单测（纯数据 + 纯函数，零 GL）。

Phase 1 的核心契约是**两套编号并存**（`blocks.py` 用 1..31，`items.py` 用 100 起），
所以这里的判据全都在盯"一个整数到底是方块还是物品"以及"挖掘耗时按公式算得对不对"。

跑：`python -m tests.test_items`
"""
from __future__ import annotations

import sys

from tests._util import make_suite

from mcclone3d import blocks as B
from mcclone3d import items as I
from mcclone3d import recipes as R

test, main = make_suite('ALL_ITEMS_TESTS_PASSED', '物品与工具')


@test('id 契约：无重复、都 ≥ ITEM_BASE、连续且只追加不改号')
def t_id_contract():
    ids = sorted(I.ITEMS)
    assert len(ids) == len(set(ids)), f'物品 id 有重复：{ids}'
    assert ids, '物品表是空的'
    assert min(ids) >= I.ITEM_BASE, f'物品 id 落进方块号段：最小值 {min(ids)} < {I.ITEM_BASE}'
    assert ids == list(range(I.ITEM_BASE, I.ITEM_BASE + len(ids))), \
        f'物品 id 出现断号（`_defs()` 的顺序即 id，断号会让"顺序即 id"这条约定失效）：{ids}'
    # 号段判据的**边界**必须钉死：99 是方块侧，100 是物品侧
    assert not I.is_item_id(I.ITEM_BASE - 1), '99 不该被当成物品 id'
    assert I.is_item_id(I.ITEM_BASE), '100 必须被当成物品 id'
    # 名字唯一 + 双向可查
    names = [it.name for it in I.all_items()]
    assert len(names) == len(set(names)), f'物品名重复：{names}'
    # 两个索引（id→Item / 名字→Item）必须**同代**：长度相等，且互相查得回来。
    # 漏了这条的话，"往表里塞了个重名/重 id 的物品"只会表现成某处莫名的 KeyError。
    assert len(I.ITEMS_BY_NAME) == len(I.ITEMS), \
        f'两个索引长度不等：ITEMS={len(I.ITEMS)} ITEMS_BY_NAME={len(I.ITEMS_BY_NAME)}（有重名/漏登记）'
    for it in I.all_items():
        assert I.item_by_name(it.name).id == it.id, f'{it.name} 名字→id 不一致'
        assert I.item(it.id).name == it.name, f'{it.id} id→名字 不一致'
        assert I.ITEMS_BY_NAME.get(it.name) is I.ITEMS.get(it.id), \
            f'{it.name} 在两个索引里不是同一个对象（索引不同代）'
    for bad in ('no_such_item', ''):
        try:
            I.item_by_name(bad)
        except KeyError:
            pass
        else:
            raise AssertionError(f'未知物品名 {bad!r} 必须抛 KeyError（不许静默返回 None）')


@test('is_item_id / is_block_id 判据互斥，且非整数一律不认')
def t_id_predicates():
    for v in (0, 1, 31, I.ITEM_BASE - 1):
        assert I.is_block_id(v), f'{v} 该被判为方块 id'
        assert not I.is_item_id(v), f'{v} 不该被判为物品 id'
    for v in (I.ITEM_BASE, 131, 9999):
        assert I.is_item_id(v), f'{v} 该被判为物品 id'
        assert not I.is_block_id(v), f'{v} 不该被判为方块 id'
    # 负数是"谁都不是"，不是方块（否则 `-1` 会被当方块去查表）
    for v in (-1, -100):
        assert not I.is_block_id(v) and not I.is_item_id(v), f'{v} 不该属于任何一个号段'
    for v in ('100', 100.0, None, [100]):
        assert not I.is_item_id(v) and not I.is_block_id(v), \
            f'{v!r} 不是整数，却通过了号段判据（会静默算错）'


@test('方块物品与方块表一一对得上（有物品的方块必须同名同 id）')
def t_block_items():
    for b in B.all_blocks():
        it = R.as_item(b.id)
        if it is None:
            continue
        assert it.is_block, f'{b.name} 对应的物品 kind={it.kind}，不是方块物品'
        # Phase 3：别名登记的格子（`lever_on`）指向"关"那件物品 ⇒ block_id 不同，
        # 判据改成"要么同 id，要么别名表显式登记了这条对应关系"
        assert it.block_id == b.id or B.BLOCK_ITEM_ALIAS.get(b.name) == it.name, \
            f'{b.name} 的物品 block_id={it.block_id} 对不上，且别名表没登记'
        # Phase 3：**状态 id 允许不同名**，但必须在别名表里显式登记
        # （`lever_on` → `lever`：一个物品对应多个方块状态，见 `BLOCK_ITEM_ALIAS`）
        if it.name != b.name:
            assert B.BLOCK_ITEM_ALIAS.get(b.name) == it.name, \
                f'方块名与物品名不同名，且别名表没登记：{b.name} vs {it.name}'
    # 明确登记"暂时没有物品的方块"：它们不是能拿在手里的东西（水/矿脉/基岩）。
    # 这条断言的作用是**防静默新增**：将来给某个方块加了物品却忘了配，或反过来，
    # 这里会响 —— 而不是等到"挖了掉空气"才发现。
    no_item = sorted(b.name for b in B.all_blocks() if R.as_item(b.id) is None)
    # Phase 2-C：金/钻石矿石与煤/铁同款 —— 挖了掉**材料**、不可放置，
    # 所以也不给方块物品（真需求确认过）。
    # 作物同理：打掉掉**小麦**（`wheat`），而"一株麦子"不是能拿在手里的方块。
    assert no_item == ['bedrock', 'coal_ore', 'crop', 'diamond_ore', 'gold_ore',
                       'iron_ore', 'water'], \
        f'没有对应物品的方块集合变了：{no_item}（改这条要先确认是真需求）'


@test('break_time 按公式对拍：t = hardness × 惩罚 / 工具速度')
def t_break_time_formula():
    stone = B.by_id(B.STONE)
    assert stone is not None, '测试前提：方块表里要有石头'
    # 徒手：不对路 ⇒ 速度 1/5（NEEDS_TOOL_PENALTY），所以 t = hardness × 5
    bare = I.break_time(B.STONE, None)
    assert abs(bare - stone.hardness * I.NEEDS_TOOL_PENALTY) < 1e-9, \
        f'徒手挖石头 {bare}，公式算出 {stone.hardness * I.NEEDS_TOOL_PENALTY}'
    # 对路工具：t = hardness / TOOL_SPEED[tier]，三档都要对拍（防止只对了一档）
    times = {}
    for name in ('wooden_pickaxe', 'stone_pickaxe', 'iron_pickaxe'):
        it = I.item_by_name(name)
        times[it.tier] = I.break_time(B.STONE, it)
        assert abs(times[it.tier] - stone.hardness / I.TOOL_SPEED[it.tier]) < 1e-9, \
            f'{name} 挖石头 {times[it.tier]}，公式算出 {stone.hardness / I.TOOL_SPEED[it.tier]}'
    # 快慢关系必须与速度表同序（木 < 石 < 铁，即"等级越高越快"）
    assert times[1] > times[2] > times[3], f'工具等级与速度不同序：{times}'
    # 作业书点名的对拍：徒手挖石头 ≈ 木镐的 10 倍
    wooden = times[1]
    assert wooden > 0
    ratio = bare / wooden
    expect = (stone.hardness * I.NEEDS_TOOL_PENALTY) / (stone.hardness / I.TOOL_SPEED[1])
    assert abs(ratio - expect) < 1e-9, f'徒手/木镐 = {ratio}，公式算出 {expect}'
    assert abs(ratio - 10.0) < 1e-9, f'徒手挖石头该是木镐的 10 倍，实际 {ratio}'
    # 空气与水：没有"挖掘耗时"这个概念
    assert I.break_time(B.AIR, None) == 0.0
    assert I.break_time(B.WATER, None) == 0.0
    # 基岩：任何工具都是 inf（内核第二道闸，见 kernel.dig_time）
    for tool in (None, I.item_by_name('iron_pickaxe')):
        t = I.break_time(B.BEDROCK, tool)
        assert t == float('inf'), f'基岩挖得动？{tool} ⇒ {t}'
    # 全覆盖：每个可破坏方块都要算出**有限正数**，否则会出现"永远挖不完"
    for b in B.all_blocks():
        if b.id in (B.AIR, B.WATER, B.BEDROCK):
            continue
        t = I.break_time(b.id, None)
        assert 0.0 < t < float('inf'), f'{b.name} 的徒手挖掘耗时是 {t}（该是有限正数）'
    # 徒手挖**不需要工具**的方块不该吃 5 倍惩罚
    dirt = B.by_id(B.DIRT)
    assert abs(I.break_time(B.DIRT, None) - dirt.hardness) < 1e-9, \
        f'徒手挖泥土 {I.break_time(B.DIRT, None)}，该等于 hardness {dirt.hardness}'


@test('harvest_ok：石类必须带对路镐，土/沙/木徒手也掉，基岩/水永远 false')
def t_harvest_ok():
    pick = I.item_by_name('wooden_pickaxe')
    axe = I.item_by_name('wooden_axe')
    shovel = I.item_by_name('wooden_shovel')
    sword = I.item_by_name('wooden_sword')
    needs_pick = (B.STONE, B.COBBLE, B.COAL_ORE, B.IRON_ORE, B.BRICK,
                  B.FURNACE, B.GLASS)
    for bid in needs_pick:
        assert I.harvest_ok(bid, None) is False, \
            f'{B.name_of(bid)} 徒手居然会掉（石类必须带镐）'
        for tool in (axe, shovel, sword):
            assert I.harvest_ok(bid, tool) is False, \
                f'{B.name_of(bid)} 用 {tool.name} 居然会掉（不对路工具 = 白挖）'
        assert I.harvest_ok(bid, pick) is True, f'{B.name_of(bid)} 带镐却不掉'
    for bid in (B.DIRT, B.GRASS, B.SAND, B.GRAVEL, B.SNOW, B.LOG, B.PLANKS,
                B.CRAFTING_TABLE, B.LEAVES, B.TORCH):
        assert I.harvest_ok(bid, None) is True, f'{B.name_of(bid)} 徒手该能挖到'
    # 基岩 / 水 / 空气：没有掉落概念
    for bid in (B.BEDROCK, B.WATER, B.AIR):
        assert I.harvest_ok(bid, None) is False, f'{B.name_of(bid)} 不该掉落'
        assert I.harvest_ok(bid, pick) is False, f'{B.name_of(bid)} 带镐也不该掉落'
    # 等级不影响"掉不掉"（只影响快慢）—— 三档镐必须一致
    for name in ('wooden_pickaxe', 'stone_pickaxe', 'iron_pickaxe'):
        assert I.harvest_ok(B.STONE, I.item_by_name(name)) is True, f'{name} 挖石头不掉？'


@test('can_break：只有基岩（与水/空气）不可破坏')
def t_can_break():
    # 水也是"不可破坏"的（它不是能被挖掉的方块，只是会被流走/装桶）—— 先前漏了它
    for b in B.all_blocks():
        if b.id in (B.BEDROCK, B.WATER):
            continue
        assert I.can_break(b.id) is True, f'{b.name} 该能被破坏'
    assert I.can_break(B.BEDROCK) is False
    assert I.can_break(B.WATER) is False, '水不该被"挖掉"'
    assert I.can_break(B.AIR) is False


@test('name_of_item 是全定义：未知 id 返回 unknown:<id>，不是 None')
def t_name_of_item():
    for it in I.all_items():
        assert I.name_of_item(it.id) == it.name, f'{it.id} 的名字不对'
    for bad in (0, 1, I.ITEM_BASE - 1, 999999, -5):
        got = I.name_of_item(bad)
        assert got is not None, f'未知物品 id {bad} 返回了 None（存档路径上会炸）'
        assert got == f'unknown:{bad}', f'未知物品 id {bad} 该返回 unknown:{bad}，实际 {got!r}'
    assert I.name_of is I.name_of_item, 'name_of 该是 name_of_item 的别名（口径只有一处）'


@test('堆叠上限：工具 max_stack == 1，方块物品 == 64')
def t_stacking():
    tools = [it for it in I.all_items() if it.is_tool]
    blocks = [it for it in I.all_items() if it.is_block]
    assert tools and blocks, '测试前提：物品表里要有工具与方块物品'
    for it in tools:
        assert it.max_stack == 1, f'{it.name} 的 max_stack={it.max_stack}，工具带耐久不能堆叠'
    for it in blocks:
        assert it.max_stack == 64, f'{it.name} 的 max_stack={it.max_stack}，方块物品该是 64'
        assert it.stack == 64, f'{it.name} 的 stack={it.stack}'
    # 材料默认 64，不能有 0 或负数（会让 take/give 直接算错）
    for it in I.all_items():
        assert it.max_stack >= 1, f'{it.name} 的 max_stack={it.max_stack}'
        if not it.is_tool:
            assert it.max_stack == 64, f'{it.name} 不是工具，max_stack 该是 64'


@test('工具档位与速度表对得上（tier/durability/mines 三个字段不许漂）')
def t_tool_table():
    all_tiers = {it.tier for it in I.all_items() if it.is_tool}
    assert all_tiers == set(I.TOOL_SPEED) - {0} or all_tiers <= set(I.TOOL_SPEED), \
        f'工具档位 {all_tiers} 与 TOOL_SPEED 的键 {sorted(I.TOOL_SPEED)} 对不上'
    for it in I.all_items():
        if not it.is_tool:
            continue
        assert it.tool in I.TOOL_KINDS, f'{it.name} 的 tool={it.tool!r} 不在 TOOL_KINDS 里'
        assert it.tier in I.TOOL_DURABILITY, f'{it.name} 的 tier={it.tier} 没有耐久定义'
        assert it.durability == I.TOOL_DURABILITY[it.tier], \
            f'{it.name} 的 durability={it.durability} 与表值 {I.TOOL_DURABILITY[it.tier]} 不一致'
        assert it.tier in I.TOOL_SPEED, f'{it.name} 的 tier={it.tier} 没有速度定义'
        assert it.mines, f'{it.name} 的 mines 是空的 ⇒ 它挖什么都不"对路"'
        for bid in it.mines:
            assert B.by_id(bid) is not None, f'{it.name} 的 mines 里有未知方块 id {bid}'
    # 每档每类都要有（缺一个就是"某把工具根本不存在"）
    for tier in I.TOOL_DURABILITY:
        kinds = {it.tool for it in I.tools_of_tier(tier)}
        assert kinds == set(I.TOOL_KINDS), f'tier={tier} 的工具种类不全：{sorted(kinds)}'
    # 剑砍树叶 = 对路（树叶是剑的靶子，也是"偶发掉落"的样本）
    sword = I.item_by_name('wooden_sword')
    assert sword.mines_block(B.LEAVES), '剑该对路树叶'


if __name__ == '__main__':
    sys.exit(main())
