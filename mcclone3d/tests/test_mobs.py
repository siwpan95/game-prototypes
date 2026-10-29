# -*- coding: utf-8 -*-
"""Phase 2-B 生物表与实体单测（纯逻辑，零 GL）。

覆盖：`MOBS` 表契约（名字唯一、数值合法、盒模型 `parts` 非空且结构正确、
**掉落里的物品名都在物品表里** —— 防"死掉落"）、`Mob` 实体的初始状态与 id、
`hurt()` 的扣血与状态迁移（被动转逃跑、敌对转追击、致死语义）、
`spawn_allowed()` 的**逐条穷举**（敌对按 `max(方块光, 天光) <= spawn_light_max`，
被动恒真）、以及 `dist_to` / `dist3_to` 的**数值对拍**。

⚠ 这里只测"数据与实体语义"；"AI 怎么走、怎么打、怎么刷"在 `tests/test_ai.py`。

跑：`python -m tests.test_mobs`
"""
from __future__ import annotations

import sys

from tests._util import make_suite

from mcclone3d import items as I
from mcclone3d import mobs as MB
from mcclone3d.mobs import (AI_CHASE, AI_FLEE, AI_IDLE, AI_WANDER, MOBS, Mob,
                            STATE_NAMES, all_kinds, hostile_kinds, mob_kind,
                            passive_kinds, spawn_allowed)

test, main = make_suite('ALL_MOBS_TESTS_PASSED', '生物表与实体')

#: Phase 2-B 规格里点名的三种生物（羊/猪/僵尸）。**只要求"在"，不要求"只有"**
#: —— 后续加生物不该让这条红，但规格里的三种掉一个就是真问题。
SPECIES_REQUIRED = ('sheep', 'pig', 'zombie')


def _vec3(v):
    return (isinstance(v, (tuple, list)) and len(v) == 3
            and all(isinstance(c, (int, float)) for c in v))


# ==================================================================== 生物表
@test('MOBS 表契约：名字唯一、规格里三种都在、数值/盒模型字段合法')
def t_table_contract():
    assert MOBS, '生物表是空的'
    for name in SPECIES_REQUIRED:
        assert name in MOBS, f'规格里的生物 {name!r} 不在表里；现有 {sorted(MOBS)}'
    # 名字唯一：dict 的键天然唯一，但"键 == 定义里的 name"必须自己钉
    for key, kind in MOBS.items():
        assert key == kind.name, f'键 {key!r} 与定义里的 name {kind.name!r} 不一致'
        assert isinstance(kind.title, str) and kind.title, f'{key}: title 空'
        assert isinstance(kind.hostile, bool), f'{key}: hostile 该是 bool'
        # 数值：能被 AI 直接当步长/距离用，所以必须是**正数**
        assert kind.health > 0.0, f'{key}: health={kind.health} 该 > 0'
        assert kind.speed > 0.0, f'{key}: speed={kind.speed} 该 > 0'
        assert kind.chase_speed > 0.0, f'{key}: chase_speed={kind.chase_speed} 该 > 0'
        assert kind.sight > 0.0, f'{key}: sight={kind.sight} 该 > 0'
        assert kind.reach > 0.0, f'{key}: reach={kind.reach} 该 > 0'
        assert kind.attack_cd > 0.0, f'{key}: attack_cd={kind.attack_cd} 该 > 0'
        assert kind.attack >= 0.0, f'{key}: attack={kind.attack} 不该为负'
        assert kind.fall_safe >= 0.0, f'{key}: fall_safe={kind.fall_safe} 不该为负'
        assert kind.width > 0.0 and kind.height > 0.0, \
            f'{key}: 体型 {kind.width}x{kind.height} 该是正数'
        assert 0 <= kind.spawn_light_max <= 15, \
            f'{key}: spawn_light_max={kind.spawn_light_max} 该在 0..15'
        assert kind.spawn_weight > 0.0, f'{key}: spawn_weight 该 > 0'
        # 敌对生物必须真的能造成伤害（否则"会追会打"只是看着像）
        if kind.hostile:
            assert kind.attack > 0.0, f'{key}: 敌对生物 attack=0 ⇒ 追上来也打不动'
        # 盒模型：渲染端按 (相对位置, 尺寸, 颜色) 画六个面 ⇒ 结构不能是空的
        assert kind.parts, f'{key}: parts 为空（渲染端画不出东西）'
        for i, part in enumerate(kind.parts):
            assert isinstance(part, (tuple, list)) and len(part) == 3, \
                f'{key}.parts[{i}] 该是 (位置, 尺寸, 颜色)，实际 {part!r}'
            pos, size, col = part
            assert _vec3(pos), f'{key}.parts[{i}] 位置不是三元组：{pos!r}'
            assert _vec3(size) and all(s > 0.0 for s in size), \
                f'{key}.parts[{i}] 尺寸该是正三元组：{size!r}'
            assert _vec3(col) and all(0.0 <= c <= 1.0 for c in col), \
                f'{key}.parts[{i}] 颜色该在 0..1：{col!r}'


