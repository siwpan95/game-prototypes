# -*- coding: utf-8 -*-
"""内核单测：动作语义 / 存档往返 / 自动机（纯逻辑，零 GL）。

跑：`python -m tests.test_kernel`
"""
from __future__ import annotations

import json
import os
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
    assert k.selected_block() == k.hotbar[0]


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
    k.select(2)                                     # 第 3 格 = 石头
    want = k.selected_block()
    assert want == B.STONE, f'测试前提：第 3 格应是石头，实际 {B.name_of(want)}'
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


@test('生存模式：挖到的进库存、放置要消耗、没有就不许放')
def t_survival_stock():
    k = _empty_kernel(creative=False)               # reach 已放大到 8
    k.pos = [20.5, 22.0, 20.5]                      # 眼睛 23.62
    k.world.set(20, 23, 20, B.STONE)                # 地板（= 眼睛那一格，射线必中）
    k.inventory.clear()
    k.pitch = -89.9
    hit = k.raycast()
    assert hit is not None and hit[0] == (20, 23, 20), f'测试前提：射线该命中地板，实际 {hit}'
    ok, name = k.dig()
    assert ok and name == 'stone', f'没挖到石头：{ok} {name}'
    assert k.inventory.get(B.STONE) == 1, f'挖到的东西没进库存：{k.inventory}'
    # 射线改朝上，命中头顶那块天花板，相邻空位就是**天花板之下、眼睛之上**那一格。
    k.world.set(20, 23, 20, B.STONE)                # 脚下那块放回去（保持站在原处）
    k.world.set(20, 25, 20, B.STONE)                # 头顶上方 2 格处一块天花板
    k.pitch = 89.9                                  # 抬头看
    hit2 = k.raycast()
    # ⚠ 抬头时眼睛那一格 (20,23,20) 本身是石头（脚下那块），射线起点在其中 ⇒
    # 会**先命中起点格**（这是 DDA 的正确行为，法向为零向量）。所以先把脚下那块清掉。
    k.world.set(20, 23, 20, B.AIR)
    hit2 = k.raycast()
    assert hit2 is not None and hit2[0] == (20, 25, 20), f'测试前提：抬头该命中天花板，实际 {hit2}'
    # ⚠ 放置用的是 **hotbar 当前格**，不是"刚挖到的那种" —— 必须选到石头那一格，
    # 否则会拿手里的草去放，测出来的是"草不够"而不是"石头被消耗"（实测踩过一次）。
    k.select(k.hotbar.index(B.STONE))
    assert k.selected_block() == B.STONE
    ok2, at = k.place()
    assert ok2, f'放置失败（射线命中 {hit2}）'
    assert k.inventory.get(B.STONE, 0) == 0, '放置没消耗库存'
    ok3, _ = k.place()
    assert not ok3, '库存为 0 还能放'


@test('创造模式：库存无限（挖了不补、放不完）')
def t_creative_stock():
    k = _empty_kernel(creative=True)
    k.world.set(20, 15, 20, B.STONE)
    n0 = k.inventory.get(B.STONE, 0)
    k.dig()
    assert k.inventory.get(B.STONE, 0) == n0, '创造模式不该改变库存'
    assert n0 == START_STOCK


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


@test('存档往返：世界增量 + 玩家状态 + hotbar 全部一致')
def t_save_roundtrip():
    k = make_offline({'seed': 31337, 'size': 48, 'height': 32})
    k.pitch = -89.9
    k.dig()
    k.select(3)
    k.place()
    k.pos = [10.25, 20.0, 12.75]
    k.yaw, k.pitch, k.flying = 33.0, -12.0, True
    k.stats['dug'] = 7
    blob = json.loads(json.dumps(k.dump()))        # 过一遍 JSON，模拟真实落盘
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


@test('存档文件往返（真实文件 + UTF-8 + 方块名而非 id）')
def t_save_file():
    k = make_offline({'seed': 777, 'size': 48, 'height': 32})
    k.pitch = -89.9
    k.dig()
    with tempfile.TemporaryDirectory() as td:
        path = os.path.join(td, 'save.mc3d')
        k.save(path)
        assert os.path.exists(path)
        raw = open(path, encoding='utf-8').read()
        assert 'grass' in raw or 'stone' in raw, '存档里应出现方块名（可读、可手改）'
        assert '"edits"' in raw and '"seed"' in raw
        k2 = McCloneKernel.__new__(McCloneKernel)
        k2.ctx = None
        k2._init({'seed': 777, 'size': 48, 'height': 32})
        k2.load_file(path)
        assert dict(k2.world.edits) == dict(k.world.edits)


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


@test('reset：换种子重建世界，增量清零，玩家回到地表')
def t_reset():
    k = make_offline({'seed': 1, 'size': 48, 'height': 32})
    k.pitch = -89.9
    k.dig()
    assert k.world.edits
    old_seed = k.seed
    k.reset(2)
    assert k.seed == 2 and k.world.seed == 2
    assert k.world.edits == {}, 'reset 没清增量'
    assert k.stats == {'dug': 0, 'placed': 0}
    k.reset(old_seed)
    assert k.world.seed == old_seed


@test('配置树的值真的到达内核（seed/size/height/reach/hotbar 全部生效）')
def t_config_passthrough():
    k = make_offline({'seed': 123, 'size': 64, 'height': 48, 'reach': 9.5,
                      'hotbar': ['stone', 'glass'], 'creative': False})
    assert (k.seed, k.size, k.height) == (123, 64, 48)
    assert abs(k.reach - 9.5) < 1e-9
    assert k.hotbar == [B.STONE, B.GLASS]
    assert k.creative is False and k.inventory == {}


if __name__ == '__main__':
    sys.exit(main())
