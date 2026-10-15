# -*- coding: utf-8 -*-
"""Phase 2-B 生物 AI 单测（纯逻辑，零 GL）。

覆盖 `ai.step_mob` 的状态机与运动、`kernel.update_mobs` 的收尾
（自燃/清理/刷怪）、`kernel.spawn_mob/hit_mob/attack` 的玩家侧交互。

世界是一块**平地理光世界**（`flat()`：全 AIR + y=19 一层石地板），
这样每条判据只测它自己那一件事，不受地形噪声干扰。

⚠ 与 `test_mobs` 的分层：那边测"数据与实体语义"（表契约、hurt、spawn_allowed
纯函数），这边测"AI 怎么走、怎么打、怎么刷"（行为对拍）。

跑：`python -m tests.test_ai`
"""
from __future__ import annotations

import math
import sys

from tests._util import make_suite

from mcclone3d import ai as AI
from mcclone3d import blocks as B
from mcclone3d import mobs as MB
from mcclone3d.kernel import MOB_CAP, make_offline
from mcclone3d.light import LightEngine

test, main = make_suite('ALL_AI_TESTS_PASSED', '生物 AI')

DT = 1.0 / 60.0
FLOOR_Y = 19                 # 平地理光世界的地板（脚底落在 y=20）
NIGHT_PHASE = 0.75           # 午夜前后的相位（`cycle.is_night()` 为真）


# ==================================================================== 夹具
def flat(seed=4242, size=48, height=32, **cfg):
    """平地理光世界：默认**关自动刷怪**（`mobs=False`），生物由用例显式放。

    光照重建 + `column_pass_all()`：`update_mobs` 的自燃判据要读 `light.sky`，
    不重算的话读到的是空场（0），判据会失真。
    """
    cfg.setdefault('mobs', False)
    k = make_offline({'seed': seed, 'size': size, 'height': height, **cfg})
    for x in range(size):
        for z in range(size):
            for y in range(height):
                k.world.set(x, y, z, B.AIR)
    for x in range(size):
        for z in range(size):
            k.world.set(x, FLOOR_Y, z, B.STONE)
    k.world.edits.clear()
    k.light = LightEngine(k.world)
    k.light.column_pass_all()
    k.pos = [24.5, FLOOR_Y + 1.0, 24.5]
    k.vel = [0.0, 0.0, 0.0]
    k.health = 1000.0
    return k


def add(k, name, x, y, z, state=None, age=0.0):
    """显式放一只生物（绕过 `spawn_mob` 的找点逻辑，位置精确可控）。"""
    m = MB.Mob(MB.mob_kind(name), x, y, z)
    if state is not None:
        m.state = state
    m.age = age
    k.mobs.append(m)
    return m


def run(k, seconds, dt=DT):
    for _ in range(int(round(seconds / dt))):
        k.update_mobs(dt)


# ==================================================================== 落地
@test('落地：从 y=28 落到平地地板，站稳在整数格且不再抖动')
def t_land_on_floor():
    k = flat()
    m = add(k, 'sheep', 10.5, 28.0, 10.5)
    ys = []
    for _ in range(300):
        k.update_mobs(DT)
        ys.append(m.pos[1])
    assert float(m.pos[1]).is_integer(), f'落点不是整数格：{m.pos[1]}'
    assert m.pos[1] == FLOOR_Y + 1.0, f'该落在地板顶面 y={FLOOR_Y + 1}：{m.pos[1]}'
    assert m.on_ground is True, '站稳了 on_ground 还是 False'
    # 站稳之后不再抖：最后 100 帧 y 一动不动（悬浮/抖动都会在这里现形）
    assert min(ys[-100:]) == max(ys[-100:]), \
        f'站稳后 y 还在抖：{min(ys[-100:])}..{max(ys[-100:])}'


