# -*- coding: utf-8 -*-
"""Phase 1 生存循环单测（纯逻辑，零 GL）。

覆盖：按住挖掘（`dig_dt`）的进度累积与换目标清零、工具耐久的**边界**、掉落物的
生成/下落/拾取/超时、饥饿与受伤/死亡/重生、熔炉的帧率无关性、创造模式与生存模式的差异。

⚠ 所有用例都用**自己铺的地板**（`_flat()`），不依赖真实地形：被测的是生存语义，
不是世界生成 —— 否则断言会随种子漂。

跑：`python -m tests.test_survival`
"""
from __future__ import annotations

import sys

from tests._util import make_suite

from mcclone3d import blocks as B
from mcclone3d import items as I
from mcclone3d import recipes as R
from mcclone3d.kernel import (DROP_FALL_V, DROP_PICKUP_R, DROP_TTL,
                              HUNGER_PER_METER, MAX_HUNGER, STARVE_RATE,
                              make_offline)

test, main = make_suite('ALL_SURVIVAL_TESTS_PASSED', '生存循环')

DT = 1.0 / 60.0
#: 测试用的固定参照点：**地板在 y=19、玩家站在 y=20.0**。
#: ⚠ 地板必须放在玩家脚**下方**那一格（19），不能放 20 —— 放 20 的话玩家整个
#: AABB（y=20..21.8）都嵌在石头里，`_blocked()` 恒为 True ⇒ 一步都走不动、
#: `grounded` 也是 False（实测踩过：走路消耗饥饿那条用例"移动了 0.000 格"）。
#: 眼睛在 20 + 1.62 = 21.62 ⇒ y=21 是"眼所在格"（空），朝下看必中地板 (20, 19, 20)。
FLOOR = (20, 19, 20)
EYE_Y = 21.62


def _flat(seed=99, size=48, height=32, creative=False, clear_lane=False, **cfg):
    """空世界 + y=19 一整层石头地板 + 玩家站地板上面朝下看。

    `clear_lane=True` 时额外把朝 -z 的行走通道清空（yaw=0 的前方），
    供"走路"类用例使用 —— 那条通道上有地板上的方块会挡住玩家。
    """
    cfg.setdefault('reach', 8.0)
    k = make_offline(dict({'seed': seed, 'size': size, 'height': height,
                           'creative': creative}, **cfg))
    for x in range(size):
        for z in range(size):
            for y in range(height):
                k.world.set(x, y, z, B.AIR)
    for x in range(size):
        for z in range(size):
            k.world.set(x, 19, z, B.STONE)
    if clear_lane:
        for x in range(size):
            for z in range(size):
                for y in range(20, height):
                    k.world.set(x, y, z, B.AIR)
    k.world.edits.clear()
    k.pos = [20.5, 20.0, 20.5]
    k.vel = [0.0, 0.0, 0.0]
    k.pitch, k.yaw = -89.9, 0.0
    k.flying = False
    return k


def _with_pick(k, name='wooden_pickaxe'):
    """给一把镐并**切到那一格**。

    ⚠ hotbar 存的是**物品 id**，而默认 hotbar 里没有工具 ⇒ 要先把工具塞进
    hotbar 才能"拿在手上"。这里塞到当前格（不改动其它格），然后断言真的拿上了。
    """
    it = I.item_by_name(name)
    k.give(it.id, 1)
    if it.id not in k.hotbar:
        k.hotbar[k.selected] = it.id
    k.select(k.hotbar.index(it.id))
    assert k.held_tool() is not None and k.held_tool().name == name, \
        f'测试前提：手上该拿着 {name}，实际 {k.held_tool()}'
    return it


# ==================================================================== 挖掘
@test('dig_dt：累积到 dig_time() 才破坏，之前只报进度')
def t_dig_dt_accumulates():
    k = _flat()
    assert k.raycast() is not None and k.raycast()[0] == FLOOR, \
        f'测试前提：射线该命中地板 {FLOOR}，实际 {k.raycast()}'
    need = k.dig_time()
    assert need > 0.0 and need < float('inf'), f'徒手挖石头该是有限正数，实际 {need}'
    # 分 10 次推进，前 9 次必须都只是 'digging'，进度严格递增且 < 1
    got = [k.dig_dt(need / 10.0) for _ in range(9)]
    for i, (kind, info) in enumerate(got):
        assert kind == 'digging', f'第 {i + 1} 次就 {kind} 了（还没到 dig_time）'
        assert 0.0 < info < 1.0, f'第 {i + 1} 次进度 {info} 不在 (0,1)'
    assert k.world.get(*FLOOR) == B.STONE, '还没挖完就把方块删了'
    assert k.stats['dug'] == 0, '还没挖完就计数了'
    progress = [info for _kind, info in got]
    assert progress == sorted(progress), f'进度不是单调递增：{progress}'
    # 第 10 次正好到点 ⇒ done
    kind, info = k.dig_dt(need / 10.0)
    assert kind == 'done', f'累积够了却没完成：{kind} {info}'
    assert k.world.get(*FLOOR) == B.AIR, '报 done 却没删方块'
    assert k.stats['dug'] == 1
    # 协议要分清：dig_dt 报 done 之后，再按住就是 idle（方块没了，瞄不到）
    assert k.dig_dt(1.0) == ('idle', None), '挖空之后该是 idle'