@test('掉落契约：drops 里的物品名**都在物品表里**（防死掉落）+ 数量区间合法')
def t_drops_are_real_items():
    """⚠ 这条盯的是"掉落指向一个不存在的物品"：那种 bug 不会在运行时爆，
    只在玩家打死生物那一刻抛 KeyError（或更糟：静默不掉东西）。"""
    total = 0
    kinds_with_drops = 0
    for kind in all_kinds():
        if kind.drops:
            kinds_with_drops += 1
        for entry in kind.drops:
            assert isinstance(entry, (tuple, list)) and len(entry) == 3, \
                f'{kind.name}: 掉落项该是 (物品名, 数量下限, 数量上限)，实际 {entry!r}'
            name, lo, hi = entry
            assert isinstance(name, str), f'{kind.name}: 掉落物品名该是 str，实际 {name!r}'
            assert name in I.ITEMS_BY_NAME, \
                f'{kind.name} 掉落 {name!r} 不在物品表里 ⇒ 打死会 KeyError（死掉落）'
            assert int(lo) >= 1, f'{kind.name} 掉 {name}: 下限 {lo} 该 ≥ 1（0 就没必要写）'
            assert int(hi) >= int(lo), f'{kind.name} 掉 {name}: 上限 {hi} < 下限 {lo}'
            total += 1
    assert total > 0, '整张表一条掉落都没有 ⇒ 这条用例是空的（狩猎没有产出）'
    assert kinds_with_drops == len(all_kinds()), \
        f'有 {len(all_kinds()) - kinds_with_drops} 种生物不掉任何东西'
    # 掉落必须能真的按名字取出物品 id（`_kill_mob` 就是这么用的）
    for kind in all_kinds():
        for name, _lo, _hi in kind.drops:
            assert I.item_by_name(name).id > 0


@test('mob_kind / all_kinds / passive_kinds / hostile_kinds 的契约')
def t_kind_helpers():
    for name in SPECIES_REQUIRED:
        assert mob_kind(name) is MOBS[name], f'mob_kind({name!r}) 不是表里那一份'
    try:
        mob_kind('no_such_mob')
    except KeyError as exc:
        assert 'no_such_mob' in str(exc), f'报错信息里该带上请求的名字：{exc}'
        assert 'sheep' in str(exc), f'报错信息里该列出合法名字：{exc}'
    else:
        raise AssertionError('未知生物名必须抛 KeyError（不能静默返回 None）')
    # all_kinds：按名字升序、且与表内容一致（顺序稳定 ⇒ 刷怪顺序可复现）
    kinds = all_kinds()
    assert sorted(k.name for k in kinds) == sorted(MOBS), 'all_kinds 与 MOBS 不一致'
    assert [k.name for k in kinds] == sorted(k.name for k in kinds), \
        'all_kinds 该按名字升序（刷怪顺序要可复现）'
    # 被动/敌对是一套**划分**：不重不漏
    passive, hostile = passive_kinds(), hostile_kinds()
    assert all(not k.hostile for k in passive), 'passive_kinds 里有敌对生物'
    assert all(k.hostile for k in hostile), 'hostile_kinds 里有被动生物'
    assert {k.name for k in passive} | {k.name for k in hostile} == set(MOBS), \
        '被动 + 敌对 没覆盖整张表'
    assert not ({k.name for k in passive} & {k.name for k in hostile}), '同一种生物既被动又敌对'
    assert hostile, 'Phase 2-B 至少要有一种敌对生物'
    assert any(k.name == 'zombie' for k in hostile), '僵尸该是敌对生物'
    assert all(k.name != 'zombie' for k in passive)
    # 状态名表：四个状态都要有中文名（HUD 会打印）
    for st in (AI_IDLE, AI_WANDER, AI_CHASE, AI_FLEE):
        assert st in STATE_NAMES and STATE_NAMES[st], f'状态 {st} 没有中文名'


