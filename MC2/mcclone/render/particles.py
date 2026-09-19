# -*- coding: utf-8 -*-
"""particles — M6 粒子系统（整合到 allin_engine.fx.particle）。

整合说明（去「本地平行实现」为「引擎上层应用」）：
  MC2 原本自带一套轻量粒子系统（仅日志/视觉）。整合后，MC2 的粒子真正
  跑在 allin_engine 的统一粒子引擎之上：

    - 粒子存储与物理演化由 allin_engine.fx.particle.ParticleSystem 承担
      （重力力场 + 生命衰减 + 死亡回收，引擎统一实现）；
    - 单个粒子即引擎的 Particle 原语；
    - 游戏特有的 spawn 预设（挖掘碎屑/受击/死亡爆裂/脚步尘土）、
      相机坐标映射 draw、以及事件订阅，作为 MC2 玩法层叠加在引擎之上。

  对外 API 完全保持兼容（test_m6_particles / MC2 探针均零改动）：
    ParticleSystem(max_particles) / spawn_break / spawn_hit / spawn_death /
    spawn_step / update(dt) / draw(camera, renderer) / subscribe(bus, registry)，
    以及内部 _ps 列表（引擎粒子的实时视图，供测试断言）。
"""

from __future__ import annotations

import math
import random
from typing import Dict, List, Optional, Tuple

# 引擎统一粒子引擎（真正承载存储与物理演化）
from allin_engine.fx.particle import (
    Particle as _EngineParticle,
    ForceField,
    ParticleSystem as _EngineParticleSystem,
)

# 屏幕映射常量（与 camera.py / tile_world_renderer.py 共享）。
VIEW_OFFSET_X: int = 0
HUD_TOP: int = 28
TILE_SIZE: int = 32

# 调色板（与 tile_world_renderer._TILE_RGB 一致，用于方块碎屑着色）。
_TILE_RGB: Dict[str, Tuple[int, int, int]] = {
    "white": (240, 240, 240), "gray": (130, 130, 130), "brown": (134, 96, 67),
    "green": (80, 170, 70), "blue": (60, 120, 220), "yellow": (224, 200, 90),
    "black": (20, 20, 20), "red": (200, 60, 60), "magenta": (180, 80, 180),
    "cyan": (80, 200, 200), "lava": (220, 90, 30),
}


def _pygame():
    """延迟导入 pygame；不可用时抛出清晰错误。"""
    import pygame
    if pygame is None:
        raise RuntimeError("需要 pygame 才能绘制粒子")
    return pygame


# 向后兼容：保留 Particle 别名（外部极少直接使用，仅保险）。
Particle = _EngineParticle