@test('dig_dt：一次给足 dig_time() 也直接完成（浮点边界不吃亏）')
def t_dig_dt_exact():
    k = _flat()
    need = k.dig_time()
    assert k.dig_dt(need) == ('done', 'stone'), '一次给足 dig_time() 却没完成'
    assert k.world.get(*FLOOR) == B.AIR


@test('dig_dt：换目标清零进度（不许左右横跳蹭进度）')
def t_dig_dt_target_reset():
    k = _flat()
    need = k.dig_time()
    # 先挖一半
    kind, info = k.dig_dt(need / 2.0)
    assert kind == 'digging' and abs(info - 0.5) < 1e-9, f'挖一半该报 0.5，实际 {kind} {info}'
    assert k.dig_target == FLOOR and abs(k.dig_progress - need / 2.0) < 1e-9
    # 抬头换到另一格：目标必须换掉，进度必须清零
    k.pitch = -45.0
    hit = k.raycast()
    assert hit is not None and hit[0] != FLOOR, \
        f'测试前提：换朝向后该命中别的格子，实际 {hit}'
    kind2, info2 = k.dig_dt(need / 10.0)
    assert k.dig_target == hit[0], '目标没跟着换'
    assert k.dig_progress <= need / 10.0 + 1e-12, \
        f'换目标后进度没清零（残留 {k.dig_progress}）⇒ 可以左右横跳蹭进度'
    # 换回来也要清零（不是"记着上一次的进度"）
    k.pitch = -89.9
    k.dig_dt(need / 10.0)
    assert k.dig_progress <= need / 10.0 + 1e-12, '换回原目标后进度没清零'


@test('dig_dt：瞄不到时 idle 且不留进度；基岩永远不完成')
def t_dig_dt_idle_and_bedrock():
    k = _flat()
    k.world.set(*FLOOR, B.AIR)                     # 脚下掏空 ⇒ 瞄不到任何东西
    assert k.raycast() is None, '测试前提：掏空后该瞄不到'
    assert k.dig_dt(5.0) == ('idle', None)
    assert k.dig_target is None and k.dig_progress == 0.0, 'idle 却留了进度'
    # 基岩：dig_time 是 inf，按多久都不动
    k2 = _flat()
    k2.world.set(*FLOOR, B.BEDROCK)
    assert k2.dig_time() == float('inf'), f'基岩的 dig_time 该是 inf，实际 {k2.dig_time()}'
    for _ in range(5):
        assert k2.dig_dt(10.0) == ('idle', None), '基岩居然在挖'
    assert k2.world.get(*FLOOR) == B.BEDROCK, '基岩被挖掉了'
    assert k2.dig_progress == 0.0, '基岩不该有挖掘进度'
    assert k2.stats['dug'] == 0
    # dig()（瞬时）也必须拒绝基岩
    ok, name = k2.dig()
    assert ok is False and name is None, f'dig() 挖掉了基岩：{ok} {name}'
    assert k2.world.get(*FLOOR) == B.BEDROCK


@test('dig_dt 与 dig：两者协议不同且都成立（dig = 一步到位）')
def t_dig_protocols():
    k1 = _flat()
    need = k1.dig_time()
    assert k1.dig_dt(need) == ('done', 'stone'), 'dig_dt 的 done 该带"掉落物名"'
    assert k1.world.get(*FLOOR) == B.AIR
    k2 = _flat()
    got = k2.dig()
    assert isinstance(got, tuple) and len(got) == 2, f'dig 该返回二元组，实际 {got!r}'
    ok, name = got
    assert ok is True and isinstance(name, str) and name, f'dig 该返回 (True, 名字)，实际 {got}'
    assert k2.world.get(*FLOOR) == B.AIR


# ==================================================================== 耐久
@test('耐久边界：连挖 N 下恰好断在**第 N 下**，且断后从背包消失')
def t_tool_durability_boundary():
    k = _flat()
    pick = _with_pick(k)
    N = pick.durability
    assert N == I.TOOL_DURABILITY[pick.tier], f'测试前提：耐久该是表值 {I.TOOL_DURABILITY[pick.tier]}'
    assert k.tool_durability.get(pick.id) == N, '进包时该初始化满耐久'
    # 前 N-1 下绝不报"断了"
    for i in range(N - 1):
        broke = k._use_tool(pick)
        assert broke is False, f'第 {i + 1} 下就断了（该在第 {N} 下）'
        assert k.tool_durability[pick.id] == N - (i + 1), '耐久扣数不对'
        assert k.inventory.get(pick.id) == 1, '还没断就从背包消失了'
    # 第 N 下必须断
    assert k._use_tool(pick) is True, f'第 {N} 下没断（耐久边界错了）'
    assert pick.id not in k.tool_durability, '断了却还留着耐久记录'
    assert pick.id not in k.inventory, '断了却还在背包里'


