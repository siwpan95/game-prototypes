# -*- coding: utf-8 -*-
"""test_m4_integration — M4 渲染 / HUD / 主循环集成 / 事件常量（headless，T-M4-07/10/11/12）。

验收：
  - CreatureRenderer.headless 不报错（遍历生物/作业）。
  - HUD.draw 接受 M4 新参数（creature_count / nearest_hp / nearest_max）。
  - EventTypes 含 6 个 M4 常量。
  - GameLoop 注入 creatures/spawn 后 _update 正常推进；creatures=None 时逐字无 M4 分支。
"""

from __future__ import annotations

from mcclone.core.geometry import AABB2D
from mcclone.core.block_registry import BlockRegistry, STONE
from mcclone.core.block_world import BlockWorld
from mcclone.player.player import Player
from mcclone.core.camera import Camera
from mcclone.render.tile_world_renderer import TileWorldRenderer
from mcclone.render.hud import HUD
from mcclone.core.event_bus import EventBus, EventTypes
from mcclone.systems.jobs import JobSystem
from mcclone.systems.survival import SurvivalSystem, SurvivalConfig
from mcclone.core.daynight import DayNight

from mcclone.creatures.entity import CreatureKind, CreatureConfig
from mcclone.creatures.system import CreatureSystem
from mcclone.creatures.spawn import SpawnSystem, SpawnConfig
from mcclone.creatures.render import CreatureRenderer

from mcclone.main_gui import GameLoop


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


# ── 事件常量（T-M4-09）──
def test_event_types_m4_constants():
    for name in ("CREATURE_SPAWNED", "CREATURE_DIED", "CREATURE_HIT",
                 "PLAYER_HIT", "CREATURE_TAMED", "SOUND_PLAYED"):
        assert hasattr(EventTypes, name)
        assert getattr(EventTypes, name) == name


# ── 渲染（T-M4-07 / R2）──
def test_creature_renderer_headless():
    reg = _reg(); world = _world(reg)
    cs = CreatureSystem(world, reg, seed=1)
    cs.spawn(CreatureKind.COW, 2.0, 3.0)
    camera = Camera(AABB2D(0, 0, 11, 11))
    renderer = TileWorldRenderer(None, reg)
    cr = CreatureRenderer(None, reg)
    # headless：仅遍历，不 blit，不报错
    cr.draw(camera, renderer, cs, jobs=None)
    jobs = JobSystem(world, reg, None)
    jobs.assign_dig(2, 3, 0)
    cr.draw(camera, renderer, cs, jobs=jobs)


# ── HUD（T-M4-10）──
def test_hud_draw_m4_params():
    reg = _reg(); world = BlockWorld(8, 8, 1)
    player = Player(1.0, 3.0, reg)
    hud = HUD(None)
    # headless：screen=None 直接返回，验证新参数签名可用
    hud.draw(player, world, 60.0, 123,
             creature_count=3, nearest_hp=8.0, nearest_max=20.0)


# ── 主循环集成（T-M4-11）──
def test_game_loop_m4_wiring_and_update():
    reg = _reg(); world = _world(reg, w=16, h=16)
    player = Player(1.0, 3.0, reg)
    camera = Camera(AABB2D(0, 0, 15, 15))
    renderer = TileWorldRenderer(None, reg)
    hud = HUD(None)
    bus = EventBus()
    daynight = DayNight(600.0)
    survival = SurvivalSystem(player, SurvivalConfig())
    creatures = CreatureSystem(world, reg, bus, CreatureConfig(), seed=1)
    spawn = SpawnSystem(world, reg, creatures, bus, SpawnConfig(seed=1), seed=1)
    loop = GameLoop(None, world, player, camera, renderer, hud, _FakeInput(), bus, 1, reg,
                    survival=survival, daynight=daynight,
                    creatures=creatures, spawn=spawn)
    assert loop.creatures is creatures
    assert loop.spawn is spawn
    assert loop.creature_renderer is not None
    # 预生成一只生物并跑若干 _update：生物应被驱动且不崩溃
    creatures.spawn(CreatureKind.COW, 2.0, 3.0)
    for _ in range(5):
        loop._update(1 / 60)
    assert creatures.count() >= 1


def test_game_loop_m4_stub_compat():
    """creatures=None 时 _update 不触发任何 M4 分支，行为逐字一致。"""
    reg = _reg(); world = _world(reg, w=16, h=16)
    player = Player(1.0, 3.0, reg)
    camera = Camera(AABB2D(0, 0, 15, 15))
    loop = GameLoop(None, world, player, camera, TileWorldRenderer(None, reg),
                    HUD(None), _FakeInput(), EventBus(), 1, reg)
    assert loop.creatures is None
    assert loop.creature_renderer is None
    loop._update(0.05)          # 不应抛异常