class ParticleSystem(_EngineParticleSystem):
    """MC2 粒子系统 —— 玩法层，底层为 allin_engine.fx.particle.ParticleSystem。

    继承引擎粒子系统，复用其存储与物理演化；游戏特有的 spawn 预设、
    相机坐标 draw、事件订阅在此叠加。
    """

    def __init__(self, max_particles: int = 400) -> None:
        super().__init__(max_particles=max_particles)
        self._max = max_particles
        self._rng = random.Random(0)
        # 重力力场：y 向上，重力使 vy 减小（引擎 gravity 返回 (0, strength)，
        # strength=-18 => vy += -18*dt，与 MC2 原语义一致）。
        self.add_force_field(ForceField("gravity", strength=-18.0))

    # ── 引擎粒子的实时视图（供测试 / 兼容断言）──
    @property
    def _ps(self) -> List[_EngineParticle]:
        return self.particles

    # ── 生成 ──
    def _add(self, x: float, y: float, vx: float, vy: float,
             life: float, color: Tuple[int, int, int], size: int) -> None:
        # 超上限丢弃最旧（R3：数量爆炸保护）
        if len(self.particles) >= self._max:
            self.particles.pop(0)
        self.particles.append(_EngineParticle(
            x, y, vx=vx, vy=vy,
            life=life, max_life=life,
            size=size, color=color, alpha=1.0,
        ))

    def spawn_break(self, x: float, y: float, color: Tuple[int, int, int],
                    count: int = 8) -> None:
        for _ in range(count):
            a = self._rng.uniform(0, math.tau)
            sp = self._rng.uniform(1.0, 4.0)
            self._add(x, y, math.cos(a) * sp, abs(math.sin(a)) * sp + 2.0,
                      self._rng.uniform(0.3, 0.6), color, 3)

    def spawn_hit(self, x: float, y: float, count: int = 6) -> None:
        for _ in range(count):
            a = self._rng.uniform(0, math.tau)
            sp = self._rng.uniform(2.0, 5.0)
            self._add(x, y, math.cos(a) * sp, math.sin(a) * sp + 1.0,
                      self._rng.uniform(0.2, 0.4), (230, 60, 60), 3)

    def spawn_death(self, x: float, y: float, color: Tuple[int, int, int],
                    count: int = 16) -> None:
        for _ in range(count):
            a = self._rng.uniform(0, math.tau)
            sp = self._rng.uniform(2.0, 6.0)
            self._add(x, y, math.cos(a) * sp, abs(math.sin(a)) * sp + 2.0,
                      self._rng.uniform(0.4, 0.8), color, 4)

    def spawn_step(self, x: float, y: float, count: int = 2) -> None:
        for _ in range(count):
            self._add(x + self._rng.uniform(-0.2, 0.2), y,
                      self._rng.uniform(-0.5, 0.5), self._rng.uniform(0.5, 1.5),
                      self._rng.uniform(0.2, 0.35), (180, 160, 130), 2)

    # ── 更新（委托引擎粒子系统：重力力场 + 生命衰减 + 死亡回收）──
    def update(self, dt: float) -> None:
        super().update(dt)

    # ── 渲染（屏幕=None 时 no-op；相机视口坐标映射，复用 tile 映射）──
    def draw(self, camera, renderer) -> None:
        screen = getattr(renderer, "screen", None)
        if screen is None:
            return
        pg = _pygame()
        vp = camera.viewport
        for p in self.particles:
            px = VIEW_OFFSET_X + (p.x - vp.min_x) * TILE_SIZE
            py = HUD_TOP + (vp.max_y - p.y) * TILE_SIZE
            alpha = int(255 * max(0.0, p.life / p.max_life))
            s = pg.Surface((p.size, p.size), pg.SRCALPHA)
            s.fill((*p.color, alpha))
            screen.blit(s, (int(px), int(py)))

    # ── 事件订阅（仅带坐标事件）──
    def subscribe(self, bus, registry=None) -> None:
        if bus is None:
            return
        from mcclone.core.event_bus import EventTypes

        def on_break(event_type, d):
            self.spawn_break(d["x"] + 0.5, d["y"] + 0.5,
                             self._block_color(registry, d.get("id")))

        def on_place(event_type, d):
            self.spawn_break(d["x"] + 0.5, d["y"] + 0.5,
                             self._block_color(registry, d.get("id")), count=5)

        def on_died(event_type, d):
            self.spawn_death(d["x"], d["y"], self._kind_color(d.get("kind")))

        def on_step(event_type, d):
            self.spawn_step(d["x"], d["y"])

        bus.subscribe(EventTypes.BLOCK_BROKEN, on_break)
        bus.subscribe(EventTypes.BLOCK_PLACED, on_place)
        bus.subscribe(EventTypes.CREATURE_DIED, on_died)
        bus.subscribe(EventTypes.PLAYER_STEP, on_step)

    # ── 颜色辅助 ──
    @staticmethod
    def _block_color(registry, bid) -> Tuple[int, int, int]:
        try:
            return _TILE_RGB.get(registry.get(bid).color, (200, 200, 200))
        except Exception:
            return (200, 200, 200)

    @staticmethod
    def _kind_color(kind) -> Tuple[int, int, int]:
        return {
            "COW": (120, 200, 120),
            "PIG": (200, 150, 120),
            "ZOMBIE": (200, 80, 80),
        }.get(kind, (200, 200, 200))