@test('落地：沙堆顶部（站立点不是地板那一层）也能站稳')
def t_land_on_sand_pile():
    """地面不是 y=19：5×5 沙台在 20/21 ⇒ 生物要贴在沙顶 22。

    ⚠ 判据必须抓"刚落塔那一刻"：羊落地后会开始游荡，**走下了沙台**
    就掉回石地板（y=20）—— 那样测的是"游荡"，不是"吸附"（实测踩过）。
    """
    k = flat()
    for x in range(8, 13):
        for z in range(8, 13):
            k.world.set(x, 20, z, B.SAND)
            k.world.set(x, 21, z, B.SAND)
    m = add(k, 'sheep', 10.5, 28.0, 10.5)
    for _ in range(300):
        k.update_mobs(DT)
        if m.on_ground:
            break
    assert m.on_ground, '5 秒还没落地'
    assert m.pos[1] == 22.0, f'该先贴在沙顶 22：{m.pos[1]}'


@test('下落不穿地板：正常帧率从 y=60 落到地面（世界高 64）')
def t_no_tunnel_normal_dt():
    k = flat(height=64)
    m = add(k, 'sheep', 10.5, 60.0, 10.5)
    run(k, 10.0)
    assert m.pos[1] == FLOOR_Y + 1.0, f'穿地板了或没落到底：{m.pos[1]}'
    assert m.on_ground is True and m.alive is True


@test('大 dt（0.1）会穿地板，但不会留下"地底幽灵"——终将被清理')
def t_big_dt_tunnels_then_cleans():
    """已知边界（记录在 `docs/phase2b_设计.md`）：单帧位移 > 0.5 格的采样窗口时
    会穿过地板。这里钉的是**兜底**：穿下去的生物最后一定被 `y < -4` 清理掉，
    不会以"地底幽灵"的形态永远活着。"""
    k = flat(height=64)
    m = add(k, 'sheep', 10.5, 60.0, 10.5)
    for _ in range(600):
        k.update_mobs(0.1)
        if m not in k.mobs:
            break
    assert m not in k.mobs, '穿到地底下的生物没有被清理（会水底/地底幽灵累积）'
    assert m.alive is False
    assert k.mob_stats['killed'] >= 1


# ==================================================================== 台阶
def _step_wall(k, x_wall, rise):
    """在 x_wall 处修一道 rise 格高的墙（从脚底所在的空气格 y=20 起）。"""
    for z in range(k.size):
        for dy in range(rise):
            k.world.set(x_wall, FLOOR_Y + 1 + dy, z, B.STONE)


@test('上台阶：1 格台阶上得去（过程峰值 = 底面 +1）')
def t_step_up_one():
    """判据看**过程峰值**：上了台阶的生物会继续朝玩家走、走下坡回到原位，
    只看终点会把"真的上去了"判成失败。"""
    k = flat()
    _step_wall(k, 12, 1)
    m = add(k, 'zombie', 10.5, FLOOR_Y + 1.0, 24.5, state=MB.AI_CHASE)
    k.pos = [15.5, FLOOR_Y + 1.0, 24.5]
    peak = FLOOR_Y + 1.0
    for _ in range(int(6.0 / DT)):
        k.update_mobs(DT)
        peak = max(peak, m.pos[1])
    assert peak >= FLOOR_Y + 2.0 - 0.01, f'1 格台阶都没上去：峰值 {peak}'


@test('台阶：2 格高墙挡得住（贪心寻路不假装会飞）')
def t_step_blocked_two():
    k = flat()
    _step_wall(k, 12, 2)
    m = add(k, 'zombie', 10.5, FLOOR_Y + 1.0, 24.5, state=MB.AI_CHASE)
    k.pos = [15.5, FLOOR_Y + 1.0, 24.5]
    peak = FLOOR_Y + 1.0
    for _ in range(int(6.0 / DT)):
        k.update_mobs(DT)
        peak = max(peak, m.pos[1])
    assert peak < FLOOR_Y + 2.0 - 0.01, f'2 格墙居然上去了：峰值 {peak}'


