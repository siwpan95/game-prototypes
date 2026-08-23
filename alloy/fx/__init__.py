"""
alloy.fx — 粒子特效子包

提供:
  - Particle / Emitter / ParticleSystem: 粒子系统核心
  - ForceField: 力场 (gravity/wind/attraction/noise/vortex)
  - 预设效果工厂:
    - create_explosion:  爆炸效果
    - create_fire:      火焰效果
    - create_rain:      雨效果
    - create_snow:      雪效果
    - create_fountain:  喷泉效果
    - create_smoke:     烟雾效果
    - create_sparkle:   星光闪烁
    - create_magic_circle: 魔法光环
    - create_trail:     尾迹效果
    - create_vortex:    漩涡特效

从 tools/particle/ 提取并简化。
"""

from alloy.fx.particle import (
    Particle, Emitter, ForceField, ParticleSystem,
    create_explosion, create_fire, create_rain, create_snow,
    create_fountain, create_smoke, create_sparkle,
    create_magic_circle, create_trail, create_vortex,
)

# 向量化粒子后端（可选，依赖 numpy）。无 numpy 时为 None，核心 fx 仍可导入。
try:
    from alloy.fx.particle_np import NumpyParticleSystem
except ImportError:
    NumpyParticleSystem = None  # type: ignore

__all__ = [
    "Particle", "Emitter", "ForceField", "ParticleSystem",
    "NumpyParticleSystem",
    "create_explosion", "create_fire", "create_rain", "create_snow",
    "create_fountain", "create_smoke", "create_sparkle",
    "create_magic_circle", "create_trail", "create_vortex",
]