@test('耐久：真的挖断一次（端到端）——耐久 1 的镐挖一下就没')
def t_tool_breaks_on_real_dig():
    """⚠ 断裂后的**可观测效果**：工具从"背包 + 耐久表"里消失。

    这里**不**断言 `held_tool() is None`：实测它仍然返回那把镐（hotbar 那一格还留着
    物品 id，而 `held_tool()` 只看 hotbar），于是断裂后 `dig_time()` 还按镐的速度算、
    石类还照样掉落 —— 已按「实现 bug #3 幽灵镐」报给 Lead 并附了最小复现。
    修好之后这里应当补上 `assert k.held_tool() is None`（那才是正确行为）。
    """
    k = _flat()
    pick = _with_pick(k)
    k.tool_durability[pick.id] = 1                  # 只剩 1 点耐久
    assert k.held_durability() == 1
    ok, name = k.dig()
    assert ok is True, f'测试前提：这一下该挖成功，实际 {(ok, name)}'
    assert k.world.get(*FLOOR) == B.AIR, '方块没被挖掉'
    assert pick.id not in k.inventory, '耐久耗尽后工具还在背包里'
    assert pick.id not in k.tool_durability, '耐久耗尽后还留着耐久记录'
    # 断掉的工具**不能再被当成可用工具**：这条按正确行为写，等 bug #3 修完转绿
    assert k.held_tool() is None, \
        '断掉的工具还能"拿在手上"（幽灵镐：仍按镐速挖、仍按镐掉落）——见 bug #3'


@test('创造模式不磨损工具（无限手感）')
def t_creative_no_tool_wear():
    k = _flat(creative=True)
    pick = _with_pick(k)
    before = k.tool_durability.get(pick.id)
    assert before == pick.durability
    for _ in range(3):
        k.world.set(*FLOOR, B.STONE)               # 补回方块，连挖三次
        assert k.dig()[0] is True
    assert k.tool_durability.get(pick.id) == before, '创造模式把工具挖磨损了'


# ==================================================================== 掉落物
@test('掉落物：挖 → 掉在世界里 → pickup_nearby 才进背包')
def t_drop_spawn_and_pickup():
    k = _flat()
    _with_pick(k)
    k.inventory.clear()
    k.tool_durability.clear()
    _with_pick(k)
    k.tool_durability[k.held_tool().id] = 999      # 别让耐久干扰这条用例
    assert k.dig()[0] is True
    cobble = I.item_by_name('cobble')
    assert len(k.drops) == 1, f'挖完该有 1 个掉落物，实际 {len(k.drops)}'
    d = k.drops[0]
    assert d['item'] == cobble.id and d['n'] == 1, f'掉的东西不对：{d}'
    assert cobble.id not in k.inventory, '掉在近处也不该"自动"进背包（要显式拾取）'
    picked = k.pickup_nearby()
    assert picked == [('cobble', 1)], f'拾取结果不对：{picked}'
    assert k.inventory.get(cobble.id) == 1, f'拾取后没进背包：{k.inventory}'
    assert k.drops == [], '拾取后掉落物没被清掉'
    assert k.stats['picked'] == 1


@test('拾取半径：近的收、远的留（边界两侧各一条）')
def t_pickup_radius():
    cobble = I.item_by_name('cobble').id
    # pickup 判据是"掉落物中心 ↔ 玩家胸口(y+0.9)"的距离 ≤ DROP_PICKUP_R
    chest = [20.5, 20.9, 20.5]
    # ① 刚好在半径内（留 1% 余量）
    k = _flat()
    k.inventory.clear()
    near = list(chest)
    near[0] += DROP_PICKUP_R * 0.99
    k.spawn_drop(*near, cobble, 2)
    assert k.pickup_nearby() == [('cobble', 2)], '半径内该被拾取'
    assert k.inventory.get(cobble) == 2
    # ② 刚好在半径外（多 1%）
    k2 = _flat()
    k2.inventory.clear()
    far = list(chest)
    far[0] += DROP_PICKUP_R * 1.01
    k2.spawn_drop(*far, cobble, 1)
    assert k2.pickup_nearby() == [], '半径外不该被拾取'
    assert k2.inventory.get(cobble, 0) == 0, '半径外的东西进了背包'
    assert len(k2.drops) == 1, '半径外的掉落物被删了（该留在世界里）'