@test('台面：整片高 1 格的平台，追击时走上去并站稳')
def t_plateau():
    k = flat()
    for x in range(12, k.size):
        for z in range(k.size):
            k.world.set(x, FLOOR_Y + 1, z, B.STONE)
    m = add(k, 'zombie', 10.5, FLOOR_Y + 1.0, 24.5, state=MB.AI_CHASE)
    k.pos = [16.5, FLOOR_Y + 1.0, 24.5]
    run(k, 3.0)
    assert m.pos[1] == FLOOR_Y + 2.0, f'该站在台面 y={FLOOR_Y + 2}：{m.pos[1]}'
    assert m.on_ground is True


@test('撞墙滑行：被挡住的方向不走、顺着墙的方向照走')
def t_wall_slide():
    """贴墙起步（差半格，角点不嵌进墙）、目标在斜前方：
    +x 被 2 格高墙挡死 ⇒ 推到墙根就停；+z 方向照样推进。

    ⚠ 起点不能真的贴到墙上（x=11.699 时 +x 角点已经嵌进墙格）——
    那时连 z 都滑不动（整个身体被墙格挡住），测的就不是滑行了。
    """
    k = flat()
    _step_wall(k, 12, 2)
    m = add(k, 'zombie', 11.45, FLOOR_Y + 1.0, 24.5, state=MB.AI_CHASE)
    k.pos = [16.0, FLOOR_Y + 1.0, 30.0]
    x0, z0 = m.pos[0], m.pos[2]
    run(k, 2.0)
    dx, dz = m.pos[0] - x0, m.pos[2] - z0
    assert m.pos[0] <= 11.5 + 1e-6, f'半个身子进墙了：x={m.pos[0]}'
    assert dx < 0.2, f'贴墙还往墙里走了 {dx:.4f}（穿墙？）'
    assert dz > 1.0, f'顺着墙的方向没滑动：dz={dz:.4f}'


# ==================================================================== 游荡
@test('待机转游荡：idle 的生物过 0.5 秒必须动起来（状态机要有出口）')
def t_idle_to_wander():
    """这条盯的是一个**不报错、只会让世界看着是死的** bug：
    状态机少了 idle→wander 的迁移时，新刷的生物永远站在原地。"""
    k = flat()
    k.pos = [0.5, FLOOR_Y + 1.0, 0.5]          # 玩家放远点，别干扰游荡
    m = add(k, 'sheep', 24.5, FLOOR_Y + 1.0, 24.5)
    assert m.state == MB.AI_IDLE, '新生物该是 idle'
    run(k, 0.5)
    # 阈值是**严格大于** 0.5：正好半秒时还没转（age 因浮点还略小于 0.5）
    assert m.state == MB.AI_IDLE, f'半秒不该转（阈值 age>0.5）：{m.state}'
    p0 = (m.pos[0], m.pos[2])
    run(k, 5.0)
    assert m.state == MB.AI_WANDER, f'5 秒后该在游荡，实际 {m.state}'
    net = math.dist((m.pos[0], m.pos[2]), p0)
    assert net > 1.0, f'5 秒只走了 {net:.2f} 格（状态机没有出口？）'


@test('游荡是真的在走：路径长度明显大于净位移（不是瞬移/抖）')
def t_wander_path():
    k = flat()
    k.pos = [0.5, FLOOR_Y + 1.0, 0.5]
    m = add(k, 'sheep', 24.5, FLOOR_Y + 1.0, 24.5)
    p0 = (m.pos[0], m.pos[2])
    path, last = 0.0, p0
    for _ in range(int(5.0 / DT)):
        k.update_mobs(DT)
        path += math.dist((m.pos[0], m.pos[2]), last)
        last = (m.pos[0], m.pos[2])
    net = math.dist((m.pos[0], m.pos[2]), p0)
    assert path > net + 0.5, f'路径 {path:.2f} ≤ 净位移 {net:.2f}（不像在走）'
    assert float(m.pos[1]).is_integer(), f'游荡中 y 不是整数格：{m.pos[1]}'


