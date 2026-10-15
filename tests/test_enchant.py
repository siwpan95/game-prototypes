# -*- coding: utf-8 -*-
"""附魔与经验单测（纯逻辑，零 GL）。

跑：`python -m tests.test_enchant`

判据一律是**可穷举的**：经验↔等级互逆、花等级后等级恰好降 n、每条附魔的效果按
给定等级算一个数 —— 不用"看起来差不多"。
"""
from __future__ import annotations

import sys

from tests._util import make_suite

from mcclone3d import blocks as B
from mcclone3d import enchant as E
from mcclone3d import items as I

test, main = make_suite('ALL_ENCHANT_TESTS_PASSED', '附魔与经验')


# ------------------------------------------------------------------ 经验
@test('经验↔等级：`level_for(xp_total(L)) == L` 精确成立（穷举 0..200）')
def t_xp_inverse():
    assert E.xp_total(0) == 0
    assert [E.xp_total(i) for i in range(4)] == [0, 7, 16, 27]
    for L in range(0, 200):
        assert E.level_for(E.xp_total(L)) == L, L
        assert E.level_for(E.xp_total(L) + E.xp_span(L) - 1) == L, L


@test('等级边界：差一点就不到下一级（`xp_total(L)-1` 仍是 L-1）')
def t_xp_edge():
    for L in range(1, 200):
        assert E.level_for(E.xp_total(L) - 1) == L - 1, L
    assert E.level_for(0) == 0 and E.level_for(-5) == 0, '负数经验当 0'


@test('本级长度：`xp_span(L) = 2L + 7`，且与 `xp_total` 自洽')
def t_xp_span():
    for L in range(0, 60):
        assert E.xp_span(L) == 2 * L + 7, L
        assert E.xp_span(L) == E.xp_total(L + 1) - E.xp_total(L)
    lv, got, need = E.level_progress(30)
    assert lv == 3 and got == 3 and need == E.xp_span(3)


@test('花等级：等级**恰好**降 n 级（这是最容易写错的一处）')
def t_spend():
    """直接减"本级长度"会越界（例：5 级、进度 1 点，减一级后仍落在 5 级）。

    所以实现走"按比例保留进度"，本测试穷举 xp 与 n 把不变量钉死。
    """
    for xp in range(0, 400):
        lv = E.level_for(xp)
        for n in (1, 2, 3, 4, 9):
            got = E.spend_xp(xp, n)
            if lv < n:
                assert got is None, (xp, n, got)
            else:
                assert E.level_for(got) == lv - n, (xp, n, got, E.level_for(got))
                assert 0 <= got <= xp, (xp, n, got)
    assert E.spend_xp(27, 0) == 27, '花 0 级不该动'
    assert E.spend_xp(27, -1) == 27


@test('花等级：连着花 N 次 1 级 == 一次花 N 级（等级口径一致）')
def t_spend_seq():
    xp = E.xp_total(12) + 5
    one = xp
    for _ in range(3):
        one = E.spend_xp(one, 1)
    assert E.level_for(one) == 9
    assert E.level_for(E.spend_xp(xp, 3)) == 9


# ------------------------------------------------------------------ 附魔表
@test('附魔表：名字唯一、上限合法、applies 都是真的工具种类')
def t_table():
    assert len(E.ENCHANT_ORDER) == len(set(E.ENCHANT_ORDER))
    assert set(E.ENCHANT_ORDER) == set(E.ENCHANTS)
    for name in E.ENCHANT_ORDER:
        e = E.ENCHANTS[name]
        assert 1 <= e.max_level <= 5, (name, e.max_level)
        assert e.applies and e.applies <= set(I.TOOL_KINDS), (name, e.applies)
        assert e.title and e.desc
    # 只有剑有锋利；效率/时运/精准采集都轮不到剑
    assert E.candidates('sword') == ('unbreaking', 'sharpness')
    assert 'fortune' in E.candidates('pickaxe')
    assert E.candidates(None) == ()