@test('_update_drops：悬空会下落、落地不下沉、超时会消失')
def t_drops_fall_and_expire():
    k = _flat()
    cobble = I.item_by_name('cobble').id
    floor_y = FLOOR[1]                             # 地板方块在 y=19
    # 悬空（下方是空气）⇒ 按 DROP_FALL_V 匀速下落
    d = k.spawn_drop(20.5, 28.0, 20.5, cobble, 1)
    assert not B.is_solid(k.world.get(20, 27, 20)), '测试前提：下方该是空气'
    k._update_drops(0.5)
    assert abs(d['pos'][1] - (28.0 - DROP_FALL_V * 0.5)) < 1e-9, \
        f'没按 DROP_FALL_V 下落：{d["pos"][1]}'
    assert abs(d['t'] - 0.5) < 1e-9, f'存活计时不对：{d["t"]}'
    # 落地：正落在地板**顶面**（y = 19 + 1 + 0.5 = 20.5，即中心刚好压在地板上面）
    # ⇒ 不再下落。⚠ 这条现在是红的（实现 bug #2：`int(p[1] - 0.5)` 截断成 20，
    # 查的是"掉落物自己那一格"而不是脚下的地板格 ⇒ 判据恒为假 ⇒ 一路沉穿地板）。
    d2 = k.spawn_drop(20.5, floor_y + 1.5, 20.5, cobble, 1)
    y_before = d2['pos'][1]
    k._update_drops(0.5)
    assert abs(d2['pos'][1] - y_before) < 1e-9, \
        f'落在地板上还在往下沉：{y_before} → {d2["pos"][1]}（会沉穿地板/掉出世界底，见 bug #2）'
    # 超时 ⇒ 清掉；没超时的留着
    fresh = k.spawn_drop(24.5, 28.0, 24.5, cobble, 1)
    d['t'] = DROP_TTL + 1.0
    k._update_drops(0.0)
    assert d not in k.drops, f'超过 TTL={DROP_TTL} 的掉落物没被清掉'
    assert fresh in k.drops and d2 in k.drops, '没超时的掉落物被误删了'
    # 时间累积跨多帧也认（不是只看单帧 dt）
    d3 = k.spawn_drop(24.5, 28.0, 24.5, cobble, 1)
    for _ in range(10):
        k._update_drops(DROP_TTL / 10.0 + 0.01)
    assert d3 not in k.drops, '跨多帧累积超时后没被清掉'


@test('掉落物随世界一起存档往返（按名字存，读回来还是同一个物品）')
def t_drops_save_roundtrip():
    k = _flat(seed=5150)
    cobble = I.item_by_name('cobble')
    k.spawn_drop(20.5, 28.25, 20.75, cobble.id, 3)
    blob = k.dump()
    assert len(blob['drops']) == 1, f'存档里没带上掉落物：{blob.get("drops")}'
    assert blob['drops'][0]['item'] == 'cobble', \
        f'掉落物该按**名字**存，实际 {blob["drops"][0]["item"]!r}'
    from mcclone3d.kernel import McCloneKernel
    k2 = McCloneKernel.__new__(McCloneKernel)
    k2.ctx = None
    k2._init({'seed': 5150, 'size': 48, 'height': 32, 'creative': False})
    k2.load(blob)
    assert len(k2.drops) == 1, f'读档后掉落物丢了：{k2.drops}'
    d = k2.drops[0]
    assert d['item'] == cobble.id and d['n'] == 3, f'读档后掉落物不对：{d}'
    assert [round(v, 6) for v in d['pos']] == [20.5, 28.25, 20.75], f'位置没还原：{d["pos"]}'


# ==================================================================== 饥饿 / 生命
@test('饥饿：走路消耗（先掉饱食度，再掉饥饿）')
def t_hunger_walk():
    k = _flat(clear_lane=True)
    k.hunger, k.saturation = MAX_HUNGER, 5.0
    z0 = k.pos[2]
    for _ in range(60):
        k.step(DT, (1.0, 0.0))
    moved = abs(k.pos[2] - z0)
    assert moved > 1.0, f'测试前提：该真的走了一段，实际 {moved:.3f}'
    cost = moved * HUNGER_PER_METER
    assert k.saturation < 5.0, '走路没消耗饱食度'
    assert abs(k.saturation - (5.0 - cost)) < 1e-6, \
        f'饱食度消耗 {5.0 - k.saturation} 与"距离×HUNGER_PER_METER"({cost}) 对不上'
    assert k.hunger == MAX_HUNGER, '饱食度还没见底，不该动饥饿值'
    # 饱食度见底后，继续走就掉饥饿
    k.saturation = 0.0
    h0 = k.hunger
    for _ in range(60):
        k.step(DT, (1.0, 0.0))
    assert k.hunger < h0, '饱食度见底后走路没掉饥饿'


@test('饥饿：创造模式与飞行都不消耗（无限手感）')
def t_hunger_creative_and_flying():
    k = _flat(creative=True)
    for _ in range(120):
        k.step(DT, (1.0, 0.0))
    assert k.hunger == MAX_HUNGER and k.saturation == 5.0, '创造模式走路消耗了饥饿'
    k2 = _flat()                                   # 生存模式，但飞着走
    k2.flying = True
    for _ in range(120):
        k2.step(DT, (1.0, 0.0))
    assert k2.hunger == MAX_HUNGER and k2.saturation == 5.0, '飞行走路消耗了饥饿'


