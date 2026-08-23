# -*- coding: utf-8 -*-
"""creatures.entity — 生物实体 / 枚举 / 配置（M4，T-M4-01）。

提供：
  - CreatureKind: 生物种类枚举（COW/PIG 被动，ZOMBIE 敌对）。
  - AIState:      AI 状态枚举（IDLE/WANDER/FLEE/ATTACK）。
  - CreatureConfig: 生物物理/战斗数值（dataclass，默认值见架构 §7.1 / §8）。
  - Creature(AABB2D): 生物实体（float 脚底 + 轴分离碰撞状态 + kind/hp/state）。

设计要点（架构 §2.4 / §7.2 / §8）：
  - 与 Player 采用同一「float 脚底 + 整数 AABB 派生」模式（继承 geometry.AABB2D），
    保证碰撞行为一致、可 headless 断言，且**完全不触碰 player.py**。
  - 仅 z=0 层活动（与玩家一致，M3 已固化）。
  - 不依赖 pygame / 不引入全局 random（rng 由调用方注入，确定性）。
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from enum import Enum

from mcclone.core.geometry import AABB2D
from mcclone.core.block_registry import AIR


# ─────────────────────────────────────────────────────────────────────────
# 枚举
# ─────────────────────────────────────────────────────────────────────────

class CreatureKind(Enum):
    """生物种类（M4：牛/猪/僵尸）。"""

    COW = "cow"
    PIG = "pig"
    ZOMBIE = "zombie"

    def is_hostile(self) -> bool:
        """仅僵尸为敌对。"""
        return self is CreatureKind.ZOMBIE


class AIState(Enum):
    """AI 状态（可观测：读 creature.state）。"""

    IDLE = "idle"        # 静止
    WANDER = "wander"    # 随机游走
    FLEE = "flee"        # 被动逃离玩家
    ATTACK = "attack"    # 敌对追击 + 攻击


# ─────────────────────────────────────────────────────────────────────────
# 配置
# ─────────────────────────────────────────────────────────────────────────

@dataclass
class CreatureConfig:
    """生物物理 / 战斗数值（架构 §7.1 / §8 采纳默认值）。"""

    gravity: float = 30.0          # 重力（与玩家一致）
    move_speed: float = 2.5        # 移动速度（慢于玩家 6）
    jump_v: float = 12.0           # 跳跃初速（≈2–3 格，越障/攀爬）
    max_fall: float = 40.0         # 下落速度上限（防穿透）
    attack_range: float = 1.5      # 玩家近战触及半径
    attack_cooldown: float = 1.0   # 生物攻击玩家冷却（秒）
    melee_damage: float = 4.0      # 生物近战对玩家伤害（ZOMBIE 经种类表覆盖为 3.0）
    flee_range: float = 5.0        # 被动生物感知玩家并开始 flee 的距离
    sight_range: float = 8.0       # 敌对生物感知玩家并进入 ATTACK 的距离
    decision_step: float = 0.5     # AI 决策节流（秒）


# ─────────────────────────────────────────────────────────────────────────
# 跨种类数值表（架构 §7.2 / §8 O2/O4）
# ─────────────────────────────────────────────────────────────────────────

#: 各生物 HP（僵尸最硬、猪最脆）。
_KIND_HP: dict = {
    CreatureKind.COW: 10.0,
    CreatureKind.PIG: 8.0,
    CreatureKind.ZOMBIE: 20.0,
}

#: 各生物尺寸 (宽, 高)；被动 0.8×0.9，敌对 0.8×1.8。
_KIND_SIZE: dict = {
    CreatureKind.COW: (0.8, 0.9),
    CreatureKind.PIG: (0.8, 0.9),
    CreatureKind.ZOMBIE: (0.8, 1.8),
}

#: 各生物对玩家的近战伤害（仅敌对有效；O4 僵尸=3.0）。
_KIND_MELEE_DMG: dict = {
    CreatureKind.ZOMBIE: 3.0,
}


# ─────────────────────────────────────────────────────────────────────────
# 实体
# ─────────────────────────────────────────────────────────────────────────

class Creature(AABB2D):
    """生物实体（继承 geometry.AABB2D）。

    AABB2D 的 min/max 运行时存整数派生包围盒；_fx/_fy 为权威浮点脚底坐标。
    所有世界查询经 world.get(x, y, 0)（z=0 层）。
    """

    # 类级自增 id（供事件标识；不跨进程一致，仅运行期唯一）。
    _next_id: int = 1

    def __init__(self, kind, x: float, y: float,
                 cfg=None, rng=None) -> None:
        self.kind = kind
        self.cfg = cfg if cfg is not None else CreatureConfig()
        self._rng = rng if rng is not None else random.Random(0)

        w, h = _KIND_SIZE[kind]
        self.width_f: float = w
        self.height_f: float = h

        # 浮点脚底坐标（左下角为权威状态）
        self._fx = float(x)
        self._fy = float(y)

        # 物理状态
        self.vx: float = 0.0
        self.vy: float = 0.0
        self.on_ground: bool = False
        self.facing: int = 1  # 1=右, -1=左

        # 生存 / 战斗
        self.max_hp: float = _KIND_HP[kind]
        self.hp: float = self.max_hp
        self.melee_damage: float = _KIND_MELEE_DMG.get(kind, 0.0)

        # AI 状态机
        self.state = AIState.IDLE
        self.attack_cd: float = 0.0      # 攻击冷却计时
        self.ai_timer: float = 0.0       # 决策节流计时
        self._wander_dir: int = 1        # 游走方向（由 AI 设定）

        # 运行期唯一 id
        self.id: int = Creature._next_id
        Creature._next_id += 1

        super().__init__(min_x=0, min_y=0, max_x=1, max_y=2)
        self._sync_aabb()

    # ── 浮点脚底坐标访问器 ──
    @property
    def fx(self) -> float:
        """脚底浮点 x。"""
        return self._fx

    @property
    def fy(self) -> float:
        """脚底浮点 y。"""
        return self._fy

    # ── 中心（用于距离/最近判定）──
    @property
    def cx(self) -> float:
        """中心浮点 x。"""
        return self._fx + self.width_f / 2.0

    @property
    def cy(self) -> float:
        """中心浮点 y。"""
        return self._fy + self.height_f / 2.0

    # ── 坐标同步（仿 player._sync_aabb）──
    def _sync_aabb(self) -> None:
        """由浮点脚底坐标派生整数包围盒。"""
        self.min_x = int(math.floor(self._fx))
        self.min_y = int(math.floor(self._fy))
        self.max_x = self.min_x + 1
        self.max_y = int(math.floor(self._fy + self.height_f))

    # ── 生存 ──
    def take_damage(self, amount: float) -> None:
        """受到伤害（钳制 hp ≥ 0）。"""
        if amount <= 0:
            return
        self.hp = max(0.0, self.hp - amount)

    def is_alive(self) -> bool:
        """是否存活。"""
        return self.hp > 0.0

    # ── 每帧推进（委托 AIController + Physics）──
    def update(self, dt: float, world, registry, ctx) -> None:
        """固定步长更新：AI 决策/执行 + 物理碰撞。

        由 CreatureSystem 调用；ctx 提供 player/world/registry/rng/cfg/daynight。
        """
        from mcclone.creatures.ai import AIController
        from mcclone.creatures.physics import move_with_collision
        AIController().apply(self, ctx, dt)
        move_with_collision(self, world, registry, dt)
