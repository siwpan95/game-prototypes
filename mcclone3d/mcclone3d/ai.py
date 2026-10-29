# -*- coding: utf-8 -*-
"""生物 AI：状态机 + **贪心寻路（带跳台阶）** + 与方块的碰撞（纯逻辑，零 GL）。

## 为什么不做 A*

`docs/phase2b_设计.md` 有完整取舍说明，一句话：本项目的"世界理解"只有方块，
而"绕过复杂迷宫"对生物体验的边际收益很低，却要把寻路做成独立子系统（代价高、调参难）。
所以这里做**贪心 + 跳台阶**：

* 每帧朝目标方向走；
* 水平被挡住时**试着往上跳一格**（能上 1 格台阶、能翻过栅栏）；
* 前方两格高都挡住 ⇒ 换个方向（左右各试 45°），都不行就停下。

这套规则的心智模型是"**生物会绕开单格障碍、会上台阶，但不会绕迷宫**"——
说到做到，不假装更强。

## 性能口径

一次 `tick` 对每个生物是常数工作量（几次方块查询），没有全局扫描、没有寻路搜索树。
判据：**300 个生物每帧 < 2ms**（`cli --only mobs` 实测报告这个数字）。
之所以敢这么定，是因为生物的"感知"只查**自己周围几个格子**，而不是看世界。
"""
from __future__ import annotations

import math

from . import blocks as B
from .mobs import (AI_CHASE, AI_FLEE, AI_IDLE, AI_WANDER, Mob, MobKind)
from .world import SEA_LEVEL

__all__ = ['step_mob', 'MobContext', 'find_spawn_spot', 'ground_below',
           'GRAVITY', 'DESPAWN_DIST', 'MAX_MOBS']

#: 与玩家同一套重力口径（生物不飞行）
GRAVITY = 28.0
TERMINAL_V = 40.0
#: 出水/撞墙时允许的自动上台阶高度（格）
STEP_UP = 1.0
#: 离玩家多远就消失（防止生物无限累积）
DESPAWN_DIST = 96.0
#: 同时存在的生物上限（性能护栏；超了就不再刷新）
MAX_MOBS = 240
#: 生物与玩家之间保持的最小水平间距（格）。比 `reach` 小，所以"站住了还打得到"
MIN_PLAYER_GAP = 0.75


class MobContext:
    """AI 需要的世界接口。**刻意收窄**：AI 只能看方块、光、时间和玩家位置。

    为什么不直接传 `kernel`：AI 一旦能摸到内核的全部接口，就会有人从 AI 里
    `dig()`/`place()`，于是"生物能改世界"这种设计意外会悄悄出现。
    现在想加这种能力必须**先改这个类**，那是一次显式的设计决定。
    """

    __slots__ = ('get', 'is_solid', 'block_light', 'day_factor', 'player_pos',
                 'hurt_player', 'size', 'height')

    def __init__(self, get, is_solid, block_light, day_factor, player_pos,
                 hurt_player, size, height):
        self.get = get
        self.is_solid = is_solid
        self.block_light = block_light
        self.day_factor = day_factor
        self.player_pos = player_pos
        self.hurt_player = hurt_player          # `(amount, cause) -> None`
        self.size = size
        self.height = height


def _solid_at(ctx: MobContext, x: float, y: float, z: float) -> bool:
    return bool(ctx.is_solid(ctx.get(int(math.floor(x)), int(math.floor(y)),
                                     int(math.floor(z)))))


def _body_blocked(ctx: MobContext, mob: Mob, x: float, y: float, z: float) -> bool:
    """生物身体（宽 × 高）在那个位置会不会被卡住 —— 用**四个角**近似。

    四个角而不是"中心一格"：只查中心的话，生物会**半个身子插进墙里**
    （宽 0.6 的生物中心离墙 0.31 格时就已经贴上了）。
    """
    half = mob.kind.width * 0.5
    h = mob.kind.height
    for dx in (-half, half):
        for dz in (-half, half):
            for dy in (0.05, h * 0.5, h - 0.05):
                if _solid_at(ctx, x + dx, y + dy, z + dz):
                    return True
    return False