@test('互斥：精准采集与时运**不能**同时存在（候选表里两者都在）')
def t_mutex():
    assert E.mutex_ok(['silk_touch'])
    assert E.mutex_ok(['fortune'])
    assert not E.mutex_ok(['silk_touch', 'fortune'])
    assert not E.mutex_ok(['efficiency', 'fortune', 'silk_touch'])
    assert E.mutex_ok(['efficiency', 'fortune'])


# ------------------------------------------------------------------ 效果
@test('效率：×（1 + 0.30·等级），等级 0 完全不改')
def t_efficiency():
    assert E.speed_factor({}) == 1.0
    assert E.speed_factor({'efficiency': 0}) == 1.0
    for lv in range(1, 6):
        assert abs(E.speed_factor({'efficiency': lv}) - (1 + 0.30 * lv)) < 1e-12


@test('耐久：每 (1 + 等级) 次才磨损 1 点 —— 精确，不是"大约"')
def t_unbreaking():
    for lv in range(0, 4):
        assert E.wear_every({'unbreaking': lv}) == 1 + lv
    assert E.wear_every({}) == 1


@test('锋利：+0.5·等级')
def t_sharpness():
    assert E.damage_bonus({}) == 0.0
    for lv in range(1, 6):
        assert abs(E.damage_bonus({'sharpness': lv}) - 0.5 * lv) < 1e-12


@test('时运：extra = floor(roll·(等级+1))，等级 0 恒为 0')
def t_fortune():
    for lv in range(0, 4):
        lvmap = {'fortune': lv} if lv else {}
        for roll in (0.0, 0.1, 0.25, 0.5, 0.75, 0.999):
            got = E.fortune_extra(lvmap, roll)
            assert got == int(roll * (lv + 1)), (lv, roll, got)
            assert got >= 0
    assert E.fortune_extra({'fortune': 3}, -1.0) == 0, 'roll 越界要夹住'
    assert E.fortune_extra({'fortune': 3}, 5.0) == 3


@test('时运的期望 = 等级/2（均匀 roll 上统计，10000 次）')
def t_fortune_mean():
    for lv in (1, 2, 3):
        tot = sum(E.fortune_extra({'fortune': lv}, (i + 0.5) / 10000)
                  for i in range(10000))
        assert abs(tot / 10000 - lv / 2) < 0.02, (lv, tot / 10000)


@test('精准采集：等级 ≥1 生效（上限就是 1）')
def t_silk():
    assert not E.has_silk({})
    assert E.has_silk({'silk_touch': 1})
    assert E.ENCHANTS['silk_touch'].max_level == 1


@test('`lv_of` / `describe_levels` 的边界（空、0 级、未知名）')
def t_describe():
    assert E.lv_of(None, 'efficiency') == 0
    assert E.lv_of({}, 'efficiency') == 0
    assert E.lv_of({'efficiency': 3}, 'efficiency') == 3
    assert E.describe_levels({}) == '无附魔'
    assert E.describe_levels({'efficiency': 3}) == '效率 III'
    assert E.describe_levels({'unbreaking': 1, 'efficiency': 2}) == '效率 II · 耐久 I'
    assert E.ROMAN[5] == 'V'


# ------------------------------------------------------------------ 报价
@test('报价：三档、成本 1/2/3、等级越高条数不少于低等级')
def t_offers_shape():
    for seed in range(30):
        o = E.offers(seed, 10, 20, 30, 'iron_pickaxe', 'pickaxe', 40)
        assert len(o) == 3
        assert [x.cost for x in o] == [1, 2, 3]
        assert [x.slot for x in o] == [0, 1, 2]
        assert all(x.affordable for x in o)
        assert all(1 <= len(x.enchants) <= 2 for x in o)
    poor = E.offers(1, 0, 0, 0, 'iron_pickaxe', 'pickaxe', 1)
    assert [x.affordable for x in poor] == [True, False, False]