@test('确定性：同种子同脚本两次跑出同轨迹（游荡伪随机不吃全局熵）')
def t_deterministic_wander():
    """游荡方向用 `age + id` 做确定性伪随机。`id` 是**全局顺序号**，
    所以两次运行前先把它复位到同一起点，两条时间线才真正同构
    （回放对拍的前提：新进程 + 同脚本 ⇒ id 序列相同）。"""
    def one_run():
        MB.Mob._next_id = 1                      # 复位顺序号（见 docstring）
        k = flat(seed=777)
        m = add(k, 'sheep', 24.5, FLOOR_Y + 1.0, 24.5)
        run(k, 5.0)
        return tuple(round(v, 6) for v in m.pos), round(m.yaw, 6)

    a, b = one_run(), one_run()
    assert a == b, f'两次运行轨迹不一致：{a} vs {b}'


# ==================================================================== 追击/攻击
def _night():
    return dict(time_phase=NIGHT_PHASE, time_paused=True)


@test('追击：sight 内第一帧转 chase，贴上来打到玩家，攻击有冷却，追丢回游荡')
def t_chase_attack_cooldown():
    """⚠ 必须**冻结在夜里**：第一天 600 秒，而"上午"的天光已足以晒死僵尸 ——
    时间在走的话，这条判据实际测的是"它能不能在 2 秒内追上"。
    """
    k = flat(**_night())
    k.pos = [30.5, FLOOR_Y + 1.0, 24.5]
    m = add(k, 'zombie', 24.5, FLOOR_Y + 1.0, 24.5)     # 6 格外（sight 16 内）
    assert m.state == MB.AI_IDLE, '测试前提：起始该是 idle'
    assert m.dist_to(k.pos[0], k.pos[2]) <= m.kind.sight, '测试前提：该在 sight 内'
    k.update_mobs(DT)
    assert m.state == MB.AI_CHASE, 'sight 内第一帧该转追击'
    hit_times, hits0, t = [], k.mob_stats['player_hits'], 0.0
    dmin = 99.0
    for _ in range(int(15.0 / DT)):
        k.update_mobs(DT)
        t += DT
        dmin = min(dmin, m.dist_to(k.pos[0], k.pos[2]))
        if k.mob_stats['player_hits'] > hits0:
            hit_times.append(t)
            hits0 = k.mob_stats['player_hits']
    assert m.state == MB.AI_CHASE, f'该保持追击，实际 {m.state}'
    assert dmin <= m.kind.reach + 0.1, f'从没贴到 reach 内：最近 {dmin:.2f}'
    assert k.health < 1000.0 and hit_times, '贴上了却一次都没打到玩家'
    gaps = [b - a for a, b in zip(hit_times, hit_times[1:])]
    assert all(g >= m.kind.attack_cd - 0.02 for g in gaps), \
        f'攻击没有冷却：间隔 {[round(g, 3) for g in gaps]}'
    # 追丢：距离超过 sight×1.4（宽于 sight，避免在边界抖动）⇒ 回游荡
    #    （把僵尸挪远，而不是把玩家挪出世界——世界只有 48 格宽）
    m.pos = [2.5, FLOOR_Y + 1.0, 2.5]
    k.update_mobs(DT)
    assert m.state == MB.AI_WANDER, \
        f'追丢了该回游荡：{m.state}（距离 {m.dist_to(k.pos[0], k.pos[2]):.1f}）'


@test('生物打玩家走唯一入口：计数 + 掉血 + 击退（不是裸 hurt）')
def t_damage_player_from_mob():
    """早先接的是裸 `self.hurt`，症状是"玩家被打了但一点反馈都没有、
    `mob_stats['player_hits']` 恒为 0" —— 守卫判定看起来全绿，
    因为它只查了血量。这条把三个副作用全钉住。"""
    k = flat(**_night())
    k.pos = [30.5, FLOOR_Y + 1.0, 24.5]
    m = add(k, 'zombie', 30.5, FLOOR_Y + 1.0, 24.5, state=MB.AI_CHASE)
    k.vel = [0.0, 0.0, 0.0]
    run(k, 1.0)
    assert k.mob_stats['player_hits'] > 0, 'player_hits 没计数'
    assert k.health < 1000.0, '玩家没掉血'
    assert k.vel[1] > 0.0 or k.vel[0] != 0.0 or k.vel[2] != 0.0, \
        f'没有击退反馈：vel={k.vel}'


