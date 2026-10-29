# -*- coding: utf-8 -*-
"""昼夜循环：把"现在是几点、天多亮"收敛成**一个纯函数**。

## 为什么单独成模块

昼夜有两个消费者，且它们的口径**必须一致**：

* **光照**（`light.py`）要一个 `day_factor` ∈ [0,1] 决定天光能照多亮；
* **渲染**（demo）要天空色、地平线色、太阳方向、星空强度。

两边各写一份"几点算白天"就必然漂（一个说 0.3、一个说 0.35，白天长度就不一样）。
所以口径只有一处：`sky_at(time)`。

## 与引擎的关系

引擎 `world3d.logic.blocks.sky_state(phase)` 已经算好了**天空颜色 / 太阳方向 / ambient /
星空**（Phase 0 的 `minecraft_style` 用它做过五幕短片）。本模块**不复写那套配色**，
而是负责：

1. 维护"世界时刻"（秒 → 相位），并**可存档**；
2. 在引擎状态之上，补本项目要的两件事：**`day_factor`（给光照用）** 与
   **`sun_axis()`（给 DDA 方向性用）**；
3. 提供 `describe(time)` 给人看（"日出/正午/黄昏/午夜"）。

## 相位约定（与引擎一致）

`phase = 0` 日出、`0.25` 正午、`0.5` 日落、`0.75` 午夜 —— 直接沿用引擎那套，
免得两处约定不同。
"""
from __future__ import annotations

import math

from ._engine import blocks as _b   # 引擎侧：sky_state / DAY 配色都在这里

__all__ = ['DAY_LENGTH', 'START_PHASE', 'phase_of', 'sky_at', 'day_factor',
           'day_factor_from_sun', 'sun_axis', 'describe', 'phase_name',
           'PHASE_BANDS', 'DayCycle', 'NIGHT_FLOOR']

#: 一昼夜的现实秒数（与 MC 的 20 分钟不同：本版给个更适合演示的短周期）
DAY_LENGTH = 600.0

#: 开局相位（0.08 ≈ 清晨刚过日出，光照充足、天色好看）
START_PHASE = 0.08

#: 夜间天光地板（0 = 全黑）。取值依据：地面顶点色在最暗处仍需"看得清轮廓"，
#: 而 `mesh.light_scale` 还有一层自己的地板 —— 两者相乘才是屏幕上的亮度。
NIGHT_FLOOR = 0.18

#: 相位 → 时段名（**按区间**判定，不是"取最后一个小于它的阈值"）
#: 先前写成"从低到高扫、取最后一个 p >= 阈值"，于是相位 0.0 会落到最后一项"黎明前"——
#: 那是**阈值表**的经典误用（阈值表只能表达"从某点开始"，表达不了"某段"）。
PHASE_BANDS = (
    (0.00, 0.04, '日出'),
    (0.04, 0.20, '上午'),
    (0.20, 0.32, '正午'),
    (0.32, 0.46, '午后'),
    (0.46, 0.54, '日落'),
    (0.54, 0.70, '黄昏'),
    (0.70, 0.78, '午夜'),
    (0.78, 0.96, '深夜'),
    (0.96, 1.00, '黎明前'),
)


def phase_name(phase: float) -> str:
    """相位 → 时段名（**全定义**：任何输入都有名字，不返回空）。"""
    p = float(phase) % 1.0
    for lo, hi, name in PHASE_BANDS:
        if lo <= p < hi:
            return name
    return '黎明前'                       # p 恰为 1.0 的边界（取模后其实是 0）


def phase_of(time_s: float, day_length: float = DAY_LENGTH) -> float:
    """世界时刻（秒）→ 相位 [0,1)。**时间可以无限增长**（不必手动取模）。"""
    return (float(time_s) / float(day_length)) % 1.0


#: 夜间天光地板（0 = 全黑）。取值依据：地面顶点色在最暗处仍需"看得清轮廓"，
#: 而 `mesh.light_scale` 还有一层自己的地板 —— 两者相乘才是屏幕上的亮度。
NIGHT_FLOOR = 0.18


def _smoothstep(e0: float, e1: float, v: float) -> float:
    """标准 smoothstep（`e0` 处 0、`e1` 处 1，中间三次平滑）。

    刻意**不用 `math` 里没有的库**、也不引 numpy：这条曲线只用于两个标量，
    自写三行比引依赖划算（且能保证换机器结果逐位一致）。
    """
    k = 0.0 if v <= e0 else (1.0 if v >= e1 else (v - e0) / (e1 - e0))
    return k * k * (3.0 - 2.0 * k)


