# -*- coding: utf-8 -*-
"""
《我的世界》文字冒险 — 基于 alloy 引擎实现
================================================

本模块在 D:/allin/MCclone/alloy（统一游戏引擎）之上构建，
**充分利用引擎的全部功能**：

  - core.ECS   : World + Entity + Component（玩家/生物实体化）
  - core.EventBus : 松耦合事件总线（采集/合成/战斗/维度切换/胜利...）
  - systems.StackableInventory + ItemRegistry + EquipmentSlots : 背包 / 装备
  - systems.CraftingSystem + Recipe : 合成 / 熔炼
  - systems.SimpleCombat + MobLibrary / MobTemplate : 回合制战斗
  - systems.SaveLoadManager : 多槽位存档读档
  - fx.ParticleSystem + create_sparkle / create_explosion : 粒子特效
  - audio.AudioSystem : 音效（无音频设备时自动降级，绝不抛错）
  - ai.decision.BehaviorTree : 生物刷新决策
  - ai.decision.GenericStateMachine : 游戏流程状态机（探索/战斗/胜利/结束）

对外 API（供 MC1/main.py 的 Tkinter GUI 调用，保持严格兼容）：
  game.execute(cmd) -> str
  game.handle_pending_mob(cmd) -> str | None
  game.player                       # 含 hp/max_hp/hunger/armor/xp/weapon/tool/dimension/day
  game.phase                       # GamePhase 枚举
  game.current_biome_name / current_biome_icon
  game.time.phase                  # TimePhase 枚举
  game.day
  game._pending_mob               # str | None
"""

from __future__ import annotations

import os
import random
import sys
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Optional

# ── 让 alloy 可被导入（引擎位于 D:/allin/MCclone/alloy）──
# 引擎父目录 = MC1 所在目录的父目录（即 MCclone）
_ENGINE_PARENT = str(Path(__file__).resolve().parent.parent)
if _ENGINE_PARENT not in sys.path:
    sys.path.insert(0, _ENGINE_PARENT)

# ── 引擎子系统（统一游戏引擎 alloy）──
from alloy.core import World, Entity, Component
from alloy.core.event_bus import EventBus, EventTypes
from alloy.systems import (
    StackableInventory, ItemRegistry, EquipmentSlots,
    CraftingSystem, Recipe,
    SimpleCombat, MobTemplate, MobLibrary,
    SaveLoadManager,
)
from alloy.fx import ParticleSystem, create_sparkle, create_explosion, create_magic_circle
from alloy.audio import AudioSystem
from alloy.ai.decision import (
    BehaviorTree, Blackboard,
    Sequence, Selector, Condition, Action,
    GenericStateMachine, create_state_machine,
)

# ── 游戏静态数据（物品 / 配方 / 群系 / 生物 / 地图）──
from game_data import (
    ITEMS, CRAFTING_RECIPES, FURNACE_RECIPES,
    BIOMES, MOBS, WORLD_MAP, SPAWN_BIOME,
)

# ═════════════════════════════════════════════════════════
#  枚举
# ═════════════════════════════════════════════════════════

class TimePhase(Enum):
    DAWN = "黎明"
    DAY = "白天"
    DUSK = "黄昏"
    NIGHT = "夜晚"


class Dimension(Enum):
    OVERWORLD = "主世界"
    NETHER = "下界"
    END = "末地"


class GamePhase(Enum):
    PLAYING = "探索中"
    COMBAT = "战斗中"
    CRAFTING = "合成中"
    GAMEOVER = "游戏结束"
    VICTORY = "通关!"


# 时间周期（与原始设计一致）
DAY_CYCLE_LENGTH = 17
NIGHT_START_TURN = 12
DAWN_START_TURN = 0


# ═════════════════════════════════════════════════════════
#  ECS 组件（玩家 / 生物实体化）
# ═════════════════════════════════════════════════════════

class PositionComponent(Component):
    def __init__(self, x: int = 0, y: int = 0):
        self.x = x
        self.y = y


class HealthComponent(Component):
    def __init__(self, hp: int = 20, max_hp: int = 20):
        self.hp = hp
        self.max_hp = max_hp


class TagComponent(Component):
    def __init__(self, tag: str = ""):
        self.tag = tag


# ═════════════════════════════════════════════════════════
#  时间系统（轻量，发射时间事件）
# ═════════════════════════════════════════════════════════

class TimeSystem:
    """昼夜循环 + 事件发射。"""

    def __init__(self, bus: EventBus, adventure: "MinecraftAdventure"):
        self.bus = bus
        self.adv = adventure
        self.turn = 0

    def phase_for_turn(self, turn: int) -> TimePhase:
        t = turn % DAY_CYCLE_LENGTH
        if t <= 2:
            return TimePhase.DAWN
        if t <= 9:
            return TimePhase.DAY
        if t <= 11:
            return TimePhase.DUSK
        return TimePhase.NIGHT

    @property
    def phase(self) -> TimePhase:
        return self.phase_for_turn(self.turn)

    @property
    def is_hostile_time(self) -> bool:
        return self.phase in (TimePhase.DUSK, TimePhase.NIGHT)

    @property
    def is_dayish(self) -> bool:
        return self.phase in (TimePhase.DAWN, TimePhase.DAY)

    def advance(self, steps: int = 1) -> None:
        old_phase = self.phase
        old_day = self.adv.player.day
        self.turn += steps
        new_phase = self.phase
        if new_phase != old_phase:
            self.bus.emit(EventTypes.TIME_PHASE_CHANGED, {"phase": new_phase.value})
        new_day = self.adv.player.day
        if new_day != old_day:
            self.bus.emit(EventTypes.DAY_CHANGED, {"day_number": new_day})


# ═════════════════════════════════════════════════════════
#  玩家数据（引擎背包 / 装备的后向兼容门面）
# ═════════════════════════════════════════════════════════

