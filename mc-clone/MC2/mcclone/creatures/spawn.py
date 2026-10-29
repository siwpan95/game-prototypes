# -*- coding: utf-8 -*-
"""creatures.spawn — 刷怪系统（M4，T-M4-06 / R3）。

提供：
  - SpawnConfig: 刷怪配置（上限/间隔/被动&敌对种类/种子）。
  - SpawnSystem: 按时间（昼夜）/上限/表面定位刷怪。

设计要点（架构 §2.1 / §7.3 / O8/O9/O10/O11）：
  - 白天刷被动（COW/PIG），夜间刷敌对（ZOMBIE）；经 DayNight.is_night() 判定。
  - 每 SPAWN_INTERVAL 秒尝试 1 次；仅当 creatures.count() < total_cap 时刷。
  - 定位：随机 x∈[0,width)，surface_y = 该列最高 solid y，生成于 surface_y+1。
  - 群系：M4 暂无 biome 系统，默认「全表面=平原」（biome_at 预留钩子）。
  - 确定性：刷怪种类/位置用 self._rng = random.Random(seed)，同种子可复现。
  - 纯标准库，headless 可断言。
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from mcclone.creatures.entity import CreatureKind
from mcclone.core.event_bus import EventBus, EventTypes


@dataclass
class SpawnConfig:
    """刷怪配置（架构 §7.1 / §7.3 / O8/O9）。"""

    total_cap: int = 20                 # 生物总数上限（性能护栏）
    interval: float = 2.0               # 刷怪尝试间隔（秒）
    passive_kinds: list = field(default_factory=lambda: [CreatureKind.COW, CreatureKind.PIG])
    hostile_kinds: list = field(default_factory=lambda: [CreatureKind.ZOMBIE])
    seed: int = 0


class SpawnSystem:
    """刷怪系统：周期性在表面生成生物（受昼夜/上限约束）。"""

    def __init__(self, world, registry, creatures, bus: "EventBus | None" = None,
                 cfg: "SpawnConfig | None" = None, seed: int = 0) -> None:
        self.world = world
        self.registry = registry
        self.creatures = creatures          # CreatureSystem（鸭子类型，提供 spawn/count）
        self.bus = bus
        self.cfg = cfg if cfg is not None else SpawnConfig(seed=seed)
        self._rng = random.Random(self.cfg.seed)
        self._acc: float = 0.0

    # ── 群系钩子（O11，M5 接入）──
    def biome_at(self, x: int) -> str:
        """返回列 x 的群系（M4 固定 PLAINS，M5 按真实群系系统扩展）。"""
        return "PLAINS"

    def _surface_y(self, x: int) -> int:
        """返回列 x 的最高 solid y；无则 -1。"""
        for y in range(self.world.height - 1, -1, -1):
            bid = self.world.get(x, y, 0)
            if bid != 0:
                try:
                    if self.registry.get(bid).solid:
                        return y
                except KeyError:
                    return y
        return -1

    def update(self, dt: float, daynight, creatures) -> None:
        """按间隔尝试刷怪；受昼夜与上限约束。

        参数：
            dt: 固定步长（秒）。
            daynight: DayNight（提供 is_night()）；None 视为白天。
            creatures: CreatureSystem（提供 count/spawn）。
        """
        self._acc += dt
        if self._acc < self.cfg.interval:
            return
        self._acc -= self.cfg.interval

        if creatures.count() >= self.cfg.total_cap:
            return

        is_night = daynight.is_night() if daynight is not None else False
        kinds = self.cfg.hostile_kinds if is_night else self.cfg.passive_kinds
        kind = self._rng.choice(kinds)
        x = self._rng.randrange(0, self.world.width)
        surface_y = self._surface_y(x)
        if surface_y < 0:
            return
        creatures.spawn(kind, float(x), float(surface_y + 1))
