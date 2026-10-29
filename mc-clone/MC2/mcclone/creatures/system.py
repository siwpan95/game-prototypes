# -*- coding: utf-8 -*-
"""creatures.system — 生物系统核心（M4，T-M4-05）。

提供：
  - CreatureSystem: 生物列表 / spawn / update（AI→移动→碰撞→攻击判定）/ 攻击
    / 死亡掉落 / 事件；nearest_within / count。

设计要点（架构 §2.1 / §3 / §4.1 / §4.3 / §4.4）：
  - update(dt, player, daynight, on_player_hit)：对每生物执行 AI+物理；
    敌对且 ATTACK 且攻击冷却就绪且 AABB 与玩家重叠 → 经 on_player_hit 回调扣玩家 HP；
    末尾 remove_dead（掉落入 player.inventory + 移除 + 事件）。
  - 生物伤害玩家复用 survival.damage 经回调注入（不耦合 survival.py）。
  - 生物死亡掉落复用 player.inventory.add（跨栈合并/空槽复用）。
  - 仅用 self._rng = random.Random(seed)（确定性，不读墙钟）。纯标准库，headless 可断言。
"""

from __future__ import annotations

import math
import random

from mcclone.creatures.entity import AIState, Creature, CreatureConfig, CreatureKind
from mcclone.creatures.ai import AIContext
from mcclone.creatures.physics import move_with_collision
from mcclone.creatures.drops import roll_drops
from mcclone.core.event_bus import EventBus, EventTypes


class CreatureSystem:
    """生物系统：持有生物列表并驱动每帧逻辑。"""

    def __init__(self, world, registry, bus: "EventBus | None" = None,
                 cfg: "CreatureConfig | None" = None, seed: int = 0) -> None:
        self.world = world
        self.registry = registry
        self.bus = bus
        self.cfg = cfg if cfg is not None else CreatureConfig()
        self._rng = random.Random(seed)
        self._creatures: list = []

    # ── 增删 ──
    def spawn(self, kind: CreatureKind, x: float, y: float) -> Creature:
        """生成一只生物并加入列表（返回该实例）。"""
        c = Creature(kind, x, y, self.cfg, self._rng)
        self._creatures.append(c)
        if self.bus is not None:
            self.bus.emit(EventTypes.CREATURE_SPAWNED, kind=c.kind.name, x=x, y=y)
        return c

    def count(self) -> int:
        """当前生物数量。"""
        return len(self._creatures)

    # ── 每帧推进 ──
    def update(self, dt: float, player, daynight, on_player_hit) -> None:
        """单帧更新：AI+物理 + 敌对近身攻击 + 死亡处理。

        参数：
            dt: 固定步长（秒）。
            player: Player（攻击目标 / 掉落入包对象）。
            daynight: DayNight（供 AI ctx；可为 None）。
            on_player_hit: 回调 callable(amount)，用于扣玩家 HP
                （通常绑定 survival.damage）。
        """
        ctx = AIContext(player=player, world=self.world, registry=self.registry,
                        rng=self._rng, cfg=self.cfg, daynight=daynight)
        for c in self._creatures:
            # 1) AI 决策/执行 + 物理碰撞
            c.update(dt, self.world, self.registry, ctx)

            # 2) 敌对近身攻击玩家（ATTACK 状态 + 冷却就绪 + AABB 重叠）
            if (c.kind.is_hostile()
                    and c.state == AIState.ATTACK
                    and c.attack_cd <= 0
                    and c.intersects(player)):
                if on_player_hit is not None and c.melee_damage > 0:
                    on_player_hit(c.melee_damage)
                if self.bus is not None:
                    self.bus.emit(EventTypes.PLAYER_HIT, dmg=c.melee_damage,
                                  kind=c.kind.name)
                c.attack_cd = c.cfg.attack_cooldown

            # 3) 攻击冷却计时
            if c.attack_cd > 0:
                c.attack_cd -= dt

        # 4) 死亡掉落 / 移除
        self.remove_dead(player)

    def remove_dead(self, player) -> None:
        """移除 hp<=0 的生物：掉落入包 + 事件 + 移除列表。"""
        survivors: list = []
        for c in self._creatures:
            if c.hp <= 0:
                drops = roll_drops(c.kind)
                for bid, n in drops:
                    player.inventory.add(bid, n)
                if self.bus is not None:
                    self.bus.emit(EventTypes.CREATURE_DIED,
                                  kind=c.kind.name, x=c.fx, y=c.fy, drops=drops)
                    self.bus.emit(EventTypes.SOUND_PLAYED, name="creature_death")
            else:
                survivors.append(c)
        self._creatures = survivors

    # ── 战斗（玩家攻击生物）──
    def attack(self, target: Creature, dmg: float) -> None:
        """玩家近战命中某生物：扣血 + 事件（死亡交由 remove_dead 处理）。"""
        if target is None:
            return
        target.take_damage(dmg)
        if self.bus is not None:
            self.bus.emit(EventTypes.CREATURE_HIT, kind=target.kind.name,
                          id=target.id, dmg=dmg)

    # ── 查询 ──
    def nearest_within(self, player, r: float) -> "Creature | None":
        """返回玩家中心 r 范围内最近的生物（无则 None）。"""
        best = None
        best_d = float(r)
        px = player.fx + player.width_f / 2.0
        py = player.fy + player.height_f / 2.0
        for c in self._creatures:
            d = math.hypot(c.cx - px, c.cy - py)
            if d <= best_d:
                best = c
                best_d = d
        return best

    @property
    def creatures(self) -> list:
        """暴露内部生物列表（供渲染只读遍历）。"""
        return self._creatures
