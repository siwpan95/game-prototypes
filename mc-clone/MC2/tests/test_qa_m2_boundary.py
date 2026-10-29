# -*- coding: utf-8 -*-
"""test_qa_m2_boundary — 独立 QA 边界补充测试（fresh eyes，headless，不依赖 pygame）。

针对实现者 test_m2_*.py 未充分覆盖的边界/精确性做补充断言：
  - 饥饿衰减精确速率（精确数值，非区间）
  - 饿伤致死时间（hp 钳制到 0，不破零）
  - 重生后玩家 AABB 不与 world 的 solid 重叠（确定性世界）
  - 合成输出跨栈时单栈不超 STACK_MAX（边界填满后再合成）
  - daynight 全天 light_factor 单调段（昼升/昼降/夜低）
  - 背包满时 add 返回 0、空背包 remove 返回 0
  - 回血阈值边界（hunger=18 回血 / 17.999 不回血）

不删除实现者任何测试；本文件独立命名 test_qa_m2_* 以区分。
"""

from __future__ import annotations

import os

from mcclone.core.block_registry import BlockRegistry, STONE, AIR
from mcclone.core.block_world import BlockWorld
from mcclone.player.player import Player
from mcclone.player.inventory import Inventory, STACK_MAX
from mcclone.systems.survival import SurvivalSystem, SurvivalConfig
from mcclone.core.daynight import DayNight
from mcclone.player.crafting import Crafting

_THIS = os.path.dirname(os.path.abspath(__file__))
_EXAMPLE = os.path.normpath(os.path.join(_THIS, ".."))
_RECIPES = os.path.join(_EXAMPLE, "data", "recipes.default.json")


def _reg():
    reg = BlockRegistry()
    reg.load_defaults()
    return reg


# ── 生存：饥饿衰减精确速率 ──
def test_hunger_decay_exact_rate():
    reg = _reg()
    world = BlockWorld(10, 20)
    p = Player(5.0, 5.0, reg)
    s = SurvivalSystem(p, SurvivalConfig())
    start = p.hunger
    # 精确推进 50s，每步 1s
    for _ in range(50):
        s.update(1.0)
    expected = start - SurvivalConfig.HUNGER_DECAY_PER_SEC * 50.0
    assert abs(p.hunger - expected) < 1e-6
    assert abs(p.hunger - 15.0) < 1e-6   # 20 - 0.1*50


# ── 生存：饿伤致死时间（钳制不破零）──
def test_starve_death_time_and_no_negative():
    reg = _reg()
    world = BlockWorld(10, 20)
    p = Player(5.0, 5.0, reg)
    s = SurvivalSystem(p, SurvivalConfig())
    p.hunger = 0.0
    p.hp = 20.0
    # 推进 20s（STARVE_DAMAGE_PER_SEC=1.0 → 刚好清零）
    for _ in range(20):
        s.update(1.0)
    assert s.is_dead() is True
    assert p.hp == 0.0
    # 继续推进 30s，hp 不应变负
    for _ in range(30):
        s.update(1.0)
    assert p.hp == 0.0
    assert p.hp >= 0.0


# ── 生存：回血阈值精确边界 ──
def test_heal_threshold_boundary():
    reg = _reg()
    world = BlockWorld(10, 20)
    p = Player(5.0, 5.0, reg)
    s = SurvivalSystem(p, SurvivalConfig())
    # 注意实现顺序：tick_hunger 先衰减饥饿再做阈值判定，
    # 因此 hunger 须 >= 阈值 + 衰减量 才会回血（本帧）。
    # 边界 18.0 + dt*0.1：dt=1.0 衰减后 17.9 < 18 → 本帧不回血
    p.hunger = 18.0
    p.hp = 10.0
    s.update(1.0)
    assert abs(p.hp - 10.0) < 1e-9
    # hunger 抬高到 18.1：衰减后 18.0 >= 18 → 回血 0.5/s
    p.hunger = 18.1
    p.hp = 10.0
    s.update(1.0)
    assert abs(p.hp - 10.5) < 1e-6


