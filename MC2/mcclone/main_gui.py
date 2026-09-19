# -*- coding: utf-8 -*-
"""main_gui — pygame 入口与游戏循环（M1 GUI 垂直切片 + M2 生存基底串联）。

职责：
  - 解析 --no-gui：走现有 main.py 的 ANSI 降级路径（不触发 pygame 渲染）。
  - 否则：pygame.init → 建窗口 → 生成世界 → 组装 Player/Camera/HUD/Input/
    EventBus/Survival/DayNight/Crafting → 主循环（固定步长累加器 + 渲染解耦）。

游戏循环（M2 扩展，T-M2-05 / T-M2-08）：
  - _update：轮询输入 → Player.update → Survival.update（饥饿/生命）→
    DayNight.update（昼夜）→ 死亡判定→respawn → 合成 overlay 态 →
    相机 follow/clamp → 鼠标目标格 → 左键 break / 右键 place →
    键盘 J/K 降级 → 滚轮切换手持 → 1-6 切手持。
  - _render：背景 → 世界 → 玩家 → 准星 → 夜间 tint（T-M2-08）→ HUD → 合成 overlay。

坐标/物理常量集中于此（架构 §7 / §8.1），供各模块引用。
保持现有地基零改动；pygame 延迟导入，导入期不依赖显示设备。
"""

from __future__ import annotations

import argparse
import logging
import math
import os
import sys

# 自举：在导入 mcclone.* 之前，先把项目根(example/)加入 sys.path，
# 使 `import mcclone` / `import main` 在任意启动方式下均可解析
# （python -m、直接 python mcclone/main_gui.py、PyInstaller 冻结包）。
# 项目根 = 本文件所在 mcclone/ 的父目录 example/，与 build.spec 的
# datas=(ROOT/data) 及 mcclone/paths.PROJECT_ROOT 保持一致。
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_THIS_DIR)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

# 整合后 mcclone._engine 复用 allin_engine，需让 allin_engine 包可导入
# （引擎位于 example 的父目录 D:/allin/MCclone）。
_ENGINE_PARENT = os.path.dirname(_PROJECT_ROOT)
if _ENGINE_PARENT not in sys.path:
    sys.path.insert(0, _ENGINE_PARENT)

from mcclone.paths import PROJECT_ROOT, DATA_DIR, SAVE_DIR

from mcclone.core.geometry import AABB2D
from mcclone.core.noise import PerlinNoise
from mcclone.core.block_registry import BlockRegistry
from mcclone.core.block_world import BlockWorld
from mcclone.core.terrain import TerrainGenerator
from mcclone.render.text_world_renderer import TextWorldRenderer

from mcclone.render.tile_world_renderer import TileWorldRenderer
from mcclone.player.player import Player
from mcclone.core.camera import Camera
from mcclone.render.hud import HUD
from mcclone.input.mouse_input import MouseStateSource, GUIInputManager
from mcclone.core.event_bus import EventBus, EventTypes, log_subscriber
from mcclone.input.input_realtime import PygameKeyStateSource, RealtimeInputManager

# M2 生存基底（T-M2-02 / T-M2-03 / T-M2-06；均为零 pygame 依赖的本地模块）。
from mcclone.core.daynight import DayNight
from mcclone.systems.survival import SurvivalSystem, SurvivalConfig
from mcclone.player.crafting import Crafting

# M3 模拟层（T-M3-08 集成闸口；零 pygame 依赖，可 headless 断言）。
from mcclone.simulation import WorldSim
from mcclone.systems.jobs import JobSystem, JobConfig

# M4 生物与世界（T-M4-11 集成闸口；零 pygame 依赖，可 headless 断言）。
from mcclone.creatures.system import CreatureSystem
from mcclone.creatures.spawn import SpawnSystem, SpawnConfig
from mcclone.creatures.render import CreatureRenderer
from mcclone.creatures.entity import CreatureConfig

# M5 群系/洞穴/存档（T-M5 集成闸口；零 pygame 依赖，可 headless 断言）。
from mcclone.world.worldgen import BiomeTerrainGenerator, CaveCarver
from mcclone.world.savegame import save_game, load_game
from mcclone.audio.audio_fx import SoundEngine
from mcclone.render.particles import ParticleSystem


