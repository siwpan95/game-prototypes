# -*- coding: utf-8 -*-
"""test_qa_m3_logic — 独立 QA 边界/正确性补充测试（fresh eyes，不删实现者测试）。

覆盖任务要求的边界：
  - R6 注册稳健性（用真实 data 文件复刻 _build_world 注册流程并断言）。
  - worldgen 确定性（to_dict 逐格相等）。
  - 岩浆 4-tick 节流精确。
  - WorldSim.tick 累加器阈值边界（<1/hz 不步进；≥1/hz 步进；累积进位）。
  - camera depth=8 双向钳制。
  - jobs cancel 中途不改动世界任意格。
  - overlay 温度与 world 同步刷新。
  - 流体碰撞守恒（两条流体汇入同一空格不应丢失质量）—— 当前源码存在 bug，此用例用于复现。
"""

from __future__ import annotations

import os

import pytest

from mcclone.core.geometry import AABB2D
from mcclone.core.block_registry import BlockRegistry, BlockDef, AIR, STONE, DIRT, WATER
from mcclone.core.block_world import BlockWorld
from mcclone.core.camera import Camera
from mcclone.world.worldgen import MultiLayerGenerator, LAVA_ID
from mcclone.simulation import WorldSim, SimConfig, LAVA_ID as SIM_LAVA, WATER_ID
from mcclone.systems.jobs import JobSystem


def _registry():
    reg = BlockRegistry()
    reg.load_defaults()
    reg.register(BlockDef(LAVA_ID, "lava", "*", "lava",
                          solid=False, transparent=True))
    return reg


# ── R6：注册稳健性（用真实 data 文件复刻 _build_world 流程）──
def test_qa_r6_registration_pattern_safe():
    base = os.path.join(os.path.dirname(__file__), "..", "data", "blocks.m2.json")
    m3 = os.path.join(os.path.dirname(__file__), "..", "data", "blocks.m3.json")
    # 复刻 main_gui._build_world：从 m2 取 0-7，仅叠加 m3 的 lava=8
    registry = BlockRegistry.from_json(base)
    lava_def = BlockRegistry.from_json(m3).get(8)
    registry.register(lava_def)
    # ① 不会因 from_json 内部 load_defaults 污染 m2 registry：只取 .get(8)
    m3_only = BlockRegistry.from_json(m3)
    assert 6 not in m3_only.ids() and 7 not in m3_only.ids(), \
        "m3 json 不应定义 6/7（否则叠加会污染 m2）"
    # ② .get(8) 能正确返回 lava 的 BlockDef
    assert lava_def.id == 8 and lava_def.name == "lava"
    # ③ 注册后 registry 含 0-7（来自 m2）+ 8（lava）
    for i in range(0, 9):
        assert i in registry, f"注册后缺少方块 id={i}"
    assert registry.get(8).name == "lava"
    # ④ 不抛异常且 m2 的 6/7 仍保留
    assert registry.get(6) is not None
    assert registry.get(7) is not None


# ── worldgen 确定性（to_dict 逐格相等）──
def test_qa_worldgen_determinism_to_dict():
    reg = _registry()
    g = MultiLayerGenerator(reg, 12345)
    w1 = g.generate(24, 24, 8)
    w2 = g.generate(24, 24, 8)
    assert w1.to_dict() == w2.to_dict()


# ── 岩浆 4-tick 节流精确 ──
def test_qa_lava_four_tick_throttle():
    reg = _registry()
    world = BlockWorld(16, 16, 1)
    world.set(5, 5, 0, SIM_LAVA)        # 岩浆，下方整列空气
    sim = WorldSim(world, reg)

    def lava_pos():
        for (x, y, z), b in world._blocks.items():
            if b == SIM_LAVA:
                return (x, y, z)
        return None

    # tick 1~3：岩浆不应移动（tick_count % 4 != 0）
    for _ in range(3):
        sim.tick(1 / 20)
    assert lava_pos() == (5, 5, 0), "岩浆在 tick<4 前不应移动"
    # tick 4：移动一格（tick_count==4，4%4==0）
    sim.tick(1 / 20)
    assert lava_pos() == (5, 4, 0), "岩浆应在第 4 tick 移动一格"
    # tick 5~7：静止
    for _ in range(3):
        sim.tick(1 / 20)
    assert lava_pos() == (5, 4, 0), "岩浆在 tick 5~7 应静止"
    # tick 8：再移动一格
    sim.tick(1 / 20)
    assert lava_pos() == (5, 3, 0), "岩浆应在第 8 tick 再移动一格"


# ── WorldSim.tick 累加器阈值边界（每个边界用独立全新 sim，避免累积干扰）──
def _fresh_sim(reg):
    w = BlockWorld(16, 16, 1)
    w.set(5, 5, 0, SIM_LAVA)
    return WorldSim(w, reg)


