# -*- coding: utf-8 -*-
"""test_m4_systems — M4 生物系统 / 刷怪系统 / 战斗 / 事件（headless，T-M4-05/06/09/12）。

验收：
  - CreatureSystem：spawn/count、update（AI→移动→攻击判定）、attack、死亡掉落、
    事件发射。
  - 战斗（R4）：玩家攻击扣生物 HP；敌对近身扣玩家 HP（on_player_hit 回调）；
    生物死亡触发移除 + 掉落入包。
  - SpawnSystem（R3）：白天被动、夜间敌对、上限约束、同种子确定性。
  - 事件（T-M4-09）：CREATURE_SPAWNED/DIED/HIT/PLAYER_HIT 正确 emit。
"""

from __future__ import annotations

import random

from mcclone.core.block_registry import BlockRegistry, STONE
from mcclone.core.block_world import BlockWorld
from mcclone.player.player import Player
from mcclone.core.event_bus import EventBus, EventTypes

from mcclone.creatures.entity import Creature, CreatureKind, AIState, CreatureConfig
from mcclone.creatures.system import CreatureSystem
from mcclone.creatures.spawn import SpawnSystem, SpawnConfig


# ── 工具 ──
def _reg():
    reg = BlockRegistry()
    reg.load_defaults()
    return reg


def _world(reg, w=16, h=16):
    world = BlockWorld(w, h, 1)
    for x in range(w):
        for y in range(3):
            world.set(x, y, 0, STONE)
    return world


class _FakeDayNight:
    """假昼夜：仅实现 is_night()。"""

    def __init__(self, night: bool) -> None:
        self._night = night

    def is_night(self) -> bool:
        return self._night


# ── CreatureSystem（T-M4-05）──
def test_creature_system_spawn_and_count():
    reg = _reg(); world = _world(reg)
    cs = CreatureSystem(world, reg, seed=1)
    cs.spawn(CreatureKind.COW, 2.0, 3.0)
    assert cs.count() == 1


def test_combat_player_attacks_creature():
    reg = _reg(); world = _world(reg)
    player = Player(1.0, 3.0, reg)
    bus = EventBus()
    hits = []
    bus.subscribe(EventTypes.CREATURE_HIT, lambda t, d: hits.append(d))
    cs = CreatureSystem(world, reg, bus=bus, seed=1)
    cow = cs.spawn(CreatureKind.COW, 1.5, 3.0)
    hp0 = cow.hp
    cs.attack(cow, 4.0)
    assert cow.hp == hp0 - 4.0
    assert len(hits) == 1 and hits[0]["dmg"] == 4.0


def test_combat_creature_hits_player():
    reg = _reg(); world = _world(reg)
    player = Player(1.0, 3.0, reg)
    bus = EventBus()
    phits = []
    bus.subscribe(EventTypes.PLAYER_HIT, lambda t, d: phits.append(d))
    called = []
    cs = CreatureSystem(world, reg, bus=bus, seed=1)
    z = cs.spawn(CreatureKind.ZOMBIE, 1.2, 3.0)
    z.state = AIState.ATTACK
    cs.update(1 / 60, player, None, on_player_hit=lambda a: called.append(a))
    assert len(called) >= 1
    assert called[0] == z.melee_damage       # 僵尸近战 3.0
    assert len(phits) == 1


def test_combat_death_drops():
    reg = _reg(); world = _world(reg)
    player = Player(1.0, 3.0, reg)
    bus = EventBus()
    died = []
    bus.subscribe(EventTypes.CREATURE_DIED, lambda t, d: died.append(d))
    cs = CreatureSystem(world, reg, bus=bus, seed=1)
    z = cs.spawn(CreatureKind.ZOMBIE, 1.2, 3.0)
    z.take_damage(999)                       # 致死
    assert z.hp <= 0
    cs.update(1 / 60, player, None, on_player_hit=lambda a: None)
    assert cs.count() == 0
    assert player.inventory.count(11) == 1   # rotten_flesh ×1
    assert len(died) == 1


def test_nearest_within():
    reg = _reg(); world = _world(reg)
    player = Player(5.0, 3.0, reg)
    cs = CreatureSystem(world, reg, seed=1)
    far = cs.spawn(CreatureKind.COW, 10.0, 3.0)
    near = cs.spawn(CreatureKind.COW, 5.3, 3.0)
    assert cs.nearest_within(player, 2.0) is near
    assert cs.nearest_within(player, 0.1) is None
    _ = far


# ── SpawnSystem（T-M4-06 / R3）──
def test_spawn_daytime_passive():
    reg = _reg(); world = _world(reg, w=16, h=16)
    cs = CreatureSystem(world, reg, seed=1)
    sp = SpawnSystem(world, reg, cs, None, SpawnConfig(seed=1), seed=1)
    day = _FakeDayNight(False)
    for _ in range(40):
        sp.update(2.0, day, cs)
    assert cs.count() > 0
    assert all(not c.kind.is_hostile() for c in cs.creatures)


def test_spawn_night_hostile():
    reg = _reg(); world = _world(reg, w=16, h=16)
    cs = CreatureSystem(world, reg, seed=1)
    sp = SpawnSystem(world, reg, cs, None, SpawnConfig(seed=1), seed=1)
    night = _FakeDayNight(True)
    for _ in range(40):
        sp.update(2.0, night, cs)
    assert cs.count() > 0
    assert all(c.kind.is_hostile() for c in cs.creatures)


def test_spawn_respects_cap():
    reg = _reg(); world = _world(reg, w=64, h=16)
    cs = CreatureSystem(world, reg, seed=1)
    sp = SpawnSystem(world, reg, cs, None,
                     SpawnConfig(total_cap=5, seed=1), seed=1)
    day = _FakeDayNight(False)
    for _ in range(200):
        sp.update(2.0, day, cs)
    assert cs.count() <= 5


def test_spawn_deterministic_same_seed():
    def run():
        reg = _reg(); world = _world(reg, w=16, h=16)
        cs = CreatureSystem(world, reg, seed=42)
        sp = SpawnSystem(world, reg, cs, None, SpawnConfig(seed=42), seed=42)
        day = _FakeDayNight(False)
        for _ in range(20):
            sp.update(2.0, day, cs)
        return [(c.kind.name, round(c.fx, 2)) for c in cs.creatures]

    assert run() == run()


def test_spawn_emits_event():
    reg = _reg(); world = _world(reg, w=16, h=16)
    bus = EventBus()
    cs = CreatureSystem(world, reg, bus=bus, seed=1)
    spawned = []
    bus.subscribe(EventTypes.CREATURE_SPAWNED, lambda t, d: spawned.append(d))
    sp = SpawnSystem(world, reg, cs, bus, SpawnConfig(seed=1), seed=1)
    sp.update(2.0, _FakeDayNight(False), cs)
    assert len(spawned) >= 1