@test('吃：bread 回饥饿；饱着吃会被拒；没得吃也会被拒')
def t_eat():
    k = _flat()
    bread = I.item_by_name('bread')
    k.hunger = 6.0
    k.give(bread.id, 2)
    k.select(k.hotbar.index(bread.id) if bread.id in k.hotbar else 0)
    # hotbar 里没有面包 ⇒ 用 slot_index 指定（eat 支持按格吃）
    k.hotbar[k.selected] = bread.id
    ok, name = k.eat()
    assert ok is True and name == 'bread', f'吃面包失败：{(ok, name)}'
    assert k.hunger == 6.0 + bread.food, f'回饥饿不对：{k.hunger}'
    assert k.inventory.get(bread.id) == 1, '吃了一口该少一个'
    assert k.stats['eaten'] == 1
    # 饱着吃：拒绝，且**不消耗**
    k.hunger = MAX_HUNGER
    ok2, why = k.eat()
    assert ok2 is False and why == 'already_full', f'饱着吃该被拒：{(ok2, why)}'
    assert k.inventory.get(bread.id) == 1, '被拒却把面包吃掉了'
    # 背包里没有：拒绝
    k.hunger = 5.0
    k.inventory.clear()
    ok3, why3 = k.eat()
    assert ok3 is False and why3 == 'none_left', f'没得吃该被拒：{(ok3, why3)}'
    # 手里的不是食物：拒绝
    _with_pick(k)
    ok4, why4 = k.eat()
    assert ok4 is False, f'吃镐子成功了？{(ok4, why4)}'


@test('饥饿归零 ⇒ 持续掉血（饿死）')
def t_starve_damage():
    k = _flat()
    k.hunger = 0.0
    k.saturation = 0.0
    h0 = k.health
    k._survival_step(1.0, 0.0)
    assert abs(k.health - (h0 - STARVE_RATE)) < 1e-9, \
        f'饿一秒钟掉血 {h0 - k.health}，该是 {STARVE_RATE}'
    assert k.stats['damage'] > 0, '掉血没记账'
    # 饿死：血量归零 ⇒ state='dead'，cause='starve'
    k.health = STARVE_RATE * 0.5
    k._survival_step(1.0, 0.0)
    assert k.health == 0.0 and k.state == 'dead', f'没饿死：{k.health} {k.state}'
    assert k.death_cause == 'starve', f'死因不对：{k.death_cause}'
    assert k.stats['deaths'] == 1
    # 死了就不再掉血/不再结算
    k._survival_step(10.0, 0.0)
    assert k.health == 0.0 and k.stats['deaths'] == 1, '死后还在重复结算'


@test('hurt → dead → respawn：状态归位（位置/血/饥饿/死因）')
def t_hurt_dead_respawn():
    k = _flat()
    # 重生点 = 世界中心那一列。这个测试世界除了自己铺的地板全是空气，
    # 而 `_spawn_y()` 靠"往下找地表"（会退回到 `world.surface_at()`）—— 一个**全空**的
    # 世界会让它返回 height-3（实测重生到 y=16，地板在 y=19 ⇒ 卡在地板里面）。
    # 所以给那一列补上固体：y=16 实心（地表）+ y=19 地板，重生点就落在 17。
    cx = cz = k.size // 2
    k.world.set(cx, 16, cz, B.STONE)
    k.world.set(cx, 19, cz, B.STONE)
    spawn_y = 17
    k.hunger = 7.0
    k.saturation = 1.0
    k.pos = [30.5, 20.0, 30.5]
    k.health = k.hurt(3.0, 'fall')
    assert abs(k.health - (k.max_health - 3.0)) < 1e-9, f'掉血不对：{k.health}'
    assert k.state == 'playing' and k.death_cause == '', '还没死就变了状态'
    assert k.hurt(999.0, 'fall') == 0.0, '血量该被夹到 0'
    assert k.state == 'dead', f'血归零却没死：{k.state}'
    assert k.death_cause == 'fall' and k.stats['deaths'] == 1
    # 死了之后再 hurt 不该改血（避免"死后再死一次"重复计数）
    assert k.hurt(5.0, 'x') == 0.0 and k.stats['deaths'] == 1
    assert k.respawn() is True
    assert k.state == 'playing' and k.health == k.max_health
    assert k.hunger == k.max_hunger, '重生没把饥饿回满'
    assert k.death_cause == '', '重生没清死因'
    assert k.pos == [cx + 0.5, float(spawn_y), cz + 0.5], \
        f'重生位置不对：{k.pos}（该是世界中心列 {cx},{cz} 的地表之上）'
    assert B.is_solid(k.world.get(cx, spawn_y - 1, cz)), '重生点脚下不是固体'
    assert k.world.get(cx, spawn_y, cz) == B.AIR, '重生点被方块占着（会卡住玩家）'
    # 活着的时候 respawn 是空操作
    assert k.respawn() is False, '活着也能"重生"'