def _try_move(ctx: MobContext, mob: Mob, dx: float, dz: float) -> bool:
    """按轴移动；被挡住就试**上台阶**。返回是否真的走动了（水平方向）。"""
    p = mob.pos
    moved = False
    # 分轴：这样"贴墙滑行"自然成立，与玩家的 `_move_axis` 同一套思路
    if dx:
        nx = p[0] + dx
        if not _body_blocked(ctx, mob, nx, p[1], p[2]):
            p[0] = nx
            moved = True
        elif mob.on_ground and not _body_blocked(ctx, mob, nx, p[1] + STEP_UP, p[2]):
            p[1] += STEP_UP
            mob.vel[1] = 0.0
            p[0] = nx
            moved = True
    if dz:
        nz = p[2] + dz
        if not _body_blocked(ctx, mob, p[0], p[1], nz):
            p[2] = nz
            moved = True
        elif mob.on_ground and not _body_blocked(ctx, mob, p[0], p[1] + STEP_UP, nz):
            p[1] += STEP_UP
            mob.vel[1] = 0.0
            p[2] = nz
            moved = True
    return moved


def _standing_on(ctx: MobContext, mob: Mob, y: float) -> bool:
    """脚在 `y` 时，**脚底那一层**有没有实心方块（判"站在地上"只该看脚下）。

    与 `_body_blocked` 的区别很重要：`_body_blocked` 会在 `y+0.05` 采样（用来判
    "身体会不会插进墙里"），拿它判"能不能往下落"会**把自己脚下的方块算成障碍**，
    于是生物永远差 0.01 格落不到底（实测：羊停在 y=13.99 不动）。
    """
    half = mob.kind.width * 0.5
    for dx in (-half, half):
        for dz in (-half, half):
            if _solid_at(ctx, mob.pos[0] + dx, y - 0.02, mob.pos[2] + dz):
                return True
    return False


def _body_clear_below(ctx: MobContext, mob: Mob, y: float) -> bool:
    """从脚底 `y` 往下到 `y-0.5` 这段空间是否为空（能不能继续下落）。"""
    half = mob.kind.width * 0.5
    for dy in (0.02, 0.25, 0.49):
        for dx in (-half, half):
            for dz in (-half, half):
                if _solid_at(ctx, mob.pos[0] + dx, y - dy, mob.pos[2] + dz):
                    return False
    return True


def _gravity(ctx: MobContext, mob: Mob, dt: float):
    """重力 + 落地（**判据只看脚下**，见 `_standing_on` 的说明）。"""
    mob.vel[1] = max(-TERMINAL_V, mob.vel[1] - GRAVITY * dt)
    if mob.vel[1] > 0.0:
        # 上升：撞到头顶就停
        ny = mob.pos[1] + mob.vel[1] * dt
        if _body_blocked(ctx, mob, mob.pos[0], ny, mob.pos[2]):
            mob.vel[1] = 0.0
        else:
            mob.pos[1] = ny
        return
    # 下落：只要脚下这一段还是空的就继续落，否则**吸附到下方方块的顶面**
    ny = mob.pos[1] + mob.vel[1] * dt
    if _body_clear_below(ctx, mob, ny):
        mob.pos[1] = ny
        mob.on_ground = False
        return
    # ⚠ 吸附到"**下方那一格的顶面**"，而不是 `floor(自己)`：
    #    先前写的是 `if pos - floor(pos) < 0.5: pos = floor(pos)`，
    #    于是 y=18.494 这种"离地面 0.506 格"的位置**永远悬空**
    #    （实测：僵尸卡在 y=18.494 且 `on_ground` 恒 False，看起来像站在地上但
    #     所有"站稳才允许"的动作全部失效）。正确判据是"往下被挡 ⇒ 贴到挡它的那格顶上"。
    fy = math.floor(mob.pos[1])
    while fy > 0 and not ctx.is_solid(ctx.get(int(math.floor(mob.pos[0])),
                                              fy - 1, int(math.floor(mob.pos[2])))):
        fy -= 1
    if fy > 0:
        mob.pos[1] = float(fy)
    mob.vel[1] = 0.0
    mob.on_ground = True


