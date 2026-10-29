# -*- coding: utf-8 -*-
"""test_m2_survival — 生命/饥饿系统：衰减 / 饿伤 / 回血 / 钳制 / 死亡 / 重生（headless，T-M2-02）。"""

from __future__ import annotations

from mcclone.core.block_registry import BlockRegistry
from mcclone.core.block_world import BlockWorld
from mcclone.player.player import Player
from mcclone.systems.survival import SurvivalSystem, SurvivalConfig


def _setup():
    reg = BlockRegistry()
    reg.load_defaults()
    world = BlockWorld(10, 20)
    p = Player(5.0, 5.0, reg)
    s = SurvivalSystem(p, SurvivalConfig())
    s.set_spawn(p.fx, p.fy)
    return reg, world, p, s


def test_hunger_decays():
    _reg, _world, p, s = _setup()
    h0 = p.hunger
    s.update(10.0)
    expected = h0 - SurvivalConfig.HUNGER_DECAY_PER_SEC * 10.0
    assert abs(p.hunger - expected) < 1e-6


def test_starve_damages():
    _reg, _world, p, s = _setup()
    p.hunger = 0.0
    p.hp = 20.0
    s.update(5.0)
    expected = 20.0 - SurvivalConfig.STARVE_DAMAGE_PER_SEC * 5.0
    assert abs(p.hp - expected) < 1e-6


def test_heal_on_full_hunger():
    _reg, _world, p, s = _setup()
    p.hunger = 20.0
    p.hp = 10.0
    s.update(4.0)
    expected = 10.0 + SurvivalConfig.HEAL_PER_SEC * 4.0
    assert abs(p.hp - expected) < 1e-6


def test_no_heal_when_already_full_hp():
    _reg, _world, p, s = _setup()
    p.hunger = 20.0
    p.hp = 20.0
    s.update(4.0)
    assert p.hp == 20.0


def test_damage_heal_clamp():
    _reg, _world, p, s = _setup()
    s.damage(100.0)
    assert p.hp == 0.0
    s.heal(5.0)
    assert p.hp == 5.0
    s.heal(100.0)
    assert p.hp == p.max_hp


def test_is_dead():
    _reg, _world, p, s = _setup()
    assert s.is_dead() is False
    p.hp = 0.0
    assert s.is_dead() is True


def test_respawn_restores_state_and_coords():
    _reg, world, p, s = _setup()
    spawn_x, spawn_y = p.fx, p.fy
    # 移动玩家并置死亡态
    p._fx = 20.0
    p._fy = 18.0
    p._sync_aabb()
    p.hp = 0.0
    p.hunger = 0.0
    p.alive = False
    # 背包放点东西（id=8，非预填）确认重生后保留
    p.inventory.add(8, 5)
    s.respawn(world)
    assert p.hp == p.max_hp
    assert p.hunger == p.max_hunger
    assert p.alive is True
    assert p.fx == spawn_x and p.fy == spawn_y
    assert p.inventory.count(8) == 5   # 背包保留