@test('最小间距：贴近到 0.4 会被推回 0.75（推不开就退回移动前）')
def t_min_gap_pushback():
    k = flat(**_night())
    k.pos = [30.5, FLOOR_Y + 1.0, 24.5]
    m = add(k, 'zombie', 30.9, FLOOR_Y + 1.0, 24.5, state=MB.AI_CHASE)
    before = m.dist_to(k.pos[0], k.pos[2])
    assert before < AI.MIN_PLAYER_GAP, f'测试前提：起始间距 {before} 该小于下限'
    k.update_mobs(DT)
    after = m.dist_to(k.pos[0], k.pos[2])
    assert abs(after - AI.MIN_PLAYER_GAP) < 1e-6, \
        f'一帧后间距该是 {AI.MIN_PLAYER_GAP}：{after}'


@test('完全重合：一帧内推开（距离不再恒 0，这一帧也不白打）')
def t_overlap_pushback():
    """盯过的死代码：重合时 `_heading` 返回 (0,0) ⇒ 不移动 ⇒ 永远走不到
    推开那一步 ⇒ 距离恒 0 且每帧都白打玩家一下。"""
    k = flat(**_night())
    k.pos = [30.5, FLOOR_Y + 1.0, 24.5]
    m = add(k, 'zombie', 30.5, FLOOR_Y + 1.0, 24.5, state=MB.AI_CHASE)
    assert m.dist_to(k.pos[0], k.pos[2]) == 0.0, '测试前提：完全重合'
    ds = []
    for _ in range(120):
        k.update_mobs(DT)
        ds.append(m.dist_to(k.pos[0], k.pos[2]))
    assert max(ds) > 0.0, f'距离 120 帧恒为 {min(ds)}（推开是死代码？）'
    assert min(ds) >= AI.MIN_PLAYER_GAP - 1e-6 or max(ds) > 0.0
    assert ds[-1] >= AI.MIN_PLAYER_GAP - 1e-6, f'稳态间距 {ds[-1]} 小于下限'


# ==================================================================== 逃跑
@test('逃跑：被动生物被打后进入 flee，与玩家距离明显变大')
def t_flee_after_hit():
    k = flat()
    k.pos = [27.5, FLOOR_Y + 1.0, 24.5]
    m = add(k, 'sheep', 24.5, FLOOR_Y + 1.0, 24.5)
    d0 = m.dist_to(k.pos[0], k.pos[2])
    dead = k.hit_mob(m, 1.0)
    assert dead is False, '打 1 点不该死（羊 8 血）'
    assert m.state == MB.AI_FLEE and abs(m.flee_t - 6.0) < 1e-9, \
        f'被打后该逃跑 6 秒：state={m.state} flee_t={m.flee_t}'
    ds = []
    for _ in range(int(10.0 / DT)):
        k.update_mobs(DT)
        ds.append(m.dist_to(k.pos[0], k.pos[2]))
    assert max(ds) > d0 + 3.0, f'逃跑距离没拉开：d0={d0:.2f} max={max(ds):.2f}'
    assert m.alive is True, '逃跑逃成了死的'
    assert ds[-1] > d0, f'10 秒后距离 {ds[-1]:.2f} 没比初始 {d0:.2f} 远'
    # 逃跑时长结束回游荡（flee 不是终身状态）
    assert m.state == MB.AI_WANDER, f'6 秒后该回到游荡：{m.state}'


@test('逃跑方向：玩家在 +x 侧 ⇒ 往 -x 跑（不是乱跑）')
def t_flee_direction():
    k = flat()
    k.pos = [27.5, FLOOR_Y + 1.0, 24.5]
    m = add(k, 'sheep', 24.5, FLOOR_Y + 1.0, 24.5)
    k.hit_mob(m, 1.0)
    run(k, 3.0)
    assert m.pos[0] < 24.5, f'该往 -x 逃，实际 x={m.pos[0]:.2f}'
    assert m.dist_to(k.pos[0], k.pos[2]) > 4.0, '3 秒还没拉开距离'