# ── 共享常量（架构 §7 / §8.1）──
TILE_SIZE: int = 32
HUD_TOP: int = 28
HUD_BOTTOM: int = 48
VIEW_OFFSET_X: int = 0
FIXED_DT: float = 1.0 / 60.0
FPS_CAP: int = 60
WORLD_W: int = 256
WORLD_H: int = 96
VIEWPORT_TILES: tuple = (80, 24)          # 列数 × 行数（瓦片）
SEED: int = 12345
WINDOW_W: int = VIEWPORT_TILES[0] * TILE_SIZE            # 2560
WINDOW_H: int = HUD_TOP + VIEWPORT_TILES[1] * TILE_SIZE + HUD_BOTTOM  # 844

# ── M2 生存基底常量（架构 §7.1 / §7.2 / §8）──
DAY_LENGTH_SEC: float = 600.0    # 一天真实秒数（与 daynight.DAY_LENGTH_SEC 一致）
MAX_DARK_ALPHA: int = 160        # 夜间最大暗化 alpha（0..255，T-M2-08）
BLOCKS_M2_DATA: str = "blocks.m2.json"               # M2 新增方块（沿用默认 0-5）
CRAFTING_DATA: str = "recipes.default.json"          # M2 合成配方表

# ── M3 模拟层常量（架构 §7.1）──
WORLD_DEPTH: int = 8             # 世界 Z 层数（M3-R1）
CHUNK_SIZE: int = 16             # 模拟 chunk 边长（沿用 M1 §8.1）
SIM_HZ: float = 20.0             # 模拟 tick 上限（PRD M3-R8）
SIM_DT: float = 1.0 / SIM_HZ     # 模拟固定步长（秒）
LAVA_ID: int = 8                 # M3 新增岩浆方块 id
SUBSURFACE_DIRT_LAYERS: int = 2  # z=1..2 为 dirt，z>=3 为 stone
BLOCKS_M3_DATA: str = "blocks.m3.json"               # M3 方块（lava）
JOB_DIG_DUR: float = 1.0         # 单个挖掘作业耗时（秒）
JOB_BUILD_DUR: float = 1.0       # 单个建造作业耗时（秒）

# ── M4 生物与世界常量（架构 §7.1 / §7.6 / §8）──
CREATURE_CAP: int = 20             # 生物实体总数上限（性能护栏）
AI_DECISION_STEP: float = 0.5      # AI 决策节流（秒）
PLAYER_MELEE_DMG: float = 4.0      # 玩家左键近战对生物伤害
ZOMBIE_MELEE_DMG: float = 3.0      # 僵尸近身对玩家伤害
ATTACK_RANGE: float = 1.5          # 玩家近战触及半径（tile）
ATTACK_COOLDOWN: float = 1.0       # 生物攻击玩家冷却（秒）
SPAWN_INTERVAL: float = 2.0        # 刷怪尝试间隔（秒）
FLEE_RANGE: float = 5.0            # 被动生物感知玩家并开始 flee 的距离
SIGHT_RANGE: float = 8.0            # 敌对生物感知玩家并进入 ATTACK 的距离
BLOCKS_M4_DATA: str = "blocks.m4.json"          # M4 掉落物方块
M4_ITEMS: dict = {9: "beef", 10: "pork", 11: "rotten_flesh"}

# ── M5 群系/洞穴/存档常量（架构 §7.1）──
DEFAULT_SAVE_PATH: str = os.path.join(SAVE_DIR, "quicksave.json")  # 退出自动存档路径
SAVE_VERSION: int = 1                            # 存档格式版本


def _pygame():
    """延迟导入 pygame；不可用时抛出清晰错误。"""
    import pygame
    if pygame is None:
        raise RuntimeError("需要安装可选依赖 pygame 才能运行 GUI")
    return pygame


# ─────────────────────────────────────────────────────────────────────────
# 世界生成 + 玩家出生
# ─────────────────────────────────────────────────────────────────────────

def _surface_y(world: BlockWorld, registry: BlockRegistry, x: int) -> int:
    """返回列 x 的最高 solid 方块 y；无则返回 -1。"""
    for y in range(world.height - 1, -1, -1):
        bid = world.get(x, y, 0)
        if bid != 0 and registry.get(bid).solid:
            return y
    return -1


def spawn_player(world: BlockWorld, registry: BlockRegistry) -> Player:
    """在世界中心附近找一个高于水位的落脚列，生成玩家于其地表之上。"""
    water_level = max(2, int(world.height * 0.5))
    cx = world.width // 2
    best_x = cx
    best_h = -1
    for x in range(cx, min(world.width, cx + 16)):
        h = _surface_y(world, registry, x)
        if h > best_h:
            best_h = h
            best_x = x
            if h >= water_level:
                break
    if best_h < 0:
        best_h = 1
        best_x = cx
    return Player(float(best_x), float(best_h + 1), registry)


