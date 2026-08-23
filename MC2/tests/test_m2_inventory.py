# -*- coding: utf-8 -*-
"""test_m2_inventory — Inventory 增删 / 查询 / 选择 / 跨栈（headless，T-M2-01）。"""

from __future__ import annotations

from mcclone.player.inventory import Inventory, STACK_MAX, AIR, HOTBAR_SIZE


def _inv() -> Inventory:
    return Inventory()


def test_add_merges_same_stack_and_clamps():
    inv = _inv()
    assert inv.add(1, 10) == 10
    assert inv.count(1) == 10
    got = inv.add(1, 100)
    # 全部加入：54 并入同栈(填满) + 46 进新栈；返回实际加入数 = 100
    assert got == 100
    assert inv.count(1) == 110
    # 但任一单栈不超过 STACK_MAX
    for it in inv.as_list():
        if it is not None:
            assert it[1] <= STACK_MAX


def test_add_spills_to_empty_slots():
    inv = _inv()
    inv.add(1, STACK_MAX)
    inv.add(2, STACK_MAX)
    got = inv.add(3, STACK_MAX * 5)
    assert got == STACK_MAX * 5
    assert inv.count(3) == STACK_MAX * 5


def test_add_zero_returns_zero():
    inv = _inv()
    assert inv.add(1, 0) == 0
    assert inv.count(1) == 0


def test_remove_cross_stack():
    inv = _inv()
    inv.add(1, STACK_MAX)
    inv.add(1, STACK_MAX)
    removed = inv.remove(1, STACK_MAX + 5)
    assert removed == STACK_MAX + 5
    assert inv.count(1) == STACK_MAX - 5


def test_remove_insufficient_returns_actual():
    inv = _inv()
    inv.add(1, 5)
    assert inv.remove(1, 100) == 5
    assert inv.count(1) == 0


def test_slot_select_held():
    inv = _inv()
    inv.add(2, 3)
    inv.add(5, 7)
    inv.select(1)
    assert inv.get_selected() == 1
    assert inv.held_block() == 5
    inv.select(0)
    assert inv.held_block() == 2


def test_select_out_of_range_ignored():
    inv = _inv()
    inv.select(999)
    assert inv.get_selected() == 0


def test_held_block_empty_is_air():
    inv = _inv()
    assert inv.held_block() == AIR


def test_hotbar_blocks_and_as_list():
    inv = _inv()
    inv.add(3, 4)
    inv.add(4, 9)
    hb = inv.hotbar_blocks()
    assert len(hb) == HOTBAR_SIZE
    assert hb[0] == 3 and hb[1] == 4
    assert hb[2:] == [AIR] * (HOTBAR_SIZE - 2)
    lst = inv.as_list()
    assert len(lst) == inv.slots


def test_slot_returns_content():
    inv = _inv()
    inv.add(7, 11)
    assert inv.slot(0) == (7, 11)
    assert inv.slot(999) is None