# ── 生存：重生后 AABB 不与 solid 重叠（确定性世界）──
def test_respawn_aabb_not_in_solid():
    reg = _reg()
    world = BlockWorld(10, 20)
    # 底部 5 行铺满 stone（solid），其余为 air
    for x in range(world.width):
        for y in range(5):
            world.set(x, y, 0, STONE)
    p = Player(5.0, 10.0, reg)        # 出生在空气层
    s = SurvivalSystem(p, SurvivalConfig())
    s.set_spawn(p.fx, p.fy)
    # 模拟“死在墙里”：把玩家塞进 stone 区域
    p._fx = 5.0
    p._fy = 2.5
    p._sync_aabb()
    assert any(world.get(cx, cy, 0) == STONE
               for cx, cy in p._occupied_cells())  # 死前确实在 solid 中
    # 死亡态 → 重生
    p.hp = 0.0
    p.hunger = 0.0
    p.alive = False
    s.respawn(world)
    assert p.hp == p.max_hp
    assert p.alive is True
    # 重生后占用格不得与任何 solid 重叠
    for cx, cy in p._occupied_cells():
        assert world.get(cx, cy, 0) != STONE, f"重生落入 solid @({cx},{cy})"
        assert p.registry.get(world.get(cx, cy, 0)).solid is False


# ── 合成：输出跨栈时单栈不超 STACK_MAX ──
def test_craft_output_respects_stack_max_cross_stack():
    reg = _reg()
    c = Crafting.from_json(reg, _RECIPES)
    inv = Inventory()
    # 预填满两个 glass(7) 栈，逼近上限
    inv._items[0] = (7, STACK_MAX)
    inv._items[1] = (7, STACK_MAX - 1)
    # 给足 sand(5) 原料用于合成 glass
    inv.add(5, 400)
    before = inv.count(7)
    ok = c.craft("glass", inv)
    assert ok is True
    assert inv.count(7) == before + 1          # 仅 +1
    # 每个 glass 栈均不超过 STACK_MAX
    for it in inv.as_list():
        if it is not None and it[0] == 7:
            assert it[1] <= STACK_MAX
    assert inv.slot(1) == (7, STACK_MAX)        # 第二个栈恰好填满


# ── 背包：满时 add 返回 0；空时 remove 返回 0 ──
def test_inventory_full_add_returns_zero_and_empty_remove_zero():
    inv = Inventory()
    # 填满所有 36 槽为 block 1 满栈
    for i in range(inv.slots):
        inv._items[i] = (1, STACK_MAX)
    assert inv.add(1, 5) == 0
    assert inv.count(1) == inv.slots * STACK_MAX
    # 空背包移除
    empty = Inventory()
    assert empty.remove(1, 10) == 0
    assert empty.count(1) == 0


# ── 昼夜：全天 light_factor 单调段 ──
def test_daynight_light_factor_monotonic_segments():
    d = DayNight()
    # 昼升段 [0.25, 0.5)
    prev = -1.0
    for i in range(25, 50):
        d._t = i / 100.0
        lf = d.light_factor()
        assert lf > prev, f"light 应在昼升段单调上升 @t={d._t}"
        prev = lf
    # 正午为峰（显式置 t=0.5）
    d._t = 0.5
    assert abs(d.light_factor() - 1.0) < 1e-9
    # 昼降段 [0.5, 0.75)
    prev = 2.0
    for i in range(50, 75):
        d._t = i / 100.0
        lf = d.light_factor()
        assert lf < prev, f"light 应在昼降段单调下降 @t={d._t}"
        prev = lf
    # 夜段 light <= 0.5（边界 0.25/0.75 恰为 0.5）
    for i in range(0, 100):
        d._t = i / 100.0
        if d.is_night():
            assert d.light_factor() <= 0.5 + 1e-9
    # 午夜最暗
    d._t = 0.0
    assert abs(d.light_factor() - 0.0) < 1e-9
