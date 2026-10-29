# -*- coding: utf-8 -*-
"""test_qa_m3_waterside — 疑点 B 回归测试（水的同层侧流支撑约束）。

headless 可跑（不依赖 pygame 显示），沿用 tests/conftest.py / _testutil.py 的路径注入。

覆盖：
  - test_flow_target_side_requires_supported_below：
      _flow_target 在「正下 / 下斜 全堵死」时，仅在同层侧格下方有支撑（非 AIR）才
      允许横向流动；本例返回有支撑的左格 (0,2,0)，且不返回无支撑的右格 (2,2,0)。
  - test_flow_target_no_unsupported_side（严格回归守卫）：
      当两侧侧下方均为 AIR（无支撑）且对应下斜已被同 tick 其他水占据（moved_dst）
      时，不再向任何悬空侧扩一格，返回 None —— 消除瞬态过梁（overhang）。
      无此修复时此处会返回 (0,2,0)，故本例是修复的唯一可观测落点。
  - test_water_no_overhang_on_cliff（集成）：
      悬崖边水不会向无支撑悬空侧扩一格（(8,5,0) 永远不是水），且在有支撑平地上
      正常横向铺开（y=5 行累计出现 >= 2 个水格，或靠崖 (7,5,0) 曾出现水）。

坐标约定：y 向上。水 (x,y,z) 的「正下」=(x,y-1,z)，「下斜」=(x±1,y-1,z)，
「同层侧」=(x±1,y,z)，「侧下方」=(x±1,y-1,z)。
"""

from __future__ import annotations

from typing import Set, Tuple

import pytest

from mcclone.core.block_registry import AIR, BlockRegistry, STONE
from mcclone.core.block_world import BlockWorld
from mcclone.simulation import WATER_ID, WorldSim


def _registry() -> BlockRegistry:
    """构造加载默认方块表的注册表（供 WorldSim 初始化）。"""
    reg = BlockRegistry()
    reg.load_defaults()
    return reg


# ── 疑点 B：同层侧流支撑约束（单格 _flow_target 直接验证）──
def test_flow_target_side_requires_supported_below():
    """正下/下斜堵死时，仅返回「侧下方有支撑」的同层侧格。

    布局（y 向上，水源 (1,2,0)）：
      - (1,1,0) 实心 -> 正下堵死
      - (0,1,0) 实心 -> 下斜左堵死，且为左格 (0,2,0) 下方支撑
      - (2,1,0) 留 AIR（无支撑），但记入 moved_dst 模拟「下斜右已被本 tick 其他
        水占据」-> 触达同层侧分支；右格 (2,2,0) 下方 AIR 视为无支撑，不应被选中
      - 左 (0,2,0) / 右 (2,2,0) 均为 AIR
    期望：返回有支撑的左格 (0,2,0)，而非无支撑的右格 (2,2,0)。
    """
    reg = _registry()
    world = BlockWorld(3, 4, 1)          # x∈0..2, y∈0..3
    world.set(1, 2, 0, WATER_ID)         # 水源 (1,2,0)
    world.set(1, 1, 0, STONE)            # 正下堵死
    world.set(0, 1, 0, STONE)            # 下斜左堵死（亦为左格下方支撑）
    # (2,1,0) 默认即为 AIR（无支撑）；(0,2,0)/(2,2,0) 默认即为 AIR
    moved_dst: Set[Tuple[int, int, int]] = {(2, 1, 0)}
    sim = WorldSim(world, reg)
    target = sim._flow_target(1, 2, 0, moved_dst)
    assert target == (0, 2, 0), target           # 选有支撑的左格
    assert target != (2, 2, 0)                    # 不选无支撑的右格
    # 返回的侧格其下方必须有支撑（非 AIR）—— 正向校验支撑约束
    assert world.get(target[0], target[1] - 1, target[2]) != AIR


def test_flow_target_no_unsupported_side():
    """两侧侧下方均无支撑且下斜被本 tick 其他水占据时，返回 None（无过梁）。

    说明：单格水在无 moved_dst 时，若某下斜为 AIR 会被优先返回（下斜优先级高于
    同层侧），因此要真正触达「同层侧 + 无支撑」分支，须用 moved_dst 把下斜目标
    标记为已被本 tick 其他水占据（模拟两水相邻、斜下方已被占的真实场景）。这正是
    疑点 B 修复的唯一可观测落点：无修复时此处会返回 (0,2,0)，形成瞬态过梁。
    """
    reg = _registry()
    world = BlockWorld(3, 4, 1)
    world.set(1, 2, 0, WATER_ID)         # 水源 (1,2,0)
    world.set(1, 1, 0, STONE)            # 正下堵死
    # (0,1,0)/(2,1,0) 默认 AIR（无支撑）；(0,2,0)/(2,2,0) 默认 AIR
    # 把两个下斜目标记为已被本 tick 其他水占据 -> 下斜分支跳过，触达同层侧分支
    moved_dst: Set[Tuple[int, int, int]] = {(0, 1, 0), (2, 1, 0)}
    sim = WorldSim(world, reg)
    target = sim._flow_target(1, 2, 0, moved_dst)
    assert target is None, target        # 不向任何无支撑悬空侧扩


# ── 疑点 B：集成验证（悬崖边无过梁 + 有支撑侧流正常）──
def test_water_no_overhang_on_cliff():
    """集成：悬崖边水不向无支撑悬空侧扩 (8,5,0) 永不为水，且在平地正常铺开。

    地图 BlockWorld(12, 8, 1)：
      - y=4 行 x∈[0,7] 铺实心（平地），x>=8 的 y=4 留 AIR（悬崖）
      - 水源放在平地上方 (2,5,0)
    跑 200 步 sim（每步 tick(1/20)）：
      - 悬崖边的无支撑悬空格 (8,5,0) 任一时刻都不得为水（无瞬态过梁）
      - 有支撑侧流确实发生：y=5 行累计出现 >= 2 个水格，或靠崖 (7,5,0) 曾出现水
    """
    reg = _registry()
    W, H, D = 12, 8, 1
    world = BlockWorld(W, H, D)
    world.fill_rect(0, 4, 7, 4, STONE)   # 平地：y=4 行 x∈[0,7] 实心
    # x>=8 的 y=4 默认 AIR（悬崖）
    world.set(2, 5, 0, WATER_ID)         # 水源

    sim = WorldSim(world, reg)
    ever_water_at_cliff_overhang = False   # 悬崖悬空格 (8,5,0) 曾出现水？
    saw_water_on_platform_right = False   # 靠崖 (7,5,0) 曾出现水？
    y5_water_seen: Set[Tuple[int, int, int]] = set()

    for _ in range(200):
        sim.tick(1.0 / 20.0)
        if sim.get_water(8, 5, 0):
            ever_water_at_cliff_overhang = True
        if sim.get_water(7, 5, 0):
            saw_water_on_platform_right = True
        for x in range(W):
            if sim.get_water(x, 5, 0):
                y5_water_seen.add((x, 5, 0))

    # 核心：悬崖边无支撑悬空格绝不为水（无过梁）
    assert not ever_water_at_cliff_overhang, \
        "悬崖边 (8,5,0) 出现瞬态过梁（无支撑侧流），疑点 B 未修复"
    # 有支撑侧流确实发生（放宽：靠崖曾出现水，或 y=5 行累计 >= 2 水格）
    assert saw_water_on_platform_right or len(y5_water_seen) >= 2, \
        "有支撑侧流未观察到水铺开"