# ─────────────────────────────────────────────────────────────────────────
# 游戏循环
# ─────────────────────────────────────────────────────────────────────────

class SaveController:
    """存档 / 读档控制器（M5），从 GameLoop 拆出。

    整合增强：可注入 allin_engine 的 SaveLoadManager（统一产品内核的共享存档），
    存档在写入文件的同时经引擎多槽位管理器持久化；读档优先从管理器读取，
    实现 MC1 / MC2 共用同一套引擎存档主干。
    """

    def __init__(self, registry, event_bus, save_mgr=None, slot: int = 1):
        self.registry = registry
        self.event_bus = event_bus
        self.save_mgr = save_mgr      # 引擎 SaveLoadManager（可选）
        self.slot = slot             # 该玩法层在共享管理器中的槽位

    def save(self, path, world, player, survival, daynight, creatures, seed):
        if survival is None or daynight is None or creatures is None:
            return
        save_game(path,
                  world=world, player=player,
                  survival=survival, daynight=daynight,
                  creatures=creatures, seed=seed,
                  registry=self.registry)
        # 整合：经引擎 SaveLoadManager 持久化到共享存档槽位
        if self.save_mgr is not None:
            try:
                from mcclone.world.savegame import build_savegame
                sg = build_savegame(world=world, player=player,
                                    survival=survival, daynight=daynight,
                                    creatures=creatures, seed=seed,
                                    registry=self.registry)
                self.save_mgr.save(sg, slot=self.slot)
            except Exception:
                pass
        if self.event_bus is not None:
            self.event_bus.emit(EventTypes.SAVE_GAME, path=path)

    def load(self, path):
        # 整合：优先从共享 SaveLoadManager 读档
        if self.save_mgr is not None:
            try:
                from mcclone.world.savegame import load_game_from_state
                state = self.save_mgr.load(slot=self.slot)
                if state is not None:
                    return load_game_from_state(state, self.registry, self.event_bus)
            except Exception:
                pass
        if path is None or not os.path.exists(path):
            return None
        return load_game(path, self.registry, self.event_bus)

    def safe_save(self, path, world, player, survival, daynight, creatures, seed):
        try:
            self.save(path, world, player, survival, daynight, creatures, seed)
        except Exception:
            pass


class GameRenderer:
    """渲染编排器（M1~M6），从 GameLoop 拆出。"""

    def __init__(self, screen, renderer, hud, camera, input_mgr, registry):
        self.screen = screen
        self.renderer = renderer
        self.hud = hud
        self.camera = camera
        self.input = input_mgr
        self.registry = registry

    def render(self, world, player, daynight, world_sim, creatures,
               creature_renderer, jobs, particles, crafting,
               crafting_open, crafting_sel, debug, fps, seed,
               show_temp, show_water, camera_z):
        pg = _pygame()
        self.screen.fill((135, 206, 235))
        overlays = (world_sim.snapshot_overlays(camera_z)
                    if world_sim is not None else None)
        self.renderer.render(world, self.camera.viewport,
                             overlays=overlays, z=camera_z,
                             show_temp=show_temp, show_water=show_water)
        self.renderer.draw_player(player, self.camera.viewport)
        mx, my = self.input.mouse_pos()
        tx, ty = self.camera.screen_to_world_cell(mx, my)
        if world.in_bounds(tx, ty, camera_z):
            self.renderer.draw_highlight(tx, ty, self.camera.viewport)
        if creature_renderer is not None:
            creature_renderer.draw(
                self.camera, self.renderer, creatures,
                jobs=jobs)
        if particles is not None:
            particles.draw(self.camera, self.renderer)
        if daynight is not None:
            light = daynight.light_factor()
            if light < 1.0:
                alpha = int((1.0 - light) * MAX_DARK_ALPHA)
                if alpha > 0:
                    dark = pg.Surface(self.screen.get_size())
                    dark.fill((0, 0, 40))
                    dark.set_alpha(alpha)
                    self.screen.blit(dark, (0, 0))
        _creature_count = creatures.count() if creatures is not None else 0
        _nearest = (creatures.nearest_within(player, 9999.0)
                    if creatures is not None else None)
        self.hud.draw(player, world, fps, seed,
                      overlays_on=debug, daynight=daynight,
                      current_z=camera_z,
                      show_temp=show_temp, show_water=show_water,
                      jobs=jobs.jobs() if jobs is not None else None,
                      creature_count=_creature_count,
                      nearest_hp=(_nearest.hp if _nearest is not None else 0.0),
                      nearest_max=(_nearest.max_hp if _nearest is not None else 0.0))
        if crafting_open and crafting is not None:
            self.hud._draw_crafting_overlay(crafting, crafting_sel, player)
        if debug:
            self._draw_debug(world, player, camera_z, seed)

    def _draw_debug(self, world, player, camera_z, seed):
        pg = _pygame()
        lines = [
            f"玩家: ({player.fx:.2f},{player.fy:.2f}) "
            f"v=({player.vx:.2f},{player.vy:.2f}) ground={player.on_ground}",
            f"视口: x[{self.camera.viewport.min_x},{self.camera.viewport.max_x}] "
            f"y[{self.camera.viewport.min_y},{self.camera.viewport.max_y}] z={camera_z}",
            f"种子={seed} 世界={world.width}x{world.height}x{world.depth}",
        ]
        y = HUD_TOP + 6
        for ln in lines:
            self.hud._text(ln, 200, y, (180, 255, 180))
            y += 18