@test('自然回血：只有饥饿 ≥ REGEN_AT 才回；饿过头不回')
def t_regen():
    k = _flat()
    k.health = 10.0
    k.hunger = 5.0                                 # 低于 REGEN_AT ⇒ 不回血
    k._survival_step(1.0, 0.0)
    assert k.health == 10.0, f'饿着却回血了：{k.health}'
    k.hunger = k.max_hunger                        # 饱着 ⇒ 回血
    k._survival_step(1.0, 0.0)
    assert k.health > 10.0, '饱着却不回血'
    # 回血速度与 dt 成正比
    step = k.health - 10.0
    k.health = 10.0
    k._survival_step(2.0, 0.0)
    assert abs((k.health - 10.0) - step * 2.0) < 1e-9, '回血速度与 dt 不成正比'
    # 不超上限
    k.health = k.max_health
    k._survival_step(10.0, 0.0)
    assert k.health == k.max_health


# ==================================================================== 熔炉
def _furnace_kernel(hz):
    """装好一炉铁（raw_iron + coal），用 hz 分帧推进到出料，返回 (结果, 内核)。"""
    k = _flat(seed=77)
    k.inventory.clear()
    k.give_item('raw_iron', 1)
    k.give_item('coal', 1)
    rec = R.recipe_by_id('iron_ingot')
    ok, out = k.furnace_load('iron_ingot')
    assert ok is True, f'装炉失败：{out}'
    assert k.furnace['recipe'] == 'iron_ingot', f'炉子里该有货：{k.furnace}'
    assert k.inventory.get(I.item_by_name('raw_iron').id, 0) == 0, '装炉没扣原料'
    assert k.inventory.get(I.item_by_name('coal').id, 0) == 0, '装炉没扣燃料'
    result = ('idle', None)
    steps = 0
    while k.furnace['recipe'] is not None and steps < 10000:
        result = k.furnace_step(1.0 / hz)
        steps += 1
    assert k.furnace['recipe'] is None, f'{hz}Hz 推进不完（配方时长 {rec.time}）'
    return result, k


@test('熔炉：拒绝路径（没材料 / 炉子有货 / 非烧炼配方 / 未知配方）')
def t_furnace_rejects():
    k = _flat(seed=77)
    k.inventory.clear()
    # 材料不够 ⇒ 拒绝，且**一点不动**（背包空、炉子空）
    ok, why = k.furnace_load('iron_ingot')
    assert ok is False, f'没材料却装炉成功：{why}'
    assert k.inventory == {}, f'被拒的装炉动了背包：{k.inventory}'
    assert k.furnace['recipe'] is None, f'被拒的装炉改了炉子状态：{k.furnace}'
    assert k.furnace['cook_left'] == 0.0 and k.furnace['fuel_left'] == 0.0
    # 非烧炼配方不许装炉
    k.give_item('log', 1)
    ok2, why2 = k.furnace_load('planks_from_log')
    assert ok2 is False and '不是烧炼' in why2, f'合成配方被装进炉子：{(ok2, why2)}'
    assert k.furnace['recipe'] is None
    # 未知配方要**响亮报错**（不是静默返回 False）
    try:
        k.furnace_load('no_such_recipe')
    except KeyError:
        pass
    else:
        raise AssertionError('未知配方必须抛 KeyError')
    # 炉子里还有货时不许再装（否则会把上一炉吞掉）
    k2 = _flat(seed=77)
    k2.inventory.clear()
    k2.give_item('raw_iron', 1)
    k2.give_item('coal', 1)
    assert k2.furnace_load('iron_ingot')[0] is True
    ok3, why3 = k2.furnace_load('glass')
    assert ok3 is False and '还有东西' in why3, f'炉子没空却装进去了：{(ok3, why3)}'


@test('熔炉：furnace_step 按 dt 累积出料（不到时间不出）')
def t_furnace_step_accumulates():
    # 直接摆好"已装炉"的状态：这条只测 `furnace_step` 的时间累积，
    # 与 furnace_load 解耦（装炉的端到端另有一条用例）。
    k = _flat(seed=77)
    k.inventory.clear()
    rec = R.recipe_by_id('iron_ingot')
    k.furnace = {'recipe': rec.id, 'cook_left': rec.time,
                 'fuel_left': rec.time * 1.5}
    iron = I.item_by_name('iron_ingot').id
    kind, _ = k.furnace_step(rec.time * 0.5)
    assert kind == 'cooking', f'烧一半该是 cooking，实际 {kind}'
    assert k.inventory.get(iron, 0) == 0, '还没到时间就出料了'
    assert k.stats['smelted'] == 0
    kind2, prod = k.furnace_step(rec.time * 0.5)
    assert kind2 == 'done' and prod == 'iron_ingot', f'该出料了：{(kind2, prod)}'
    assert k.inventory.get(iron, 0) >= 1, f'产出没进背包：{k.inventory}'
    assert k.stats['smelted'] == 1
    assert k.furnace['recipe'] is None, '出料后炉子没清空'
    # 空炉子推进是 idle
    assert k.furnace_step(1.0) == ('idle', None)