# ==================================================================== 死亡/清理
@test('死亡掉落：hit_mob 打死 ⇒ 掉出它表里的东西、计数 +1、移出世界')
def t_kill_drops():
    k = flat()
    m = add(k, 'sheep', 24.5, FLOOR_Y + 1.0, 24.5)
    n_before = len(k.drops)
    dead = k.hit_mob(m, m.kind.health)
    assert dead is True and m.alive is False
    assert m not in k.mobs, '死了还在世界里（会被重复打/重复掉）'
    assert k.mob_stats['killed'] == 1 and k.mob_stats['mob_hits'] == 1
    assert len(k.drops) > n_before, '打死了却没有掉落'
    from mcclone3d import items as I
    names = {I.name_of(d['item']) for d in k.drops}
    assert names & {n for (n, _lo, _hi) in m.kind.drops}, \
        f'掉落 {names} 不在该生物的掉落表 {m.kind.drops} 里'


@test('白天露天敌对 ⇒ 自燃烧死，且烧死不给掉落')
def t_burn_in_day():
    k = flat(time_phase=0.25)                   # 白天（不冻结也行：烧死只要几秒）
    assert k.cycle.is_night() is False, '测试前提：该是白天'
    m = add(k, 'zombie', 24.5, FLOOR_Y + 1.0, 24.5, age=2.0)
    assert k.light.sky(24, 21, 24) >= 12, '测试前提：头顶该有天光'
    t = 0.0
    while m in k.mobs and t < 10.0:
        k.update_mobs(DT)
        t += DT
    assert m not in k.mobs, '晒了 10 秒还没死'
    assert m.alive is False and m.health <= 0.0
    assert k.mob_stats['killed'] == 1, '烧死没计数'
    assert not k.drops, f'烧死不该给掉落：{k.drops}'


@test('白天有屋顶（洞里）的敌对生物不烧（"躲洞"是可行对策）')
def t_no_burn_under_roof():
    k = flat(time_phase=0.25)
    for z in range(k.size):
        for x in range(k.size):
            k.world.set(x, 22, z, B.STONE)       # 屋顶
    k.light = LightEngine(k.world)
    k.light.column_pass_all()
    m = add(k, 'zombie', 24.5, FLOOR_Y + 1.0, 24.5, age=2.0)
    assert k.light.sky(24, 21, 24) == 0, '测试前提：头顶该被挡住'
    run(k, 5.0)
    assert m.alive is True, '洞里的僵尸被晒死了（屋顶判据失效）'
    assert abs(m.health - m.kind.health) < 1e-9, f'洞里居然在掉血：{m.health}'
    assert k.mob_stats['killed'] == 0


@test('超出 DESPAWN_DIST 被移除并计数（防止生物无限累积）')
def t_despawn_far():
    k = flat(size=128)
    m = add(k, 'sheep', 2.5, FLOOR_Y + 1.0, 2.5)
    k.pos = [120.5, FLOOR_Y + 1.0, 2.5]          # 距离 118 > DESPAWN_DIST(96)
    assert m.dist_to(k.pos[0], k.pos[2]) > AI.DESPAWN_DIST, '测试前提：该超出消失半径'
    k.update_mobs(DT)
    assert m not in k.mobs, '超距了还在世界里'
    assert k.mob_stats['despawned'] == 1, 'despawned 没计数'
    assert m.alive is True, '消失不等于死亡（别顺手把它打死掉东西）'


@test('掉出世界（y < -4）判死并移除（不留地底幽灵）')
def t_out_of_world():
    k = flat()
    m = add(k, 'sheep', 10.5, -3.0, 10.5)
    for _ in range(120):
        k.update_mobs(DT)
        if m not in k.mobs:
            break
    assert m not in k.mobs, '掉出世界却没被清理'
    assert m.alive is False and k.mob_stats['killed'] >= 1


