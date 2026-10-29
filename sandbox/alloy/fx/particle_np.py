"""粒子 numpy 后端 — 补齐 "粒子为纯 Python 列表" 性能短板。

NumpyParticleSystem 对齐引擎 ParticleSystem 的核心 API（add_emitter /
add_force_field / update / count / clear），但用 numpy 数组向量化物理更新，
在高粒子数下甩开纯 Python 列表的解释器开销。

说明：聚焦物理吞吐，颜色 / 大小用基值 + 生命透明度衰减（引擎的 color_over_life /
size_over_life 生命曲线可在此之上叠加，本模块不内置以保向量化纯粹）。

依赖 numpy（可选）。若运行环境无 numpy，导入本模块会抛 ImportError，
调用方应改用 fx.particle.ParticleSystem 纯 Python 后端。
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional

import numpy as np

from alloy.fx.particle import Emitter, ForceField


class NumpyParticleSystem:
    """向量化粒子系统。"""

    def __init__(self, max_particles: int = 100_000):
        self.max_particles = int(max_particles)
        self.capacity = self.max_particles
        self.emitters: List[Emitter] = []
        self.force_fields: List[ForceField] = []
        self._time: float = 0.0
        self._n: int = 0  # 活跃粒子数（紧凑存于数组前部）

        C = self.capacity
        self.x = np.zeros(C, dtype=np.float64)
        self.y = np.zeros(C, dtype=np.float64)
        self.vx = np.zeros(C, dtype=np.float64)
        self.vy = np.zeros(C, dtype=np.float64)
        self.life = np.zeros(C, dtype=np.float64)
        self.max_life = np.ones(C, dtype=np.float64)
        self.mass = np.ones(C, dtype=np.float64)
        self.size = np.full(C, 3.0, dtype=np.float64)
        self.alpha = np.zeros(C, dtype=np.float64)
        self.color = np.zeros((C, 3), dtype=np.float64)  # 0-255
        self._rng = np.random.default_rng()

    # ── 组件管理 ──
    def add_emitter(self, emitter: Emitter) -> None:
        self.emitters.append(emitter)

    def add_force_field(self, field: ForceField) -> None:
        self.force_fields.append(field)

    # ── 发射（向量化）──
    def _emit(self, dt: float, audio_data: Optional[Dict[str, float]]) -> None:
        rms = 0.0
        if audio_data and "rms" in audio_data:
            rms = audio_data["rms"]
        for em in self.emitters:
            em._accum += dt
            rate = em.rate * (1.0 + rms * 2.0)
            if rate <= 0:
                continue
            num = int(em._accum * rate)
            if num <= 0:
                continue
            em._accum -= num / rate
            if self._n + num > self.capacity:
                num = self.capacity - self._n
                if num <= 0:
                    return
            idx = slice(self._n, self._n + num)
            if em.shape == "circle":
                ang = self._rng.uniform(0.0, 2.0 * math.pi, num)
                rad = em.radius * np.sqrt(self._rng.random(num))
                px = em.x + rad * np.cos(ang)
                py = em.y + rad * np.sin(ang)
            else:
                px = np.full(num, em.x, dtype=np.float64)
                py = np.full(num, em.y, dtype=np.float64)
            spread = self._rng.uniform(-em.spread, em.spread, num) + em.direction
            sp = em.speed
            vx = sp * np.cos(spread)
            vy = sp * np.sin(spread)
            self.x[idx] = px
            self.y[idx] = py
            self.vx[idx] = vx
            self.vy[idx] = vy
            self.life[idx] = 1.0
            self.max_life[idx] = em.life
            self.mass[idx] = 1.0
            self.size[idx] = em.size
            self.alpha[idx] = 1.0
            col = np.asarray(em.color, dtype=np.float64)
            self.color[idx] = col[None, :]
            self._n += num

    # ── 力场（向量化）──
    def _apply_forces(self, dt: float) -> None:
        if self._n == 0:
            return
        n = self._n
        ax = np.zeros(n, dtype=np.float64)
        ay = np.zeros(n, dtype=np.float64)
        for ff in self.force_fields:
            ff.update(dt)
            t = ff._time
            if ff.field_type == "gravity":
                ay += ff.strength
            elif ff.field_type == "wind":
                ax += ff.strength
            elif ff.field_type == "attraction":
                dx = ff.x - self.x[:n]
                dy = ff.y - self.y[:n]
                d2 = np.maximum(dx * dx + dy * dy, 1e-9)
                d = np.sqrt(d2)
                mag = ff.strength / (1.0 + d * 0.01)
                ax += mag * dx / d
                ay += mag * dy / d
            elif ff.field_type == "noise":
                sx = ff.noise_scale
                ax += ff.noise_strength * np.sin(self.x[:n] / sx + t) * np.cos(self.y[:n] / sx * 0.7)
                ay += ff.noise_strength * np.cos(self.y[:n] / sx + t) * np.sin(self.x[:n] / sx * 0.7)
            elif ff.field_type == "vortex":
                dx = self.x[:n] - ff.x
                dy = self.y[:n] - ff.y
                d2 = np.maximum(dx * dx + dy * dy, 1e-9)
                d = np.sqrt(d2)
                tx = -dy / d
                ty = dx / d
                falloff = np.exp(-d * ff.vortex_falloff)
                direction = 1.0 if ff.vortex_clockwise else -1.0
                mag = ff.strength * falloff * direction
                ax += mag * tx
                ay += mag * ty
        inv_m = 1.0 / np.maximum(self.mass[:n], 1e-9)
        self.vx[:n] += ax * inv_m * dt
        self.vy[:n] += ay * inv_m * dt

    # ── 更新 ──
    def update(self, dt: float, audio_data: Optional[Dict[str, float]] = None) -> None:
        self._time += dt
        self._emit(dt, audio_data)
        self._apply_forces(dt)
        if self._n == 0:
            return
        n = self._n
        self.x[:n] += self.vx[:n] * dt
        self.y[:n] += self.vy[:n] * dt
        self.life[:n] -= dt / np.maximum(self.max_life[:n], 1e-9)
        self.alpha[:n] = np.clip(self.life[:n], 0.0, 1.0)
        # 淘汰 + 紧凑
        alive = self.life[:n] > 0.0
        if not bool(alive.all()):
            n_alive = int(alive.sum())
            self.x[:n_alive] = self.x[:n][alive]
            self.y[:n_alive] = self.y[:n][alive]
            self.vx[:n_alive] = self.vx[:n][alive]
            self.vy[:n_alive] = self.vy[:n][alive]
            self.life[:n_alive] = self.life[:n][alive]
            self.max_life[:n_alive] = self.max_life[:n][alive]
            self.mass[:n_alive] = self.mass[:n][alive]
            self.size[:n_alive] = self.size[:n][alive]
            self.alpha[:n_alive] = self.alpha[:n][alive]
            self.color[:n_alive] = self.color[:n][alive]
            self._n = n_alive

    def clear(self) -> None:
        self._n = 0

    @property
    def count(self) -> int:
        return self._n

    @property
    def time(self) -> float:
        return self._time

    def numpy_state(self) -> Dict[str, Any]:
        """返回当前活跃粒子的 numpy 视图（渲染用）。"""
        n = self._n
        return {
            "x": self.x[:n], "y": self.y[:n],
            "vx": self.vx[:n], "vy": self.vy[:n],
            "life": self.life[:n], "size": self.size[:n],
            "alpha": self.alpha[:n], "color": self.color[:n],
        }

    def to_particles(self):
        """物化回引擎 Particle 列表（仅逐粒子渲染 / 调试时调用，非热路径）。"""
        from alloy.fx.particle import Particle

        out = []
        for i in range(self._n):
            out.append(Particle(
                x=float(self.x[i]), y=float(self.y[i]),
                vx=float(self.vx[i]), vy=float(self.vy[i]),
                life=float(self.life[i]), max_life=float(self.max_life[i]),
                size=float(self.size[i]),
                color=(int(self.color[i][0]), int(self.color[i][1]), int(self.color[i][2])),
                alpha=float(self.alpha[i]),
            ))
        return out

    def render(self, renderer: Any) -> None:
        if hasattr(renderer, "render"):
            renderer.render(self.to_particles())