class PlayerData:
    """玩家状态。

    物品与装备真实存储于引擎 `StackableInventory`（含 `EquipmentSlots`），
    此处以属性（property）向外暴露与原始 `PlayerData` 完全一致的字段，
    从而保证 MC1/main.py 的 GUI 无需任何改动即可工作。
    """

    def __init__(self, inv: StackableInventory):
        self.inv = inv
        # 位置
        self.biome_x: int = SPAWN_BIOME[0]
        self.biome_y: int = SPAWN_BIOME[1]
        self.dimension: Dimension = Dimension.OVERWORLD
        # 生命 / 饥饿 / 经验
        self.hp: int = 20
        self.max_hp: int = 20
        self.hunger: int = 0
        self.max_hunger: int = 20
        self.xp: int = 0
        # 标志位
        self.visited_biomes: set[str] = set()
        self.defeated_ender_dragon: bool = False
        self.shelter_built: bool = False
        self.placed_crafting_table: bool = False
        self.placed_furnace: bool = False
        self.placed_bed: bool = False
        # 统计
        self.turn: int = 0
        self.day: int = 1
        self.mobs_killed: int = 0
        self.total_gathered: int = 0

    # ── 装备槽（委托给引擎 EquipmentSlots）──
    @property
    def weapon(self) -> Optional[str]:
        return self.inv.equipment.weapon

    @weapon.setter
    def weapon(self, v: Optional[str]) -> None:
        self.inv.equipment._slots["weapon"] = v

    @property
    def tool(self) -> Optional[str]:
        return self.inv.equipment.tool

    @tool.setter
    def tool(self, v: Optional[str]) -> None:
        self.inv.equipment._slots["tool"] = v

    @property
    def helmet(self) -> Optional[str]:
        return self.inv.equipment._slots.get("helmet")

    @helmet.setter
    def helmet(self, v: Optional[str]) -> None:
        self.inv.equipment._slots["helmet"] = v

    @property
    def chestplate(self) -> Optional[str]:
        return self.inv.equipment._slots.get("chestplate")

    @chestplate.setter
    def chestplate(self, v: Optional[str]) -> None:
        self.inv.equipment._slots["chestplate"] = v

    @property
    def leggings(self) -> Optional[str]:
        return self.inv.equipment._slots.get("leggings")

    @leggings.setter
    def leggings(self, v: Optional[str]) -> None:
        self.inv.equipment._slots["leggings"] = v

    @property
    def boots(self) -> Optional[str]:
        return self.inv.equipment._slots.get("boots")

    @boots.setter
    def boots(self, v: Optional[str]) -> None:
        self.inv.equipment._slots["boots"] = v

    @property
    def armor(self) -> int:
        return self.inv.equipment.get_total_defense()

    # ── 背包（委托给引擎 StackableInventory）──
    @property
    def inventory(self) -> list[dict]:
        return self.inv.list_items()

    def count_item(self, item_id: str) -> int:
        return self.inv.count_item(item_id)

    def has_item(self, item_id: str, count: int = 1) -> bool:
        return self.inv.has_item(item_id, count)

    def add_item(self, item_id: str, count: int = 1) -> int:
        return self.inv.add_item(item_id, count)

    def remove_item(self, item_id: str, count: int = 1) -> bool:
        return self.inv.remove_item(item_id, count)

    def equip(self, item_id: str, slot: Optional[str] = None) -> bool:
        return self.inv.equipment.equip(item_id, slot)

    def get_weapon_damage(self) -> int:
        return self.inv.equipment.get_weapon_damage()

    def get_tool_tier(self) -> int:
        return self.inv.equipment.get_tool_tier()

    # ── 序列化（供 SaveLoadManager 使用）──
    def to_dict(self) -> dict:
        return {
            "biome_x": self.biome_x,
            "biome_y": self.biome_y,
            "dimension": self.dimension.value,
            "hp": self.hp,
            "max_hp": self.max_hp,
            "hunger": self.hunger,
            "max_hunger": self.max_hunger,
            "xp": self.xp,
            "inventory": self.inv.to_dict(),
            "visited_biomes": list(self.visited_biomes),
            "defeated_ender_dragon": self.defeated_ender_dragon,
            "shelter_built": self.shelter_built,
            "placed_crafting_table": self.placed_crafting_table,
            "placed_furnace": self.placed_furnace,
            "placed_bed": self.placed_bed,
            "turn": self.turn,
            "day": self.day,
            "mobs_killed": self.mobs_killed,
            "total_gathered": self.total_gathered,
        }

    def from_dict(self, d: dict) -> None:
        self.biome_x = d.get("biome_x", SPAWN_BIOME[0])
        self.biome_y = d.get("biome_y", SPAWN_BIOME[1])
        self.dimension = Dimension(d.get("dimension", "主世界"))
        self.hp = d.get("hp", 20)
        self.max_hp = d.get("max_hp", 20)
        self.hunger = d.get("hunger", 0)
        self.max_hunger = d.get("max_hunger", 20)
        self.xp = d.get("xp", 0)
        self.inv.from_dict(d.get("inventory", {"items": [], "equipment": {}}))
        self.visited_biomes = set(d.get("visited_biomes", []))
        self.defeated_ender_dragon = d.get("defeated_ender_dragon", False)
        self.shelter_built = d.get("shelter_built", False)
        self.placed_crafting_table = d.get("placed_crafting_table", False)
        self.placed_furnace = d.get("placed_furnace", False)
        self.placed_bed = d.get("placed_bed", False)
        self.turn = d.get("turn", 0)
        self.day = d.get("day", 1)
        self.mobs_killed = d.get("mobs_killed", 0)
        self.total_gathered = d.get("total_gathered", 0)


# ═════════════════════════════════════════════════════════
#  存档状态包装（供 SaveLoadManager.to_dict 调用）
# ═════════════════════════════════════════════════════════

class MC1SaveState:
    def __init__(self, adventure: "MinecraftAdventure"):
        self._adv = adventure

    def to_dict(self) -> dict:
        return self._adv.player.to_dict()


# ═════════════════════════════════════════════════════════
#  主游戏类
# ═════════════════════════════════════════════════════════