def _heading(mob: Mob, tx: float, tz: float):
    """朝 (tx,tz) 的单位方向（与玩家 `look_dir` 同一套 yaw 约定：0 = 朝 -z）。"""
    dx, dz = tx - mob.pos[0], tz - mob.pos[2]
    n = math.hypot(dx, dz)
    if n < 1e-6:
        return 0.0, 0.0
    return dx / n, dz / n


def ground_below(ctx: MobContext, x: int, z: int, from_y: int):
    """从 `from_y` 往下找**第一个"站得住"的脚底高度**（脚下实心、身位是空）。

    ⚠ 别用 `world.surface_at()` 来放生物（实测踩过）：它答的是"这一列的地面"，
    而实际地形里地面之上可能还有水/沙 —— 实测 `surface_at(38,32)` 返回 12，
    可沙一直堆到 y=13，于是 `surface_at + 1` 等于**把生物埋进沙里**，
    症状是"生物一动不动、`_body_blocked` 恒为真"。
    这里改成自上而下找"脚下实心 + 身位空"，与玩家出生用同一套判据。
    """
    for y in range(min(ctx.height - 3, int(from_y)), 0, -1):
        if ctx.is_solid(ctx.get(x, y - 1, z)) \
                and not ctx.is_solid(ctx.get(x, y, z)) \
                and not ctx.is_solid(ctx.get(x, y + 1, z)):
            return y
    return None


def _keep_distance_from_player(ctx: MobContext, mob: Mob, bx: float, bz: float):
    """把生物推到"离玩家至少 `MIN_PLAYER_GAP`"的位置；推不过去就退回移动前的位置。

    `reach` 是**攻击**距离（比间距大），所以"能打得到"与"不会重叠"并不冲突：
    生物停在间距处照样在 reach 内。
    """
    px, py, pz = ctx.player_pos()
    dx, dz = mob.pos[0] - px, mob.pos[2] - pz
    d = math.hypot(dx, dz)
    if d >= MIN_PLAYER_GAP:
        return
    if d < 1e-4:
        # 完全重合：往"生物自己的朝向前方"的反方向推（至少有个确定方向）
        ang = math.radians(mob.yaw)
        dx, dz, d = math.sin(ang), math.cos(ang), 1.0
    nx = px + dx / d * MIN_PLAYER_GAP
    nz = pz + dz / d * MIN_PLAYER_GAP
    if not _body_blocked(ctx, mob, nx, mob.pos[1], nz):
        mob.pos[0], mob.pos[2] = nx, nz
    else:
        mob.pos[0], mob.pos[2] = bx, bz          # 推不开就退回去（别挤进墙里）


