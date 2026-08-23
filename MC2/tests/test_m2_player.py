# -*- coding: utf-8 -*-
"""test_m2_player — Player 生存态 / 背包预填 / 挖放联动 / 手持同步 / 伤害钳制（headless，T-M2-04）。"""

from __future__ import annotations

from mcclone.core.block_registry import BlockRegistry, STONE, DIRT, GRASS, SAND, WATER, AIR
from mcclone.core.block_world import BlockWorld
from mcclone.player.player import Player
from mcclone.player.inventory import Inventory


def _reg():
    reg = BlockRegistry()
    reg.load_defaults()
    return reg


def test_survival_defaults():
    p = Player(5.0, 5.0, _reg())
    assert p.max_hp == 20.0 and p.hp == 20.0
    assert p.max_hunger == 20.0 and p.hunger == 20.0
    assert p.alive is True


def test_inventory_prefilled():
    """快捷栏前 5 槽预填 STACK_MAX，第 6 槽为空（AIR）——保证 M1 放置测试仍绿（R2）。"""
    p = Player(5.0, 5.0, _reg())
    for i, bid in enumerate([STONE, DIRT, GRASS, SAND, WATER, AIR]):
        it = p.inventory.slot(i)
        if bid == AIR:
            assert it is None
        else:
            assert it == (bid, Inventory.STACK_MAX)
    assert p.hotbar == [STONE, DIRT, GRASS, SAND, WATER, AIR]


def test_try_break_adds_to_inventory():
    reg = _reg()
    world = BlockWorld(10, 10)
    world.set(3, 3, 0, STONE)
    p = Player(5.0, 3.0, reg)
    before = p.inventory.count(STONE)
    ok = p.try_break(world, 3, 3)
    assert ok is True
    assert p.inventory.count(STONE) == before + 1


def test_try_place_consumes_and_fails_when_empty():
    reg = _reg()
    world = BlockWorld(10, 10)
    p = Player(5.0, 3.0, reg)
    # 默认手持 stone，背包有 64
    assert p.try_place(world, 4, 3) is True
    assert p.inventory.count(STONE) == Inventory.STACK_MAX - 1
    # 清空 stone 后放置应失败（无法消耗）
    p.inventory.remove(STONE, 999)
    assert p.inventory.count(STONE) == 0
    assert p.try_place(world, 6, 3) is False


def test_select_slot_syncs_held():
    reg = _reg()
    p = Player(5.0, 3.0, reg)
    p.select_slot(3)              # sand
    assert p.held_id == SAND
    assert p.inventory.held_block() == SAND
    p.select_slot(0)
    assert p.held_id == STONE


def test_take_damage_heal_clamp():
    reg = _reg()
    p = Player(5.0, 5.0, reg)
    p.take_damage(100.0)
    assert p.hp == 0.0
    p.heal(3.0)
    assert p.hp == 3.0
    p.heal(100.0)
    assert p.hp == p.max_hp
