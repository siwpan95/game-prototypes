"""AutoFeederSystem（priority=47）：玩法五阶段之③——饱食度与自动投食。

🔴 禁止 `from __future__ import annotations`（E6）。
🔴 与 :func:`fishtank.offline.advance_step` 的第③阶段同构：
   `step_satiety` → 若自动投食器在工作则 `auto_feed`。
   **必须排在 IncomeSystem(50) 之前**，因为饱食度是收益公式的输入。
   （架构文档给的 55 会让收益滞后一步，与 `advance_step` 对不上，故改为 47。）

🔴 喂食器的维护费**不在这里扣**：它已经并进
   :func:`fishtank.economy.net_rate_milli`（毛收 − 维护费，且下限为 0），
   由 IncomeSystem 一次性结算。在这里再扣一次就是重复扣费。

准则 L1/L4：饱食度掉到 0 也只是产出打到 `feeder.output_floor`，鱼不会饿死。
准则 L3：自动投食器 = 一次性购买、永久生效的"别再管我"开关。
"""

import math

from fishtank.components import FishTag, FoodPellet, Transform
from fishtank.constants import (
    WD_BALANCE, WD_BUS, WD_CFG, WD_STATE, WD_STEP,
)
from fishtank.economy import (
    auto_feed, clamp, feeder_upkeep_rate_milli, satiety_factor, step_satiety,
)
from fishtank.engine_bootstrap import System


class AutoFeederSystem(System):
    """饱食度衰减 + 自动投食 + 手动鱼食入口。"""

    priority = 47

    def __init__(self, logger=None):
        """:param logger: 可选日志器。"""
        self._log = logger
        self.satiety = 1.0
        """最近一次的饱食度（HUD 读）。"""
        self.factor = 1.0
        """最近一次的饱食产出系数。"""
        self.auto_feeds = 0
        """本次会话自动投食次数（诊断用）。"""
        self.eaten = 0
        """本次会话被吃掉的手动鱼食颗数。"""

    def update(self, world, dt):
        """执行一帧饱食度。"""
        state = world.get_data(WD_STATE)
        bal = world.get_data(WD_BALANCE)
        if state is None or bal is None:
            return

        step = float(world.get_data(WD_STEP, 0.0) or 0.0)
        if step > 0.0:
            state.tank.satiety = step_satiety(state.tank.satiety, step, bal)
            if state.tank.feeder_active():
                state.tank.satiety, fed = auto_feed(state.tank.satiety, bal)
                if fed:
                    self.auto_feeds += 1

        # 手动鱼食：鱼游到了就吃掉（在线专属，离线没有手动投喂）
        self._consume_pellets(world, state, bal)

        self.satiety = state.tank.satiety
        self.factor = satiety_factor(state.tank.satiety, bal)

    # ── 手动鱼食 ──

    def _consume_pellets(self, world, state, bal):
        """任何鱼进入 `arrive_radius` 就吃掉这颗鱼食。"""
        cfg = world.get_data(WD_CFG)
        if cfg is None:
            return
        radius = cfg.arrive_radius
        if radius <= 0.0:
            return

        fishes = [(e.get(Transform).x, e.get(Transform).y)
                  for e in world.each(FishTag, Transform)]
        if not fishes:
            return

        gain = float(bal.get("feeder.feed_gain", 0.5) or 0.0)
        lo = float(bal.get("feeder.satiety_min", 0.0) or 0.0)
        hi = float(bal.get("feeder.satiety_max", 1.0) or 1.0)

        pellets = list(world.each(FoodPellet))
        MAX_PELLETS_PER_TICK = 30
        if len(pellets) > MAX_PELLETS_PER_TICK:
            pellets = pellets[:MAX_PELLETS_PER_TICK]

        eaten = []
        for ent in pellets:
            p = ent.get(FoodPellet)
            for fx, fy in fishes:
                if math.hypot(p.x - fx, p.y - fy) <= radius:
                    # 同 tick.py：匿名实体只能用 int id 删，用 eid(None) 会静默失败
                    eaten.append(ent.id)
                    break
        for eid in eaten:
            world.remove_entity(eid)
            state.tank.satiety = clamp(state.tank.satiety + gain, lo, hi)
            self.eaten += 1

    # ── 供 UI 查询 ──

    def upkeep_rate_milli(self, state, bal):
        """当前每分钟的喂食器维护费（厘）。0 表示没开或没买。"""
        if not state.tank.feeder_active():
            return 0
        return feeder_upkeep_rate_milli(state.fish_count(), bal)
