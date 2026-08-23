# -*- coding: utf-8 -*-
"""test_m4_creatures — M4 实体/物理/AI/寻路/掉落（headless，T-M4-01/02/03/04/08）。

验收：
  - 实体构造 AABB 同步、take_damage 钳制、is_alive。
  - 物理：不进 solid、落地稳定、撞墙阻挡、跳跃回落。
  - AI：idle/wander/flee/attack 状态切换符合规则，状态可观测。
  - 寻路 R6：朝目标收敛 + 遇阻跳跃攀爬。
  - 掉落表 / 驯服占位。
"""

from __future__ import annotations

import random

from mcclone.core.geometry import AABB2D
from mcclone.core.block_registry import BlockRegistry, STONE
from mcclone.core.block_world import BlockWorld
from mcclone.player.player import Player

from mcclone.creatures.entity import Creature, CreatureKind, AIState, CreatureConfig
from mcclone.creatures.physics import move_with_collision
from mcclone.creatures.ai import AIController, AIContext, Pathing
from mcclone.creatures.drops import DROP_TABLE, roll_drops, TAMING


# ── 工具 ──
def _reg():
    reg = BlockRegistry()
    reg.load_defaults()
    return reg


def _world(reg, w=16, h=16):
    world = BlockWorld(w, h, 1)
    for x in range(w):
        for y in range(3):  # 底层 3 行实心（地表最高 solid y=2）
            world.set(x, y, 0, STONE)
    return world


# ── 实体（T-M4-01）──
def test_creature_kind_hostile():
    assert CreatureKind.ZOMBIE.is_hostile() is True
    assert CreatureKind.COW.is_hostile() is False
    assert CreatureKind.PIG.is_hostile() is False


def test_creature_construct_aabb_sync():
    reg = _reg()
    c = Creature(CreatureKind.COW, 2.0, 3.0)
    assert c.fx == 2.0 and c.fy == 3.0
    assert c.min_x == 2 and c.min_y == 3
    assert c.width_f == 0.8 and c.height_f == 0.9
    assert c.hp == 10.0          # COW HP
    assert c.is_alive()


def test_creature_take_damage_clamped():
    c = Creature(CreatureKind.PIG, 0, 0)   # PIG HP=8
    c.take_damage(3.0)
    assert c.hp == 5.0
    c.take_damage(100.0)
    assert c.hp == 0.0
    assert not c.is_alive()


# ── 物理（T-M4-02）──
def test_physics_falls_and_lands():
    reg = _reg()
    world = _world(reg)
    c = Creature(CreatureKind.COW, 5.0, 8.0, CreatureConfig(), random.Random(0))
    for _ in range(400):
        move_with_collision(c, world, reg, 1 / 60)
    assert c.on_ground
    assert abs(c.fy - 3.0) < 0.2          # 静止于地表（solid 顶 y=2 → 脚底 y=3）
    assert c._fx == 5.0                    # 无水平输入不应偏移


def test_physics_wall_blocks():
    reg = _reg()
    world = _world(reg, w=16, h=16)
    world.set(8, 3, 0, STONE)              # 地表上方的 1 格障碍
    c = Creature(CreatureKind.COW, 5.0, 3.0, CreatureConfig(), random.Random(0))
    c.vx = 2.5
    for _ in range(200):
        move_with_collision(c, world, reg, 1 / 60)
    assert c.fx <= 8 - c.width_f + 1e-6    # 未穿透墙体


def test_physics_jump_returns():
    reg = _reg()
    world = _world(reg)
    cfg = CreatureConfig()
    c = Creature(CreatureKind.COW, 5.0, 3.0, cfg, random.Random(0))
    c.vy = cfg.jump_v                      # 起跳（≈2–3 格）
    peak = c.fy
    for _ in range(400):
        move_with_collision(c, world, reg, 1 / 60)
        peak = max(peak, c.fy)
    assert peak > 3.0 + 1.5                # 确实跃起
    assert c.on_ground and abs(c.fy - 3.0) < 0.2   # 落回地表


