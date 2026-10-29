"""ParticleBridgeSystem（priority=70）：气泡特效桥接。

🔴 禁止 `from __future__ import annotations`（E6）。
🔴 纯表现层：**绝不读写 GameState**，随机源用表现流 `WD_AI_RNG`。
   帧率不同只会让气泡多一点少一点，不会影响任何玩法数值。

🔴 E16：引擎 `ForceField` 没有"浮力"类型。水里气泡向上飘 =
   一个 strength 为**负数**的 `gravity` 力场（配置项 `fx.bubble_force = -0.35`）。

坐标系：粒子全程使用归一化坐标 [0,1]，由渲染层乘以画布尺寸。
这样窗口缩放 / 双端不同分辨率都不用改特效参数。
"""

from fishtank.constants import (
    WD_AI_RNG, WD_BALANCE, WD_DT, WD_PARTICLES, WD_TURNS,
)
from fishtank.engine_bootstrap import ForceField, Particle, ParticleSystem, System

_BUBBLE_COLOR = (210, 240, 255)
"""气泡底色（纯美术常量，不是玩法数值）。"""


class ParticleBridgeSystem(System):
    """把游戏事件翻译成引擎粒子。"""

    priority = 70

    def __init__(self, logger=None, fx_enabled=True):
        """:param fx_enabled: False 时整个系统空转（对应 `--no-fx` / 省电模式）。

        🔴 注意：属性名**必须**是 ``fx_enabled`` 而不是 ``enabled``。
        引擎 ``System`` 基类把 ``enabled`` 定义为**方法**
        （``World.update`` 里调用 ``system.enabled(world)``），
        用同名布尔属性覆盖会让整个世界 `TypeError: 'bool' object is not callable`。
        """
        self._log = logger
        self.fx_enabled = bool(fx_enabled)
        self.system = None
        self._accum = 0.0
        self._max_particles = 0
        self.spawned = 0
        """累计生成的气泡数（诊断用）。"""

    def enabled(self, world):
        """引擎钩子：关特效时让 World 直接跳过本系统，一点开销都不花。"""
        return self.fx_enabled

    # ── 初始化 ──

    def _ensure(self, world, bal):
        """惰性建立 ParticleSystem + 浮力力场。"""
        if self.system is not None:
            return self.system
        self._max_particles = max(0, int(bal.get("fx.max_particles", 60) or 0))
        ps = ParticleSystem(max_particles=max(1, self._max_particles))
        force = float(bal.get("fx.bubble_force", -0.35) or 0.0)
        # E16：负重力 = 浮力
        ps.add_force_field(ForceField("gravity", strength=force))
        self.system = ps
        world.set_data(WD_PARTICLES, ps)
        return ps

    # ── 主循环 ──

    def update(self, world, dt):
        """执行一帧特效。"""
        bal = world.get_data(WD_BALANCE)
        if bal is None:
            return
        if not self.fx_enabled:
            return
        ps = self._ensure(world, bal)
        if self._max_particles <= 0:
            return

        dt = float(world.get_data(WD_DT, dt) or 0.0)
        rng = world.get_data(WD_AI_RNG)
        if dt <= 0.0 or rng is None:
            return

        self._ambient(bal, rng, dt)
        self._turn_bubbles(world, bal, rng)
        ps.update(dt)

    # ── 生成 ──

    def _ambient(self, bal, rng, dt):
        """缸底持续冒的环境气泡。"""
        rate = float(bal.get("fx.bubble_rate", 0.8) or 0.0)
        if rate <= 0.0:
            return
        self._accum += rate * dt
        while self._accum >= 1.0:
            self._accum -= 1.0
            self._spawn(bal, rng, rng.random(), 1.0)

    def _turn_bubbles(self, world, bal, rng):
        """鱼掉头时甩出的一小串气泡。"""
        turns = world.get_data(WD_TURNS)
        if not turns:
            return
        chance = float(bal.get("fx.turn_bubble_chance", 0.25) or 0.0)
        lo, hi = self._pair(bal, "fx.turn_bubbles", 1, 3)
        for x, y in turns:
            if not rng.chance(chance):
                continue
            for _ in range(rng.randint(int(lo), int(hi))):
                self._spawn(bal, rng, x, y)

    def _spawn(self, bal, rng, x, y):
        """生成一颗气泡粒子。"""
        ps = self.system
        if ps is None or len(ps.particles) >= ps.max_particles:
            return
        life_lo, life_hi = self._pair(bal, "fx.bubble_life", 1.6, 3.2)
        size_lo, size_hi = self._pair(bal, "fx.bubble_size", 1.5, 3.5)
        life = rng.uniform(life_lo, life_hi)
        ps.particles.append(Particle(
            x=float(x), y=float(y),
            vx=0.0, vy=0.0,
            life=1.0, max_life=max(0.01, life),
            size=rng.uniform(size_lo, size_hi),
            color=_BUBBLE_COLOR,
            alpha=1.0, mass=1.0,
        ))
        self.spawned += 1

    # ── 工具 ──

    @staticmethod
    def _pair(bal, path, lo_default, hi_default):
        """读 [lo, hi] 区间配置，带容错。"""
        raw = bal.get(path)
        if isinstance(raw, (list, tuple)) and len(raw) >= 2:
            try:
                lo = float(raw[0])
                hi = float(raw[1])
            except (TypeError, ValueError):
                return lo_default, hi_default
            return (lo, hi) if lo <= hi else (hi, lo)
        return lo_default, hi_default

    # ── 供渲染层读取 ──

    def particles(self):
        """返回当前存活粒子列表（渲染层只读）。"""
        return self.system.particles if self.system is not None else []

    def clear(self):
        """清空所有粒子（切换窗口形态时用）。"""
        if self.system is not None:
            self.system.clear()
