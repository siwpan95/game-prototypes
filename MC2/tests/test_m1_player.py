# -*- coding: utf-8 -*-
"""test_m1_player — Player 物理 / 破坏放置 / 快捷栏（headless）。

覆盖：
  - 重力下落、落地静止（不进 solid）
  - 撞墙被阻挡
  - 跳跃高度 3-4 格（调参后）
  - 破坏：边界保护 / 不挖脚下防穿地 / 不挖占用格 / 成功置 0
  - 放置：目标须空气或水 / 不可放占用格防卡死 / 成功
  - 快捷栏切换
"""

from __future__ import annotations

import math

from mcclone.core.block_registry import BlockRegistry, AIR, STONE
from mcclone.core.block_world import BlockWorld
from mcclone.player.player import Player


def _reg():
    reg = BlockRegistry()
    reg.load_defaults()
    return reg


class _FakeInput:
    """鸭子类型输入桩：left/right/jump_pressed 可控。"""

    def __init__(self, left=False, right=False):
        self._left = left
        self._right = right
        self._jump = False

    def left(self):
        return self._left

    def right(self):
        return self._right

    def jump_pressed(self):
        j = self._jump
        self._jump = False
        return j


def _ground(w, top_y):
    """填充 x∈[0,w) 的 y∈[0,top_y] 为 stone（地表 top_y）。"""
    world = BlockWorld(w, top_y + 6)
    for x in range(w):
        for y in range(0, top_y + 1):
            world.set(x, y, 0, STONE)
    return world


def test_player_falls_and_lands():
    reg = _reg()
    world = _ground(10, 4)        # 地表 top_y=4，玩家应停在 fy=5
    p = Player(5.0, 12.0, reg)
    inp = _FakeInput()
    for _ in range(600):          # 10s
        p.update(1 / 60, world, inp)
        # 不进 solid
        for (cx, cy) in p._occupied_cells():
            assert not p._is_solid(world, cx, cy), f"进入 solid 格 ({cx},{cy})"
    assert p.fy == 5.0, f"应停在 fy=5，实际 {p.fy}"
    assert p.on_ground is True


def test_player_blocked_by_wall():
    reg = _reg()
    world = _ground(20, 2)        # 地表 top_y=2，玩家停在 fy=3
    for y in range(3, 20):
        world.set(10, y, 0, STONE)  # 右墙 x=10
    p = Player(2.0, 4.0, reg)
    inp = _FakeInput(right=True)
    for _ in range(400):
        p.update(1 / 60, world, inp)
    # 不穿过墙（墙占 [10,11)），玩家右缘止于 10 → fx = 10 - 0.8 = 9.2
    assert p.fx < 10.0, f"不应穿过墙 x=10，fx={p.fx}"
    assert p.fx <= 10.0 - p.width_f + 1e-6, f"应停在墙左侧，fx={p.fx}"


def test_player_jump_height():
    reg = _reg()
    world = _ground(10, 2)        # 地表 top_y=2，停在 fy=3
    p = Player(5.0, 4.0, reg)
    inp = _FakeInput()
    for _ in range(120):          # 先落稳
        p.update(1 / 60, world, inp)
    assert p.on_ground, "落稳后应着地"
    base_y = p.fy
    inp._jump = True              # 触发一次跳跃
    max_y = base_y
    for _ in range(180):
        p.update(1 / 60, world, inp)
        max_y = max(max_y, p.fy)
    jump_h = max_y - base_y
    assert 3.0 <= jump_h <= 4.0, f"跳跃高度应 3-4 格，实际 {jump_h:.2f}"


def test_try_break_basic():
    reg = _reg()
    world = BlockWorld(10, 10)
    world.set(3, 3, 0, STONE)
    p = Player(5.0, 3.0, reg)
    assert p.try_break(world, 3, 3) is True
    assert world.get(3, 3, 0) == AIR
    # 再挖同格（已是空气）失败
    assert p.try_break(world, 3, 3) is False
    # 越界失败
    assert p.try_break(world, 100, 100) is False


def test_try_break_floor_protected():
    reg = _reg()
    world = _ground(10, 2)        # 地表 top_y=2
    p = Player(5.0, 3.0, reg)
    p.on_ground = True            # 模拟已着陆
    # 脚下格 = floor(fy)-1 = 2（玩家水平范围含列 5）
    assert p.try_break(world, 5, 2) is False, "不应挖脚下支撑格"


def test_try_break_self_cell_rejected():
    reg = _reg()
    world = BlockWorld(10, 10)
    world.set(5, 3, 0, STONE)     # 玩家占用格
    p = Player(5.0, 3.0, reg)
    # 玩家 AABB 重叠 (5,3) → 拒绝（防自埋）
    assert p.try_break(world, 5, 3) is False


def test_try_place_basic_and_anti_stuck():
    reg = _reg()
    world = BlockWorld(10, 10)
    p = Player(5.0, 3.0, reg)
    # 放置在空白格 (4,3) 成功
    assert p.try_place(world, 4, 3) is True
    assert world.get(4, 3, 0) == p.held_id
    # 放置在玩家占用格 (5,3)/(5,4) 失败（防卡死）
    assert p.try_place(world, 5, 3) is False
    assert p.try_place(world, 5, 4) is False
    # 越界失败
    assert p.try_place(world, 100, 100) is False


def test_try_place_into_water():
    reg = _reg()
    world = BlockWorld(10, 10)
    from mcclone.core.block_registry import WATER
    world.set(4, 3, 0, WATER)
    p = Player(6.0, 3.0, reg)
    # 可放置到水格（非 solid）
    assert p.try_place(world, 4, 3) is True
    assert world.get(4, 3, 0) == p.held_id


def test_hotbar_switch():
    reg = _reg()
    p = Player(5.0, 3.0, reg)
    assert p.selected_slot == 0 and p.held_id == STONE
    p.select_slot(3)              # 第 4 槽 = sand(5)
    assert p.selected_slot == 3 and p.held_id == 5
    p.select_slot(10)             # 越界忽略
    assert p.selected_slot == 3
    p.select_slot(0)
    assert p.held_id == STONE