# ==================================================================== 实体
@test('Mob 初始状态：满血 / idle / 位置与 id / 两套距离的初始值')
def t_mob_init():
    kind = mob_kind('sheep')
    m = Mob('sheep', 1.0, 2.0, 3.0)
    assert m.kind is kind, 'Mob 该按名字解析成表里的那一份定义'
    assert m.kind is Mob(kind, 0, 0, 0).kind, '传定义与传名字该等价'
    assert m.pos == [1.0, 2.0, 3.0], f'位置该按脚底中心存：{m.pos}'
    assert m.vel == [0.0, 0.0, 0.0], f'初始速度该是 0：{m.vel}'
    assert m.health == kind.health and m.health > 0.0, f'初始血量该是满血：{m.health}'
    assert m.state == AI_IDLE, f'新生物该是 idle，实际 {m.state}'
    assert m.target is None and m.cd == 0.0 and m.age == 0.0 and m.hurt_t == 0.0
    assert m.on_ground is False, '刚放下的生物不该已经在地面上'
    assert m.alive is True
    assert m.name == kind.name
    assert abs(m.eye_y() - (2.0 + kind.height * 0.85)) < 1e-9, \
        f'eye_y 口径变了：{m.eye_y()}（该是脚底 y=2.0 + 身高×0.85）'
    # id：唯一（游荡方向用 age + id 做确定性伪随机，重复 id 就不是"可对拍"了）
    a, b = Mob('pig', 0, 0, 0), Mob('pig', 0, 0, 0)
    assert a.id != b.id, f'两只生物的 id 撞了：{a.id}'
    assert Mob._next_id > a.id and Mob._next_id > b.id, '_next_id 没有推进'
    # 未知生物名当场爆（不静默当成"某种默认生物"）
    try:
        Mob('no_such_mob', 0, 0, 0)
    except KeyError:
        pass
    else:
        raise AssertionError('Mob 该拒绝未知生物名')
    # dump：HUD / 快照用的字段齐
    d = m.dump()
    for key in ('kind', 'pos', 'yaw', 'health', 'state'):
        assert key in d, f'dump 缺字段 {key}'
    assert d['kind'] == 'sheep' and d['health'] == m.health


@test('hurt：扣血精确、非致死返回 False、致死返回 True 且 alive 变 False')
def t_hurt_numbers():
    m = Mob('sheep', 0.0, 0.0, 0.0)
    full = m.health
    assert m.hurt(3.0) is False, '打掉 3 点不该死'
    assert abs(m.health - (full - 3.0)) < 1e-9, f'扣血不对：{m.health}'
    assert abs(m.hurt_t - 0.35) < 1e-9, f'受击闪烁计时该被置位：{m.hurt_t}'
    # 0 与负数：不是"伤害"，不该扣血也不该算受击
    before = m.health
    m.hurt_t = 0.0
    assert m.hurt(0.0) is False and m.health == before, 'hurt(0) 改了血量'
    assert m.hurt(-5.0) is False and m.health == before, 'hurt(负数) 改了血量'
    assert m.hurt_t == 0.0, 'hurt(0) 也置了受击计时'
    # 致死：返回 True，血量归零附近，alive False
    assert m.hurt(before) is True, '血量刚好打空却报"没死"'
    assert m.health <= 0.0 and m.alive is False, f'打死了却还活着：{m.health} {m.alive}'
    # 死后再打：不再扣血、不再报死（避免"死两次"重复计数）
    assert m.hurt(99.0) is False, '死了还能再被打死一次'
    assert m.health <= 0.0
    # 过量伤害不会把血量打到负很多（-0.0 级别即可）
    m2 = Mob('zombie', 0.0, 0.0, 0.0)
    assert m2.hurt(999.0) is True and m2.alive is False
    assert m2.health <= 0.0