class GameUpdater:
    """每 tick 状态更新器：输入分发→系统串联→作业/生物/模拟/粒子。"""

    def __init__(self, gui_input, event_bus, on_save=None, on_load=None):
        self.input = gui_input
        self.event_bus = event_bus
        self._on_save = on_save
        self._on_load = on_load
        self.crafting_open = False
        self.crafting_sel = 0
        self.sim_acc = 0.0
        self.show_temp = False
        self.show_water = False
        self.job_mode = None
        self.step_acc = 0.0

    def update(self, dt, world, player, camera, registry,
               survival, daynight, crafting,
               world_sim, jobs, creatures, spawn, particles):
        p = player
        p.update(dt, world, self.input)
        if survival is not None:
            survival.update(dt)
        if daynight is not None:
            daynight.update(dt)
        if (survival is not None and survival.is_dead() and p.alive):
            p.alive = False
            if self.event_bus is not None:
                self.event_bus.emit(EventTypes.PLAYER_DIED, hp=p.hp)
            survival.respawn(world)
            if self.event_bus is not None:
                self.event_bus.emit(EventTypes.PLAYER_RESPAWN, x=p.fx, y=p.fy)
        if crafting is not None and self.input.craft_toggle_pressed():
            self.crafting_open = not self.crafting_open
            if self.crafting_open:
                self.crafting_sel = 0
        if self.crafting_open:
            self._update_crafting(crafting, player)
            return
        camera.follow(p)
        camera.clamp_to(world.bounds())
        if self._input_action("layer_up_pressed"):
            camera.set_z(camera.current_z + 1, world.depth)
            self._on_z_changed(camera)
        if self._input_action("layer_down_pressed"):
            camera.set_z(camera.current_z - 1, world.depth)
            self._on_z_changed(camera)
        if self._input_action("temp_overlay_toggle"):
            self.show_temp = not self.show_temp
        if self._input_action("water_overlay_toggle"):
            self.show_water = not self.show_water
        if self._input_action("dig_mode_pressed"):
            self.job_mode = "dig" if self.job_mode != "dig" else None
        if self._input_action("build_mode_pressed"):
            self.job_mode = "build" if self.job_mode != "build" else None
        if world_sim is not None:
            self.sim_acc += dt
            while self.sim_acc >= SIM_DT:
                world_sim.tick(SIM_DT)
                self.sim_acc -= SIM_DT
                if self.event_bus is not None:
                    self.event_bus.emit(EventTypes.SIM_TICK)
        if jobs is not None:
            jobs.tick(dt)
        if creatures is not None:
            creatures.update(
                dt, player, daynight,
                on_player_hit=(survival.damage
                               if survival is not None
                               else (lambda a: None)))
        if spawn is not None:
            spawn.update(dt, daynight, creatures)
        mx, my = self.input.mouse_pos()
        tx, ty = camera.screen_to_world_cell(mx, my)
        tz = camera.current_z
        if self.input.mouse_pressed(0):
            if self.job_mode == "dig" and jobs is not None:
                jobs.assign_dig(tx, ty, tz)
            elif self.job_mode == "build" and jobs is not None:
                jobs.assign_build(tx, ty, tz, p.held_id)
            elif creatures is not None:
                target = creatures.nearest_within(player, ATTACK_RANGE)
                if target is not None:
                    creatures.attack(target, PLAYER_MELEE_DMG)
                    if particles is not None:
                        particles.spawn_hit(target.fx, target.fy)
                else:
                    p.try_break(world, tx, ty, tz)
            else:
                p.try_break(world, tx, ty, tz)
        if self.input.mouse_pressed(2):
            if self.job_mode is not None and jobs is not None:
                jobs.cancel_under(tx, ty, tz)
            else:
                p.try_place(world, tx, ty, tz)
        if self.input.is_break_key_pressed():
            bx, by = self._adjacent_cell(p)
            p.try_break(world, bx, by, tz)
        if self.input.is_place_key_pressed():
            bx, by = self._adjacent_cell(p)
            p.try_place(world, bx, by, tz)
        d = self.input.wheel_slot_delta()
        if d != 0:
            n = len(p.hotbar)
            p.select_slot((p.selected_slot + d) % n)
        for i in range(len(p.hotbar)):
            if self.input.select_slot_pressed(i):
                p.select_slot(i)
        if particles is not None:
            particles.update(dt)
            _p = player
            if getattr(_p, "on_ground", False) and abs(getattr(_p, "vx", 0.0)) > 0.5:
                self.step_acc += dt
                if self.step_acc >= 0.28:
                    self.step_acc = 0.0
                    if self.event_bus is not None:
                        self.event_bus.emit(EventTypes.PLAYER_STEP,
                                            x=_p.fx, y=_p.fy)
        if self._on_save is not None and self._input_action("save_pressed"):
            self._on_save()
        if self._on_load is not None and self._input_action("load_pressed"):
            self._on_load()

    def _update_crafting(self, crafting, player):
        if crafting is None:
            return
        recipes = crafting.recipes
        if not recipes:
            return
        if self.input.craft_up_pressed():
            self.crafting_sel = (self.crafting_sel - 1) % len(recipes)
        if self.input.craft_down_pressed():
            self.crafting_sel = (self.crafting_sel + 1) % len(recipes)
        if self.input.craft_confirm_pressed():
            r = recipes[self.crafting_sel]
            if crafting.craft(r.id, player.inventory):
                if self.event_bus is not None:
                    _out_id = next(iter(r.output))
                    _out_n = r.output[_out_id]
                    self.event_bus.emit(EventTypes.ITEM_CRAFTED,
                                        id=_out_id, n=_out_n)

    def _input_action(self, name):
        fn = getattr(self.input, name, None)
        return fn() if callable(fn) else False

    def _on_z_changed(self, camera):
        if self.event_bus is not None:
            self.event_bus.emit(EventTypes.Z_LEVEL_CHANGED, z=camera.current_z)

    @staticmethod
    def _adjacent_cell(p):
        if p.facing >= 0:
            tx = int(math.floor(p.fx + p.width_f + 0.5))
        else:
            tx = int(math.floor(p.fx - 0.5))
        ty = int(math.floor(p.fy + p.height_f * 0.5))
        return (tx, ty)