class MinecraftAdventure:
    """基于 alloy 的《我的世界》文字冒险。"""

    def __init__(self, log_callback=None, bus: Optional[EventBus] = None, core=None):
        self.log_callback = log_callback
        # 统一产品内核（可选）：MC1 文字模式作为同一游戏的玩法层挂载其上
        self.core = core

        # ── 引擎：ECS 世界 ──
        self.world = World()
        # 统一产品内核：若提供则复用共享事件总线；否则自建（或注入 bus）
        if core is not None:
            core.mount("MC1-文字", "我的世界文字冒险")
            self.bus = core.bus
        else:
            self.bus = bus if bus is not None else EventBus()

        # ── 引擎：物品注册表 + 可堆叠背包 + 装备槽 ──
        # 整合：挂载到产品内核时复用共享 ItemRegistry（MC1 物品 + MC2 方块同处一表）
        if core is None:
            self.registry = ItemRegistry()
        else:
            self.registry = core.registry
        self.registry.register_batch({k: dict(v) for k, v in ITEMS.items()})
        self.inv = StackableInventory(self.registry)
        self.player = PlayerData(self.inv)

        # ── 引擎：合成系统（配方来自 game_data）──
        self.crafting = CraftingSystem(self.inv, station_checker=self._has_station)
        for rid, spec in {**CRAFTING_RECIPES, **FURNACE_RECIPES}.items():
            self.crafting.register(rid, Recipe(
                needs=[tuple(n) for n in spec["needs"]],
                yields=spec.get("yields", 1),
                station=spec.get("station", "无"),
            ))

        # ── 引擎：生物模板库（来自 game_data.MOBS）──
        self.mob_lib = MobLibrary()
        for mid, m in MOBS.items():
            mob_type = m["type"]
            self.mob_lib.register(MobTemplate(
                mob_id=mid,
                name=m["name"],
                icon=m.get("icon", "👾"),
                mob_type=mob_type,
                hp=m["hp"],
                damage=m["damage"],
                drops=[tuple(d) for d in m.get("drops", [])],
                flee_chance=0.3 if mob_type == "passive" else 0.05,
                crit_chance=0.15,
            ))

        # ── 引擎：战斗系统 ──
        self.combat = SimpleCombat()

        # ── 引擎：存档管理器（挂载产品内核时复用共享 SaveLoadManager）──
        if core is None:
            self.save_dir = Path(__file__).resolve().parent / "saves"
            self.save_mgr = SaveLoadManager(str(self.save_dir), version=1)
        else:
            self.save_mgr = core.save_mgr

        # ── 引擎：粒子特效系统（主系统 + 预设特效子系统）──
        self.fx = ParticleSystem(max_particles=2000)
        self.fx_systems: list = []  # 预设特效子系统（爆炸/星光/魔法阵）

        # ── 引擎：音频系统（无设备自动降级；挂载内核时复用共享实例）──
        if core is None:
            self.audio = AudioSystem()
        else:
            self.audio = core.audio
        self.audio_plays: int = 0

        # ── 引擎：行为树（生物刷新决策）──
        self.spawn_bt = self._build_spawn_tree()

        # ── 引擎：状态机（游戏流程：探索/战斗/胜利/结束）──
        self.fsm = create_state_machine(
            "game_flow", GAME_FLOW_CONFIG, on_action=self._on_fsm_action
        )

        # 战斗状态 / 临时实体 / 待处理生物
        self.combat_state = None
        self._mob_entity: Optional[Entity] = None
        self._pending_mob: Optional[str] = None

        # 时间系统
        self.time = TimeSystem(self.bus, self)

        # 引擎：玩家实体（ECS）
        self.player_entity = self.world.create_entity("player")
        self.player_entity.add(PositionComponent(self.player.biome_x, self.player.biome_y))
        self.player_entity.add(HealthComponent(self.player.hp, self.player.max_hp))

        # ── 订阅事件 → 特效 / 音频 ──
        self._subscribe_events()

        # 初始群系
        self.player.visited_biomes.add(self._biome_id())

    # ───────────────────────────────────────────────
    #  引擎接线
    # ───────────────────────────────────────────────

    def _subscribe_events(self) -> None:
        """把引擎事件总线接到特效与音频。"""
        self.bus.subscribe(EventTypes.ITEM_CRAFTED, self._on_crafted)
        self.bus.subscribe(EventTypes.ITEM_SMELTED, self._on_crafted)
        self.bus.subscribe(EventTypes.MOB_DEFEATED, self._on_mob_defeated)
        self.bus.subscribe(EventTypes.BOSS_DEFEATED, self._on_boss_defeated)
        self.bus.subscribe(EventTypes.DIMENSION_CHANGED, self._on_dimension)
        self.bus.subscribe(EventTypes.ITEM_TAKE, self._on_item_take)
        self.bus.subscribe(EventTypes.PLAYER_MOVED, self._on_move)

    # ── 特效 / 音频 处理器 ──
    def _spawn_fx(self, fx) -> None:
        """挂载特效。

        fx 可能是:
          - alloy.fx.ParticleSystem（create_sparkle/explosion/magic_circle
            等预设工厂的返回值，本身已是完整粒子系统）→ 存入 fx_systems 单独驱动
          - Emitter（单个发射器）→ 加入主系统 self.fx
        """
        if fx is None:
            return
        if isinstance(fx, ParticleSystem):
            # 预设特效本身就是一个完整的粒子系统
            self.fx_systems.append(fx)
            # 防止子系统无限堆积
            if len(self.fx_systems) > 24:
                self.fx_systems.pop(0)
        else:
            self.fx.add_emitter(fx)
            # 防止发射器无限堆积
            if len(self.fx.emitters) > 24:
                self.fx.emitters.pop(0)

    def update_fx(self, dt: float = 0.016) -> int:
        """推进所有粒子系统（主系统 + 预设子系统），返回当前存活粒子总数。

        文本游戏没有连续渲染循环，但调用此方法可驱动粒子演化，便于探针测试验证。
        """
        total = 0
        self.fx.update(dt)
        total += self.fx.count
        alive_systems = []
        for sys in self.fx_systems:
            sys.update(dt)
            if sys.count > 0:
                alive_systems.append(sys)
                total += sys.count
        self.fx_systems = alive_systems
        return total

    def _synth(self, freq: float = 440.0, dur: float = 0.08) -> Optional[Any]:
        try:
            import numpy as np
        except Exception:
            return None
        sr = 22050
        n = max(1, int(sr * dur))
        t = np.linspace(0.0, dur, n, endpoint=False)
        wave = (np.sin(2.0 * np.pi * freq * t) * 0.3).astype(np.float32)
        return wave

    def _play_tone(self, freq: float = 440.0, dur: float = 0.08) -> None:
        wave = self._synth(freq, dur)
        self.audio_plays += 1
        try:
            self.audio.play_sfx_from_array(wave, volume=0.4)
        except Exception:
            pass

    def _on_crafted(self, data) -> None:
        self._spawn_fx(create_sparkle(0, 0))
        self._play_tone(660.0, 0.07)

    def _on_item_take(self, data) -> None:
        self._play_tone(520.0, 0.05)

    def _on_move(self, data) -> None:
        self._play_tone(300.0, 0.04)

    def _on_mob_defeated(self, data) -> None:
        self._spawn_fx(create_explosion(0, 0))
        self._play_tone(180.0, 0.18)

    def _on_boss_defeated(self, data) -> None:
        self._spawn_fx(create_explosion(0, 0))
        self._spawn_fx(create_magic_circle(0, 0))
        self._play_tone(120.0, 0.35)

    def _on_dimension(self, data) -> None:
        self._spawn_fx(create_magic_circle(0, 0))
        self._play_tone(500.0, 0.2)

    # ── 状态机回调：phase 由状态机单一来源决定 ──
    def _on_fsm_action(self, action_type: str, state_id: str, detail: dict) -> None:
        mapping = {
            "exploring": GamePhase.PLAYING,
            "combat": GamePhase.COMBAT,
            "victory": GamePhase.VICTORY,
            "gameover": GamePhase.GAMEOVER,
        }
        if state_id in mapping:
            self.phase = mapping[state_id]

    # ───────────────────────────────────────────────
    #  行为与群系辅助
    # ───────────────────────────────────────────────

    def _biome_id(self) -> str:
        return WORLD_MAP[self.player.biome_y][self.player.biome_x]

    @property
    def current_biome_name(self) -> str:
        return BIOMES[self._biome_id()]["name"]

    @property
    def current_biome_icon(self) -> str:
        return BIOMES[self._biome_id()]["icon"]

    @property
    def day(self) -> int:
        """代理到玩家天数（main.py 与探针可能直接读 game.day）。"""
        return self.player.day

    def _item_id_from_name(self, name: str) -> Optional[str]:
        """中文名 / id 统一解析为物品 id。"""
        name = (name or "").strip()
        if not name:
            return None
        if name in ITEMS:
            return name
        for iid, info in ITEMS.items():
            if info.get("name") == name:
                return iid
        return None

    def _has_station(self, station: str) -> bool:
        if station == "工作台":
            return self.player.placed_crafting_table
        if station == "熔炉":
            return self.player.placed_furnace
        return True

    # ───────────────────────────────────────────────
    #  命令分发
    # ───────────────────────────────────────────────

    def execute(self, command: str) -> str:
        raw = (command or "").strip()
        if not raw:
            return ""
        cmd = raw.lower()  # 用于 ASCII 别名的大小写无关匹配

        def _m(*alts) -> bool:
            return raw in alts or cmd in alts

        # 顺序与原始设计保持一致（避免 s/e/n/w 别名冲突）
        if _m("help", "帮助", "?", "？"):
            return self._cmd_help()
        if _m("status", "状态", "s"):
            return self._cmd_status()
        if _m("look", "观察", "看", "l"):
            return self._cmd_look()
        if _m("inv", "背包", "i", "inventory"):
            return self._cmd_inventory()
        if _m("craft", "合成", "c"):
            return self._cmd_craft_list()
        if raw.startswith("合成 ") or cmd.startswith("craft "):
            item = raw.split(" ", 1)[1] if " " in raw else ""
            return self._cmd_craft(item)
        if cmd.startswith("c ") and len(cmd) > 2:
            return self._cmd_craft(raw[2:].strip())
        if _m("smelt", "熔炼"):
            item = raw.split(" ", 1)[1] if " " in raw else ""
            return self._cmd_smelt(item)
        if _m("save", "存档"):
            return self._cmd_save()
        if _m("load", "读档"):
            return self._cmd_load()
        if _m("北", "north", "n"):
            return self._cmd_move(0, -1)
        if _m("南", "south", "s"):
            return self._cmd_move(0, 1)
        if _m("西", "west", "w"):
            return self._cmd_move(-1, 0)
        if _m("东", "east", "e"):
            return self._cmd_move(1, 0)
        if _m("gather", "采集", "g", "挖"):
            return self._cmd_gather()
        if self.phase == GamePhase.COMBAT:
            return self._cmd_combat(cmd)
        if _m("eat", "吃", "e"):
            return self._cmd_eat()
        if raw.startswith("放置 ") or cmd.startswith("place "):
            item = raw.split(" ", 1)[1] if " " in raw else ""
            return self._cmd_place(item)
        if raw.startswith("装备 ") or cmd.startswith("equip "):
            item = raw.split(" ", 1)[1] if " " in raw else ""
            return self._cmd_equip(item)
        if _m("sleep", "睡觉"):
            return self._cmd_sleep()
        if _m("build", "建造", "造"):
            return self._cmd_build()
        if _m("portal", "传送门", "下界", "nether"):
            return self._cmd_nether_portal()
        if _m("end", "末地"):
            return self._cmd_end_portal()
        if _m("home", "回家", "spawn"):
            return self._cmd_home()
        return self._cmd_help()

    # ───────────────────────────────────────────────
    #  被动生物：猎杀 / 放弃
    # ───────────────────────────────────────────────

    def handle_pending_mob(self, cmd: str) -> Optional[str]:
        if not self._pending_mob:
            return None
        raw = (cmd or "").strip()
        low = raw.lower()
        if raw in ("猎杀", "hunt", "kill", "打") or low in ("hunt", "kill"):
            return self._cmd_hunt()
        # 其它命令（含移动方向）视为放弃猎杀
        self._pending_mob = None
        return None

    # ───────────────────────────────────────────────
    #  各命令实现
    # ───────────────────────────────────────────────

    def _cmd_help(self) -> str:
        return (
            "📋 可用命令：\n"
            "  采集 / 观察 / 背包 / 状态 / 帮助\n"
            "  合成（查看配方）| 合成 <物品> | 熔炼 <物品>\n"
            "  北/南/西/东（探索）| 吃 | 装备 <物品>\n"
            "  放置 <工作台/熔炉/床> | 建造 | 睡觉\n"
            "  下界（传送门）| 末地 | 回家 | 存档 | 读档\n"
            "  战斗中：攻击 / 防御 / 逃跑"
        )

    def _cmd_status(self) -> str:
        p = self.player
        return (
            f"❤️ 生命: {p.hp}/{p.max_hp}\n"
            f"🍖 饥饿: {p.hunger}/{p.max_hunger}\n"
            f"🛡️ 护甲: {p.armor}  |  ⭐ 经验: {p.xp}\n"
            f"{self.current_biome_icon} 位置: {self.current_biome_name}\n"
            f"🌍 维度: {p.dimension.value}  |  🌓 {self.time.phase.value}"
        )

    def _cmd_look(self) -> str:
        bid = self._biome_id()
        info = BIOMES[bid]
        lines = [f"{info['icon']} 你正处于「{info['name']}」", info["desc"], "可采集资源："]
        for rid in info["resources"]:
            rinfo = ITEMS.get(rid, {})
            lines.append(f"  {rinfo.get('icon','')} {rinfo.get('name', rid)}")
        lines.append("可前往：北 / 南 / 西 / 东")
        return "\n".join(lines)

    def _cmd_inventory(self) -> str:
        items = self.inv.list_items()
        if not items:
            return "🎒 背包空空如也。"
        lines = ["🎒 背包："]
        for slot in items[:20]:
            info = ITEMS.get(slot["id"], {})
            lines.append(f"  {info.get('icon','')} {info.get('name', slot['id'])} ×{slot['count']}")
        return "\n".join(lines)

    def _cmd_craft_list(self) -> str:
        avail = self.crafting.list_available()
        if not avail:
            return "🔨 暂无可合成物品（可能缺少材料或合成站）。"
        lines = ["🔨 可合成："]
        for rid in avail:
            lines.append("  " + self.crafting.format_recipe(rid))
        return "\n".join(lines)

    def _cmd_craft(self, item: str) -> str:
        rid = self._item_id_from_name(item)
        if not rid or rid not in self.crafting.recipes:
            return f"🔨 未知配方：{item}"
        ok, msg = self.crafting.try_craft(rid)
        if ok:
            self.bus.emit(EventTypes.ITEM_CRAFTED, {"item_id": rid})
        return msg

    def _cmd_smelt(self, item: str) -> str:
        rid = self._item_id_from_name(item)
        if not rid or rid not in self.crafting.recipes:
            return f"🔥 未知熔炼配方：{item}"
        ok, msg = self.crafting.try_craft(rid)
        if ok:
            self.bus.emit(EventTypes.ITEM_SMELTED, {"item_id": rid})
        return msg

    def _cmd_save(self) -> str:
        ok = self.save_mgr.save(MC1SaveState(self), slot=0)
        if ok:
            return "💾 游戏已保存！（引擎 SaveLoadManager · 槽位 0）"
        return "❌ 保存失败。"

    def _cmd_load(self) -> str:
        data = self.save_mgr.load(0)
        if not data:
            return "❌ 没有找到存档。"
        self.player.from_dict(data)
        # 同步 ECS 玩家实体
        self.player_entity.get(PositionComponent).x = self.player.biome_x
        self.player_entity.get(PositionComponent).y = self.player.biome_y
        self.player_entity.get(HealthComponent).hp = self.player.hp
        self.combat_state = None
        self._pending_mob = None
        self.fsm.trigger("combat_end") if self.phase == GamePhase.COMBAT else None
        self.phase = GamePhase.PLAYING
        return "📂 游戏已读取！"

    def _cmd_move(self, dx: int, dy: int) -> str:
        nx = max(0, min(len(WORLD_MAP[0]) - 1, self.player.biome_x + dx))
        ny = max(0, min(len(WORLD_MAP) - 1, self.player.biome_y + dy))
        moved = (nx != self.player.biome_x or ny != self.player.biome_y)
        old_bid = self._biome_id()
        self.player.biome_x, self.player.biome_y = nx, ny
        self.player.turn += 1
        self.time.advance(1)
        self._tick_hunger()
        # 同步玩家实体位置
        pos = self.player_entity.get(PositionComponent)
        pos.x, pos.y = nx, ny
        self.bus.emit(EventTypes.PLAYER_MOVED,
                        {"from": (self.player.biome_x - dx, self.player.biome_y - dy),
                         "to": (nx, ny)})
        msgs = []
        if moved:
            new_bid = self._biome_id()
            self.player.visited_biomes.add(new_bid)
            self.bus.emit(EventTypes.BIOME_CHANGED,
                            {"from_biome": old_bid, "to_biome": new_bid})
            msgs.append(f"🚶 你向{'北' if dy<0 else '南' if dy>0 else '东' if dx>0 else '西'}方前进，"
                       f"来到 {BIOMES[new_bid]['icon']}{BIOMES[new_bid]['name']}。")
        else:
            msgs.append("🚶 你撞上了世界的边界。")
        spawn = self._roll_spawn()
        if spawn:
            msgs.append(spawn)
        return "\n".join(msgs)

    def _cmd_gather(self) -> str:
        bid = self._biome_id()
        info = BIOMES[bid]
        res = info["resources"]
        rid = random.choice(list(res.keys()))
        lo, hi = res[rid]
        count = random.randint(lo, hi) if hi > lo else hi
        count = max(1, count)
        self.inv.add_item(rid, count)
        self.player.total_gathered += count
        self.player.turn += 1
        self.time.advance(1)
        self._tick_hunger()
        rinfo = ITEMS.get(rid, {})
        self.bus.emit(EventTypes.ITEM_TAKE, {"item_id": rid, "count": count})
        msgs = [f"⛏️ 你采集到 {rinfo.get('icon','')} {rinfo.get('name', rid)} ×{count}。"]
        spawn = self._roll_spawn()
        if spawn:
            msgs.append(spawn)
        return "\n".join(msgs)

    def _cmd_eat(self) -> str:
        # 找第一个食物
        for slot in self.inv.list_items():
            info = ITEMS.get(slot["id"], {})
            if info.get("type") == "food":
                hunger_restore = int(info.get("hunger", 0))
                self.inv.remove_item(slot["id"], 1)
                self.player.hunger = max(0, self.player.hunger - hunger_restore)
                self.bus.emit(EventTypes.HUNGER_CHANGED,
                                {"old": self.player.hunger + hunger_restore,
                                 "new": self.player.hunger})
                return f"🍖 你吃下了 {info.get('name', slot['id'])}，饥饿缓解了。"
        return "🍖 背包里没有可吃的食物。"

    def _cmd_place(self, item: str) -> str:
        rid = self._item_id_from_name(item)
        if rid == "crafting_table":
            if not self.inv.has_item("crafting_table", 1):
                return "🔲 你没有工作台可放置。"
            self.inv.remove_item("crafting_table", 1)
            self.player.placed_crafting_table = True
            self.bus.emit(EventTypes.STATION_PLACED, {"station_type": "crafting_table"})
            return "🔲 你放置了工作台，现在可以合成工具了！"
        if rid == "furnace":
            if not self.inv.has_item("furnace", 1):
                return "🔥 你没有熔炉可放置。"
            self.inv.remove_item("furnace", 1)
            self.player.placed_furnace = True
            self.bus.emit(EventTypes.STATION_PLACED, {"station_type": "furnace"})
            return "🔥 你放置了熔炉，现在可以熔炼矿石了！"
        if rid == "bed":
            if not self.inv.has_item("bed", 1):
                return "🛏️ 你没有床可放置。"
            self.inv.remove_item("bed", 1)
            self.player.placed_bed = True
            self.bus.emit(EventTypes.STATION_PLACED, {"station_type": "bed"})
            return "🛏️ 你放置了床，夜晚可以睡觉了！"
        return "放置失败：仅支持 工作台 / 熔炉 / 床。"

    def _cmd_equip(self, item: str) -> str:
        rid = self._item_id_from_name(item)
        if not rid:
            return f"🗡️ 未知物品：{item}"
        if not self.inv.has_item(rid, 1):
            return f"🗡️ 背包里没有 {ITEMS.get(rid, {}).get('name', rid)}。"
        ok = self.player.equip(rid)
        if not ok:
            return "🗡️ 无法装备该物品。"
        self.bus.emit(EventTypes.ITEM_EQUIPPED, {"item_id": rid})
        return f"🗡️ 你装备了 {ITEMS.get(rid, {}).get('name', rid)}。"

    def _cmd_sleep(self) -> str:
        if self.time.phase not in (TimePhase.DUSK, TimePhase.NIGHT):
            return "🌙 现在不是睡觉的时候（需黄昏或夜晚）。"
        if not self.player.placed_bed:
            return "🛏️ 你还没有放置床，无法睡觉。"
        # 跳到次日黎明
        self.player.day += 1
        self.player.turn = (self.player.turn // DAY_CYCLE_LENGTH + 1) * DAY_CYCLE_LENGTH
        self.time.turn = self.player.turn
        self.bus.emit(EventTypes.DAY_CHANGED, {"day_number": self.player.day})
        self.bus.emit(EventTypes.TIME_PHASE_CHANGED, {"phase": self.time.phase.value})
        return f"🌙 你躺下睡去，醒来已是第 {self.player.day} 天黎明。"

    def _cmd_build(self) -> str:
        if not self.inv.has_item("wood_planks", 10) or not self.inv.has_item("cobblestone", 5):
            return "🏠 建造庇护所需：木板 ×10 + 圆石 ×5。"
        self.inv.remove_item("wood_planks", 10)
        self.inv.remove_item("cobblestone", 5)
        self.player.shelter_built = True
        self.bus.emit(EventTypes.SHELTER_BUILT, {})
        return "🏠 你建造了一座坚固的庇护所，夜晚怪物刷怪率大幅下降！"

    def _cmd_nether_portal(self) -> str:
        if not self.inv.has_item("obsidian", 10) or not self.inv.has_item("flint_and_steel", 1):
            return "🟣 激活下界传送门需要：黑曜石 ×10 + 打火石 ×1。"
        self.inv.remove_item("obsidian", 10)
        self.inv.remove_item("flint_and_steel", 1)
        self.player.dimension = Dimension.NETHER
        self.player.biome_x, self.player.biome_y = 1, 0  # nether 群系
        self.bus.emit(EventTypes.DIMENSION_CHANGED,
                        {"from_dim": "主世界", "to_dim": "下界"})
        self.bus.emit(EventTypes.PORTAL_ACTIVATED, {"target_dimension": "下界"})
        return "🟣 下界传送门激活！你踏入了炽热的下界。"

    def _cmd_end_portal(self) -> str:
        if not self.inv.has_item("ender_eye", 12) or not self.inv.has_item("ender_pearl", 4):
            return "🟢 激活末地传送门需要：末影之眼 ×12 + 末影珍珠 ×4。"
        self.inv.remove_item("ender_eye", 12)
        self.inv.remove_item("ender_pearl", 4)
        self.player.dimension = Dimension.END
        self.player.biome_x, self.player.biome_y = 2, 2  # end 群系
        self.bus.emit(EventTypes.DIMENSION_CHANGED,
                        {"from_dim": "主世界", "to_dim": "末地"})
        self.bus.emit(EventTypes.PORTAL_ACTIVATED, {"target_dimension": "末地"})
        return "🟢 末地传送门激活！末影龙的巢穴近在眼前……"

    def _cmd_home(self) -> str:
        if self.player.dimension == Dimension.OVERWORLD:
            return "🏡 你已经在主世界了。"
        self.player.dimension = Dimension.OVERWORLD
        self.player.biome_x, self.player.biome_y = SPAWN_BIOME
        self.bus.emit(EventTypes.DIMENSION_CHANGED,
                        {"from_dim": self.player.dimension.value, "to_dim": "主世界"})
        return "🏡 你使用指令回到了主世界的出生点。"

    # ───────────────────────────────────────────────
    #  生物刷新（引擎行为树决策）
    # ───────────────────────────────────────────────

    def _build_spawn_tree(self) -> BehaviorTree:
        """构造生物刷新决策行为树。

        黑板键：is_hostile_time / sheltered / spawn_rate /
        hostile_candidates / passive_candidates / rng / rng_passive
        结果写入黑板：spawn = mob_id | None
        """
        bb = Blackboard()

        def is_hostile_time(ctx):
            return bool(ctx.blackboard.get("is_hostile_time", False))

        def not_sheltered(ctx):
            return not bool(ctx.blackboard.get("sheltered", False))

        def rng_pass(ctx):
            return ctx.blackboard.get("rng", 1.0) < ctx.blackboard.get("spawn_rate", 0.0)

        def rng_passive_pass(ctx):
            return ctx.blackboard.get("rng", 1.0) < ctx.blackboard.get("rng_passive", 0.0)

        def do_hostile(ctx):
            cands = ctx.blackboard.get("hostile_candidates", []) or []
            ctx.blackboard.set("spawn", random.choice(cands) if cands else None)

        def do_passive(ctx):
            cands = ctx.blackboard.get("passive_candidates", []) or []
            ctx.blackboard.set("spawn", random.choice(cands) if cands else None)

        def do_none(ctx):
            ctx.blackboard.set("spawn", None)

        root = Selector("spawn_root")
        seq_h = Sequence("hostile_seq")
        seq_h.add(Condition("c_hostile_time", is_hostile_time))
        seq_h.add(Condition("c_not_sheltered", not_sheltered))
        seq_h.add(Condition("c_rng", rng_pass))
        seq_h.add(Action("a_hostile", do_hostile))
        root.add(seq_h)

        seq_p = Sequence("passive_seq")
        seq_p.add(Condition("c_dayish", lambda c: bool(c.blackboard.get("is_dayish", False))))
        seq_p.add(Condition("c_rng_passive", rng_passive_pass))
        seq_p.add(Action("a_passive", do_passive))
        root.add(seq_p)

        root.add(Action("a_none", do_none))
        return BehaviorTree(root, blackboard=bb)

    def _roll_spawn(self) -> Optional[str]:
        bid = self._biome_id()
        binfo = BIOMES[bid]
        base_rate = binfo.get("hostile_spawn_rate", 0.2)
        # 庇护所 + 主世界 → 刷怪率大幅下降
        sheltered = self.player.dimension == Dimension.OVERWORLD and self.player.shelter_built
        eff_rate = base_rate * 0.3 if sheltered else base_rate

        hostile_cands = ["zombie", "skeleton", "creeper", "spider", "slime"]
        if self.player.dimension == Dimension.NETHER:
            hostile_cands = [m for m in hostile_cands if m != "creeper"]
        # 仅保留已在 MOBS 中定义的被动生物；生物群系若列出未登记生物
        # （如 goat/fox/turtle/dolphin/bat）则跳过，避免 MOBS[mob_id] 触发 KeyError
        # （移动命令每次都会 _roll_spawn，未定义生物会导致游戏崩溃）。
        passive_cands = [m for m in binfo.get("passive_mobs", []) if m in MOBS]

        bb_data = {
            "is_hostile_time": self.time.is_hostile_time,
            "is_dayish": self.time.is_dayish,
            "sheltered": sheltered,
            "spawn_rate": eff_rate,
            "hostile_candidates": hostile_cands,
            "passive_candidates": passive_cands,
            "rng": random.random(),
            "rng_passive": 0.20,
        }
        self.spawn_bt.blackboard.update(bb_data)
        self.spawn_bt.reset()
        self.spawn_bt.tick()
        mob_id = self.spawn_bt.blackboard.get("spawn")
        if not mob_id:
            return None
        if MOBS[mob_id]["type"] == "passive":
            self._pending_mob = mob_id
            minfo = MOBS[mob_id]
            return (f"{minfo['icon']} 一只{minfo['name']}出现了！\n"
                    f"   输入「猎杀」与之战斗，或移动离开。")
        # 敌对生物 → 直接进入战斗
        self._enter_combat(mob_id)
        return (f"{MOBS[mob_id]['icon']} 一只{MOBS[mob_id]['name']}袭击了你！\n"
                f"   战斗开始：攻击 / 防御 / 逃跑")

    def _cmd_hunt(self) -> str:
        mob_id = self._pending_mob
        self._pending_mob = None
        if not mob_id:
            return "周围没有可猎杀的生物。"
        self._enter_combat(mob_id)
        return self._combat_prompt(mob_id)

    # ───────────────────────────────────────────────
    #  战斗（引擎 SimpleCombat + MobLibrary）
    # ───────────────────────────────────────────────

    def _enter_combat(self, mob_id: str, prefix: str = "") -> None:
        mob = self.mob_lib.get(mob_id)
        if mob is None:
            return
        self.combat_state = self.combat.start(
            mob, player_hp=self.player.hp, armor=self.player.armor
        )
        # ECS：生物实体化
        self._mob_entity = self.world.create_entity(mob_id)
        self._mob_entity.add(HealthComponent(
            self.combat_state.mob_hp, self.combat_state.mob_max_hp))
        self._pending_mob = None
        # 状态机 → 进入战斗
        self.fsm.trigger("combat_start")
        self.bus.emit(EventTypes.MOB_SPAWNED, {"mob_id": mob_id})
        self.bus.emit(EventTypes.COMBAT_START, {"mob_id": mob_id})

    def _combat_prompt(self, mob_id: str) -> str:
        st = self.combat_state
        minfo = MOBS[mob_id]
        return (
            f"{minfo['icon']} {minfo['name']} 来袭！\n"
            f"   怪物 HP: {st.mob_hp}/{st.mob_max_hp}  |  你的 HP: {self.player.hp}/{self.player.max_hp}\n"
            f"   命令：攻击 / 防御 / 逃跑"
        )

    def _cmd_combat(self, cmd: str) -> str:
        if self.combat_state is None:
            self.phase = GamePhase.PLAYING
            return "⚔️ 当前没有进行中的战斗。"
        st = self.combat_state
        if cmd in ("攻击", "attack", "a", "打"):
            msg = self.combat.attack(st, weapon_damage=self.player.get_weapon_damage())
        elif cmd in ("防御", "block", "defend", "b", "d"):
            msg = self.combat.defend(st)
        elif cmd in ("逃跑", "flee", "f", "跑"):
            msg = self.combat.flee(st)
        else:
            return "⚔️ 战斗中可用：攻击 / 防御 / 逃跑。"
        self.player.hp = st.player_hp
        self.player_entity.get(HealthComponent).hp = st.player_hp
        if st.is_over:
            return self._finish_combat(st)
        return msg + "\n" + self._combat_status()

    def _combat_status(self) -> str:
        st = self.combat_state
        return (f"   怪物 HP: {max(0, st.mob_hp)}/{st.mob_max_hp}  |  "
                f"你的 HP: {max(0, self.player.hp)}/{self.player.max_hp}")

    def _finish_combat(self, st) -> str:
        result = ""
        if st.player_won:
            drops = self.combat.generate_drops(st)
            for item_id, cnt in drops:
                self.inv.add_item(item_id, cnt)
            xp = self.combat.get_xp_reward(st)
            self.player.xp += xp
            self.player.mobs_killed += 1
            mob_id = st.mob.mob_id
            self.bus.emit(EventTypes.MOB_DEFEATED, {"mob_id": mob_id, "drops": drops})
            result = f"💀 你击败了 {MOBS[mob_id]['name']}！获得经验 {xp}。"
            if drops:
                dn = "、".join(f"{ITEMS.get(i, {}).get('name', i)}×{c}" for i, c in drops)
                result += f"（掉落：{dn}）"
            if mob_id == "ender_dragon":
                self.player.defeated_ender_dragon = True
                self.bus.emit(EventTypes.BOSS_DEFEATED, {"boss_id": mob_id})
                result += "\n🐉 你击败了末影龙！"
            # 清理 ECS 生物实体
            if self._mob_entity is not None:
                self.world.remove_entity(self._mob_entity.eid)
                self._mob_entity = None
            if self.player.defeated_ender_dragon:
                self.fsm.trigger("victory")
                result += "\n\n🏆 恭喜通关！感谢游玩《我的世界》文字冒险。"
                return result
            self.fsm.trigger("combat_end")
            return result
        else:
            self.player.hp = 0
            self.player_entity.get(HealthComponent).hp = 0
            self.bus.emit(EventTypes.PLAYER_DIED, {})
            if self._mob_entity is not None:
                self.world.remove_entity(self._mob_entity.eid)
                self._mob_entity = None
            self.fsm.trigger("game_over")
            return "💀 你被击败了……游戏结束。输入「读档」继续，或重启游戏。"

    def _tick_hunger(self) -> None:
        """每回合饥饿 +1；饥饿满则扣血。"""
        self.player.hunger = min(self.player.max_hunger, self.player.hunger + 1)
        if self.player.hunger >= self.player.max_hunger:
            self.player.hp = max(0, self.player.hp - 1)
            self.player_entity.get(HealthComponent).hp = self.player.hp
            if self.player.hp <= 0:
                self.bus.emit(EventTypes.PLAYER_DIED, {})
                if self._mob_entity is not None:
                    self.world.remove_entity(self._mob_entity.eid)
                    self._mob_entity = None
                self.fsm.trigger("game_over")


# ═════════════════════════════════════════════════════════
#  游戏流程状态机配置（引擎 GenericStateMachine）
# ═════════════════════════════════════════════════════════

GAME_FLOW_CONFIG = {
    "state_machines": {
        "game_flow": {
            "initial": "exploring",
            "states": {
                "exploring": {
                    "on_enter": "探索中",
                    "transitions": {
                        "combat_start": "combat",
                        "victory": "victory",
                        "game_over": "gameover",
                    },
                },
                "combat": {
                    "on_enter": "战斗中",
                    "transitions": {
                        "combat_end": "exploring",
                        "victory": "victory",
                        "game_over": "gameover",
                    },
                },
                "victory": {"on_enter": "通关!", "transitions": {}},
                "gameover": {"on_enter": "游戏结束", "transitions": {}},
            },
        }
    }
}


# 方便探针测试：当前有多少引擎子系统在线
def engine_subsystems_snapshot(adv: "MinecraftAdventure") -> dict:
    return {
        "ecs_world": adv.world is not None,
        "event_bus": adv.bus is not None,
        "registered_events": adv.bus.registered_events(),
        "stackable_inventory": adv.inv is not None,
        "item_registry_count": adv.registry.count,
        "crafting_recipes": adv.crafting.recipe_count,
        "mob_library": adv.mob_lib.count,
        "particle_system": adv.fx is not None,
        "audio_system_available": adv.audio.is_available,
        "audio_plays": adv.audio_plays,
        "spawn_behavior_tree": adv.spawn_bt is not None,
        "game_flow_fsm": adv.fsm is not None,
        "save_manager": adv.save_mgr is not None,
        "fsm_state": adv.fsm.current_state_id,
    }