@test('hurt：被动转 AI_FLEE（6 秒）、敌对转 AI_CHASE；致死一击不转逃跑')
def t_hurt_state_transition():
    for name in ('sheep', 'pig'):
        m = Mob(name, 0.0, 0.0, 0.0)
        assert not m.kind.hostile, f'测试前提：{name} 该是被动生物'
        assert m.state == AI_IDLE
        assert m.hurt(1.0) is False, f'{name} 打 1 点不该死'
        assert m.state == AI_FLEE, f'{name} 被打后该转逃跑，实际 {m.state}'
        assert abs(m.flee_t - 6.0) < 1e-9, f'{name} 逃跑时长该是 6 秒，实际 {m.flee_t}'
        assert m.alive is True
    zombie = Mob('zombie', 0.0, 0.0, 0.0)
    assert zombie.kind.hostile, '测试前提：僵尸该是敌对生物'
    assert zombie.state == AI_IDLE
    assert zombie.hurt(1.0) is False
    assert zombie.state == AI_CHASE, f'敌对生物被打后该立刻锁定追击，实际 {zombie.state}'
    assert zombie.flee_t == 0.0, '敌对生物不该进逃跑状态'
    # 致死一击：被动生物不需要"逃跑状态"（它已经死了），状态保持原样
    sheep = Mob('sheep', 0.0, 0.0, 0.0)
    assert sheep.hurt(sheep.health) is True
    assert sheep.state == AI_IDLE, \
        f'致死一击不该留下逃跑状态（免得调用方看到"死了还在跑"）：{sheep.state}'
    assert sheep.alive is False


# ==================================================================== 刷怪判据
@test('spawn_allowed：逐条穷举（敌对 = max(方块光,天光) ≤ spawn_light_max；被动恒真）')
def t_spawn_allowed_exhaustive():
    """纯函数 ⇒ 把取值范围**全部走一遍**，并与文档口径逐条对拍。

    文档口径（`mobs.spawn_allowed` 的 docstring）：敌对生物的方块光与天光折算值
    都不超过 `spawn_light_max` ⇒ 只在暗处/夜里出现；被动生物不挑光。
    这里把"不超过"实现成 `max(blk, sky) <= spawn_light_max`（含边界）。
    """
    lo, hi = 0, 15
    for kind in all_kinds():
        for blk in range(lo, hi + 1):
            for sky in range(lo, hi + 1):
                for night in (False, True):
                    got = spawn_allowed(kind, blk, sky, night)
                    assert isinstance(got, bool), \
                        f'{kind.name}: spawn_allowed 该返回 bool，实际 {got!r}'
                    if kind.hostile:
                        want = max(blk, sky) <= kind.spawn_light_max
                    else:
                        want = True
                    assert got is want, (
                        f'{kind.name}(hostile={kind.hostile}, light_max='
                        f'{kind.spawn_light_max}) 在 blk={blk} sky={sky} night={night} '
                        f'下返回 {got}，文档口径要求 {want}')
        # 超范围的输入也不许翻车（"亮到爆"当然不能刷敌对）
        if kind.hostile:
            for weird in (16, 20, 255):
                assert spawn_allowed(kind, weird, 0, True) is False, \
                    f'{kind.name}: 方块光 {weird} 还能刷敌对'
                assert spawn_allowed(kind, 0, weird, False) is False, \
                    f'{kind.name}: 天光 {weird} 还能刷敌对'


