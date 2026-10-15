# -*- coding: utf-8 -*-
"""天气：确定性天气状态机（纯逻辑，零 GL）。

## 口径：天气**由时间 + 种子**决定，不随机、不进存档

与 `sun.py` 的昼夜同一套纪律：天气是**世界时刻的函数**（`f(day_time, seed)`），
所以同一时刻两次查询结果相同、回放能对上、**存档不需要存天气**
（读档后按那一刻的时刻重算即可 —— 与光照/水流同口径）。

## 三种天气与它们的实际影响

| 天气 | 判据 | 影响 |
| --- | --- | --- |
| 晴 `clear` | 强度 < 0.15 | 天光满档 |
| 雨 `rain` | 强度 ≥ 0.15 且 `is_snow_phase` 为假 | **天光 ×0.72**、能见度变差 |
| 雪 `snow` | 强度 ≥ 0.15 且 `is_snow_phase` 为真 | **天光 ×0.80**（比雨亮） |

"下雪还是下雨"由**温度带**决定：夜里（`day_factor` 低）下雪、白天下雨 ——
这是 MC 的直觉口径，也不需要额外的温度系统。

切换节奏：一段天气持续 `WEATHER_SLOT`（默认 90s），段内强度按
`sin` 平滑起落（**不突变**，免得天光跳变看起来像 bug）。
"""
from __future__ import annotations

import math

__all__ = ['WeatherCycle', 'WEATHER_SLOT', 'CLEAR', 'RAIN', 'SNOW',
           'WEATHER_NAMES', 'describe_weather', 'weather_light_scale']

#: 一段天气持续多久（秒）
WEATHER_SLOT = 90.0

CLEAR = 'clear'
RAIN = 'rain'
SNOW = 'snow'

#: 天气中文名（HUD 用）
WEATHER_NAMES = {CLEAR: '晴', RAIN: '雨', SNOW: '雪'}


def describe_weather(kind: str) -> str:
    return WEATHER_NAMES.get(kind, kind)


def weather_light_scale(kind: str, intensity: float) -> float:
    """天气对**天光强度的乘子**（1.0 = 不影响）。

    雨天压到 0.72：够明显（"下雨天光照变暗"是玩家能直接看出来的），
    但不压到看不清路（`light_scale` 已经有 0.10 的地板）。
    """
    if kind == RAIN:
        return 1.0 - 0.28 * max(0.0, min(1.0, intensity))
    if kind == SNOW:
        return 1.0 - 0.20 * max(0.0, min(1.0, intensity))
    return 1.0


class WeatherCycle:
    """天气的确定性状态机（不可变风格：所有查询都是纯函数）。"""

    __slots__ = ('seed', 'slot', 'paused')

    def __init__(self, seed: int, slot: float = WEATHER_SLOT):
        self.seed = int(seed)
        self.slot = float(slot)
        #: 冻结天气（配置口，判据用 —— 与 `cycle.paused` 同一套理由）
        self.paused = False

    # ------------------------------------------------------------ 强度
    def intensity_at(self, t: float) -> float:
        """某一时刻的天气强度 0..1（**分段 + 平滑起落**）。"""
        if self.slot <= 0.0:
            return 0.0
        i = int(math.floor(t / self.slot))
        # 确定性伪随机（不用 random/hash —— hash 带随机盐）
        h = (i * 2654435761 + self.seed * 40503) & 0x7FFFFFFF
        base = (h % 1000) / 1000.0
        if base < 0.45:
            return 0.0                                   # 约 45% 的时段是晴天
        # 段内强度：前 15% 上升、后 15% 下降（不突变 ⇒ 天光不会跳变）
        local = (t / self.slot) - i
        if local < 0.15:
            shape = local / 0.15
        elif local > 0.85:
            shape = (1.0 - local) / 0.15
        else:
            shape = 1.0
        return max(0.0, min(1.0, (base - 0.45) / 0.55) * shape)

    # ------------------------------------------------------------ 查询
    def kind_at(self, t: float, *, day_factor: float = 1.0) -> str:
        """某一时刻的天气种类。

        `day_factor` 决定下雪还是下雨：**夜里（暗）下雪、白天下雨**。
        """
        s = self.intensity_at(t)
        if s < 0.15:
            return CLEAR
        return SNOW if day_factor < 0.45 else RAIN

    def state_at(self, t: float, *, day_factor: float = 1.0) -> dict:
        """给渲染/ HUD 用的一行快照。"""
        kind = self.kind_at(t, day_factor=day_factor)
        inten = self.intensity_at(t)
        return {'kind': kind, 'name': describe_weather(kind), 'intensity': inten,
                'light_scale': weather_light_scale(kind, inten)}

    # ------------------------------------------------------------ 推进
    def advance(self, dt: float) -> None:
        """**无状态**：天气不需要推进（它是时刻的纯函数）。

        保留这个方法是给内核一个与其他循环一致的接口 —— 免得调用方
        以为"不推进就不变"（而 `sun.py` 那边是真的在推进）。
        """
        return None

    def dump(self) -> dict:
        return {'seed': self.seed, 'slot': self.slot, 'paused': self.paused}