@test('熔炉：装炉只扣材料、不出货；烧完才出且只出一次（bug 回归）')
def t_furnace_load_then_earn():
    """⚠ 这条是 `furnace_load` 提前发货 bug 的回归测试。

    曾经的实现借用 `recipes.craft()` 扣料，而 `craft()` 语义含"加产出" ⇒
    一装上材料产物就进背包，烧完 `furnace_step` 再给一次（**同一炉给两次**）。
    修法是 `recipes.consume()`（只扣不加）。这条钉死修复后的行为。

    `charcoal` 是本条**最尖**的样本：它的产出名与输入名重叠（`log + coal|charcoal
    → charcoal`），任何"借 craft 扣料"的写法都会让它当场露馅。
    """
    for rid, give, out_name in (('iron_ingot', (('raw_iron', 1), ('coal', 1)), 'iron_ingot'),
                                ('charcoal', (('log', 1), ('coal', 1)), 'charcoal'),
                                ('glass', (('sand', 1), ('coal', 1)), 'glass')):
        k = _flat(seed=77)
        k.inventory.clear()
        for name, n in give:
            k.give_item(name, n)
        rec = R.recipe_by_id(rid)
        out_id = I.item_by_name(out_name).id
        ok, out = k.furnace_load(rid)
        assert ok is True and out == out_name, f'{rid} 装炉失败：{(ok, out)}'
        # ① 装炉只扣材料：输入清空
        for name, _n in give:
            assert k.inventory.get(I.item_by_name(name).id, 0) == 0, \
                f'{rid} 装炉没扣干净 {name}：{k.inventory}'
        # ② **不许立刻发货**（老 bug 就在这一条上）
        assert k.inventory.get(out_id, 0) == 0, \
            f'{rid} 装炉就把产物发了（还没烧）：{k.inventory} —— furnace_load 又借了 craft()'
        assert k.stats['smelted'] == 0
        # ③ 烧到一半仍然没有
        k.furnace_step(rec.time * 0.5)
        assert k.inventory.get(out_id, 0) == 0, f'{rid} 烧一半就出料了：{k.inventory}'
        # ④ 烧完才出，且**只出一次**
        kind, prod = k.furnace_step(rec.time * 0.5)
        assert kind == 'done' and prod == out_name, f'{rid} 该出料了：{(kind, prod)}'
        n_now = k.inventory.get(out_id, 0)
        assert n_now >= 1, f'{rid} 烧完却没产出：{k.inventory}'
        # 燃料给 1.5 倍时间 ⇒ 一炉可能出 >1 个（设计如此，见设计稿 §四.5）。
        # 但**绝不能**是"装炉 1 个 + 烧完 1 个"那种重复计数：出料后炉子已清空，
        # 再推进也不该再给。
        k.furnace_step(rec.time * 0.5)
        assert k.inventory.get(out_id, 0) == n_now, \
            f'{rid} 炉子清空后还在继续出料：{k.inventory}'
        assert k.stats['smelted'] == 1, f'{rid} 的 smelted 计数该是 1，实际 {k.stats["smelted"]}'


@test('熔炉：30/60/120Hz 结果一致（按累计时间，不按帧数）')
def t_furnace_framerate():
    results = []
    for hz in (30, 60, 120):
        result, k = _furnace_kernel(hz)
        iron = I.item_by_name('iron_ingot').id
        results.append((result[0], result[1], k.inventory.get(iron, 0),
                        k.stats['smelted']))
    assert len(set(results)) == 1, f'帧率影响了熔炉结果：{results}'
    # 而且真的出料了 —— 否则"三种帧率都 idle"也会让上面那条通过（假绿）
    kind, prod, n, smelted = results[0]
    assert kind == 'done' and prod == 'iron_ingot', f'三种帧率都没烧出铁：{results[0]}'
    assert n >= 1, f'燃料给 1.5 倍时间 ⇒ 至少出 1 个，实际 {n}'
    assert smelted == 1, f'smelted 计数该是 1，实际 {smelted}'