# ==================================================================== 刷怪
@test('周期刷怪：白天只出被动生物（敌对刷不出来）')
def t_spawn_day_only_passive():
    k = flat(mobs=True)
    k.cycle.skip_to_phase(0.25)                  # 白天
    for _ in range(30):
        k._try_spawn_mobs()
    assert k.mobs, '白天 30 次一只都没刷出来（刷怪路径坏了？）'
    for m in k.mobs:
        assert not m.kind.hostile, f'白天刷出了敌对生物 {m.kind.name}'
        assert m.pos[1] == FLOOR_Y + 1.0, f'刷在了奇怪的高度：{m.pos}'


@test('周期刷怪：夜里能刷出敌对生物（刷新判据与昼夜同源）')
def t_spawn_night_hostile():
    k = flat(mobs=True)
    k.cycle.skip_to_phase(NIGHT_PHASE)
    for _ in range(30):
        k._try_spawn_mobs()
    assert k.mobs, '夜里 30 次一只都没刷出来'
    names = {m.kind.name for m in k.mobs}
    assert names & {'zombie'}, f'夜里没刷出敌对生物：{sorted(names)}'


@test('刷新点可复现：同一个 rng 序列两次 find_spawn_spot 结果一致')
def t_find_spawn_spot_deterministic():
    import random
    k = flat()
    ctx = k.mob_context()
    a = AI.find_spawn_spot(ctx, random.Random(7).random, light_max=7, night=True)
    b = AI.find_spawn_spot(ctx, random.Random(7).random, light_max=7, night=True)
    assert a == b, f'同一 rng 序列两次找点不一致：{a} vs {b}'
    if a is not None:
        ix, iy, iz = int(a[0]), int(a[1]), int(a[2])
        assert B.is_solid(k.world.get(ix, iy - 1, iz)), '刷新点脚下不是实心'
        assert not B.is_solid(k.world.get(ix, iy, iz)), '刷新点身位是实心（埋进去了）'
        assert not B.is_solid(k.world.get(ix, iy + 1, iz)), '刷新点头上被堵'


@test('MAX_MOBS 上限：刷满之后 spawn_mob 返回 None（护栏生效）')
def t_max_mobs_cap():
    k = flat(mobs=True)
    ok = 0
    last = None
    for _ in range(AI.MAX_MOBS + 5):
        last = k.spawn_mob('sheep', 10.5, FLOOR_Y + 1.0, 10.5)
        if last is not None:
            ok += 1
    assert ok == AI.MAX_MOBS, f'成功刷出 {ok} ≠ MAX_MOBS {AI.MAX_MOBS}'
    assert len(k.mobs) == AI.MAX_MOBS
    assert last is None, '超上限了还返回生物（护栏失效）'


@test('spawn_mob(y=None)：用 ground_below 找站立点，不埋进沙/水里')
def t_spawn_mob_ground_below():
    """实测踩过：`surface_at + 1` 会把生物埋进沙里（surface_at(38,32) 返回 12
    而沙堆到 13），症状是"生物一动不动、`_body_blocked` 恒真"。
    这里复刻实测现场：沙一格 + 水两格盖顶。"""
    k = flat()
    cx, cz = 10, 10
    s = k.world.surface_at(cx, cz)
    k.world.set(cx, s + 1, cz, B.SAND)            # 沙顶 s+1
    k.world.set(cx, s + 2, cz, B.WATER)           # 水盖住（会盖住原来的石地板）
    k.world.set(cx, s + 3, cz, B.WATER)
    k.world.set(cx, s + 4, cz, B.AIR)
    m = k.spawn_mob('sheep', cx + 0.5, None, cz + 0.5)
    assert m is not None, '没刷出来'
    assert m.pos[1] == float(s + 2), f'该站在沙顶（水下）{s + 2}：{m.pos[1]}'
    run(k, 1.0)
    assert m.pos[1] == float(s + 2) and m.on_ground is True, '站稳失败（埋进去了？）'


