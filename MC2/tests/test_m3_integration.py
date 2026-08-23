# -*- coding: utf-8 -*-
"""test_m3_integration — T-M3-08/12/13 集成与回归（headless）。

验收要点：
  - _build_world 返回 depth==WORLD_DEPTH 世界 + lava=8 已注册（R6）。
  - EventTypes 含 5 个 M3 常量。
  - GameLoop.__init__ 新增 world_sim/jobs 可选；M2 stub（均 None）仍可用。
  - 端到端 _update：模拟节流推进（tick_count 增加）；jobs 接线 world_sim。
"""

from __future__ import annotations

import pytest

from mcclone.core.geometry import AABB2D
from mcclone.core.block_registry import BlockRegistry, BlockDef
from mcclone.core.block_world import BlockWorld
from mcclone.player.player import Player
from mcclone.core.camera import Camera
from mcclone.render.tile_world_renderer import TileWorldRenderer
from mcclone.render.hud import HUD
from mcclone.core.event_bus import EventBus, EventTypes

from mcclone.world.worldgen import MultiLayerGenerator, LAVA_ID
from mcclone.simulation import WorldSim
from mcclone.systems.jobs import JobSystem
from mcclone.systems.survival import SurvivalSystem, SurvivalConfig
from mcclone.core.daynight import DayNight

from mcclone.main_gui import (_build_world, GameLoop, WORLD_DEPTH)


def _registry():
    reg = BlockRegistry()
    reg.load_defaults()
    reg.register(BlockDef(LAVA_ID, "lava", "*", "lava",
                          solid=False, transparent=True))
    return reg


class _FakeInput:
    """鸭子类型输入源：所有语义动作返回安全默认值（headless）。"""
    def left(self): return False
    def right(self): return False
    def jump_pressed(self): return False
    def craft_toggle_pressed(self): return False
    def craft_confirm_pressed(self): return False
    def craft_up_pressed(self): return False
    def craft_down_pressed(self): return False
    def layer_up_pressed(self): return False
    def layer_down_pressed(self): return False
    def temp_overlay_toggle(self): return False
    def water_overlay_toggle(self): return False
    def dig_mode_pressed(self): return False
    def build_mode_pressed(self): return False
    def cancel_job_pressed(self): return False
    def mouse_pos(self): return (0, 0)
    def mouse_pressed(self, b): return False
    def is_break_key_pressed(self): return False
    def is_place_key_pressed(self): return False
    def wheel_slot_delta(self): return 0
    def select_slot_pressed(self, i): return False
    def update(self): pass
    def escape_pressed(self): return False
    def debug_toggle_pressed(self): return False


def test_build_world_depth_and_lava_registered():
    # R6：lava=8 经 register 叠加，不依赖 from_json 覆盖 0-7
    registry, world = _build_world(12345)
    assert world.depth == WORLD_DEPTH
    assert registry.get(LAVA_ID).name == "lava"
    bottom = world.depth - 1
    assert any(world.get(x, y, bottom) == LAVA_ID
               for x in range(world.width) for y in range(world.height))


def test_event_types_m3_constants():
    for name in ("Z_LEVEL_CHANGED", "SIM_TICK",
                 "JOB_CREATED", "JOB_DONE", "JOB_CANCELLED"):
        assert hasattr(EventTypes, name)
        assert getattr(EventTypes, name) == name


def test_game_loop_m2_stub_compat():
    """M2 stub：不传 world_sim/jobs 仍能构造并 _update 不崩溃。"""
    reg = _registry()
    world = BlockWorld(16, 16, 4)
    player = Player(1.0, 1.0, reg)
    camera = Camera(AABB2D(0, 0, 15, 15))
    renderer = TileWorldRenderer(None, reg)
    hud = HUD(None)
    bus = EventBus()
    loop = GameLoop(None, world, player, camera, renderer, hud,
                    _FakeInput(), bus, 1, reg)
    assert loop.world_sim is None
    assert loop.jobs is None
    loop._update(0.05)          # 不应抛出异常


def test_game_loop_wiring_and_update_advances_sim():
    """M3 集成：world_sim/jobs 注入并接线；_update 推进模拟。"""
    reg = _registry()
    world = MultiLayerGenerator(reg, 7).generate(16, 16, 4)
    player = Player(1.0, 1.0, reg)
    camera = Camera(AABB2D(0, 0, 15, 15))
    renderer = TileWorldRenderer(None, reg)
    hud = HUD(None)
    bus = EventBus()
    survival = SurvivalSystem(player, SurvivalConfig())
    daynight = DayNight(600.0)
    world_sim = WorldSim(world, reg)
    jobs = JobSystem(world, reg, bus)
    loop = GameLoop(None, world, player, camera, renderer, hud,
                    _FakeInput(), bus, 7, reg,
                    survival=survival, daynight=daynight,
                    world_sim=world_sim, jobs=jobs)
    # 接线验证
    assert loop.world_sim is world_sim
    assert loop.jobs is jobs
    assert jobs._world_sim is world_sim       # attach_sim 已调用
    # 跑若干 _update：模拟节流推进
    for _ in range(3):
        loop._update(0.05)
    assert world_sim._tick_count >= 1