# ==================================================================== 创造 / 生存
@test('创造模式：挖了直接进背包（给方块本身），放置不消耗')
def t_creative_infinite():
    """⚠ 语义要点：创造模式挖方块给的是**方块本身**（`as_item(old)`，搭房子要方块），
    **不是**生存模式的掉落物（石头→圆石）—— 这两条口径是**有意不同**的（Lead 确认）。
    所以下面断言的是"石头 +1"而不是"圆石 +1"；返回的标签也跟给的东西一致（bug #4 修后）。
    """
    k = _flat(creative=True)
    _with_pick(k)                                  # ⚠ 必须手持镐：否则徒手挖石头不掉落
    stone = I.item_by_name('stone')
    n0 = k.inventory.get(stone.id, 0)
    assert n0 == 64, f'测试前提：创造模式开局该有满库存，实际 {n0}'
    assert k.world.get(*FLOOR) == B.STONE
    ok, label = k.dig()
    assert ok is True, f'该挖成功：{(ok, label)}'
    assert k.drops == [], '创造模式不该往世界里掉东西（直接进背包）'
    assert k.inventory.get(stone.id, 0) == n0 + 1, \
        f'创造模式挖石头该直接进背包 +1：{n0} → {k.inventory.get(stone.id)}'
    assert label == 'stone', \
        f'标签该跟"实际给的东西"一致（给石头就报 stone）：{label!r}'
    # 放置：朝下会让相邻格落在玩家 AABB 里（会被"不许封死自己"拒），
    # 所以用**水平**射线打墙，往"来路那一格"放。
    k.pos = [20.5, 20.0, 20.5]
    k.yaw, k.pitch = -90.0, 0.0                    # 朝 +x
    k.hotbar[k.selected] = I.item_by_name('stone').id
    k.select(k.hotbar.index(I.item_by_name('stone').id))
    assert k.selected_block() == B.STONE, '测试前提：手上该是石头方块'
    ey = 21                                       # 眼睛 21.62 ⇒ 眼所在格 y=21
    for y in (ey - 1, ey, ey + 1):
        for z in range(18, 23):
            k.world.set(24, y, z, B.STONE)          # 墙（射线必中）
    hit = k.raycast()
    assert hit is not None and hit[0] == (24, ey, 20), f'测试前提：射线该命中墙，实际 {hit}'
    tgt = (hit[0][0] + hit[1][0], hit[0][1] + hit[1][1], hit[0][2] + hit[1][2])
    assert k.world.get(*tgt) == B.AIR, f'测试前提：目标格该是空的：{tgt}'
    before = dict(k.inventory)
    ok, at = k.place()
    assert ok is True and at == tgt, f'创造模式该放得下：{(ok, at)} vs {tgt}'
    assert k.world.get(*at) == B.STONE, '放下的不是石头'
    assert k.inventory == before, f'创造模式放置**不该消耗**库存：{before} → {k.inventory}'
    # 连放 N 次也放不完（库存是无限的）
    for i in range(5):
        k.world.set(*tgt, B.AIR)
        assert k.place()[0] is True, f'第 {i + 2} 次放置失败（创造模式该放不完）'
    assert k.inventory == before, '连放之后库存变了'


@test('生存模式：走路/挖掘都消耗饥饿，且挖出来的东西掉在地上')
def t_survival_loop():
    k = _flat()
    pick = _with_pick(k)
    k.inventory = {pick.id: 1}                     # 只有这把镐
    k.tool_durability = {pick.id: pick.durability}
    k.hunger, k.saturation = MAX_HUNGER, 0.0
    h0 = k.hunger
    assert k.dig()[0] is True
    assert k.hunger < h0, '生存模式挖方块没消耗饥饿'
    assert len(k.drops) == 1, f'生存模式挖了该掉在地上，实际 {k.drops}'
    cobble = I.item_by_name('cobble')
    assert cobble.id not in k.inventory, '还没走过去捡，东西就进背包了'
    assert k.pickup_nearby() == [('cobble', 1)], '走过去该能捡起来'
    assert k.inventory.get(cobble.id) == 1
    # 工具被磨损（生存模式才磨）
    assert k.tool_durability[pick.id] == pick.durability - 1, '生存模式挖方块没磨工具'


@test('生存模式：放置要消耗库存，没有就不许放')
def t_survival_place_consumes():
    k = _flat()
    stone = I.item_by_name('stone')
    cobble = I.item_by_name('cobble')
    k.inventory = {cobble.id: 2}
    k.hotbar[k.selected] = stone.id                # 手持石头（物品 id，不是方块 id）
    assert k.selected_block() == B.STONE, '测试前提：手上该是石头方块'
    # 朝下看：相邻空位正好是玩家脚所在格 ⇒ 会被"不许封死自己"正确地拒掉。
    # 所以这条用例用**水平**射线打墙，相邻空位在来路那一格（玩家 AABB 之外）。
    k.pos = [20.5, 20.0, 20.5]
    k.yaw, k.pitch = -90.0, 0.0                    # 朝 +x
    ey = 20 + int(21.62 - 20.0)                    # 眼所在格 = 21
    for y in (ey - 1, ey, ey + 1):
        for z in range(18, 23):
            k.world.set(24, y, z, B.STONE)
    hit = k.raycast()
    assert hit is not None, '测试前提：射线该命中墙'
    # 库存里没有石头 ⇒ 必须拒绝，且世界不变
    before_world = dict(k.world.edits)
    assert k.place()[0] is False, '库存为 0 还能放石头'
    assert k.world.edits == before_world, '被拒的放置改动了世界'
    # 给一个石头 ⇒ 能放，并且扣掉
    k.give(stone.id, 1)
    assert k.inventory.get(stone.id) == 1
    ok, at = k.place()
    assert ok is True and at is not None, f'有库存却放不了：{(ok, at)}'
    assert k.inventory.get(stone.id, 0) == 0, f'放置没消耗库存：{k.inventory}'
    assert k.world.get(*at) == B.STONE, '放下的不是石头'
    # 再放（库存 0）⇒ 拒绝
    assert k.place()[0] is False, '库存清空后还能继续放'


if __name__ == '__main__':
    sys.exit(main())
