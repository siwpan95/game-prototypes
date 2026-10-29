# -*- coding: utf-8 -*-
"""systems.survival — 生命/饥饿系统（M2 生存基底）。

提供：
  - SurvivalConfig: 生存数值配置（dataclass，架构 §7.1 / §7.2）。
  - SurvivalSystem(player, cfg): 每帧 update(dt) → tick_hunger(dt)，
    饥饿衰减；饥饿=0 持续扣血（饿伤）；饥饿≥阈值且未满血缓慢回血；
    hp 钳制 [0, max_hp]；死亡判定交给调用方（GameLoop）；
    respawn(world) 把玩家送回出生点、满血满饥饿、alive=True，背包保留。

约定：
  - 运行时直接读写 player.hp / player.hunger / player.alive /
    player.max_hp / player.max_hunger。
  - 玩家坐标重置使用 player 既有的 _fx/_fy 浮点脚底访问器与 _sync_aabb()；
    若 player 无 _sync_aabb，则重算 AABB（见 respawn 兜底）。
  - 零依赖（仅 dataclasses）；headless 可断言。
"""

from __future__ import annotations

from dataclasses import dataclass

from mcclone.core.geometry import clamp
from mcclone.core.block_world import BlockWorld  # 仅类型注解用，运行时不强制
from mcclone.player.player import Player          # 仅类型注解用


# ── 配置（架构 §7.1 / §7.2 / §8 D2~D4）──
@dataclass
class SurvivalConfig:
    """生存系统数值配置。

    所有默认值来自架构 §7.1 与 §8 采纳默认值。
    """

    MAX_HP: float = 20.0                 # 生命上限（M2-R1）
    MAX_HUNGER: float = 20.0            # 饥饿上限（M2-R1）
    HUNGER_DECAY_PER_SEC: float = 0.1   # 饥饿每秒衰减（≈200s 从满到空）
    STARVE_DAMAGE_PER_SEC: float = 1.0  # 饥饿=0 时每秒扣血
    HEAL_HUNGER_THRESHOLD: float = 18.0 # 饥饿≥此值才回血（M2-R7）
    HEAL_PER_SEC: float = 0.5           # 满饥饿时每秒回血


class SurvivalSystem:
    """生命/饥饿系统：驱动玩家 hp/hunger 变化与重生。"""

    def __init__(self, player: Player, cfg: SurvivalConfig | None = None) -> None:
        """构造。

        参数：
            player: 目标玩家（读写其 hp/hunger/alive 等）。
            cfg: 配置；为 None 时取默认 SurvivalConfig。
        """
        self.player: Player = player
        self.cfg: SurvivalConfig = cfg if cfg is not None else SurvivalConfig()
        # 出生点（由 GameLoop 经 set_spawn 写入，来自 spawn_player）。
        self._spawn_x: float = 0.0
        self._spawn_y: float = 0.0
        self._has_spawn: bool = False

    # ── 出生点 ──
    def set_spawn(self, x: float, y: float) -> None:
        """记录安全出生点（浮点脚底坐标）。"""
        self._spawn_x = float(x)
        self._spawn_y = float(y)
        self._has_spawn = True

    # ── 每帧推进 ──
    def update(self, dt: float) -> None:
        """单帧推进：仅调度饥饿 tick（hp 钳制在内部完成）。"""
        if dt <= 0:
            return
        self.tick_hunger(dt)

    def tick_hunger(self, dt: float) -> None:
        """饥饿衰减 → 饿伤 / 满饥饿回血；hp 钳制 [0,max_hp]。"""
        p = self.player
        # 饥饿衰减并钳制下限（仅衰减，上限由 max 决定；这里顺带钳制到合法区间）
        p.hunger = clamp(p.hunger - self.cfg.HUNGER_DECAY_PER_SEC * dt,
                         0.0, p.max_hunger)
        if p.hunger <= 0:
            # 饿伤
            self.damage(self.cfg.STARVE_DAMAGE_PER_SEC * dt)
        elif p.hunger >= self.cfg.HEAL_HUNGER_THRESHOLD and p.hp < p.max_hp:
            # 满饥饿缓慢回血（M2-R7）
            self.heal(self.cfg.HEAL_PER_SEC * dt)

    # ── 伤害 / 治疗 ──
    def damage(self, amount: float) -> None:
        """对玩家造成伤害（钳制 hp 到 [0, max_hp]）。"""
        if amount <= 0:
            return
        self.player.hp = clamp(self.player.hp - amount, 0.0, self.player.max_hp)

    def heal(self, amount: float) -> None:
        """治疗玩家（钳制 hp 到 [0, max_hp]）。"""
        if amount <= 0:
            return
        self.player.hp = clamp(self.player.hp + amount, 0.0, self.player.max_hp)

    def is_dead(self) -> bool:
        """玩家是否已死亡（hp<=0）。"""
        return self.player.hp <= 0

    # ── 重生 ──
    def respawn(self, world: BlockWorld) -> None:
        """把玩家送回出生点、满血满饥饿、alive=True；背包保留。

        坐标重置：写入 player 浮点脚底 _fx/_fy，再调用 _sync_aabb()
        重算整数 AABB；若 player 无 _sync_aabb（防御性），则用 min/max 兜底。
        """
        p = self.player
        if self._has_spawn:
            p._fx = self._spawn_x
            p._fy = self._spawn_y
        # 重算 AABB（优先用既有 _sync_aabb）
        if hasattr(p, "_sync_aabb") and callable(p._sync_aabb):
            p._sync_aabb()
        else:  # 防御性兜底：直接按浮点脚底派生整数 AABB
            import math
            p.min_x = int(math.floor(p._fx))
            p.min_y = int(math.floor(p._fy))
            p.max_x = p.min_x + 1
            p.max_y = int(math.floor(p._fy + p.height_f))
        # 状态重置（背包保留）
        p.hp = p.max_hp
        p.hunger = p.max_hunger
        p.alive = True

    # ── 快照接口（M5 存档/读档，供 savegame.py 使用）──

    def to_snapshot(self) -> dict:
        """返回生存系统的可序列化快照 dict。"""
        return {
            "spawn_x": self._spawn_x,
            "spawn_y": self._spawn_y,
            "hp": self.player.hp,
            "max_hp": self.player.max_hp,
            "hunger": self.player.hunger,
            "max_hunger": self.player.max_hunger,
        }

    @classmethod
    def from_snapshot(cls, d: dict, player: Player) -> "SurvivalSystem":
        """由快照 dict 重建 SurvivalSystem（仅走公开接口）。"""
        survival = cls(player, SurvivalConfig())
        survival.set_spawn(float(d.get("spawn_x", 0.0)),
                           float(d.get("spawn_y", 0.0)))
        player.max_hp = float(d.get("max_hp", player.max_hp))
        player.hp = float(d.get("hp", player.max_hp))
        player.max_hunger = float(d.get("max_hunger", player.max_hunger))
        player.hunger = float(d.get("hunger", player.max_hunger))
        return survival