@test('spawn_allowed：夜里的真实取值能刷敌对、正午露天刷不出来（边界两侧）')
def t_spawn_allowed_daynight():
    """把 test_ai 里真实世界的数值**先在纯函数这层钉住**（分层定位：判据错了在这里看）。

    真实取值（实测）：夜里的折算天光 = `round(15 × NIGHT_FLOOR)` = 3；
    正午露天 = 15。僵尸的 `spawn_light_max = 7`。
    """
    zombie = mob_kind('zombie')
    night_sky = int(round(15 * 0.18))                      # NIGHT_FLOOR = 0.18
    assert zombie.spawn_light_max < 15, '测试前提：敌对生物的天光阈值该低于满亮'
    # 夜里露天：方格光 0、折算天光 3 ⇒ 能刷
    assert spawn_allowed(zombie, 0, night_sky, True) is True, \
        '夜里露天（天光折算 3）该能刷敌对生物'
    # 白天露天：天光满 15 ⇒ 刷不出来（**不管是不是黑天**）
    for night in (False, True):
        assert spawn_allowed(zombie, 0, 15, night) is False, \
            f'正午露天（天光 15, night={night}）不该刷出敌对生物'
    # 边界：正好等于阈值能刷，多 1 就不行
    t = zombie.spawn_light_max
    assert spawn_allowed(zombie, t, 0, False) is True, f'光 {t}（= 阈值）该允许'
    assert spawn_allowed(zombie, t + 1, 0, False) is False, f'光 {t + 1}（> 阈值）该拒绝'
    # 被动生物：白天夜里都刷
    for kind in passive_kinds():
        for blk, sky, night in ((0, 15, False), (15, 15, False), (0, 3, True), (15, 15, True)):
            assert spawn_allowed(kind, blk, sky, night) is True, \
                f'{kind.name} 是被动生物，不该挑光（blk={blk} sky={sky} night={night}）'


# ==================================================================== 距离
@test('dist_to / dist3_to：数值对拍（水平距离不吃 y；只吃两个参数）')
def t_distance_numbers():
    m = Mob('sheep', 0.0, 0.0, 0.0)
    # 3-4-5 直角三角：水平距离必须**精确**是 5
    assert abs(m.dist_to(3.0, 4.0) - 5.0) < 1e-12, f'dist_to(3,4) = {m.dist_to(3, 4)}'
    assert m.dist_to(0.0, 0.0) == 0.0, '同点的距离该是 0'
    # 5-12-13：水平 5（3,4）+ 竖直 12 ⇒ 三维 13
    assert abs(m.dist3_to(3.0, 4.0, 12.0) - 13.0) < 1e-12, \
        f'dist3_to(3,4,12) = {m.dist3_to(3, 4, 12)}'
    assert abs(m.dist3_to(0.0, 0.0, 12.0) - 12.0) < 1e-12, '纯竖直距离不对'
    # dist_to **只吃两个参数**（历史坑：早先叫 ray_to，签名被读错）
    high = Mob('sheep', 0.0, 100.0, 0.0)
    assert abs(high.dist_to(3.0, 4.0) - 5.0) < 1e-12, \
        f'dist_to 不该把 y 算进去：{high.dist_to(3, 4)}'
    # 同高（y 都是 100）时三维距离退化成水平距离 5
    #   （曾把参数写成 (3, 4, 100)：y=4 与身位 y=100 差了 96 格，量出来 138.65）
    assert abs(high.dist3_to(3.0, 100.0, 4.0) - 5.0) < 1e-12, \
        f'dist3_to 同高时该退化成水平距离：{high.dist3_to(3.0, 100.0, 4.0)}'
    try:
        m.dist_to(1.0, 2.0, 3.0)
    except TypeError:
        pass
    else:
        raise AssertionError('dist_to 只该吃 (x, z) 两个参数 —— 多一个参数必须当场爆')
    # 负方向 / 对称性（AI 里目标可能在身后）
    p = Mob('zombie', 10.0, 3.0, -4.0)
    assert abs(p.dist_to(13.0, 0.0) - 5.0) < 1e-12
    assert abs(p.dist_to(13.0, 0.0) - p.dist_to(13.0, 0.0)) < 1e-12


if __name__ == '__main__':
    sys.exit(main())