def day_factor_from_sun(elev: float) -> float:
    """**由太阳高度角算天光强度** —— 这是 `day_factor` 的唯一来源。

    为什么不用引擎的 `ambient`（实测踩过）：`sky_state` 的 `ambient = 0.26 + 0.74*day`，
    而 `day` 在**日落时就已饱和到 0**（elev=-0.06 附近）⇒ 日落与午夜的 `ambient`
    **完全相同（都是 0.26）**，于是"下午 → 傍晚 → 夜里"在光照上没有任何渐变，
    表现为"天还亮着地面突然全黑"。

    现在按高度角算：
    * `elev >= 0.20`（太阳升高）⇒ 1.0；
    * `elev <= -0.20`（落到地平线下）⇒ `NIGHT_FLOOR`；
    * 中间用 smoothstep 平滑过渡 ⇒ 日出/日落有真实的一段"天色渐暗"。
    """
    k = _smoothstep(-0.20, 0.20, float(elev))
    return NIGHT_FLOOR + (1.0 - NIGHT_FLOOR) * k


def sky_at(time_s: float, day_length: float = DAY_LENGTH) -> dict:
    """引擎的 `sky_state` + 本项目补的两个字段（`day_factor` / `phase`）。

    `day_factor` 的口径：**天光能提供多少"可见度"**，夜间地板给 `NIGHT_FLOOR`
    而不是 0 —— 全黑在游戏里等于看不见路，那不是"夜晚"是"黑屏"。
    """
    phase = phase_of(time_s, day_length)
    st = dict(_b.sky_state(phase))
    st['phase'] = phase
    st['day_factor'] = day_factor_from_sun(st['sun'][1])
    return st


def day_factor(time_s: float, day_length: float = DAY_LENGTH) -> float:
    """只要"天多亮"这一个数时的便捷入口。"""
    return sky_at(time_s, day_length)['day_factor']


def sun_axis(time_s: float, day_length: float = DAY_LENGTH):
    """太阳方向（单位向量，指向太阳）—— 供画面外的东西（云、粒子）用。"""
    return sky_at(time_s, day_length)['sun']


def describe(time_s: float, day_length: float = DAY_LENGTH) -> str:
    """人话描述当前时刻（HUD 与 CLI 共用）。"""
    p = phase_of(time_s, day_length)
    return f'{phase_name(p)}（相位 {p:.3f}）'


class DayCycle:
    """可存档的世界时刻。**推进只走 `advance(dt)`**（内核不读时钟 ⇒ 可回放）。"""

    __slots__ = ('time', 'day_length', 'paused', 'days')

    def __init__(self, time: float = 0.0, day_length: float = DAY_LENGTH):
        self.time = float(time)
        self.day_length = float(day_length)
        self.paused = False
        self.days = int(self.time // self.day_length)

    def advance(self, dt: float) -> float:
        """推进 `dt` 秒；返回当前相位。暂停时只累加 `days` 的判定不前进。"""
        if not self.paused:
            self.time += max(0.0, float(dt))
            self.days = int(self.time // self.day_length)
        return phase_of(self.time, self.day_length)

    def skip_to_phase(self, phase: float):
        """直接跳到某相位（调试/截图用：想拍正午就跳正午，不用等）。"""
        target = (float(phase) % 1.0) * self.day_length
        day = int(self.time // self.day_length)
        self.time = day * self.day_length + target
        self.days = int(self.time // self.day_length)
        return self.time

    def sky(self) -> dict:
        return sky_at(self.time, self.day_length)

    def is_night(self) -> bool:
        """夜间的判据：太阳在地平线以下（相位 0.5~1.0）。"""
        return 0.5 <= phase_of(self.time, self.day_length) < 1.0

    def dump(self) -> dict:
        return {'time': self.time, 'day_length': self.day_length,
                'paused': self.paused}

    def load(self, data: dict):
        self.time = float(data.get('time', 0.0))
        self.day_length = float(data.get('day_length', DAY_LENGTH))
        self.paused = bool(data.get('paused', False))
        self.days = int(self.time // self.day_length)
        return self

    def __repr__(self):
        return (f'<DayCycle t={self.time:.1f}s 第{self.days + 1}天 '
                f'{describe(self.time, self.day_length)}>')