def test_qa_sim_tick_accumulator_threshold():
    reg = _registry()
    # dt 远小于 1/sim_hz：不步进
    sim = _fresh_sim(reg)
    sim.tick(1 / 60)
    assert sim._tick_count == 0
    # 边界下方（全新累加器，恰好低于 1/20）：不步进
    sim = _fresh_sim(reg)
    sim.tick(1 / 20 - 1e-9)
    assert sim._tick_count == 0
    # 恰好 1/20：步进 1 次
    sim = _fresh_sim(reg)
    sim.tick(1 / 20)
    assert sim._tick_count == 1
    # 1/10：步进 2 次
    sim = _fresh_sim(reg)
    sim.tick(1 / 10)
    assert sim._tick_count == 2
    # 累积进位：两次 1/40 合计 1/20 → 步进 1 次
    sim = _fresh_sim(reg)
    sim.tick(1 / 40)
    assert sim._tick_count == 0
    sim.tick(1 / 40)
    assert sim._tick_count == 1


# ── camera depth=8 双向钳制 + clamp_z ──
def test_qa_camera_depth8_bidirectional_clamp():
    cam = Camera(AABB2D(0, 0, 79, 23))
    # 上溢
    cam.set_z(99, 8)
    assert cam.current_z == 7
    cam.set_z(8, 8)           # 恰好越界 1
    assert cam.current_z == 7
    # 下溢
    cam.set_z(-5, 8)
    assert cam.current_z == 0
    cam.set_z(-1, 8)
    assert cam.current_z == 0
    # 边界内
    cam.set_z(0, 8)
    assert cam.current_z == 0
    cam.set_z(7, 8)
    assert cam.current_z == 7
    cam.set_z(3, 8)
    assert cam.current_z == 3
    # clamp_z 用 world.depth
    cam.current_z = 100
    cam.clamp_z(BlockWorld(32, 32, 8))
    assert cam.current_z == 7


# ── jobs cancel 中途不改动世界任意格 ──
def test_qa_jobs_cancel_midflight_no_world_change():
    reg = _registry()
    world = BlockWorld(16, 16, 4)
    world.set(3, 3, 1, STONE)
    world.set(9, 9, 2, DIRT)
    j = JobSystem(world, reg)
    jid = j.assign_dig(3, 3, 1)
    # 推进到一半（未达 duration）
    j.tick(0.5)
    # 中途取消
    assert j.cancel(jid) is True
    # 再推进：世界不应改变
    j.tick(1.0)
    assert world.get(3, 3, 1) == STONE, "cancel 后目标格不应被挖空"
    assert world.get(9, 9, 2) == DIRT, "其他格不应受影响"
    # 扫描整个世界：除初始方块外无新增/删除
    remaining = {(x, y, z): b for (x, y, z), b in world._blocks.items()}
    assert remaining == {(3, 3, 1): STONE, (9, 9, 2): DIRT}


# ── overlay 温度与 world 同步刷新 ──
def test_qa_overlay_temp_syncs_after_tick():
    reg = _registry()
    world = BlockWorld(16, 16, 1)
    world.set(5, 5, 0, SIM_LAVA)
    sim = WorldSim(world, reg)
    ov0 = sim.snapshot_overlays(0)
    assert ov0.temp[5][5] == pytest.approx(1.0)
    # 邻格初始环境温度
    assert ov0.temp[6][5] == pytest.approx(0.0)
    # 步进后邻格升温，overlay 同步
    sim.tick(1 / 20)
    ov1 = sim.snapshot_overlays(0)
    assert ov1.temp[6][5] > 1e-3, "邻格温度应随模拟上升并反映在 overlay"
    # overlay 直接读自 world/sim，与 get_temperature 一致
    assert abs(ov1.temp[6][5] - sim.get_temperature(6, 5, 0)) < 1e-9


# ── 流体碰撞守恒（复现源码 bug：两流体汇入同一空格丢失质量）──
def test_qa_fluid_collision_conserves_mass():
    """两条流体汇入同一空格：应守恒（一条移动、一条停留），不应丢失。

    复现：A(5,4) 下落到 (5,3)；B(4,4) 下被挡、下斜 (3,3) 被挡、
    下右斜 (5,3) 为空 → 与 A 竞争同一格 (5,3)。
    当前 WorldSim._step 中 moved_dst 守卫在收集期从未被填充，
    导致两流体都写入 (5,3)，源格清空 → 2 格变 1 格（质量丢失）。
    """
    reg = _registry()
    world = BlockWorld(16, 16, 1)
    world.set(5, 4, 0, WATER)          # 下落 (5,3)
    world.set(4, 4, 0, WATER)          # 下 (4,3) 挡、下斜(3,3) 挡、下右斜(5,3)
    world.set(4, 3, 0, STONE)
    world.set(3, 3, 0, STONE)
    before = sum(1 for (_x, _y, _z), b in world._blocks.items() if b == WATER)
    sim = WorldSim(world, reg)
    sim.tick(1 / 20)
    after = sum(1 for (_x, _y, _z), b in world._blocks.items() if b == WATER)
    assert after == before, \
        f"流体碰撞导致质量丢失：{before} 格变 {after} 格（moved_dst 守卫失效）"
