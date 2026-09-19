"""
粒子系统核心 — Particle + Emitter + ParticleSystem + 预设效果工厂

简化的 2D 粒子系统:
    - Particle: 单个粒子 (位置/速度/生命/大小/颜色/透明度)
    - Emitter: 发射器 (频率/扩散/速度/生命/位置形状)
    - ForceField: 力场 (重力/风/吸引/噪声)
    - ParticleSystem: 粒子系统管理器

10 种开箱即用的预设效果。

从 tools/particle/core/particle.py 和 tools/particle/components/effects.py 提取并简化。
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple


# ================================================================
#  Particle — 单个粒子
# ================================================================

@dataclass
class Particle:
    """单个 2D 粒子。

    属性:
        x, y: 当前位置
        vx, vy: 速度
        life: 剩余生命 (0~1, 0=死亡)
        max_life: 最大生命值 (秒)
        size: 当前大小 (像素)
        color: RGB 颜色
        alpha: 透明度 (0~1)
        rotation: 旋转角度 (弧度)
        angular_velocity: 角速度 (弧度/秒)
        mass: 质量
        trail: 拖尾历史坐标
    """
    x: float
    y: float
    vx: float = 0.0
    vy: float = 0.0
    life: float = 1.0
    max_life: float = 1.0
    size: float = 3.0
    color: Tuple[int, int, int] = (255, 255, 255)
    alpha: float = 1.0
    rotation: float = 0.0
    angular_velocity: float = 0.0
    mass: float = 1.0
    trail_enabled: bool = False
    trail: List[Tuple[float, float]] = field(default_factory=list)
    trail_max: int = 10

    # 生命周期曲线
    color_over_life: Optional[List[Tuple[float, Tuple[int, int, int]]]] = None
    size_over_life: Optional[List[Tuple[float, float]]] = None

    def is_alive(self) -> bool:
        """是否存活。"""
        return self.life > 0.0

    def update(self, dt: float):
        """更新粒子状态。

        参数:
            dt: 时间步长 (秒)
        """
        # 位置更新
        self.x += self.vx * dt
        self.y += self.vy * dt

        # 拖尾记录
        if self.trail_enabled and self.trail_max > 0:
            self.trail.append((self.x, self.y))
            if len(self.trail) > self.trail_max:
                self.trail.pop(0)

        # 旋转
        self.rotation += self.angular_velocity * dt

        # 生命值衰减
        self.life -= dt / self.max_life

        # 透明度随生命
        self.alpha = max(0.0, min(1.0, self.life))

        # 颜色生命周期
        if self.color_over_life:
            self.color = _eval_color_curve(self.color_over_life, 1.0 - self.life)

        # 大小生命周期
        if self.size_over_life:
            self.size = _eval_curve(self.size_over_life, 1.0 - self.life)

    def enable_trail(self, length: int = 10):
        """启用拖尾。

        参数:
            length: 拖尾最大点数
        """
        self.trail_enabled = True
        self.trail_max = length
        self.trail = [(self.x, self.y)]

    def get_trail_points(self) -> List[Tuple[float, float]]:
        """获取拖尾坐标列表。"""
        pts = list(self.trail)
        pts.append((self.x, self.y))
        return pts


# ================================================================
#  ForceField — 力场
# ================================================================

class ForceField:
    """2D 力场 — 施加于粒子上的外力。

    类型:
        gravity:    重力 (向下)
        wind:       风力 (水平)
        attraction: 点吸引
        noise:      噪声扰动
        vortex:     漩涡

    使用示例:
        gravity = ForceField("gravity", strength=9.8)
        vortex = ForceField("vortex", x=400, y=300, strength=3.0)
    """

    def __init__(
        self,
        field_type: str = "gravity",
        x: float = 0.0,
        y: float = 0.0,
        strength: float = 1.0,
        noise_scale: float = 50.0,
        noise_strength: float = 1.0,
        vortex_clockwise: bool = True,
        vortex_falloff: float = 0.01,
    ):
        self.field_type = field_type
        self.x = x
        self.y = y
        self.strength = strength
        self.noise_scale = noise_scale
        self.noise_strength = noise_strength
        self.vortex_clockwise = vortex_clockwise
        self.vortex_falloff = vortex_falloff
        self._time: float = 0.0

    def update(self, dt: float):
        """更新时间。"""
        self._time += dt

    def get_force(self, particle: Particle) -> Tuple[float, float]:
        """计算粒子受到的力。

        参数:
            particle: 粒子实例

        返回:
            (fx, fy) 力分量
        """
        if self.field_type == "gravity":
            return (0.0, self.strength)
        elif self.field_type == "wind":
            return (self.strength, 0.0)
        elif self.field_type == "attraction":
            return self._force_attraction(particle)
        elif self.field_type == "noise":
            return self._force_noise(particle)
        elif self.field_type == "vortex":
            return self._force_vortex(particle)
        return (0.0, 0.0)

    def set_position(self, x: float, y: float):
        """更新力场位置。"""
        self.x = x
        self.y = y

    def _force_attraction(self, p: Particle) -> Tuple[float, float]:
        dx = self.x - p.x
        dy = self.y - p.y
        dist_sq = dx * dx + dy * dy
        if dist_sq < 1e-6:
            return (0.0, 0.0)
        dist = math.sqrt(dist_sq)
        force_mag = self.strength / (1.0 + dist * 0.01)
        return (force_mag * dx / dist, force_mag * dy / dist)

    def _force_noise(self, p: Particle) -> Tuple[float, float]:
        sx = self.noise_scale
        t = self._time
        fx = self.noise_strength * math.sin(p.x / sx + t) * math.cos(p.y / sx * 0.7)
        fy = self.noise_strength * math.cos(p.y / sx + t) * math.sin(p.x / sx * 0.7)
        return (fx, fy)

    def _force_vortex(self, p: Particle) -> Tuple[float, float]:
        dx = p.x - self.x
        dy = p.y - self.y
        dist = math.sqrt(dx * dx + dy * dy)
        if dist < 1e-6:
            return (0.0, 0.0)
        direction = 1.0 if self.vortex_clockwise else -1.0
        tx = -dy / dist
        ty = dx / dist
        falloff = math.exp(-dist * self.vortex_falloff)
        mag = self.strength * falloff * direction
        return (mag * tx, mag * ty)


# ================================================================
#  Emitter — 粒子发射器
# ================================================================

class Emitter:
    """粒子发射器 — 控制粒子的生成速率和初始属性。

    参数:
        x, y: 发射位置
        rate: 每秒发射粒子数
        spread: 发射扩散角 (弧度)
        direction: 发射方向偏移 (弧度)
        speed: 初始速度
        life: 粒子生命 (秒)
        size: 粒子大小
        color: 粒子颜色
        shape: 发射形状 ("point" / "circle")
        radius: 圆形发射半径
    """

    def __init__(
        self,
        x: float,
        y: float,
        rate: float = 10.0,
        spread: float = 0.5,
        direction: float = 0.0,
        speed: float = 1.0,
        life: float = 1.0,
        size: float = 3.0,
        color: Tuple[int, int, int] = (255, 255, 255),
        shape: str = "point",
        radius: float = 10.0,
        rotation_range: Tuple[float, float] = (0.0, 0.0),
        angular_velocity_range: Tuple[float, float] = (0.0, 0.0),
        color_over_life: Optional[List[Tuple[float, Tuple[int, int, int]]]] = None,
        size_over_life: Optional[List[Tuple[float, float]]] = None,
        trail_enabled: bool = False,
        trail_length: int = 8,
    ):
        self.x = x
        self.y = y
        self.rate = rate
        self.spread = spread
        self.direction = direction
        self.speed = speed
        self.life = life
        self.size = size
        self.color = color
        self.shape = shape
        self.radius = radius
        self.rotation_range = rotation_range
        self.angular_velocity_range = angular_velocity_range
        self.color_over_life = color_over_life
        self.size_over_life = size_over_life
        self.trail_enabled = trail_enabled
        self.trail_length = trail_length
        self._accum: float = 0.0

    def emit(self, dt: float, audio_data: Optional[Dict[str, float]] = None) -> List[Particle]:
        """发射一帧粒子。

        参数:
            dt: 时间步长
            audio_data: 音频数据 (可选, {'rms': float})

        返回:
            新粒子列表
        """
        self._accum += dt
        current_rate = self.rate

        # 音频驱动发射率
        if audio_data and "rms" in audio_data:
            current_rate *= (1.0 + audio_data["rms"] * 2.0)

        num = int(self._accum * current_rate)
        self._accum -= num / current_rate if current_rate > 0 else 0.0

        new = []
        for _ in range(num):
            px, py, vx, vy = self._sample_position()
            rot = random.uniform(*self.rotation_range)
            av = random.uniform(*self.angular_velocity_range)

            p = Particle(
                x=px, y=py, vx=vx, vy=vy,
                life=1.0, max_life=self.life,
                size=self.size, color=self.color, alpha=1.0,
                rotation=rot, angular_velocity=av,
                color_over_life=self.color_over_life,
                size_over_life=self.size_over_life,
                trail_enabled=self.trail_enabled,
                trail_max=self.trail_length,
            )
            if self.trail_enabled:
                p.enable_trail(self.trail_length)
            new.append(p)

        return new

    def _sample_position(self) -> Tuple[float, float, float, float]:
        """采样发射位置和速度。"""
        if self.shape == "circle":
            angle = random.uniform(0, 2 * math.pi)
            r = self.radius * math.sqrt(random.random())
            px = self.x + r * math.cos(angle)
            py = self.y + r * math.sin(angle)
        else:
            px, py = self.x, self.y

        spread_angle = random.uniform(-self.spread, self.spread) + self.direction
        vx = self.speed * math.cos(spread_angle)
        vy = self.speed * math.sin(spread_angle)
        return px, py, vx, vy

    def set_position(self, x: float, y: float):
        """更新发射器位置。"""
        self.x = x
        self.y = y


# ================================================================
#  ParticleSystem — 粒子系统管理器
# ================================================================

class ParticleSystem:
    """粒子系统管理器 — 统一管理发射器/力场/粒子。

    使用示例:
        system = ParticleSystem(max_particles=500)
        system.add_emitter(Emitter(400, 300, rate=30))
        system.add_force_field(ForceField("gravity", strength=5.0))

        while running:
            system.update(dt=0.016, audio_data={"rms": 0.2})
            system.render(renderer)  # renderer 需实现 render(particles) 方法
    """

    def __init__(self, max_particles: int = 1000):
        self.max_particles = max_particles
        self.particles: List[Particle] = []
        self.emitters: List[Emitter] = []
        self.force_fields: List[ForceField] = []
        self._time: float = 0.0

    # ── 组件管理 ──

    def add_emitter(self, emitter: Emitter):
        """添加发射器。"""
        self.emitters.append(emitter)

    def add_force_field(self, field: ForceField):
        """添加力场。"""
        self.force_fields.append(field)

    # ── 更新 ──

    def update(self, dt: float, audio_data: Optional[Dict[str, float]] = None):
        """更新粒子系统 — 发射 / 受力 / 运动 / 淘汰。

        参数:
            dt: 时间步长 (秒)
            audio_data: 可选音频数据
        """
        self._time += dt

        # 更新力场时间
        for ff in self.force_fields:
            ff.update(dt)

        # 发射
        for emitter in self.emitters:
            new = emitter.emit(dt, audio_data)
            for p in new:
                if len(self.particles) < self.max_particles:
                    self.particles.append(p)

        # 物理更新 + 淘汰
        alive: List[Particle] = []
        for p in self.particles:
            if not p.is_alive():
                continue

            # 力场
            for ff in self.force_fields:
                fx, fy = ff.get_force(p)
                p.vx += (fx / p.mass) * dt
                p.vy += (fy / p.mass) * dt

            p.update(dt)

            if p.is_alive():
                alive.append(p)

        self.particles = alive

    def render(self, renderer: Any):
        """使用渲染器渲染所有粒子。

        参数:
            renderer: 任何实现了 render(particles: List[Particle]) 方法的对象
        """
        if hasattr(renderer, "render"):
            renderer.render(self.particles)

    def clear(self):
        """清空所有粒子。"""
        self.particles.clear()

    @property
    def count(self) -> int:
        """当前存活粒子数。"""
        return len(self.particles)

    @property
    def time(self) -> float:
        """系统运行时间。"""
        return self._time


# ================================================================
#  颜色曲线辅助函数
# ================================================================

def _eval_curve(curve: List[Tuple[float, float]], t: float) -> float:
    """线性插值曲线值。"""
    t = max(0.0, min(1.0, t))
    if not curve:
        return 1.0
    if len(curve) == 1:
        return curve[0][1]
    if t <= curve[0][0]:
        return curve[0][1]
    if t >= curve[-1][0]:
        return curve[-1][1]
    for i in range(len(curve) - 1):
        t0, v0 = curve[i]
        t1, v1 = curve[i + 1]
        if t0 <= t <= t1:
            s = (t - t0) / (t1 - t0) if t1 > t0 else 0.0
            return v0 + (v1 - v0) * s
    return curve[-1][1]


def _eval_color_curve(curve: List[Tuple[float, Tuple[int, int, int]]], t: float) -> Tuple[int, int, int]:
    """线性插值颜色曲线值。"""
    t = max(0.0, min(1.0, t))
    if not curve:
        return (255, 255, 255)
    if len(curve) == 1:
        return curve[0][1]
    if t <= curve[0][0]:
        return curve[0][1]
    if t >= curve[-1][0]:
        return curve[-1][1]
    for i in range(len(curve) - 1):
        t0, c0 = curve[i]
        t1, c1 = curve[i + 1]
        if t0 <= t <= t1:
            s = (t - t0) / (t1 - t0) if t1 > t0 else 0.0
            return _lerp_color(c0, c1, s)
    return curve[-1][1]


def _lerp_color(c1: Tuple[int, int, int], c2: Tuple[int, int, int], t: float) -> Tuple[int, int, int]:
    """颜色线性插值。"""
    t = max(0.0, min(1.0, t))
    return (
        int(c1[0] + (c2[0] - c1[0]) * t),
        int(c1[1] + (c2[1] - c1[1]) * t),
        int(c1[2] + (c2[2] - c1[2]) * t),
    )


# ================================================================
#  预设颜色曲线
# ================================================================

_FIRE_COLORS = [
    (255, 255, 240), (255, 220, 80), (255, 160, 30),
    (255, 80, 10), (100, 30, 5),
]

_SMOKE_COLORS = [
    (80, 80, 85), (120, 120, 125), (160, 160, 165), (200, 200, 205),
]

_MAGIC_COLORS = [
    (80, 50, 180), (100, 150, 255), (180, 200, 255), (255, 255, 255),
]

_WATER_COLORS = [
    (150, 200, 255), (100, 170, 255), (200, 230, 255),
]


def _gradient(colors: List[Tuple[int, int, int]]) -> List[Tuple[float, Tuple[int, int, int]]]:
    """将颜色列表转为颜色曲线。"""
    n = len(colors)
    if n <= 1:
        return [(0.0, colors[0])]
    curve = []
    for i in range(n - 1):
        t0 = i / (n - 1)
        t1 = (i + 1) / (n - 1)
        curve.append((t0, colors[i]))
        curve.append(((t0 + t1) / 2, _lerp_color(colors[i], colors[i + 1], 0.5)))
    curve.append((1.0, colors[-1]))
    return curve


FIRE_COLOR = _gradient(_FIRE_COLORS)
SMOKE_COLOR = _gradient(_SMOKE_COLORS)
MAGIC_COLOR = _gradient(_MAGIC_COLORS)
WATER_COLOR = _gradient(_WATER_COLORS)

_EXPLOSION_SIZE = [(0.0, 0.5), (0.05, 3.0), (0.3, 1.5), (1.0, 0.0)]
_SPARK_SIZE = [(0.0, 2.0), (0.5, 1.0), (1.0, 0.0)]


# ================================================================
#  预设效果工厂函数
# ================================================================

def create_explosion(
    x: float,
    y: float,
    intensity: float = 1.0,
    color_palette: Optional[List[Tuple[int, int, int]]] = None,
) -> ParticleSystem:
    """爆炸效果 — 从中心向四周喷射粒子并下落。

    参数:
        x, y: 爆炸中心
        intensity: 强度倍数 (1.0=标准)
        color_palette: 调色板

    返回:
        配置好的 ParticleSystem
    """
    if color_palette is None:
        color_palette = [
            (255, 200, 50), (255, 120, 20), (255, 60, 10),
            (255, 255, 200), (100, 100, 100),
        ]

    system = ParticleSystem(max_particles=int(300 * intensity))

    # 主爆
    for _ in range(int(5 * intensity)):
        emitter = Emitter(
            x=x, y=y, rate=80 * intensity, spread=math.pi * 2,
            speed=random.uniform(8, 20) * intensity, life=random.uniform(0.2, 0.6),
            size=random.uniform(2, 6) * intensity,
            color=random.choice(color_palette),
            color_over_life=FIRE_COLOR, size_over_life=_EXPLOSION_SIZE,
        )
        system.add_emitter(emitter)

    # 残骸
    debris_colors = [(80, 60, 40), (120, 90, 60), (60, 50, 40)]
    for _ in range(int(3 * intensity)):
        emitter = Emitter(
            x=x, y=y, rate=30 * intensity, spread=math.pi * 0.8,
            speed=random.uniform(1, 5), life=random.uniform(0.5, 1.5),
            size=random.uniform(3, 8), color=random.choice(debris_colors),
            color_over_life=SMOKE_COLOR,
        )
        system.add_emitter(emitter)

    system.add_force_field(ForceField("gravity", strength=5.0))
    return system


def create_fire(
    x: float,
    y: float,
    width: float = 40,
    height: float = 80,
    intensity: float = 1.0,
) -> ParticleSystem:
    """火焰效果 — 从底部向上升腾的火焰。

    参数:
        x, y: 火焰底部中心
        width: 火焰宽度
        height: 火焰高度
        intensity: 强度

    返回:
        配置好的 ParticleSystem
    """
    system = ParticleSystem(max_particles=int(400 * intensity))

    fire_colors = [
        (255, 255, 150), (255, 200, 50), (255, 120, 20),
        (255, 60, 0), (180, 20, 0),
    ]

    for i in range(5):
        ly = y - (i / 5) * height * 0.6
        emitter = Emitter(
            x=x + random.uniform(-width / 4, width / 4), y=ly,
            rate=(40 - i * 5) * intensity,
            spread=math.pi * (0.3 + i * 0.15),
            speed=(3 + i * 2) * intensity,
            life=random.uniform(0.3, 0.9 - i * 0.08),
            size=(4 - i * 0.5) * intensity,
            color=fire_colors[min(i, len(fire_colors) - 1)],
            color_over_life=FIRE_COLOR,
        )
        system.add_emitter(emitter)

    system.add_force_field(ForceField("gravity", strength=-2.0))
    return system


def create_rain(
    width: int,
    height: int,
    density: float = 1.0,
    wind: float = 0.0,
    color: Tuple[int, int, int] = (150, 180, 255),
) -> ParticleSystem:
    """雨效果 — 屏幕顶部均匀降落的雨滴。

    参数:
        width, height: 场景尺寸
        density: 密度倍数
        wind: 风力 (负=左)
        color: 雨滴颜色

    返回:
        配置好的 ParticleSystem
    """
    system = ParticleSystem(max_particles=int(500 * density))

    num_sources = max(5, int(width / 80))
    for i in range(num_sources):
        emitter = Emitter(
            x=(i + 0.5) * width / num_sources + random.uniform(-20, 20),
            y=0, rate=30 * density, spread=0.1,
            speed=random.uniform(15, 25), life=height / 18,
            size=random.uniform(1, 2), color=color,
            rotation_range=(0.0, 2 * math.pi),
            angular_velocity_range=(-2.0, 2.0),
        )
        system.add_emitter(emitter)

    system.add_force_field(ForceField("gravity", strength=20.0))
    if wind != 0:
        system.add_force_field(ForceField("wind", strength=wind))
    return system


def create_snow(
    width: int,
    height: int,
    density: float = 0.5,
    wind: float = 0.0,
) -> ParticleSystem:
    """雪效果 — 缓缓飘落的雪花。

    参数:
        width, height: 场景尺寸
        density: 密度倍数
        wind: 基础风力

    返回:
        配置好的 ParticleSystem
    """
    system = ParticleSystem(max_particles=int(300 * density))
    snow_colors = [(255, 255, 255), (230, 240, 255), (200, 220, 255)]

    num_sources = max(5, int(width / 100))
    for i in range(num_sources):
        emitter = Emitter(
            x=(i + 0.5) * width / num_sources + random.uniform(-30, 30),
            y=0, rate=8 * density, spread=math.pi * 0.3,
            speed=random.uniform(0.8, 2.5), life=height / 2.5,
            size=random.uniform(1.5, 4.5), color=random.choice(snow_colors),
            rotation_range=(0.0, 2 * math.pi),
            angular_velocity_range=(-0.8, 0.8),
        )
        system.add_emitter(emitter)

    system.add_force_field(ForceField("gravity", strength=1.5))
    if abs(wind) > 0.01:
        system.add_force_field(ForceField("wind", strength=wind))
    return system


def create_fountain(
    x: float,
    y: float,
    height: float = 120,
    spread: float = 0.4,
) -> ParticleSystem:
    """喷泉效果 — 从底部喷出后抛物线下落。

    参数:
        x, y: 喷口位置
        height: 最大喷射高度
        spread: 扩散角度

    返回:
        配置好的 ParticleSystem
    """
    system = ParticleSystem(max_particles=600)

    water = [
        (150, 200, 255), (100, 170, 255), (200, 230, 255),
    ]

    main = Emitter(
        x=x, y=y, rate=60, spread=spread, speed=height / 10,
        life=2.0, size=2.5, color=water[0], color_over_life=WATER_COLOR,
    )
    system.add_emitter(main)

    for side in [-1, 1]:
        splash = Emitter(
            x=x + side * 10, y=y - height * 0.35, rate=25,
            spread=math.pi * (0.4 + random.uniform(0, 0.3)),
            speed=random.uniform(2, 6), life=random.uniform(0.5, 1.2),
            size=random.uniform(1, 3), color=random.choice(water),
        )
        system.add_emitter(splash)

    system.add_force_field(ForceField("gravity", strength=8.0))
    return system


def create_smoke(
    x: float,
    y: float,
    direction: str = "up",
    density: float = 1.0,
) -> ParticleSystem:
    """烟雾效果 — 缓慢扩散逐渐消散。

    参数:
        x, y: 烟源位置
        direction: 方向 ("up" / "left" / "right" / "down")
        density: 密度

    返回:
        配置好的 ParticleSystem
    """
    system = ParticleSystem(max_particles=int(250 * density))

    smoke_colors = [
        (80, 80, 85), (110, 110, 115), (140, 140, 145), (160, 155, 150),
    ]

    dir_map = {
        "up":    (-math.pi / 2, 0.0, -1.5),
        "down":  (math.pi / 2, 0.0, 1.5),
        "left":  (math.pi, -0.8, 0.0),
        "right": (0.0, 0.8, 0.0),
    }
    base_angle, wind_x, gravity_y = dir_map.get(direction, dir_map["up"])

    for _ in range(3):
        emitter = Emitter(
            x=x + random.uniform(-5, 5), y=y + random.uniform(-5, 5),
            rate=15 * density, spread=math.pi * 0.4,
            speed=random.uniform(0.5, 2), life=random.uniform(1.5, 3.5),
            size=random.uniform(4, 12), color=random.choice(smoke_colors),
            color_over_life=SMOKE_COLOR,
            rotation_range=(0.0, 2 * math.pi),
            angular_velocity_range=(-1.0, 1.0),
        )
        system.add_emitter(emitter)

    system.add_force_field(ForceField("gravity", strength=gravity_y))
    if abs(wind_x) > 0.01:
        system.add_force_field(ForceField("wind", strength=wind_x))
    return system


def create_sparkle(
    x: float,
    y: float,
    area_size: float = 60,
    intensity: float = 1.0,
) -> ParticleSystem:
    """星光闪烁 — 区域内随机闪现的光点。

    参数:
        x, y: 中心位置
        area_size: 区域大小
        intensity: 强度

    返回:
        配置好的 ParticleSystem
    """
    system = ParticleSystem(max_particles=int(100 * intensity))
    spark_colors = [
        (255, 255, 220), (255, 240, 180), (220, 230, 255), (255, 200, 220),
    ]

    for _ in range(int(8 * intensity)):
        px = x + random.uniform(-area_size / 2, area_size / 2)
        py = y + random.uniform(-area_size / 2, area_size / 2)
        emitter = Emitter(
            x=px, y=py, rate=random.uniform(2, 8), spread=math.pi * 2,
            speed=random.uniform(0.2, 1.0), life=random.uniform(0.2, 0.6),
            size=random.uniform(1, 3), color=random.choice(spark_colors),
            size_over_life=_SPARK_SIZE,
        )
        system.add_emitter(emitter)

    return system


def create_magic_circle(
    x: float,
    y: float,
    radius: float = 80,
    rotation_speed: float = 1.0,
    color: Tuple[int, int, int] = (100, 150, 255),
) -> ParticleSystem:
    """魔法光环 — 粒子沿圆形轨道旋转。

    参数:
        x, y: 圆心
        radius: 光环半径
        rotation_speed: 旋转速度
        color: 主颜色

    返回:
        配置好的 ParticleSystem
    """
    system = ParticleSystem(max_particles=500)
    inner = (200, 220, 255)

    for ring in range(3):
        r = radius * (0.6 + ring * 0.25)
        num = int(12 + ring * 8)
        for _ in range(num):
            angle = random.uniform(0, 2 * math.pi)
            px = x + r * math.cos(angle)
            py = y + r * math.sin(angle)
            emitter = Emitter(
                x=px, y=py, rate=3, spread=math.pi * 0.3,
                speed=rotation_speed * (2 + ring),
                life=random.uniform(0.5, 1.5), size=random.uniform(1.5, 3.5),
                color=_lerp_color(inner, color, ring / 2),
                color_over_life=MAGIC_COLOR,
                rotation_range=(0.0, 2 * math.pi),
                angular_velocity_range=(-0.5, 0.5),
            )
            system.add_emitter(emitter)

    system.add_force_field(ForceField("attraction", x=x, y=y, strength=0.8))
    return system


def create_trail(
    x: float,
    y: float,
    direction_x: float = 1.0,
    direction_y: float = 0.0,
    color: Tuple[int, int, int] = (255, 200, 100),
    length: float = 1.0,
) -> ParticleSystem:
    """尾迹效果 — 移动物体留下的拖尾粒子。

    参数:
        x, y: 起点
        direction_x, direction_y: 运动方向
        color: 尾迹颜色
        length: 长度倍数

    返回:
        配置好的 ParticleSystem（可用 emitter.set_position() 追踪移动）
    """
    system = ParticleSystem(max_particles=int(200 * length))
    base_angle = math.atan2(direction_y, direction_x)
    emit_angle = base_angle + math.pi  # 反向发射

    emitter = Emitter(
        x=x, y=y, rate=40 * length, direction=emit_angle,
        spread=math.pi * 0.4, speed=random.uniform(0.5, 2),
        life=random.uniform(0.2, 0.6) * length,
        size=random.uniform(1, 4), color=color,
    )
    system.add_emitter(emitter)
    return system


def create_vortex(
    x: float = 400,
    y: float = 300,
    radius: float = 80,
    strength: float = 4.0,
    particle_count: int = 200,
) -> ParticleSystem:
    """漩涡特效 — 粒子围绕中心旋转上升。

    参数:
        x, y: 漩涡中心
        radius: 半径
        strength: 漩涡力度
        particle_count: 粒子数

    返回:
        配置好的 ParticleSystem
    """
    system = ParticleSystem(max_particles=particle_count)

    colors = [(150, 180, 220), (180, 200, 230), (200, 220, 240)]
    emitter = Emitter(
        x=x, y=y, rate=60, spread=math.pi * 2,
        speed=random.uniform(1, 3), life=random.uniform(1.5, 3.5),
        size=random.uniform(2, 5), color=random.choice(colors),
        shape="circle", radius=radius,
        trail_enabled=True, trail_length=12,
        rotation_range=(0, math.pi * 2),
        angular_velocity_range=(-3, 3),
    )
    system.add_emitter(emitter)

    system.add_force_field(ForceField(
        "vortex", x=x, y=y - radius * 0.3,
        strength=strength, vortex_clockwise=True,
    ))
    system.add_force_field(ForceField("gravity", strength=-1.5))
    return system
