# -*- coding: utf-8 -*-
"""test_m2_blocks_and_gameloop — R4（M2 方块注册）/ GameLoop 集成串联（headless，T-M2-05/06/08）。

用 stub 输入/相机/渲染/HUD 构造 GameLoop，直接调用 _update 验证：
  - survival.update 每帧推进（饥饿衰减）
  - 死亡 → 重生（坐标回出生点 / hp 满 / alive）
  - 合成 overlay 流程（E 打开 → Enter 合成 → 消耗/产出 + ITEM_CRAFTED）
  - 夜间 tint alpha 与 light_factor 的关系（T-M2-08，公式层验证）
"""

from __future__ import annotations

import os

from mcclone.core.geometry import AABB2D
from mcclone import main_gui

from mcclone.core.block_registry import BlockRegistry
from mcclone.core.block_world import BlockWorld
from mcclone.player.player import Player
from mcclone.core.daynight import DayNight
from mcclone.systems.survival import SurvivalSystem, SurvivalConfig
from mcclone.player.crafting import Crafting
from mcclone.core.event_bus import EventBus, EventTypes

_THIS = os.path.dirname(os.path.abspath(__file__))
_EXAMPLE = os.path.normpath(os.path.join(_THIS, ".."))
_BLOCKS_M2 = os.path.join(_EXAMPLE, "data", "blocks.m2.json")
_RECIPES = os.path.join(_EXAMPLE, "data", "recipes.default.json")


# ── R4：加载 blocks.m2.json 须保留 0-5 并新增 6/7 ──
def test_m2_blocks_load_keeping_defaults_R4():
    reg = BlockRegistry.from_json(_BLOCKS_M2)
    for bid in (0, 1, 2, 3, 4, 5):
        assert bid in reg
    assert 6 in reg and reg.get(6).name == "stone_brick"
    assert 7 in reg and reg.get(7).name == "glass"
    assert reg.get(7).transparent is True


def test_block_registry_from_json_keeps_defaults_count():
    reg = BlockRegistry.from_json(_BLOCKS_M2)
    assert len(reg.ids()) >= 8   # 0..7


# ── GameLoop 集成 stub ──
class _StubInput:
    def __init__(self):
        self.flags = {}
        self._mouse_buttons = set()
        self._wheel = 0
        self._mouse_pos = (0, 0)

    def update(self):
        pass

    def left(self):
        return False

    def right(self):
        return False

    def jump_pressed(self):
        return False

    def escape_pressed(self):
        return False

    def debug_toggle_pressed(self):
        return False

    def mouse_pos(self):
        return self._mouse_pos

    def mouse_pressed(self, b):
        return b in self._mouse_buttons

    def is_break_key_pressed(self):
        return False

    def is_place_key_pressed(self):
        return False

    def select_slot_pressed(self, i):
        return False

    def wheel_slot_delta(self):
        w = self._wheel
        self._wheel = 0
        return w

    def craft_toggle_pressed(self):
        return bool(self.flags.get("craft_toggle", False))

    def craft_confirm_pressed(self):
        return bool(self.flags.get("craft_confirm", False))

    def craft_up_pressed(self):
        return bool(self.flags.get("craft_up", False))

    def craft_down_pressed(self):
        return bool(self.flags.get("craft_down", False))


class _StubCamera:
    def __init__(self, vp):
        self.viewport = vp
        self.current_z = 0

    def follow(self, p):
        pass

    def clamp_to(self, b):
        pass

    def screen_to_world_cell(self, mx, my):
        return (0, 0)


class _StubRenderer:
    def render(self, w, vp):
        pass

    def draw_player(self, p, vp):
        pass

    def draw_highlight(self, x, y, vp):
        pass


class _StubHUD:
    def draw(self, *a, **k):
        pass

    def _draw_crafting_overlay(self, *a, **k):
        pass

    def _text(self, *a, **k):
        pass


class _StubScreen:
    def get_width(self):
        return 2560

    def get_height(self):
        return 844

    def get_size(self):
        return (2560, 844)

    def fill(self, *a, **k):
        pass

    def blit(self, *a, **k):
        pass


def _make_loop():
    reg = BlockRegistry()
    reg.load_defaults()
    world = BlockWorld(20, 20)
    p = Player(5.0, 5.0, reg)
    daynight = DayNight(600)
    crafting = Crafting.from_json(reg, _RECIPES)
    survival = SurvivalSystem(p, SurvivalConfig())
    survival.set_spawn(p.fx, p.fy)
    bus = EventBus()
    events = []
    for t in (EventTypes.PLAYER_DIED, EventTypes.PLAYER_RESPAWN,
              EventTypes.ITEM_CRAFTED):
        bus.subscribe(t, lambda tt, dd: events.append(tt))
    cam = _StubCamera(AABB2D(0, 0, 79, 23))
    loop = main_gui.GameLoop(
        _StubScreen(), world, p, cam, _StubRenderer(), _StubHUD(),
        _StubInput(), bus, 1, reg,
        survival=survival, daynight=daynight, crafting=crafting)
    return loop, p, survival, crafting, events


def test_gameloop_updates_survival_hunger():
    loop, p, _s, _c, _e = _make_loop()
    h0 = p.hunger
    loop._update(10.0)
    assert p.hunger < h0


def test_gameloop_death_triggers_respawn():
    loop, p, _s, _c, events = _make_loop()
    spawn_x, spawn_y = p.fx, p.fy
    p._fx = 15.0
    p._fy = 12.0
    p._sync_aabb()
    p.hp = 0.0
    p.hunger = 0.0
    p.alive = True
    loop._update(0.1)
    assert p.hp == p.max_hp
    assert p.alive is True
    assert p.fx == spawn_x and p.fy == spawn_y
    assert EventTypes.PLAYER_DIED in events
    assert EventTypes.PLAYER_RESPAWN in events


def test_gameloop_crafting_flow():
    loop, p, _s, crafting, events = _make_loop()
    # 干净的背包，只给 4 个 sand 以合成 glass(id7)
    p.inventory = __import__("mcclone.player.inventory", fromlist=["Inventory"]).Inventory()
    p.inventory.add(5, 4)
    inp = loop.input
    # 1) 打开合成菜单
    inp.flags["craft_toggle"] = True
    loop._update(0.1)
    assert loop._crafting_open is True
    inp.flags["craft_toggle"] = False
    # 2) 选中 glass 配方并确认合成
    glass_idx = next(i for i, r in enumerate(crafting.recipes) if r.id == "glass")
    loop._crafting_sel = glass_idx
    inp.flags["craft_confirm"] = True
    loop._update(0.1)
    inp.flags["craft_confirm"] = False
    assert p.inventory.count(7) == 1
    assert p.inventory.count(5) == 0
    assert EventTypes.ITEM_CRAFTED in events


def test_night_tint_alpha_relation():
    """夜间 tint：light_factor=0 → alpha=MAX_DARK_ALPHA；正午 → 0（T-M2-08）。"""
    d = DayNight()
    d._t = 0.0   # 午夜
    light = d.light_factor()
    alpha = int((1.0 - light) * main_gui.MAX_DARK_ALPHA)
    assert alpha == main_gui.MAX_DARK_ALPHA
    d._t = 0.5   # 正午
    assert int((1.0 - d.light_factor()) * main_gui.MAX_DARK_ALPHA) == 0
