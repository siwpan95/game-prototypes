# -*- coding: utf-8 -*-
"""test_m6_integration — M6 集成（事件常量 / GameLoop 接线 / headless 更新，T-M6-10/11/12）。

不调用 _render（draw_player 依赖 pygame 显示，由既有 M4 测试同样规避）；聚焦事件常量、
GameLoop 新字段、_update 内粒子 update 与事件订阅生成，headless 全程不崩。
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
from mcclone.audio.audio_fx import SoundEngine
from mcclone.render.particles import ParticleSystem

from mcclone.main_gui import GameLoop


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


def test_player_step_event_constant():
    assert EventTypes.PLAYER_STEP == "PLAYER_STEP"


def test_game_loop_m6_fields_default_none():
    reg = _reg()
    world = _world(reg)
    player = Player(1.0, 3.0, reg)
    camera = Camera(AABB2D(0, 0, 15, 15))
    loop = GameLoop(None, world, player, camera, TileWorldRenderer(None, reg),
                    HUD(None), _FakeInput(), EventBus(), 1, reg)
    assert loop.sound is None
    assert loop.particles is None


def test_game_loop_m6_wiring_update_headless():
    reg = _reg()
    world = _world(reg)
    player = Player(1.0, 3.0, reg)
    camera = Camera(AABB2D(0, 0, 15, 15))
    renderer = TileWorldRenderer(None, reg)
    hud = HUD(None)
    bus = EventBus()
    sound = SoundEngine()
    sound.init()
    sound.subscribe(bus)
    particles = ParticleSystem()
    particles.subscribe(bus, reg)
    loop = GameLoop(None, world, player, camera, renderer, hud, _FakeInput(),
                    bus, 1, reg, sound=sound, particles=particles)
    assert loop.sound is sound and loop.particles is particles

    # 触发挖掘事件 → 粒子生成
    bus.emit(EventTypes.BLOCK_BROKEN, x=2, y=3, id=1)
    assert len(particles._ps) >= 1
    # 若干 _update：粒子 update + 脚步检测 + 生物 tick 均不崩
    for _ in range(10):
        loop._update(1 / 60)
    assert True


def test_audio_engine_init_headless():
    eng = SoundEngine()
    assert eng.init() is True
