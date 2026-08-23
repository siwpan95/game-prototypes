# -*- coding: utf-8 -*-
"""creatures.ai — 生物 AI 状态机 + 简易寻路（M4，T-M4-03 / T-M4-04）。

提供：
  - AIContext: 轻量上下文（player/world/registry/rng/cfg/daynight）。
  - AIController: 状态机 decide_state + apply（idle/wander/flee/attack）。
  - Pathing.step_toward: 贪心朝目标 + 遇阻跳跃攀爬（R6，无 A*，确定性）。

设计要点（架构 §2.1 / §7.4 / R6）：
  - 状态机可观测（读 creature.state）；决策按 ai_timer 节流（decision_step），
    非每帧随机，保证确定性 + 省 CPU。
  - AI 只设置速度意图 + 攀爬跳跃；实际位移由 creatures.physics.move_with_collision 完成。
  - 不引入全局 random（一律用 ctx.rng）；纯标准库，headless 可断言。
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field

from mcclone.creatures.entity import AIState, CreatureConfig
from mcclone.creatures.physics import _is_solid


# ─────────────────────────────────────────────────────────────────────────
# 上下文
# ─────────────────────────────────────────────────────────────────────────

@dataclass
class AIContext:
    """AI 决策/执行所需的轻量上下文（由 CreatureSystem 每帧构建）。"""

    player: object                      # Player（含 fx/fy/width_f/height_f）
    world: object                       # BlockWorld（z=0 层）
    registry: object                    # BlockRegistry
    rng: random.Random                  # 系统级 rng（确定性）
    cfg: CreatureConfig                 # 生物配置
    daynight: object = None             # DayNight（按需，如刷怪/光照）


# ─────────────────────────────────────────────────────────────────────────
# 工具
# ─────────────────────────────────────────────────────────────────────────

def _player_center(player) -> tuple[float, float]:
    """返回玩家中心 (cx, cy)（Player 无 cx 属性，手动算）。"""
    return (player.fx + player.width_f / 2.0,
            player.fy + player.height_f / 2.0)


def _dist(c, player) -> float:
    """生物中心到玩家中心的距离。"""
    px, py = _player_center(player)
    return math.hypot(c.cx - px, c.cy - py)


def _is_solid_ahead(c, world, registry) -> bool:
    """生物面朝方向前方（脚/头高度）是否有 solid 方块（用于攀爬跳跃）。"""
    fx = c.cx + c.facing * (c.width_f / 2.0 + 0.1)
    x = int(math.floor(fx))
    y0 = int(math.floor(c.fy))
    y1 = int(math.floor(c.fy + c.height_f - 1e-6))
    return (_is_solid(registry, world, x, y0)
            or _is_solid(registry, world, x, y1))


# ─────────────────────────────────────────────────────────────────────────
# 状态机
# ─────────────────────────────────────────────────────────────────────────

class AIController:
    """生物 AI 状态机控制器。"""

    def decide_state(self, c, ctx) -> AIState:
        """依据玩家距离与生物种类决定目标状态。"""
        d = _dist(c, ctx.player)
        if c.kind.is_hostile():
            # 敌对：玩家进入视野 → 追击；否则静止待命。
            if d <= c.cfg.sight_range:
                return AIState.ATTACK
            return AIState.IDLE
        # 被动：玩家逼近 → 逃离；否则在 IDLE/WANDER 间周期切换。
        if d <= c.cfg.flee_range:
            return AIState.FLEE
        if c.state == AIState.WANDER:
            return AIState.IDLE
        return AIState.WANDER

    def apply(self, c, ctx, dt: float) -> None:
        """按节流计时重决策，并按当前状态设置速度意图/攀爬跳跃。"""
        c.ai_timer -= dt
        if c.ai_timer <= 0:
            c.ai_timer = c.cfg.decision_step
            new_state = self.decide_state(c, ctx)
            if new_state == AIState.WANDER:
                # 游走方向仅在决策时随机（节流，确定性靠 ctx.rng）。
                c._wander_dir = 1 if ctx.rng.random() < 0.5 else -1
            c.state = new_state

        if c.state == AIState.ATTACK:
            Pathing.step_toward(c, ctx.player.fx, ctx.player.fy,
                                ctx.world, ctx.registry)
            px, _ = _player_center(ctx.player)
            c.facing = 1 if px >= c.cx else -1
        elif c.state == AIState.FLEE:
            px, _ = _player_center(ctx.player)
            away = -1 if px >= c.cx else 1
            c.facing = away
            c.vx = away * c.cfg.move_speed
            if c.on_ground and _is_solid_ahead(c, ctx.world, ctx.registry):
                c.vy = c.cfg.jump_v
        elif c.state == AIState.WANDER:
            c.facing = c._wander_dir
            c.vx = c._wander_dir * c.cfg.move_speed
            if c.on_ground and _is_solid_ahead(c, ctx.world, ctx.registry):
                c.vy = c.cfg.jump_v
        else:  # IDLE
            c.vx = 0.0


# ─────────────────────────────────────────────────────────────────────────
# 简易寻路（R6）
# ─────────────────────────────────────────────────────────────────────────

class Pathing:
    """启发式寻路：贪心朝目标 + 遇阻跳跃攀爬。无 A*，纯确定性。"""

    @staticmethod
    def step_toward(c, tx: float, ty: float, world, registry) -> None:
        """朝目标 (tx, ty) 设置水平速度；若前方受阻且着地则起跳越障。"""
        dx = tx - c.cx
        if abs(dx) < 0.05:
            c.vx = 0.0
            return
        c.facing = 1 if dx > 0 else -1
        c.vx = c.facing * c.cfg.move_speed
        # 遇阻攀爬：前方有 solid 且着地 → 起跳（越 1 格障碍）
        if c.on_ground and _is_solid_ahead(c, world, registry):
            c.vy = c.cfg.jump_v