@test('ground_below：水下沙顶 / 全实心列（无站立点返回 None）')
def t_ground_below_edges():
    k = flat()
    cx, cz = 6, 6
    k.world.set(cx, FLOOR_Y, cz, B.SAND)          # 沙顶 20
    k.world.set(cx, FLOOR_Y + 1, cz, B.WATER)     # 水盖住
    k.world.set(cx, FLOOR_Y + 2, cz, B.WATER)
    ctx = k.mob_context()
    gy = AI.ground_below(ctx, cx, cz, k.height - 1)
    assert gy == FLOOR_Y + 1, f'该踩在沙顶 {FLOOR_Y + 1}：{gy}'
    m = add(k, 'sheep', cx + 0.5, float(gy), cz + 0.5)
    run(k, 1.0)
    assert m.pos[1] == float(gy) and m.on_ground is True, '水下沙顶没站稳'
    # 稠密实心列：没有"脚下实心 + 身位空"的点 ⇒ None（调用方据此换一个刷新点）
    for y in range(1, k.height - 2):
        k.world.set(30, y, 30, B.STONE)
    assert AI.ground_below(ctx, 30, 30, k.height - 1) is None, \
        '全实心列居然找到了站立点'


# ==================================================================== 玩家攻击
@test('attack：准星对准生物 ⇒ 挥中并掉血；打空 ⇒ None')
def t_attack_hits_and_misses():
    k = flat()
    k.pos = [24.5, FLOOR_Y + 1.0, 24.5]
    k.yaw, k.pitch = 0.0, 0.0                    # yaw=0 ⇒ 朝 -z
    m = k.spawn_mob('sheep', 24.5, FLOOR_Y + 1.0, 21.5)   # 正前方 3 格
    assert m is not None and m.health == m.kind.health
    r = k.attack()
    assert r is not None and r[0] == 'sheep' and r[1] is False, f'第一挥该中而不死：{r}'
    assert m.health < m.kind.health, '挥中了却没掉血'
    # 打空：把生物挪到背后
    m.pos[2] = 27.5
    assert k.attack() is None, '背后的生物不该被挥中'
    # 挪回正前方：第二下该致死（羊 8 血、每下 4）
    m.pos[2] = 21.5
    r2 = k.attack()
    assert r2 is not None and r2[1] is True, f'第二下该致死：{r2}'


@test('attack：隔墙打不到（视线先被方块挡住时这一下什么都不会发生）')
def t_attack_blocked_by_wall():
    """文档早就承诺"视线前方没有方块挡住"，先前没实现 —— 隔墙抡人实测复现过。
    与挖方块同口径：`raycast` 先问到墙，就什么都不会发生。"""
    k = flat()
    k.pos = [24.5, FLOOR_Y + 1.0, 24.5]
    k.yaw, k.pitch = 0.0, 0.0
    m = k.spawn_mob('sheep', 24.5, FLOOR_Y + 1.0, 21.5)
    # 墙要挡住**眼睛高度的水平射线**（眼高 1.62 ⇒ 射线在 y=21 格）：
    # 只砌 y=20 一格的话射线从墙头上方过去，墙等于没砌
    k.world.set(24, FLOOR_Y + 1, 22, B.STONE)
    k.world.set(24, FLOOR_Y + 2, 22, B.STONE)
    hp = m.health
    assert k.attack() is None, '隔墙挥中了（墙拦不住攻击？）'
    assert m.health == hp, '隔墙打掉了血'


@test('mobs=False 只关自动刷怪：spawn_mob 手动放照常放（显式意图）')
def t_spawn_mob_ignores_disable():
    """早先两者共用一个开关，于是 `make_offline({'mobs': False})` 之后
    `spawn_mob` 静默返回 None，测试拿到 None 才在下一行炸 AttributeError
    （报错点离根因很远）。"""
    k = flat(mobs=False)
    assert k.mob_enabled is False
    run(k, 8.0)                                   # 超过一个刷怪周期
    assert not k.mobs, '关了自动刷怪却刷出来了'
    m = k.spawn_mob('sheep', 24.5, FLOOR_Y + 1.0, 24.5)
    assert m is not None, '手动放生物被 mobs=False 挡住了'
    assert m in k.mobs and k.mob_stats['spawned'] == 1


if __name__ == '__main__':
    sys.exit(main())
