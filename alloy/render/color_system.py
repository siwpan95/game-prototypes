"""
颜色系统 — 声明式颜色生成器

支持的类型:
    solid     — 固定颜色 [r, g, b] 或 #RRGGBB
    hsv_flow  — HSV 流动渐变（按元素和时间分配色相）
    energy    — 音频能量映射颜色
    rainbow   — 彩虹循环色

从 pywallpaper/engine/color_system.py 提取并独立化。
"""

from __future__ import annotations

import math
from abc import ABC, abstractmethod
from typing import Tuple


# ================================================================
#  HSV ↔ RGB 转换（独立实现，零外部依赖）
# ================================================================

def hsv_to_rgb(h: float, s: float, v: float) -> Tuple[int, int, int]:
    """HSV 转 RGB。

    参数:
        h: 色相 (0~1 或 0~360)
        s: 饱和度 (0~1)
        v: 明度 (0~1)

    返回:
        (r, g, b) 各分量 0~255
    """
    # 归一化色相到 0~1
    h = (h % max(h + 1, 360))
    if h > 1.0:
        h = h / 360.0
    h = h % 1.0

    s = max(0.0, min(1.0, s))
    v = max(0.0, min(1.0, v))

    if s == 0:
        c = int(v * 255)
        return (c, c, c)

    h6 = h * 6.0
    i = int(h6)
    f = h6 - i
    p = v * (1.0 - s)
    q = v * (1.0 - s * f)
    t = v * (1.0 - s * (1.0 - f))

    mapping = {
        0: (v, t, p),
        1: (q, v, p),
        2: (p, v, t),
        3: (p, q, v),
        4: (t, p, v),
        5: (v, p, q),
    }
    r, g, b = mapping[i % 6]
    return (int(r * 255), int(g * 255), int(b * 255))


def get_energy_color(energy: float, hue_offset: float = 0.0) -> Tuple[int, int, int]:
    """根据音频能量级别映射颜色。

    低能量 → 蓝紫，高能量 → 红橙。

    参数:
        energy: 能量值 (0~1)
        hue_offset: 色相偏移 (0~1)

    返回:
        (r, g, b)
    """
    energy = max(0.0, min(1.0, energy))
    hue = (0.65 - energy * 0.65 + hue_offset) % 1.0  # 蓝→红
    sat = 0.7 + energy * 0.3
    val = 0.5 + energy * 0.5
    return hsv_to_rgb(hue, sat, val)


# ================================================================
#  ColorGenerator 基类 + 四种策略
# ================================================================

class ColorGenerator(ABC):
    """颜色生成器抽象基类。

    子类实现 get_color() 返回 (r, g, b) 元组。
    """

    @abstractmethod
    def get_color(self, index: int, total: int, time: float, energy: float = 0.0) -> Tuple[int, int, int]:
        """返回 (r, g, b) 元组。

        参数:
            index: 当前元素索引
            total: 总元素数
            time: 全局时间 (秒)
            energy: 音频能量 (0~1)
        """
        raise NotImplementedError

    @staticmethod
    def create(config: dict | None) -> "ColorGenerator":
        """从配置字典创建颜色生成器。

        配置格式:
            {'type': 'solid', 'value': [255, 0, 0]} 或 '#FF0000'
            {'type': 'hsv_flow', 'hue': [0, 0.7], 'speed': 0.1, 'sat': 0.8, 'val': 0.9}
            {'type': 'energy', 'hue_offset': 0.0}
            {'type': 'rainbow', 'speed': 0.05, 'sat': 0.8, 'val': 0.9}

        参数:
            config: 配置字典，None 或空则返回默认 HSVFlowColor

        返回:
            ColorGenerator 子类实例
        """
        if not config or not isinstance(config, dict):
            return HSVFlowColor({})
        t = config.get("type", "hsv_flow")
        if t == "solid":
            return SolidColor(config)
        elif t == "hsv_flow":
            return HSVFlowColor(config)
        elif t == "energy":
            return EnergyColor(config)
        elif t == "rainbow":
            return RainbowColor(config)
        else:
            return HSVFlowColor({})


class SolidColor(ColorGenerator):
    """固定颜色 — 始终返回同一颜色。

    配置:
        value: [r, g, b] 或 '#RRGGBB'
    """

    def __init__(self, config: dict):
        val = config.get("value", [255, 255, 255])
        if isinstance(val, str) and val.startswith("#"):
            val = val.lstrip("#")
            self.color: Tuple[int, int, int] = tuple(int(val[i:i + 2], 16) for i in (0, 2, 4))
        elif isinstance(val, (list, tuple)):
            self.color = tuple(int(c) for c in val[:3])
        else:
            self.color = (255, 255, 255)

    def get_color(self, index: int = 0, total: int = 1, time: float = 0.0, energy: float = 0.0) -> Tuple[int, int, int]:
        return self.color


class HSVFlowColor(ColorGenerator):
    """HSV 流动渐变 — 色相在元素间和时间上流动。

    配置:
        hue / hue_range: [min, max]  色相范围 (0~1 或 0~360)
        speed / color_speed: float   时间流动速度
        sat / saturation: float      饱和度 (0~1)
        val / value: float            明度 (0~1)
    """

    def __init__(self, config: dict):
        hue_range = config.get("hue", config.get("hue_range", [0, 0.7]))
        self.hue_min: float = min(hue_range[0], hue_range[1])
        self.hue_max: float = max(hue_range[0], hue_range[1])
        self.speed: float = config.get("speed", config.get("color_speed", 0.1))
        self.sat: float = config.get("sat", config.get("saturation", 0.8))
        self.val: float = config.get("val", config.get("value", 0.9))

    def get_color(self, index: int = 0, total: int = 1, time: float = 0.0, energy: float = 0.0) -> Tuple[int, int, int]:
        frac = index / max(total, 1)
        hue = (frac * (self.hue_max - self.hue_min) + self.hue_min + time * self.speed) % 1.0
        return hsv_to_rgb(hue, self.sat, self.val)


class EnergyColor(ColorGenerator):
    """能量颜色 — 根据音频能量级别映射颜色。

    配置:
        hue_offset: float  色相偏移
    """

    def __init__(self, config: dict):
        self.hue_offset: float = config.get("hue_offset", 0.0)

    def get_color(self, index: int = 0, total: int = 1, time: float = 0.0, energy: float = 0.0) -> Tuple[int, int, int]:
        return get_energy_color(energy, self.hue_offset)


class RainbowColor(ColorGenerator):
    """彩虹色 — 色相循环，所有元素共享同一动态色相。

    配置:
        speed: float  色相循环速度
        sat: float    饱和度
        val: float     明度
    """

    def __init__(self, config: dict):
        self.speed: float = config.get("speed", 0.05)
        self.sat: float = config.get("sat", 0.8)
        self.val: float = config.get("val", 0.9)

    def get_color(self, index: int = 0, total: int = 1, time: float = 0.0, energy: float = 0.0) -> Tuple[int, int, int]:
        hue = (time * self.speed) % 1.0
        return hsv_to_rgb(hue, self.sat, self.val)
