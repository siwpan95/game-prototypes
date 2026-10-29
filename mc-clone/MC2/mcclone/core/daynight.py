# -*- coding: utf-8 -*-
"""daynight — 昼夜循环（M2 生存基底）。

提供：
  - DayNight: 时间累加器 t∈[0,1)；update(dt) 推进；light_factor()（0..1）
    用于夜间 tint；is_night() 判断夜段；time_str() 返回 HUD 时钟 "HH:MM"；
    to_dict()/from_dict() 可序列化（M2-R4）。

公式（架构 §7.2）：
  - light_factor = clamp(0.5 + 0.5*cos(2π*(t-0.5)), 0, 1)
    t=0.5（正午）→ 1；t=0/1（午夜）→ 0。
  - 夜段：t<0.25 or t>=0.75。

零依赖（math），可在 headless 下断言。
"""

from __future__ import annotations

import math
from typing import Dict

from mcclone.core.geometry import clamp


# 默认一天时长（秒）；架构 §7.1 / §8 D1。
DAY_LENGTH_SEC: float = 600.0
# 2π 常量（避免重复计算）。
_TWO_PI: float = 2.0 * math.pi


class DayNight:
    """昼夜时间累加器。

    t 表示一天内的归一化进度：0=午夜，0.5=正午，趋近 1 回到午夜。
    update(dt) 按 dt/day_length_sec 累加并取模 1，与帧时序无关。
    """

    def __init__(self, day_length_sec: float = DAY_LENGTH_SEC) -> None:
        """构造。

        参数：
            day_length_sec: 一天真实秒数（默认 600 → 10 分钟/天）。
        """
        self.day_length_sec: float = float(day_length_sec)
        self._t: float = 0.0  # 归一化时间进度 [0,1)

    def update(self, dt: float) -> None:
        """推进时间。dt 为真实秒数。"""
        if dt <= 0:
            return
        self._t = (self._t + dt / self.day_length_sec) % 1.0

    def t(self) -> float:
        """返回当前归一化时间进度 [0,1)。"""
        return self._t

    def light_factor(self) -> float:
        """光照因子 ∈ [0,1]：正午 1，午夜 0。"""
        val = 0.5 + 0.5 * math.cos(_TWO_PI * (self._t - 0.5))
        return clamp(val, 0.0, 1.0)

    def is_night(self) -> bool:
        """是否处于夜段（t<0.25 或 t>=0.75）。"""
        return self._t < 0.25 or self._t >= 0.75

    def time_str(self) -> str:
        """返回 HUD 时钟字符串 "HH:MM"（基于 t*24 小时）。"""
        total_minutes = int(self._t * 24.0 * 60.0) % (24 * 60)
        hh = total_minutes // 60
        mm = total_minutes % 60
        return f"{hh:02d}:{mm:02d}"

    def to_dict(self) -> Dict:
        """序列化为 dict（M2-R4 存档）。"""
        return {"t": self._t, "day_length_sec": self.day_length_sec}

    @classmethod
    def from_dict(cls, d: Dict) -> "DayNight":
        """从 dict 还原（M2-R4 读档）。缺失字段使用默认值。"""
        day_len = float(d.get("day_length_sec", DAY_LENGTH_SEC))
        dn = cls(day_len)
        dn._t = float(d.get("t", 0.0)) % 1.0
        return dn