def step_mob(ctx: MobContext, mob: Mob, dt: float) -> None:
    """推进一个生物一帧（**纯函数式**：只改这个生物的字段与位置）。"""
    dt = max(0.0, min(0.1, float(dt)))
    mob.age += dt
    if mob.cd > 0.0:
        mob.cd = max(0.0, mob.cd - dt)
    if mob.hurt_t > 0.0:
        mob.hurt_t = max(0.0, mob.hurt_t - dt)
    if not mob.alive:
        return

    px, py, pz = ctx.player_pos()
    dist = mob.dist_to(px, pz)
    k = mob.kind

    # ---------------------------------------------------------- 状态迁移
    if mob.state == AI_FLEE:
        mob.flee_t -= dt
        if mob.flee_t <= 0.0:
            mob.state = AI_WANDER
            mob.wander_t = 0.0
    elif k.hostile:
        if dist <= k.sight:
            mob.state = AI_CHASE
        elif mob.state == AI_CHASE and dist > k.sight * 1.4:
            mob.state = AI_WANDER                     # 追丢了（比 sight 宽，避免抖动）
    elif mob.state == AI_CHASE:
        mob.state = AI_WANDER
    # ⚠ 被动的待机生物要**自己开始游荡**：先前漏了这条迁移，于是"新刷出来的生物
    #   永远站在原地"（实测：羊 5 秒走了 0.0 格）。这类"状态机少了出口"的 bug
    #   不会报错，只会让世界看着是死的。
    if mob.state == AI_IDLE and mob.age > 0.5:
        mob.state = AI_WANDER
        mob.wander_t = 0.0

    # ---------------------------------------------------------- 期望方向
    speed = k.speed
    if mob.state == AI_CHASE:
        wx, wz = _heading(mob, px, pz)
        speed = k.chase_speed
        # 攻击：贴到 reach 内就打（走 `ctx.hurt_player` —— 受伤只有这一个入口）
        if dist <= k.reach and mob.cd <= 0.0:
            ctx.hurt_player(k.attack, k.name)
            mob.cd = k.attack_cd
    elif mob.state == AI_FLEE:
        wx, wz = _heading(mob, px, pz)
        wx, wz = -wx, -wz
        speed = k.speed * 1.5
    elif mob.state == AI_WANDER:
        mob.wander_t -= dt
        if mob.wander_t <= 0.0:
            # 用**年龄 + id** 做确定性伪随机：同一条时间线回放结果一致（可对拍）
            h = math.sin(mob.age * 12.9898 + mob.id * 78.233) * 43758.5453
            ang = (h % 1.0) * math.tau
            mob.wish = [math.cos(ang), math.sin(ang)]
            mob.wander_t = 1.5 + (h % 1.0) * 2.5
        wx, wz = mob.wish
    else:                                             # AI_IDLE
        wx = wz = 0.0

    mob.wish = [wx, wz]
    if wx or wz:
        mob.yaw = math.degrees(math.atan2(-wx, -wz))  # 与玩家同名约定
    _gravity(ctx, mob, dt)

    if wx or wz:
        step = speed * dt
        before_x, before_z = mob.pos[0], mob.pos[2]
        if not _try_move(ctx, mob, wx * step, wz * step):
            # 撞住了：敌对生物试**左右绕行**（各 45°），被动就换个方向
            for sign in (1.0, -1.0):
                ax = wx * 0.7071 - wz * 0.7071 * sign
                az = wz * 0.7071 + wx * 0.7071 * sign
                if _try_move(ctx, mob, ax * step, az * step):
                    break
            else:
                if mob.state == AI_WANDER:
                    mob.wander_t = 0.0            # 下帧换方向
                elif mob.state == AI_CHASE and mob.on_ground:
                    mob.vel[1] = 8.0              # 追击时被矮墙挡住 ⇒ 跳
    # ⚠ 推开这一步**必须在 `if wx or wz:` 之外**（mob-tester 实测抓出的死代码）：
    #    当生物与玩家**完全重合**时 `_heading()` 因 `n < 1e-6` 返回 `(0,0)`，
    #    于是 `wx=wz=0` ⇒ 既不移动、也就永远走不到推开那一步 ⇒ 距离恒为 0
    #    而且这一帧照样打中玩家。`_keep_distance_from_player` 里
    #    `if d < 1e-4:` 的兜底因此**永远执行不到**。
    _keep_distance_from_player(ctx, mob, mob.pos[0], mob.pos[2])
    # 掉出世界就移除（由调用方按 `alive` 与 `pos` 判定）
    if mob.pos[1] < -4.0:
        mob.health = 0.0


def find_spawn_spot(ctx: MobContext, rng, *, tries: int = 24,
                    light_max: int = 15, night: bool = False):
    """在玩家附近找一个**站得住的刷新点**，返回 `(x, y, z)` 或 None。

    `rng` 是"给出 [0,1) 随机数"的可调用对象（调用方传 `random.Random(seed).random`
    或自写的确定性序列）—— 刷怪位置**可复现**，录制/回放才对得上。
    """
    px, py, pz = ctx.player_pos()
    for _ in range(int(tries)):
        ang = rng() * math.tau
        r = 16.0 + rng() * 32.0                 # 别刷在脸上（MC 也是这个量级）
        x = px + math.cos(ang) * r
        z = pz + math.sin(ang) * r
        if not (2.0 <= x < ctx.size - 2.0 and 2.0 <= z < ctx.size - 2.0):
            continue
        ix, iz = int(math.floor(x)), int(math.floor(z))
        # 自上而下找"站得住"的高度（见 `ground_below` 的说明：
        # 不能用 `surface_at + 1`，那会刷进沙/水里）
        gy = ground_below(ctx, ix, iz, min(ctx.height - 3, int(py) + 12))
        if gy is None:
            continue
        if ctx.block_light(ix, gy, iz) > light_max:
            continue
        return (ix + 0.5, float(gy), iz + 0.5)
    return None
