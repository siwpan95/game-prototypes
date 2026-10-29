"""IncomeSystem（priority=50）：玩法五阶段之④——收益。

🔴 禁止 `from __future__ import annotations`（E6）。
🔴 与 :func:`fishtank.offline.advance_step` 的第④阶段**同一个函数**：
   直接调 :func:`fishtank.economy.step_gain_milli`，在线只是 `efficiency=1.0`。
   全流程唯一一次取整就发生在那里（`round_half_up`），
   这样在线累加与离线结算不会因为取整策略不同而漂移。

准则 L2：收益只增不减 —— `step_gain_milli` 已经保证结果 ≥ 0，
`GameState.add_coins_milli` 又兜了一层"金币永不为负"。
"""

from fishtank.constants import (
    WD_BALANCE, WD_BONUS, WD_BUS, WD_DECOR, WD_SPECIES, WD_STATE, WD_STEP,
)
from fishtank.economy import BonusCache, net_rate_milli, step_gain_milli
from fishtank.engine_bootstrap import System
from fishtank.events import COINS_CHANGED


class IncomeSystem(System):
    """按固定步长结算金币。"""

    priority = 50

    def __init__(self, logger=None):
        """:param logger: 可选日志器。"""
        self._log = logger
        self.session_gain_milli = 0
        """本次会话累计入账（厘），HUD 的"本次在线收益"。"""
        self.rate_milli = 0
        """最近一次算出的净产出速率（厘/分钟）。"""
        self.bonus = 0.0
        """最近一次算出的总加成。"""

    def update(self, world, dt):
        """执行一帧收益。"""
        state = world.get_data(WD_STATE)
        bal = world.get_data(WD_BALANCE)
        species = world.get_data(WD_SPECIES)
        decor = world.get_data(WD_DECOR)
        if state is None or bal is None or species is None or decor is None:
            return

        cache = world.get_data(WD_BONUS)
        if cache is None:
            cache = BonusCache(bal, species, decor)
            world.set_data(WD_BONUS, cache)
        self.bonus = cache.value(state)

        step = float(world.get_data(WD_STEP, 0.0) or 0.0)
        if step > 0.0:
            gain = step_gain_milli(state, bal, species, decor, step,
                                   efficiency=1.0, bonus=self.bonus)
            if gain:
                state.add_coins_milli(gain)
                self.session_gain_milli += gain
                bus = world.get_data(WD_BUS)
                if bus is not None:
                    bus.emit(COINS_CHANGED, {
                        "coins_milli": state.coins_milli, "delta_milli": gain,
                    })

        self.rate_milli = net_rate_milli(state, bal, species, decor, bonus=self.bonus)