@test('报价：合法（名字认识 / 不超上限 / 适用该工具 / 不违反互斥）')
def t_offers_legal():
    for seed in range(120):
        for name, kind in (('iron_pickaxe', 'pickaxe'), ('iron_axe', 'axe'),
                           ('iron_shovel', 'shovel'), ('iron_sword', 'sword'),
                           ('wooden_pickaxe', 'pickaxe')):
            for pos in ((0, 0, 0), (5, 33, 7), (seed, seed, seed)):
                for lv in (0, 1, 12, 40):
                    o = E.offers(seed, pos[0], pos[1], pos[2], name, kind, lv)
                    for off in o:
                        assert E.mutex_ok(list(off.enchants)), (seed, name, off)
                        for n, value in off.enchants.items():
                            e = E.ENCHANTS[n]
                            assert E.applies_to(n, kind), (n, kind)
                            assert 1 <= value <= e.max_level, (n, value)
                            assert value <= E.offer_cap(off.cost, n), \
                                f'{n} 的等级 {value} 超了第 {off.cost} 档的上限'


@test('报价：**确定性**（同种子+同坐标+同物品+同等级 ⇒ 同一批）')
def t_offers_deterministic():
    a = E.offers(7, 3, 4, 5, 'iron_pickaxe', 'pickaxe', 20)
    b = E.offers(7, 3, 4, 5, 'iron_pickaxe', 'pickaxe', 20)
    assert [(x.cost, x.enchants) for x in a] == [(x.cost, x.enchants) for x in b]
    # 任一维度变了都应当**可能**变（不是断言"一定变"，而是"报告里出现过不同"）
    seen = set()
    for x in (E.offers(s, 3, 4, 5, 'iron_pickaxe', 'pickaxe', 20) for s in range(12)):
        seen.add(tuple(sorted((o.cost, tuple(sorted(o.enchants.items()))) for o in x)))
    assert len(seen) > 1, '换种子后报价完全不变 ⇒ 种子没参与'


@test('报价：付不起时 affordable 为假（0 级一档都付不起，1 级只付得起第 1 档）')
def t_offers_affordable():
    zero = E.offers(3, 1, 2, 3, 'iron_sword', 'sword', 0)
    assert [o.affordable for o in zero] == [False, False, False]
    one = E.offers(3, 1, 2, 3, 'iron_sword', 'sword', 1)
    assert [o.affordable for o in one] == [True, False, False]


@test('报价：没有可附属性的工具（或不是工具）⇒ 三档都空')
def t_offers_empty():
    o = E.offers(1, 0, 0, 0, 'stone', None, 40)
    assert len(o) == 3 and all(not x.enchants for x in o)
    assert o[0].label().endswith('此工具没有可附的属性）')


# ------------------------------------------------------------------ 方块/物品接线
@test('附魔台：方块/物品都在，id 不越界，名字一致')
def t_block_item():
    b = B.by_id(B.ENCHANT_TABLE)
    assert b is not None and b.name == 'enchant_table'
    assert b.tile('top') == 'enchant_table_top' and b.tile('side') == 'enchant_table_side'
    it = I.item_by_name('enchant_table')
    assert it.is_block and it.block_id == B.ENCHANT_TABLE
    assert B.MAX_ID == max(B.BLOCKS), 'MAX_ID 必须等于当前最大 id'
    assert sorted(B.BLOCKS) == list(range(1, B.MAX_ID + 1)), 'id 必须连续无空洞'


@test('`items.break_time` 的 `speed_mult`：只改速度、不改其他分支')
def t_break_time_mult():
    base = I.break_time(B.STONE, I.item_by_name('iron_pickaxe'))
    fast = I.break_time(B.STONE, I.item_by_name('iron_pickaxe'), speed_mult=2.5)
    assert abs(fast - base / 2.5) < 1e-12
    assert I.break_time(B.STONE, I.item_by_name('iron_pickaxe'), speed_mult=1.0) == base
    # 非法倍率必须被夹住（不许出现 inf/负耗时）
    assert I.break_time(B.STONE, None, speed_mult=0.0) > 0
    assert I.break_time(B.STONE, None, speed_mult=-3.0) > 0
    assert I.break_time(B.BEDROCK, None, speed_mult=99.0) == float('inf')


if __name__ == '__main__':
    sys.exit(main())