class GameLoop:
    """pygame 固定步长游戏循环（M2~M6 系统串联）。

    M6 重构：存档→SaveController / 渲染→GameRenderer / 更新→GameUpdater，
    GameLoop 仅保留主循环骨架（帧率控制 + 固定步长累加器 + helpers 委派）。
    """

    def __init__(self, screen, world, player, camera, renderer, hud,
                 gui_input, event_bus, seed, registry,
                 survival=None, daynight=None, crafting=None,
                 world_sim=None, jobs=None,
                 creatures=None, spawn=None, save_path=None,
                 sound=None, particles=None,
                 save_mgr=None, save_slot: int = 1) -> None:
        self.screen = screen
        self.world = world
        self.player = player
        self.camera = camera
        self.renderer = renderer
        self.hud = hud
        self.input = gui_input
        self.event_bus = event_bus
        self.seed = seed
        self.registry = registry
        self.fixed_dt = FIXED_DT
        self.fps_cap = FPS_CAP
        self._clock = None
        self._running = True
        self._debug = False
        self._fps = 0.0

        self.survival = survival
        self.daynight = daynight
        self.crafting = crafting
        self.world_sim = world_sim
        self.jobs = jobs
        self.creatures = creatures
        self.spawn = spawn
        self.save_path = save_path
        self.sound = sound
        self.particles = particles

        if self.jobs is not None and self.world_sim is not None:
            self.jobs.attach_sim(self.world_sim)

        self.creature_renderer = (CreatureRenderer(screen, registry)
                                  if creatures is not None else None)

        # ── M6 重构：委派 helpers ──
        self._updater = GameUpdater(gui_input, event_bus,
                                    on_save=lambda: self.request_save(),
                                    on_load=lambda: self.request_load())
        self._renderer_h = GameRenderer(screen, renderer, hud, camera,
                                        gui_input, registry)
        self._saver = SaveController(registry, event_bus,
                                     save_mgr=save_mgr, slot=save_slot)

    # ── 测试兼容：M2/M3/M4 测试直接访问 loop._xxx ──
    @property
    def _crafting_open(self):
        return self._updater.crafting_open

    @_crafting_open.setter
    def _crafting_open(self, v):
        self._updater.crafting_open = v

    @property
    def _crafting_sel(self):
        return self._updater.crafting_sel

    @_crafting_sel.setter
    def _crafting_sel(self, v):
        self._updater.crafting_sel = v

    @property
    def _show_temp(self):
        return self._updater.show_temp

    @property
    def _show_water(self):
        return self._updater.show_water

    def run(self) -> None:
        """主循环：每帧轮询输入 → 固定步长更新 → 渲染。"""
        pg = _pygame()
        self._clock = pg.time.Clock()
        acc = 0.0
        while self._running:
            frame_ms = self._clock.tick(self.fps_cap)
            dt = frame_ms / 1000.0
            self._fps = self._clock.get_fps()
            # 1) 轮询输入（每帧一次）
            self.input.update()
            # 2) 退出 / 调试事件
            self._handle_events()
            # 3) 固定步长更新（累加器消纳帧时间，防死亡螺旋）
            acc += dt
            if acc > 0.25:
                acc = 0.25
            while acc >= self.fixed_dt:
                self._update(self.fixed_dt)
                acc -= self.fixed_dt
            # 4) 渲染（与逻辑解耦）
            self._render()
            pg.display.flip()
        self.save_on_exit()      # M5：退出前自动存档到默认路径
        pg.quit()

    def _handle_events(self) -> None:
        """处理退出与调试开关（基于本帧刚按下）。"""
        if self.input.escape_pressed():
            self._running = False
        if self.input.debug_toggle_pressed():
            self._debug = not self._debug

    def _update(self, dt: float) -> None:
        """固定步长更新：委派 GameUpdater。"""
        self._updater.update(
            dt,
            self.world, self.player, self.camera, self.registry,
            self.survival, self.daynight, self.crafting,
            self.world_sim, self.jobs,
            self.creatures, self.spawn, self.particles)

    # ── M5：存档 / 读档（T-M5-*）──
    def request_save(self) -> None:
        """F5 触发：委派 SaveController。"""
        if self.save_path is None:
            return
        self._saver.save(self.save_path,
                         world=self.world, player=self.player,
                         survival=self.survival, daynight=self.daynight,
                         creatures=self.creatures, seed=self.seed)

    def request_load(self) -> None:
        """F9 触发：读取存档并置换运行态，同步 helpers 引用。"""
        if self.save_path is None:
            return
        data = self._saver.load(self.save_path)
        if data is None:
            return
        self.world = data["world"]
        self.player = data["player"]
        self.player.event_bus = self.event_bus
        self.survival = data["survival"]
        self.daynight = data["daynight"]
        self.creatures = data["creatures"]
        self.seed = data["seed"]
        self.spawn = SpawnSystem(self.world, self.registry, self.creatures,
                                 self.event_bus, SpawnConfig(seed=self.seed),
                                 seed=self.seed)
        self.camera.clamp_to(self.world.bounds())
        if self.event_bus is not None:
            self.event_bus.emit(EventTypes.LOAD_GAME, path=self.save_path)

    def save_on_exit(self) -> None:
        """退出自动存档（委派 SaveController.safe_save）。"""
        if self.save_path is None:
            return
        self._saver.safe_save(self.save_path,
                              world=self.world, player=self.player,
                              survival=self.survival, daynight=self.daynight,
                              creatures=self.creatures, seed=self.seed)

    def _render(self) -> None:
        """单帧渲染：委派 GameRenderer。"""
        self._renderer_h.render(
            self.world, self.player, self.daynight, self.world_sim,
            self.creatures, self.creature_renderer,
            self.jobs, self.particles, self.crafting,
            self._updater.crafting_open, self._updater.crafting_sel,
            self._debug, self._fps, self.seed,
            self._updater.show_temp, self._updater.show_water,
            self.camera.current_z)


