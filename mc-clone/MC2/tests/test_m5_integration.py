# -*- coding: utf-8 -*-
"""test_m5_integration — M5 存档/读档 + 群系世界 + 输入键位集成（headless）。

验收：
  - EventTypes 含 M5 的 SAVE_GAME / LOAD_GAME 常量。
  - GUIInputManager 提供 save_pressed / load_pressed（F5/F9）语义动作。
  - GameLoop 注入 save_path 后 request_save 写盘 + 发射 SAVE_GAME，
    request_load 还原玩家/生物且发射 LOAD_GAME；creatures=None 时逐字无 M5 分支。
  - _build_world 产出群系 + 洞穴世界：depth 一致、底部岩浆湖保留、存在海洋水体。
"""

from __future__ import annotations

import os
import tempfile

from mcclone.core.geometry import AABB2D
from mcclone.core.block_registry import BlockRegistry, STONE
from mcclone.core.block_world import BlockWorld
from mcclone.player.player import Player
from mcclone.core.camera import Camera
from mcclone.render.tile_world_renderer import TileWorldRenderer
from mcclone.render.hud import HUD
from mcclone.core.event_bus import EventBus, EventTypes
from mcclone.systems.survival import SurvivalSystem, SurvivalConfig
from mcclone.core.daynight import DayNight
from mcclone.input.mouse_input import GUIInputManager

from mcclone.creatures.entity import CreatureKind, CreatureConfig
from mcclone.creatures.system import CreatureSystem

from mcclone.main_gui import GameLoop, _build_world, WORLD_DEPTH


# ── 工具 ──
def _reg():
    reg = BlockRegistry()
    reg.load_defaults()
    return reg


def _fake_input():
    """鸭子类型输入源：所有语义动作返回安全默认值（headless）。"""

    class _F:
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
    return _F()


# ── 事件常量（T-M5-*）──
def test_event_types_m5_constants():
    for name in ("SAVE_GAME", "LOAD_GAME"):
        assert hasattr(EventTypes, name)
        assert getattr(EventTypes, name) == name


# ── 输入键位（T-M5-*）──
def test_input_save_load_actions_present():
    # 仅校验方法存在（避免 headless 下触发 pygame 键常量解析）。
    assert callable(getattr(GUIInputManager, "save_pressed", None))
    assert callable(getattr(GUIInputManager, "load_pressed", None))


# ── 主循环 stub 兼容（M5 新增 save_path 参数）──
def test_game_loop_m5_stub_compat():
    reg = _reg(); world = BlockWorld(16, 16, 1)
    for x in range(16):
        for y in range(3):
            world.set(x, y, 0, STONE)
    player = Player(1.0, 3.0, reg)
    camera = Camera(AABB2D(0, 0, 15, 15))
    loop = GameLoop(None, world, player, camera, TileWorldRenderer(None, reg),
                    HUD(None), _fake_input(), EventBus(), 1, reg,
                    save_path=None)
    assert loop.save_path is None
    loop._update(0.05)          # 不应抛异常，且无 M5 存档分支被触发
    # 无存档路径时 request_save 应安全跳过
    loop.request_save()


# ── 存档 / 读档往返（T-M5-*）──
def test_game_loop_save_load_roundtrip():
    reg = _reg()
    world = BlockWorld(16, 16, 3)
    for x in range(16):
        for z in range(3):
            for y in range(16):
                world.set(x, y, z, STONE)
    player = Player(2.0, 5.0, reg)
    bus = EventBus()
    daynight = DayNight(600.0)
    survival = SurvivalSystem(player, SurvivalConfig())
    survival.set_spawn(2.0, 5.0)
    creatures = CreatureSystem(world, reg, bus, CreatureConfig(), seed=1)
    creatures.spawn(CreatureKind.COW, 3.0, 5.0)
    camera = Camera(AABB2D(0, 0, 15, 15))

    events = []
    bus.subscribe(EventTypes.SAVE_GAME, lambda t, d: events.append(t))
    bus.subscribe(EventTypes.LOAD_GAME, lambda t, d: events.append(t))

    with tempfile.TemporaryDirectory() as td:
        save_path = os.path.join(td, "save.json")
        loop = GameLoop(None, world, player, camera, TileWorldRenderer(None, reg),
                        HUD(None), _fake_input(), bus, 1, reg,
                        survival=survival, daynight=daynight,
                        creatures=creatures, spawn=None, save_path=save_path)

        # 存档
        loop.request_save()
        assert os.path.exists(save_path)
        assert EventTypes.SAVE_GAME in events

        # 破坏运行态
        player.hp = 1.0
        for c in creatures.creatures:
            c.hp = 1.0

        # 读档还原
        loop.request_load()
        assert EventTypes.LOAD_GAME in events
        assert loop.player.hp == player.max_hp        # 还原满血
        assert loop.creatures.count() == 1            # 还原生物
        # 读档后世界为重新构建的实例（与旧 world 不同对象）
        assert loop.world is not world


# ── 群系 + 洞穴世界（T-M5-* 集成闸口）──
def test_build_world_biomes_and_caves():
    reg, world = _build_world(12345)
    assert world.depth == WORLD_DEPTH
    # 底部岩浆湖层（z=depth-1）仍含岩浆（未被洞穴挖穿）
    bottom = world.depth - 1
    has_lava = any(world.get(x, y, bottom) == 8
                   for x in range(world.width) for y in range(world.height))
    assert has_lava
    # 存在海洋水体（OCEAN 群系注入 WATER）
    has_water = any(world.get(x, y, 0) == 5
                    for x in range(world.width) for y in range(world.height))
    assert has_water
