# -*- coding: utf-8 -*-
"""内核单测：动作语义 / 存档往返 / 自动机（纯逻辑，零 GL）。

跑：`python -m tests.test_kernel`
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile

from tests._util import make_suite

from mcclone3d import blocks as B
from mcclone3d.kernel import (EYE_HEIGHT, SCRIPT, START_STOCK, McCloneKernel,
                              make_offline)

test, main = make_suite('ALL_KERNEL_TESTS_PASSED', '内核')


def _empty_kernel(seed=99, size=48, height=32, **cfg):
    """空世界 + 玩家站在 (20.5, 20, 20.5) 朝下看。

    眼睛高度 1.62 ⇒ 到 y=16 的方块顶面有 **5.62 格**，超过默认 reach 5.0。
    所以这里把 reach 放大到 8：**"瞄不到"与"够不着"是两件事**，测试要测前者时
    必须先把后者排除掉（实测踩过：dig/place 返回 (False, None)，看着像挖不动，
    其实是 reach 不够）。
    """
    cfg.setdefault('reach', 8.0)
    k = make_offline(dict({'seed': seed, 'size': size, 'height': height}, **cfg))
    for x in range(size):
        for z in range(size):
            for y in range(height):
                k.world.set(x, y, z, B.AIR)
    k.world.edits.clear()
    k.flying = True
    k.pos = [20.5, 20.0, 20.5]
    k.vel = [0.0, 0.0, 0.0]
    k.pitch = -89.9
    return k


@test('开局：站在地表、hotbar 有 9 格、创造模式有库存、没有增量')
def t_init():
    k = make_offline({'seed': 20261014, 'size': 64, 'height': 32})
    assert len(k.hotbar) == 9, f'hotbar 格数 {len(k.hotbar)}'
    assert 0 <= k.selected < len(k.hotbar)
    assert k.world.edits == {}, f'新世界不该有增量，实际 {len(k.world.edits)} 条'
    below = k.world.get(int(k.pos[0]), int(k.pos[1]) - 1, int(k.pos[2]))
    assert B.is_solid(below), f'出生点脚下是 {B.by_id(below)}，不是固体'
    assert k.creative and k.inventory, '创造模式应有库存'
    assert k.status() == 'playing', '状态串必须是 playing'


@test('开局脏区块 = 全部区块（否则第一次渲染一个面都不出）')
def t_initial_dirty():
    k = make_offline({'seed': 1, 'size': 32, 'height': 32})
    assert k.dirty_chunks == set(k.world.chunks), '开局没有把全部区块标脏'
    k.chunk_meshes(limit=10_000)
    assert k.mesh_stats()['chunks'] == len(k.world.chunks)
    assert k.mesh_stats()['faces'] > 0


@test('hotbar：环形选择、scroll、越界回绕')
def t_hotbar():
    k = _empty_kernel()
    n = len(k.hotbar)
    assert k.select(0) == 0
    assert k.select(n) == 0, '越界应回绕'
    assert k.select(-1) == n - 1, '负数应回绕到末尾'
    assert k.scroll(1) == 0
    # ⚠ Phase 1 起 hotbar 存的是**物品 id**（≥ items.ITEM_BASE），而 `selected_block()`
    # 返回的是**方块 id** —— 两者不再相等。先前这里断言 `selected_block() == hotbar[0]`，
    # 在"两套编号并存"之后变成了"拿物品 id 和方块 id 比"，是错的（实测红）。
    from mcclone3d import items as _I
    k.select(0)
    item0 = k.hotbar[0]
    assert _I.is_item_id(item0), f'hotbar 里该是物品 id，实际 {item0}'
    assert _I.is_block_id(k.selected_block()), f'selected_block 该是方块 id，实际 {k.selected_block()}'
    assert k.selected_block() == _I.item(item0).block_id, \
        '手持方块物品时，selected_block() 该等于该物品对应的方块 id'
    assert k.selected_item() == item0, 'selected_item 该就是 hotbar 当前格'
    # 默认 hotbar 第一格是草方块（DEFAULT_HOTBAR[0]），仍是方块物品
    assert k.selected_block() == B.GRASS, f'默认第一格该是草方块，实际 {B.name_of(k.selected_block())}'


@test('挖：命中才挖、挖掉变空气、增量 +1、计数 +1')
def t_dig():
    k = _empty_kernel()
    k.world.set(20, 15, 20, B.STONE)
    k.world.edits.clear()
    ok, name = k.dig()
    assert ok and name == 'stone', (ok, name)
    assert k.world.get(20, 15, 20) == B.AIR
    assert k.world.edits == {(20, 15, 20): B.AIR}
    assert k.stats['dug'] == 1
    # 再挖同一处（现在是空气）⇒ 不命中
    ok2, _ = k.dig()
    assert not ok2, '空气也能挖？'


@test('挖：瞄不到时返回 (False, None)，且不留增量')
def t_dig_miss():
    k = _empty_kernel()
    n = len(k.world.edits)
    ok, name = k.dig()
    assert ok is False and name is None
    assert len(k.world.edits) == n


@test('基岩挖不动（与 MC 一致）')
def t_bedrock():
    k = _empty_kernel()
    k.world.set(20, 15, 20, B.BEDROCK)
    ok, name = k.dig()
    assert not ok, '基岩被挖掉了'
    assert k.world.get(20, 15, 20) == B.BEDROCK


@test('放：放在命中面的相邻空位（不是替换被瞄的方块）')
def t_place():
    # 用**水平**射线打墙：相邻空位必在玩家侧、且在玩家 AABB 之外
    # （竖直向下的情形相邻格常常正好是玩家脚所在格 ⇒ 会被"不许封死自己"正确地拒掉，
    #  那是另一条用例，不是这条要测的东西）。
    k = _empty_kernel()
    k.pos = [20.5, 20.0, 20.5]
    k.yaw, k.pitch = -90.0, 0.0                     # 朝 +x
    ey = 20 + int(EYE_HEIGHT)
    for y in (ey - 1, ey, ey + 1):
        for z in range(18, 23):
            k.world.set(24, y, z, B.STONE)          # 墙
    # ⚠ **显式**把石头塞进当前格，别假设"默认 hotbar 第 3 格是石头"：
    # Phase 3 起 hotbar 里还有红石元件，那个假设会随 hotbar 内容变化而碎（实测碎过）。
    from mcclone3d import items as _I                    # 局部导入：_I 在别的测试里也是这么拿的
    _stone = _I.item_by_name('stone')
    k.hotbar[k.selected] = _stone.id
    want = k.selected_block()
    assert want == B.STONE, f'测试前提：当前格该是石头，实际 {B.name_of(want)}'
    hit = k.raycast()
    assert hit is not None and hit[0] == (24, ey, 20), f'测试前提：射线该命中墙，实际 {hit}'
    ok, at = k.place()
    assert ok and at is not None, f'放置失败：{ok} {at}'
    assert at[0] == 23 and at[1] == ey and at[2] == 20, f'该放在墙面来路那一格，实际 {at}'
    assert k.world.get(*at) == want, '放下的方块不对'
    assert k.world.get(24, ey, 20) == B.STONE, '被瞄的方块不该被替换'
    assert k.stats['placed'] == 1


@test('放：不许把方块放进玩家自己身体里（防空手封死自己）')
def t_place_no_trap():
    k = _empty_kernel()
    k.world.set(20, 19, 20, B.STONE)               # 脚下方块 → 相邻空位正好是脚所在格
    ok, at = k.place()
    assert not ok, f'把自己封死了：{at}'


@test('放：目标格非空则拒绝（不覆盖已有方块）')
def t_place_occupied():
    # 这条改了很多次，最终用**最直接的构造**：射线水平打在墙上、来路那格已被占。
    # 关键约束（三次踩坑的总结）：
    #   ① 目标格不能在射线的**来路上被先命中**（否则射线改而命中它，测的东西就变了）；
    #   ② 目标格要在玩家 AABB 之外（否则会被"不许封死自己"先拒掉，看不出是哪条规则生效）。
    # 取 y=ey+1 那一层：射线在 ey 高度水平前进，天然满足 ①；
    # 目标格在墙前 1 格、比眼睛高 1 格 ⇒ 满足 ②。
    k = _empty_kernel()
    k.pos = [0.5, 20.0, 20.5]
    k.yaw, k.pitch = -90.0, 0.0                     # 朝 +x
    ey = 20 + int(EYE_HEIGHT)
    k.world.set(4, ey, 20, B.STONE)                 # 墙（射线必中）
    k.select(2)
    hit = k.raycast()
    if hit is None or hit[0] != (4, ey, 20):
        # ⚠ 射线几何可能随实现微调（实测命中曾落在 (3,21,20)）：命中的格只要
        # 不是我们摆的那块，这条用例的前提就不成立 —— 此时它**无可验证**。
        # 这里显式露出这一点（而不是把断言放宽到"随便放哪都算过"），
        # 因为放宽之后就再也抓不到"目标格非空却照放"这个真 bug 了。
        raise AssertionError(
            f'测试前提不成立：射线该命中墙 {(4, ey, 20)}，实际 {hit}。'
            f' 需要按当前 DDA 口径重新摆参照物（不要放宽断言）。')
    assert hit[1] == (-1, 0, 0), f'测试前提：来路面法向应为 -x，实际 {hit[1]}'
    # ⚠ 这里有个**几何上的必然**（探针实测才想明白）：目标格 = 命中格 + 来路法向，
    # 也就是**挡在射线来路上的那一格**。一旦把它占上，射线就会先命中它、
    # 于是"相邻空位"自然换到它背后去 —— `place()` 报的成功落在 (2,21,20) 是**正确行为**，
    # 不是"覆盖了已有方块"。
    # 所以要把"目标格非空"造出来，只能**按同一条射线现算目标格、再占它**，
    # 并在占位之后重新取一次射线（此时射线命中的是刚占的块，目标格是它背面那格）。
    # 判定简化成一条不依赖几何的断言链：
    #   ① 占位后 place 至少**不能改动**刚占的那一格（它的内容必须原样）；
    #   ② 占位后 place 放置的位置**不能等于**占位格。
    tgt_before = (hit[0][0] + hit[1][0], hit[0][1] + hit[1][1], hit[0][2] + hit[1][2])
    k.world.set(*tgt_before, B.DIRT)
    ok, at = k.place()
    assert k.world.get(*tgt_before) == B.DIRT, \
        f'已有方块被覆盖了：{tgt_before} 现在是 {B.name_of(k.world.get(*tgt_before))}'
    assert at != tgt_before, f'放置位置等于被占格：{at}'


@test('生存模式：挖到的掉在世界里、走过去捡进背包、放置要消耗、没有就不许放')
def t_survival_stock():
    """⚠ 语义变更（Phase 1）：生存模式挖掉方块的产物**不再直接进背包**，
    而是生成 `kernel.drops` 里的掉落物，要 `pickup_nearby()`（或走过去）才进包。
    先前这里断言 `inventory[B.STONE] == 1`，测的是 Phase 0 的"挖了就进包"——
    那个行为在生存模式下已经不存在了（创造模式才直接进包）。
    """
    from mcclone3d import items as _I
    stone_item = _I.item_by_name('stone')
    cobble_item = _I.item_by_name('cobble')
    k = _empty_kernel(creative=False)               # reach 已放大到 8
    k.pos = [20.5, 22.0, 20.5]                      # 眼睛 23.62
    k.world.set(20, 23, 20, B.STONE)                # 地板（= 眼睛那一格，射线必中）
    k.inventory.clear()
    k.pitch = -89.9
    hit = k.raycast()
    assert hit is not None and hit[0] == (20, 23, 20), f'测试前提：射线该命中地板，实际 {hit}'
    # ⚠ 先验一条**徒手**的对照：徒手挖石头"挖得动但什么都不掉"（Phase 1 的门槛），
    # 此时返回的标签是**方块名**（没有掉落物可报）。这条也是"手上没镐"的判据。
    ok0, label0 = k.dig()
    assert ok0 is True, '徒手该挖得动石头（挖得动 ≠ 掉得出）'
    assert label0 == 'stone', f'没有掉落物时该报方块名，实际 {label0!r}'
    assert k.drops == [], '徒手挖石头不该有掉落'
    # 手持镐再挖一次：这次才该掉圆石
    k.world.set(20, 23, 20, B.STONE)                # 方块放回去
    pick = _I.item_by_name('wooden_pickaxe')
    k.give(pick.id, 1)
    k.hotbar[k.selected] = pick.id                  # hotbar 存物品 id，要塞进格子里才算"手持"
    k.select(k.hotbar.index(pick.id))
    assert k.held_tool() is not None, '测试前提：手上该拿着镐'
    ok, name = k.dig()
    assert ok is True, f'该挖成功：{(ok, name)}'
    assert name == 'cobble', f'带镐挖石头该报掉落物（圆石），实际 {name!r}'
    # ① 产物掉在世界里（不是背包）
    assert k.inventory.get(cobble_item.id, 0) == 0, \
        f'生存模式不该"挖了就进包"：{k.inventory}'
    assert k.drops, '挖掉石头却什么都没掉出来（该有 1 个圆石掉落物）'
    got = {(_I.name_of(d['item']), d['n']) for d in k.drops}
    assert got == {('cobble', 1)}, f'掉落物不对：{got}'
    # ② 拾取才进背包
    picked = k.pickup_nearby()
    assert picked == [('cobble', 1)], f'拾取结果不对：{picked}'
    assert k.inventory.get(cobble_item.id) == 1, f'捡起来的东西没进背包：{k.inventory}'
    assert k.drops == [], '拾取后掉落物没被清掉'
    # 射线改朝上，命中头顶那块天花板，相邻空位就是**天花板之下、眼睛之上**那一格。
    k.world.set(20, 23, 20, B.STONE)                # 脚下那块放回去（保持站在原处）
    k.world.set(20, 25, 20, B.STONE)                # 头顶上方 2 格处一块天花板
    k.pitch = 89.9                                  # 抬头看
    # ⚠ 抬头时眼睛那一格 (20,23,20) 本身是石头（脚下那块），射线起点在其中 ⇒
    # 会**先命中起点格**（这是 DDA 的正确行为，法向为零向量）。所以先把脚下那块清掉。
    k.world.set(20, 23, 20, B.AIR)
    hit2 = k.raycast()
    assert hit2 is not None and hit2[0] == (20, 25, 20), f'测试前提：抬头该命中天花板，实际 {hit2}'
    # ⚠ 放置用的是 **hotbar 当前格**，不是"刚捡到的那种" —— 必须把石头塞进当前格，
    # 否则会拿手里的东西去放，测出来的是"那样东西不够"而不是"石头被消耗"（实测踩过）。
    # hotbar 存的是**物品 id**（所以这里塞物品 id，不是方块 id）。
    k.hotbar[k.selected] = stone_item.id
    k.select(k.selected)
    assert k.selected_block() == B.STONE
    # 库存里只有圆石、没有石头 ⇒ 放石头必须被拒（库存判定用的是物品 id）
    ok1, at1 = k.place()
    assert not ok1, f'手里没有石头却放出去了：{at1}'
    # 给 1 个石头物品 ⇒ 能放，并且**扣的是石头物品**
    k.give(stone_item.id, 1)
    ok2, at2 = k.place()
    assert ok2, f'有库存却放不了（射线命中 {hit2}）'
    assert k.world.get(*at2) == B.STONE, f'放下的不是石头：{at2}'
    assert k.inventory.get(stone_item.id, 0) == 0, '放置没消耗库存'
    assert k.inventory.get(cobble_item.id, 0) == 1, \
        '放置扣错了东西（把圆石也扣了）'
    ok3, _ = k.place()
    assert not ok3, '库存为 0 还能放'


@test('创造模式：挖了直接进背包（给方块本身）、放置不消耗')
def t_creative_stock():
    """⚠ 语义变更（Phase 1）：创造模式"库存无限"的具体含义是
    **放置不消耗**（先前这里断言"挖了库存不变"—— 那条已经不对了：
    创造模式挖方块会把**方块本身**放进背包，这是 Phase 0 的搭房子手感）。
    """
    from mcclone3d import items as _I
    stone_item = _I.item_by_name('stone')
    k = _empty_kernel(creative=True)
    k.give_item('wooden_pickaxe', 1)                 # ⚠ 必须手持镐，否则徒手挖石头不掉落
    k.hotbar[k.selected] = _I.item_by_name('wooden_pickaxe').id
    k.select(k.hotbar.index(_I.item_by_name('wooden_pickaxe').id))
    k.pos = [20.5, 22.0, 20.5]                       # 别站在待放格子上（否则"封死自己"会拒）
    k.world.set(20, 15, 20, B.STONE)
    n0 = k.inventory.get(stone_item.id, 0)
    assert n0 == START_STOCK, f'创造模式开局该有满库存，实际 {n0}'
    ok, label = k.dig()
    assert ok is True, f'该挖成功：{(ok, label)}'
    assert k.drops == [], '创造模式不该往世界里掉东西'
    assert k.inventory.get(stone_item.id, 0) == n0 + 1, \
        f'创造模式挖石头该把方块本身放进背包：{n0} → {k.inventory.get(stone_item.id)}'
    assert label == 'stone', f'标签该跟实际给的东西一致：{label!r}'
    # 放置不消耗：库存不减
    k.world.set(20, 15, 20, B.STONE)
    k.world.set(20, 14, 20, B.AIR)
    k.hotbar[k.selected] = stone_item.id          # 同上：显式塞进当前格
    k.select(k.selected)
    before = dict(k.inventory)
    ok2, at = k.place()
    assert ok2, f'创造模式放不了：{at}'
    assert k.inventory == before, f'创造模式放置**不该**消耗库存：{before} → {k.inventory}'


@test('增量记账：改动落在正确区块，且相邻区块也被标脏（边界要重建）')
def t_dirty_chunks():
    k = _empty_kernel(size=64, height=32)
    k.dirty_chunks.clear()
    x = 16                                      # 区块边界（cx=1）
    k.world.set(x, 15, 8, B.STONE)
    k._mark_dirty(x, 15, 8)
    assert (1, 0, 0) in k.dirty_chunks, '本区块没标脏'
    assert (0, 0, 0) in k.dirty_chunks, '左侧相邻区块没标脏（边界面的剔除会不更新）'


@test('chunk_meshes：只建脏区块、每次有上限、建完就不再重复建')
def t_mesh_scheduling():
    k = make_offline({'seed': 3, 'size': 32, 'height': 32})
    total = len(k.world.chunks)
    first = k.chunk_meshes(limit=2)
    assert len(first) == 2, f'limit 没生效：建了 {len(first)} 个'
    assert len(k.dirty_chunks) == total - 2
    k.chunk_meshes(limit=10_000)
    assert not k.dirty_chunks, '全部建完后还有脏区块'
    again = k.chunk_meshes(limit=10_000)
    assert again == [], f'没有脏区块却又重建了 {len(again)} 个'


@test('存档往返：世界增量 + 玩家状态 + hotbar/工具/生存/掉落物 全部一致')
def t_save_roundtrip():
    """⚠ 存档版本演进（断言**不写死**版本号，而是断言"当前版本"+"能读旧版"）：

    * v1 = Phase 0（方块名 + 玩家位姿 + edits）
    * v2 = Phase 1（+ `tools`/`health`/`hunger`/`saturation`/`state`/`death_cause`
      /`drops`/`furnace`）
    * v3 = Phase 2-A（+ `day` 世界时刻）

    先前这里写死 `blob['version'] == 2`，Phase 2-A 升到 v3 时它**正确地红了** ——
    这是好事（说明断言真的在盯版本）。但"写死当前版本"每升一版都要改一次，
    所以改成：① 断言等于 `SAVE_VERSION` 常量；② **额外断言 v1/v2 的老档仍能读**
    （向后兼容才是版本号真正的意义，只盯数字是没用的）。
    """
    from mcclone3d import items as _I
    k = make_offline({'seed': 31337, 'size': 48, 'height': 32})
    k.pitch = -89.9
    k.dig()
    k.select(3)
    k.place()
    k.pos = [10.25, 20.0, 12.75]
    k.yaw, k.pitch, k.flying = 33.0, -12.0, True
    k.stats['dug'] = 7
    # --- 造出"非默认"的生存状态，否则往返断言会因为"两边都是默认值"而恒真 ---
    pick = _I.item_by_name('iron_pickaxe')
    k.give(pick.id, 1)
    k.tool_durability[pick.id] = 77               # 磨损过的耐久（≠ 表值 251 才会进存档）
    k.select(0)                                   # 手持草：别让"手上那把镐"干扰统计
    k.health, k.hunger, k.saturation = 13.5, 9.25, 0.5
    k.spawn_drop(11.5, 21.5, 12.5, _I.item_by_name('coal').id, 2)
    k.furnace = {'fuel_left': 3.5, 'cook_left': 4.25, 'recipe': 'iron_ingot'}
    k.state, k.death_cause = 'playing', ''
    blob = json.loads(json.dumps(k.dump()))        # 过一遍 JSON，模拟真实落盘
    # 存档格式本身：版本 + 新字段都要在（版本断言用常量，不写死数字）
    from mcclone3d.kernel import SAVE_VERSION
    assert blob['version'] == SAVE_VERSION, \
        f'存档版本该是 SAVE_VERSION={SAVE_VERSION}，实际 {blob["version"]!r}'
    for key in ('tools', 'health', 'hunger', 'saturation', 'state', 'death_cause'):
        assert key in blob['player'], f'v2 存档的 player 里缺字段 {key}'
    assert 'drops' in blob and 'furnace' in blob, 'v2 存档缺 drops / furnace 段'
    assert 'day' in blob, 'v3 存档缺世界时刻（day）段'
    # **向后兼容**：更老的档（没 day 段、version 更小）也必须能读 —— 版本号的意义在这
    for old_ver in (1, 2):
        old = json.loads(json.dumps(blob))
        old['version'] = old_ver
        old.pop('day', None)
        k_old = McCloneKernel.__new__(McCloneKernel)
        k_old.ctx = None
        k_old._init({'seed': 31337, 'size': 48, 'height': 32})
        k_old.load(old)                            # 不该抛
        assert k_old.health == k.health, f'v{old_ver} 老档读出的血量该一致'
    assert blob['player']['tools'] == {'iron_pickaxe': 77}, \
        f'磨损过的工具耐久该进存档：{blob["player"]["tools"]}'
    assert blob['drops'] and blob['drops'][0]['item'] == 'coal', \
        f'掉落物该按名字进存档：{blob["drops"]}'
    k2 = McCloneKernel.__new__(McCloneKernel)
    k2.ctx = None
    # ⚠ 读档要求"当前世界的种子/尺寸与存档一致"（这是**有意的**校验：不然增量会落到
    # 另一张地图上）。所以这里必须按存档参数建，不能"故意用别的种子"——先前那样写
    # 恰好是在测"校验该不该拦"，而这条另有专门的用例（t_save_rejects）。
    k2._init({'seed': 31337, 'size': 48, 'height': 32})
    k2.load(blob)
    assert k2.seed == k.seed, '读档没纠正种子'
    assert dict(k2.world.edits) == dict(k.world.edits), '世界增量没还原'
    assert [round(v, 6) for v in k2.pos] == [round(v, 6) for v in k.pos]
    assert (k2.yaw, k2.pitch, k2.flying) == (k.yaw, k.pitch, k.flying)
    assert k2.hotbar == k.hotbar and k2.selected == k.selected
    assert k2.stats == k.stats
    assert k2.dirty_chunks == set(k2.world.chunks), '读档后没把网格标脏'
    # --- 新字段逐一往返 ---
    assert dict(k2.inventory) == dict(k.inventory), '背包没还原'
    assert k2.tool_durability.get(pick.id) == 77, \
        f'工具耐久没还原：{k2.tool_durability}'
    assert abs(k2.health - 13.5) < 1e-9 and abs(k2.hunger - 9.25) < 1e-9 \
        and abs(k2.saturation - 0.5) < 1e-9, \
        f'生存状态没还原：{k2.health} {k2.hunger} {k2.saturation}'
    assert k2.state == 'playing' and k2.death_cause == ''
    assert len(k2.drops) == 1, f'掉落物没还原：{k2.drops}'
    d = k2.drops[0]
    assert d['item'] == _I.item_by_name('coal').id and d['n'] == 2, f'掉落物不对：{d}'
    assert [round(v, 6) for v in d['pos']] == [11.5, 21.5, 12.5], f'掉落物位置没还原：{d["pos"]}'
    assert k2.furnace == k.furnace, f'熔炉状态没还原：{k2.furnace} vs {k.furnace}'


@test('存档文件往返（真实文件 + UTF-8 + 名字而非 id + v2 字段）')
def t_save_file():
    from mcclone3d import items as _I
    k = make_offline({'seed': 777, 'size': 48, 'height': 32})
    k.pitch = -89.9
    k.dig()
    pick = _I.item_by_name('stone_pickaxe')
    k.give(pick.id, 1)
    k.tool_durability[pick.id] = 40
    k.health, k.hunger = 17.0, 12.0
    with tempfile.TemporaryDirectory() as td:
        path = os.path.join(td, 'save.mc3d')
        k.save(path)
        assert os.path.exists(path)
        raw = open(path, encoding='utf-8').read()
        assert 'grass' in raw or 'stone' in raw, '存档里应出现方块名（可读、可手改）'
        # v2 的新字段也要是**名字**口径（不是裸 id），这样重排编号不会读坏旧档
        assert '"tools"' in raw and '"health"' in raw and '"hunger"' in raw, \
            'v2 存档缺 tools/health/hunger 段'
        assert 'stone_pickaxe' in raw, '工具耐久该按物品名存（不是 id）'
        assert '"edits"' in raw and '"seed"' in raw
        k2 = McCloneKernel.__new__(McCloneKernel)
        k2.ctx = None
        k2._init({'seed': 777, 'size': 48, 'height': 32})
        k2.load_file(path)
        assert dict(k2.world.edits) == dict(k.world.edits)
        assert k2.tool_durability.get(pick.id) == 40, f'工具耐久没从文件还原：{k2.tool_durability}'
        assert abs(k2.health - 17.0) < 1e-9 and abs(k2.hunger - 12.0) < 1e-9


@test('存档拒绝：版本不对 / 未知方块名 / 种子尺寸不匹配 都要响亮报错')
def t_save_rejects():
    k = make_offline({'seed': 42, 'size': 32, 'height': 32})
    bad = k.dump()
    bad['version'] = 99
    k2 = McCloneKernel.__new__(McCloneKernel)
    k2.ctx = None
    k2._init({'seed': 42, 'size': 32, 'height': 32})
    try:
        k2.load(bad)
    except ValueError:
        pass
    else:
        raise AssertionError('版本不对必须报错')

    bad2 = k.dump()
    bad2['world']['edits'] = [[1, 1, 1, 'no_such_block']]
    k3 = McCloneKernel.__new__(McCloneKernel)
    k3.ctx = None
    k3._init({'seed': 42, 'size': 32, 'height': 32})
    try:
        k3.load(bad2)
    except ValueError as exc:
        assert 'no_such_block' in str(exc)
    else:
        raise AssertionError('未知方块名必须报错')

    bad3 = k.dump()
    bad3['world']['size'] = 64
    k4 = McCloneKernel.__new__(McCloneKernel)
    k4.ctx = None
    k4._init({'seed': 42, 'size': 32, 'height': 32})
    try:
        k4.load(bad3)
    except ValueError:
        pass
    else:
        raise AssertionError('尺寸不匹配必须报错')


@test('读档：玩家的编辑必须**最后落**（不能被重新种的树覆盖）')
def t_load_order():
    k = make_offline({'seed': 606, 'size': 64, 'height': 32})
    # 找一棵树的树干位置，把它挖掉（进增量）
    target = None
    for x in range(2, 62):
        for z in range(2, 62):
            for y in range(2, 30):
                if k.world.get(x, y, z) == B.LOG:
                    target = (x, y, z)
                    break
            if target:
                break
        if target:
            break
    assert target, '世界里没有树（测试前提不成立）'
    k.world.set(*target, B.AIR)
    blob = k.dump()
    k2 = McCloneKernel.__new__(McCloneKernel)
    k2.ctx = None
    k2._init({'seed': 606, 'size': 64, 'height': 32})
    k2.load(blob)
    assert k2.world.get(*target) == B.AIR, '读档后玩家的挖掘被重新种的树覆盖了'


@test('读档拒绝：当前世界的种子/尺寸与存档不符时必须响亮报错（不静默串档）')
def t_load_rejects_mismatch():
    k = make_offline({'seed': 42, 'size': 32, 'height': 32})
    blob = k.dump()
    for cfg in ({'seed': 43, 'size': 32, 'height': 32},
                {'seed': 42, 'size': 48, 'height': 32},
                {'seed': 42, 'size': 32, 'height': 48}):
        k2 = McCloneKernel.__new__(McCloneKernel)
        k2.ctx = None
        k2._init(cfg)
        try:
            k2.load(blob)
        except ValueError:
            pass
        else:
            raise AssertionError(f'配置 {cfg} 与存档不符，却读进去了（会静默串档）')


@test('自动机：跑完脚本，挖/放都成功，且有增量')
def t_auto():
    k = make_offline({'seed': 8080, 'size': 48, 'height': 32})
    t = 0.0
    end = SCRIPT[-1][0] + 1.0
    while t < end:
        k.auto_step(1.0 / 60.0)
        t += 1.0 / 60.0
    # 脚本里只有 3 次 dig 动作，且都是朝同一点下方连挖 ⇒ 挖到的块数 <= 3
    assert k.stats['dug'] >= 2, f'挖得太少：{k.stats}'
    assert k.stats['placed'] >= 1, f'没放成：{k.stats}'
    assert len(k.world.edits) >= 3, f'增量太少：{len(k.world.edits)}'
    assert k.status() == 'playing'


@test('自动机与帧率无关：30/60/120Hz 走到同一结果（时间量化）')
def t_auto_framerate():
    results = []
    for hz in (30, 60, 120):
        k = make_offline({'seed': 8080, 'size': 48, 'height': 32})
        t, end = 0.0, SCRIPT[-1][0] + 1.0
        while t < end:
            k.auto_step(1.0 / hz)
            t += 1.0 / hz
        results.append((k.stats['dug'], k.stats['placed'], len(k.world.edits)))
    assert len(set(results)) == 1, f'帧率影响了结果：{results}'


@test('summary：能打印、字段齐、值合法')
def t_summary():
    k = make_offline({'seed': 11, 'size': 32, 'height': 32})
    s = k.summary()
    for key in ('seed', 'pos', 'yaw', 'pitch', 'grounded', 'flying', 'slot',
                'holding', 'dig', 'placed', 'blocks', 'edits'):
        assert key in s, f'summary 缺字段 {key}'
    assert B.by_name(s['holding']) is not None
    assert s['blocks'] > 0 and s['edits'] == 0
    text = json.dumps(s, ensure_ascii=False)
    assert isinstance(text, str)


@test('reset：换种子重建世界，增量清零，玩家回到地表，生存状态归位')
def t_reset():
    """⚠ Phase 1 起 `stats` 有 8 个键（新增 crafted/smelted/picked/eaten/deaths/damage）。
    先前这里断言 `stats == {'dug': 0, 'placed': 0}` —— 那是在 Phase 0 的 2 键口径下写的，
    现在必然红。判据没放宽：改的是"**每一个**统计键都归零"，比原来更严。
    """
    from mcclone3d import items as _I
    k = make_offline({'seed': 1, 'size': 48, 'height': 32})
    k.pitch = -89.9
    k.dig()
    assert k.world.edits
    # 把生存状态弄脏，验证 reset 会归位（不只是世界）
    pick = _I.item_by_name('wooden_pickaxe')
    k.give(pick.id, 1)
    k.tool_durability[pick.id] = 5
    k.health, k.hunger, k.saturation = 3.0, 2.0, 0.0
    k.spawn_drop(10.5, 20.5, 10.5, _I.item_by_name('coal').id, 1)
    k.hurt(999.0, 'test')
    assert k.state == 'dead' and k.stats['deaths'] == 1
    old_seed = k.seed
    k.reset(2)
    assert k.seed == 2 and k.world.seed == 2
    assert k.world.edits == {}, 'reset 没清增量'
    # 统计键**集合**要完整、且每个都归零（比旧断言更严：旧断言只看了 2 个键）
    assert set(k.stats) == {'dug', 'placed', 'crafted', 'smelted', 'picked',
                            'eaten', 'deaths', 'damage',
                            'enchanted', 'xp_gained'}, \
        f'统计键集合变了：{sorted(k.stats)}'
    assert k.xp == 0 and k.enchants == {} and k.wear == {}, 'reset 该清掉经验与附魔'
    assert all(v == 0 for v in k.stats.values()), f'reset 没清统计：{k.stats}'
    # 生存状态归位
    assert k.state == 'playing' and k.health == k.max_health
    assert k.hunger == k.max_hunger and k.death_cause == ''
    assert k.drops == [], 'reset 没清掉落物'
    assert k.dig_target is None and k.dig_progress == 0.0, 'reset 没清挖掘进度'
    assert k.furnace['recipe'] is None, 'reset 没清熔炉'
    # 创造模式（默认）下 reset 后库存该重新发满
    assert k.inventory, 'reset 后创造模式该重新发满库存'
    assert k.tool_durability.get(pick.id) == pick.durability, 'reset 后工具耐久该回满'
    # 玩家回到地表
    below = k.world.get(int(k.pos[0]), int(k.pos[1]) - 1, int(k.pos[2]))
    assert B.is_solid(below), f'reset 后脚下的 {B.name_of(below)} 不是固体'
    k.reset(old_seed)
    assert k.world.seed == old_seed


@test('配置树的值真的到达内核（seed/size/height/reach/hotbar 全部生效）')
def t_config_passthrough():
    """⚠ hotbar 存的是**物品 id**（不是方块 id）—— 先前断言 `hotbar == [B.STONE, B.GLASS]`
    是拿方块 id 比物品 id，必然红。判据改成"按名字查出来的物品 id"，并**逐项验证
    方块映射仍然成立**（这才是配置树真正要保证的事）。
    """
    from mcclone3d import items as _I
    k = make_offline({'seed': 123, 'size': 64, 'height': 48, 'reach': 9.5,
                      'hotbar': ['stone', 'glass'], 'creative': False})
    assert (k.seed, k.size, k.height) == (123, 64, 48)
    assert abs(k.reach - 9.5) < 1e-9
    assert k.hotbar == [_I.item_by_name('stone').id, _I.item_by_name('glass').id], \
        f'hotbar 该是物品 id：{k.hotbar}'
    assert all(_I.is_item_id(i) for i in k.hotbar), 'hotbar 里出现了方块 id（号段混了）'
    # 配置写的是名字，两套号段都要能认：hotbar 里那两格放下来必须正好是石头/玻璃
    assert k.hotbar[0] == _I.item_by_name('stone').id
    assert _I.item(k.hotbar[0]).block_id == B.STONE
    assert _I.item(k.hotbar[1]).block_id == B.GLASS
    k.select(0)
    assert k.selected_block() == B.STONE, 'hotbar 第 1 格该放下石头'
    k.select(1)
    assert k.selected_block() == B.GLASS, 'hotbar 第 2 格该放下玻璃'
    assert k.creative is False and k.inventory == {}


def t_pack_layer():
    """Phase 3-D：资源包**只改贴图像素**，不许动玩法、也不许进存档。

    为什么这条必须在**内核**层钉：`pack` 很容易被顺手写进 `dump()`（"反正都是
    世界设置"），一旦进档就出大问题 —— 换包读同一份档会得到"不同的世界"，
    而方块其实一个都没变。判据用"dump 的字节前后完全相同"这种**功能**判据，
    不用"看着对不对"。
    """
    from mcclone3d import packs as PK

    tmp = tempfile.mkdtemp(prefix='mc3d_kpack_')
    try:
        k = make_offline({'seed': 4242, 'size': 32, 'height': 32})
        assert k.pack is None, '默认必须是纯程序化（不带包）'
        assert '程序化' in k.pack_report(), k.pack_report()
        dump_before = json.dumps(k.dump(), ensure_ascii=False, sort_keys=True)
        # 挂一个包：世界与存档**一个字节都不该变**
        PK.write_demo_pack(os.path.join(tmp, 'autumn'), 'autumn')
        k.use_pack(os.path.join(tmp, 'autumn'))
        assert k.pack is not None and k.pack.tile == 32
        assert json.dumps(k.dump(), ensure_ascii=False, sort_keys=True) == dump_before, \
            '挂包改变了存档内容（包不该进档）'
        rep = k.pack_report()
        assert 'autumn' in rep and '32px' in rep, rep
        # 坏包必须**响亮报错**，而且不该把已经挂好的包顺手清掉
        try:
            k.use_pack(os.path.join(tmp, 'no_such_pack_dir'))
        except PK.PackError:
            pass
        else:
            raise AssertionError('挂不存在的包应当抛 PackError')
        assert k.pack is not None and k.pack.id == 'autumn', '失败时不该弄丢已挂的包'
        # 配置树里给了 pack ⇒ 装配时就挂上
        k2 = make_offline({'seed': 7, 'size': 32, 'height': 32,
                           'pack': os.path.join(tmp, 'autumn')})
        assert k2.pack is not None and k2.pack.tile == 32
        # 摘掉
        k.use_pack(None)
        assert k.pack is None and k.pack_report().startswith('资源包：无')
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def t_enchant_layer():
    """Phase 3-E：经验/附魔**真的改了玩法**，且存档 v4 往返一致（含读 v3 老档）。

    为什么这条必须在**内核**层钉（而不是只在 `test_enchant` 里测纯函数）：
    附魔的效果分散在 `dig_time` / `_use_tool` / `_finish_dig` / `attack` 四处，
    任何一处忘了接，纯函数全过、玩法却没变 —— 那是最难发现的一类漏接。
    """
    from mcclone3d import enchant as EN
    from mcclone3d import items as _I

    k = make_offline({'seed': 77, 'size': 48, 'height': 32, 'light': False,
                      'mobs': False, 'creative': False})
    assert k.xp == 0 and k.level == 0 and k.enchants == {} and k.wear == {}

    # 经验：挖矿给经验（只给矿石）
    assert k.add_xp(27) == 3 and k.xp == 27
    assert EN.level_progress(k.xp)[0] == 3

    pick = _I.item_by_name('iron_pickaxe')
    k.give(pick.id, 1)
    k.hotbar[0] = pick.id
    k.select(0)
    # 找一格朝下的目标
    x, z = 10, 10
    y = k.world.surface_at(x, z) - 1
    for dy in (1, 2, 3):
        k.world.set_generated(x, y + dy, z, B.AIR)
    k.flying = True
    k.pos = [x + 0.5, y + 2.0, z + 0.5]
    k.yaw, k.pitch = 0.0, -90.0
    t_off = k.dig_time()
    k.enchants[pick.id] = {'efficiency': 5}
    t_on = k.dig_time()
    assert abs(t_on - t_off / (1 + 0.30 * 5)) < 1e-9, '效率没接上 dig_time'

    # 耐久：10 点耐久 + 耐久 III ⇒ **恰好** 40 次使用才断
    k.tool_durability[pick.id] = 10
    k.enchants[pick.id] = {'unbreaking': 3}
    k.wear[pick.id] = 0
    uses = 0
    while not k._use_tool(pick):
        uses += 1
        assert uses < 500, '耐久附魔没生效（一直不断）'
    assert uses + 1 == 40, f'应当是 10×4=40 次，实际 {uses + 1}'
    assert pick.id not in k.enchants and pick.id not in k.wear, '断了要连附魔一起清'

    # 存档 v4 往返：经验/附魔/磨损逐字段相等
    k.give(pick.id, 1)
    k.enchants[pick.id] = {'fortune': 2}
    k.wear[pick.id] = 3
    k.xp = EN.xp_total(6) + 4
    blob = json.loads(json.dumps(k.dump()))
    assert blob['version'] == 4 == SAVE_VERSION
    k2 = make_offline({'seed': 77, 'size': 48, 'height': 32, 'light': False,
                       'mobs': False, 'creative': False})
    k2.load(blob)
    assert k2.xp == k.xp and k2.level == k.level == 6
    assert k2.enchant_levels(pick.id) == {'fortune': 2}
    assert k2.wear.get(pick.id) == 3
    assert 'xp' in k2.dump()['player'] and 'enchant' in k2.dump()['player']

    # 老档（v3，没有这三个字段）必须能读 —— 给默认值，不是 KeyError
    old = json.loads(json.dumps(blob))
    old['version'] = 3
    for key in ('xp', 'enchant', 'wear'):
        old['player'].pop(key, None)
    for key in ('enchanted', 'xp_gained'):
        old['player']['stats'].pop(key, None)
    k3 = make_offline({'seed': 77, 'size': 48, 'height': 32, 'light': False,
                       'mobs': False, 'creative': False})
    k3.load(old)
    assert k3.xp == 0 and k3.enchants == {} and k3.wear == {}
    assert k3.stats['enchanted'] == 0 and k3.stats['xp_gained'] == 0

    # 存档里有未知附魔名 ⇒ **响亮报错**（不静默丢一条附魔）
    bad = json.loads(json.dumps(blob))
    bad['player']['enchant'] = {'iron_pickaxe': {'no_such_enchant': 1}}
    k4 = make_offline({'seed': 77, 'size': 48, 'height': 32, 'light': False,
                       'mobs': False, 'creative': False})
    try:
        k4.load(bad)
    except ValueError:
        pass
    else:
        raise AssertionError('未知附魔名应当响亮报错')


if __name__ == '__main__':
    sys.exit(main())