# ─────────────────────────────────────────────────────────────────────────
# 入口
# ─────────────────────────────────────────────────────────────────────────

def _build_registry() -> BlockRegistry:
    """构建方块注册表（M2 0-5 + M3 lava=8 + M4 掉落物 9/10/11），不修改地基。

    注册逻辑集中到此处，供 _build_world 与读档分支复用，保证方块 id 表一致
    （R6：仅叠加新方块，不动 0-8）。
    """
    registry = BlockRegistry.from_json(
        os.path.join(DATA_DIR, BLOCKS_M2_DATA))
    # 仅取 lava=8 定义并登记（R6：只叠加新方块，不动 0-7）。
    lava_def = BlockRegistry.from_json(
        os.path.join(DATA_DIR, BLOCKS_M3_DATA)).get(LAVA_ID)
    registry.register(lava_def)
    # 仅取 M4 新方块（beef=9/pork=10/rotten_flesh=11）并登记
    # （R6：只叠加新方块，不动 0-8）。
    m4_defs = BlockRegistry.from_json(
        os.path.join(DATA_DIR, BLOCKS_M4_DATA))
    for _bid in (9, 10, 11):
        registry.register(m4_defs.get(_bid))
    return registry


def _build_world(seed: int) -> "tuple[BlockRegistry, BlockWorld]":
    """生成确定性群系 + 洞穴世界（WORLD_W×WORLD_H×WORLD_DEPTH）。

    方块注册沿用既有 M2/M3/M4（0-5 默认 + 6/7(JSON) + lava=8 + 9/10/11）。
    世界生成改为 worldgen.BiomeTerrainGenerator（组合复用 MultiLayerGenerator
    填 z>=1，再用群系逻辑重写 z=0 地表），随后用 CaveCarver 雕刻洞穴。
    """
    registry = _build_registry()
    world = BlockWorld(WORLD_W, WORLD_H, WORLD_DEPTH)
    # ① 群系地形：BiomeTerrainGenerator 先填 z>=1（含底部岩浆湖），再重写 z=0 地表
    BiomeTerrainGenerator(registry, seed).generate(world, registry, seed)
    # ② 洞穴雕刻：仅挖 z∈[1, depth-2]，绝不破坏 z=0 地表与 z=depth-1 岩浆湖
    CaveCarver(registry, seed).carve(world, registry, seed)
    return registry, world