# ── AI（T-M4-03）──
def _ctx(player, world, reg, cfg, rng):
    return AIContext(player=player, world=world, registry=reg,
                     rng=rng, cfg=cfg, daynight=None)


def test_ai_hostile_attacks_when_near():
    reg = _reg(); world = _world(reg)
    player = Player(5.0, 3.0, reg)
    z = Creature(CreatureKind.ZOMBIE, 5.3, 3.0, CreatureConfig(), random.Random(0))
    state = AIController().decide_state(z, _ctx(player, world, reg, z.cfg, random.Random(0)))
    assert state == AIState.ATTACK


def test_ai_hostile_idle_when_far():
    reg = _reg(); world = _world(reg, w=16, h=16)
    player = Player(1.0, 3.0, reg)
    z = Creature(CreatureKind.ZOMBIE, 14.0, 3.0, CreatureConfig(), random.Random(0))
    state = AIController().decide_state(z, _ctx(player, world, reg, z.cfg, random.Random(0)))
    assert state == AIState.IDLE


def test_ai_passive_flees_when_close():
    reg = _reg(); world = _world(reg)
    player = Player(3.0, 3.0, reg)
    cow = Creature(CreatureKind.COW, 2.0, 3.0, CreatureConfig(), random.Random(0))
    state = AIController().decide_state(cow, _ctx(player, world, reg, cow.cfg, random.Random(0)))
    assert state == AIState.FLEE


def test_ai_passive_wanders_when_far():
    reg = _reg(); world = _world(reg, w=16, h=16)
    player = Player(14.0, 3.0, reg)
    cow = Creature(CreatureKind.COW, 2.0, 3.0, CreatureConfig(), random.Random(0))
    state = AIController().decide_state(cow, _ctx(player, world, reg, cow.cfg, random.Random(0)))
    assert state == AIState.WANDER


def test_ai_state_observable_and_throttled():
    reg = _reg(); world = _world(reg)
    player = Player(3.0, 3.0, reg)
    cow = Creature(CreatureKind.COW, 2.0, 3.0, CreatureConfig(), random.Random(0))
    ctrl = AIController()
    ctx = _ctx(player, world, reg, cow.cfg, random.Random(0))
    # 多次 apply：状态应被设定且可读（不抛异常）
    for _ in range(10):
        ctrl.apply(cow, ctx, 1 / 60)
    assert cow.state in (AIState.IDLE, AIState.WANDER, AIState.FLEE, AIState.ATTACK)


# ── 寻路（T-M4-04 / R6）──
def test_pathing_moves_toward_target():
    reg = _reg(); world = _world(reg)
    c = Creature(CreatureKind.ZOMBIE, 1.0, 3.0, CreatureConfig(), random.Random(0))
    start = c.fx
    for _ in range(120):
        Pathing.step_toward(c, 10.0, 3.0, world, reg)
        move_with_collision(c, world, reg, 1 / 60)
    assert c.fx > start + 1.0


def test_pathing_climbs_obstacle():
    reg = _reg(); world = _world(reg, w=16, h=16)
    world.set(4, 3, 0, STONE)              # 1 格台阶障碍
    c = Creature(CreatureKind.ZOMBIE, 1.0, 3.0, CreatureConfig(), random.Random(0))
    jumped = False
    for _ in range(250):
        Pathing.step_toward(c, 10.0, 3.0, world, reg)
        move_with_collision(c, world, reg, 1 / 60)
        if c.vy > 0.1:
            jumped = True
    assert jumped
    assert c.fx > 4.2                        # 越过障碍 x=4


# ── 掉落 / 驯服（T-M4-08 / R5 / R7）──
def test_drops_table():
    assert DROP_TABLE[CreatureKind.COW] == [(9, 2)]
    assert DROP_TABLE[CreatureKind.PIG] == [(10, 2)]
    assert DROP_TABLE[CreatureKind.ZOMBIE] == [(11, 1)]
    assert roll_drops(CreatureKind.ZOMBIE) == [(11, 1)]
    assert TAMING.enabled is False