def _run_gui(seed: int, load_path: str | None = None,
             save_path: str | None = None,
             core: "ProductCore | None" = None) -> int:
    """真实 GUI 运行路径（M2~M5 系统串联）。

    若 load_path 指向存在的存档，则从存档还原世界/玩家/系统（不重新生成世界）；
    否则按 seed 生成群系 + 洞穴世界并初始化 M2~M4 系统。

    整合：若传入统一产品内核 core，则把本玩法层挂到共享引擎主干上 ——
    事件总线 / 音频系统 / 存档管理器 全部复用 core 的同一实例，使 MC1 文字模式
    与 MC2 2D 模式成为同一游戏的两种可切换玩法层。
    """
    pg = _pygame()
    pg.init()
    save_path = save_path or DEFAULT_SAVE_PATH

    # 事件总线（M1~M5 事件均接日志订阅）
    if core is not None:
        core.mount("MC2-2D", "我的世界2D侧视复刻")
        # 复用共享引擎总线：MC2 事件流经与 MC1 同一个总线
        bus = EventBus(engine_bus=core.bus)
        shared_audio = core.audio
        shared_save_mgr = core.save_mgr
    else:
        bus = EventBus()
        shared_audio = None
        shared_save_mgr = None
    for _t in (EventTypes.PLAYER_MOVED, EventTypes.BLOCK_BROKEN,
               EventTypes.BLOCK_PLACED, EventTypes.PLAYER_LANDED,
               EventTypes.PLAYER_DIED, EventTypes.PLAYER_RESPAWN,
               EventTypes.ITEM_CRAFTED,
               EventTypes.Z_LEVEL_CHANGED, EventTypes.SIM_TICK,
               EventTypes.JOB_CREATED, EventTypes.JOB_DONE,
               EventTypes.JOB_CANCELLED,
               EventTypes.CREATURE_SPAWNED, EventTypes.CREATURE_DIED,
               EventTypes.CREATURE_HIT, EventTypes.PLAYER_HIT,
               EventTypes.CREATURE_TAMED, EventTypes.SOUND_PLAYED,
               EventTypes.SAVE_GAME, EventTypes.LOAD_GAME):
        bus.subscribe(_t, log_subscriber)

    # ── 世界 / 玩家 / 系统：读档优先 ──
    if load_path and os.path.exists(load_path):
        registry = _build_registry()
        data = load_game(load_path, registry, bus)
        world = data["world"]
        player = data["player"]
        daynight = data["daynight"]
        survival = data["survival"]
        creatures_sys = data["creatures"]
        seed = data["seed"]
    else:
        registry, world = _build_world(seed)
        player = spawn_player(world, registry)
        daynight = DayNight(DAY_LENGTH_SEC)
        survival = SurvivalSystem(player, SurvivalConfig())
        survival.set_spawn(player.fx, player.fy)
        creatures_sys = None

    # ── 共同系统（crafting / world_sim / jobs / spawn）──
    crafting = Crafting.from_json(
        registry, os.path.join(DATA_DIR, CRAFTING_DATA))
    world_sim = WorldSim(world, registry)
    jobs = JobSystem(world, registry, bus,
                     JobConfig(dig_duration=JOB_DIG_DUR,
                               build_duration=JOB_BUILD_DUR))
    if creatures_sys is None:
        creatures_sys = CreatureSystem(world, registry, bus, CreatureConfig(), seed=seed)
    spawn_sys = SpawnSystem(world, registry, creatures_sys, bus, SpawnConfig(seed=seed), seed=seed)

    # 玩家事件总线接线（读档分支的 player 为新对象，需重新接 bus）
    player.event_bus = bus

    # ── M6：音效 + 粒子系统（事件驱动；headless/无设备静音容错）──
    # 整合：若挂载到统一产品内核，则音效复用共享 AudioSystem，
    # 存档经共享 SaveLoadManager 持久化（MC1 / MC2 同一套存档主干）。
    m6_sound = SoundEngine(audio_system=shared_audio) if shared_audio \
        else SoundEngine()
    m6_sound.init()
    m6_sound.subscribe(bus)
    m6_particles = ParticleSystem()
    m6_particles.subscribe(bus, registry)

    # 相机（视口固定尺寸，宽=列数-1，高=行数-1）
    viewport = AABB2D(0, 0, VIEWPORT_TILES[0] - 1, VIEWPORT_TILES[1] - 1)
    camera = Camera(viewport)
    camera.follow(player)
    camera.clamp_to(world.bounds())

    # 屏幕与渲染/HUD
    screen = pg.display.set_mode((WINDOW_W, WINDOW_H))
    pg.display.set_caption("MC 复刻版（GUI）")
    renderer = TileWorldRenderer(screen, registry)
    hud = HUD(screen)

    # 输入（键盘 RealtimeInputManager + 鼠标 MouseStateSource）
    from mcclone._engine import InputManager
    base = InputManager()
    key_source = PygameKeyStateSource()
    mouse = MouseStateSource()
    gui_input = GUIInputManager(base, key_source, mouse)

    loop = GameLoop(screen, world, player, camera, renderer, hud,
                    gui_input, bus, seed, registry,
                    survival=survival, daynight=daynight, crafting=crafting,
                    world_sim=world_sim, jobs=jobs,
                    creatures=creatures_sys, spawn=spawn_sys,
                    save_path=save_path,
                    sound=m6_sound, particles=m6_particles,
                    save_mgr=shared_save_mgr, save_slot=1)
    # 玩家受伤红屑（PLAYER_HIT 无坐标，用 loop.player 定位，兼容读档后的新对象）
    if loop.particles is not None:
        bus.subscribe(EventTypes.PLAYER_HIT,
                      lambda d: loop.particles.spawn_hit(loop.player.fx,
                                                         loop.player.fy))
    loop.run()
    return 0


def parse_args(argv=None) -> argparse.Namespace:
    """解析命令行参数。"""
    parser = argparse.ArgumentParser(description="MC 复刻版 GUI 入口")
    parser.add_argument("--no-gui", action="store_true",
                        help="无 GUI 降级（ANSI 文字渲染，复用 main.py）")
    parser.add_argument("--seed", type=int, default=SEED,
                        help="地形种子（默认 12345）")
    parser.add_argument("--load", type=str, default=None,
                        help="从指定存档 JSON 读档（替代世界生成）")
    parser.add_argument("--save", type=str, default=None,
                        help="指定存档/退出自动存档的目标 JSON 路径")
    return parser.parse_args(argv)


def main(argv=None) -> int:
    """程序入口。

    - --no-gui：复用现有 main.py 的 ANSI 路径（不修改它，地基零改动）。
    - 否则：启动 pygame GUI 主循环（含 M2 生存基底串联）。
    """
    args = parse_args(argv)
    if args.no_gui:
        # 降级路径：复用现有 main.py（不修改它）
        import main as main_module
        main_module.main()
        return 0
    return _run_gui(args.seed, args.load, args.save)


if __name__ == "__main__":
    sys.exit(main())
