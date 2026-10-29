"""WaterSystem（priority=45）：玩法五阶段之②——水质。

🔴 禁止 `from __future__ import annotations`（E6）。
🔴 与 :func:`fishtank.offline.advance_step` 的第②阶段同构，
   唯一区别是在线走 `offline=False`（不乘 `water.offline_scale`）。

🔴 E11：`ReactiveTracker` 只要值变了就会触发。水质是每帧都在动的浮点数，
   直接订阅 `water` 会导致回调每帧狂响。所以这里订阅的是**离散档位**
   `water_band`（整数），只有真正跨档才发 `WATER_BAND_CHANGED`。

准则 L4：水质再差也只是产出打折（有下限 `quality_floor`），鱼不会生病或死亡。
"""

from fishtank.constants import WD_BALANCE, WD_BUS, WD_STATE, WD_STEP
from fishtank.economy import quality_factor, step_water, water_band
from fishtank.engine_bootstrap import ReactiveTracker, System
from fishtank.events import WATER_BAND_CHANGED

_KEY_BAND = "water_band"


class WaterSystem(System):
    """水质推进 + 跨档事件。"""

    priority = 45

    def __init__(self, logger=None):
        """:param logger: 可选日志器。"""
        self._log = logger
        self._tracker = None
        self._bus = None
        self.water = 0.0
        """最近一次的水质原值（跨档回调与 HUD 都读它）。"""
        self.band = 0
        """最近一次计算出的档位。"""
        self.factor = 1.0
        """最近一次计算出的水质产出系数。"""
        self.changes = 0
        """跨档次数（诊断用）。"""

    # ── 初始化 ──

    def _ensure_tracker(self, state, bal):
        """惰性建立 ReactiveTracker，把首帧档位作为基线（基线本身不发事件）。"""
        if self._tracker is not None:
            return
        self.water = state.tank.water
        self.band = water_band(state.tank.water, bal)
        self._tracker = ReactiveTracker({_KEY_BAND: self.band})
        self._tracker.subscribe(_KEY_BAND, self._on_band_changed)

    def _on_band_changed(self, entry, snapshot):
        """档位跨档回调 —— 只发事件，绝不弹窗（准则 L6）。"""
        self.changes += 1
        if self._bus is None:
            return
        self._bus.emit(WATER_BAND_CHANGED, {
            "band": entry.new, "old_band": entry.old, "water": self.water,
        })

    # ── 主循环 ──

    def update(self, world, dt):
        """执行一帧水质。"""
        state = world.get_data(WD_STATE)
        bal = world.get_data(WD_BALANCE)
        if state is None or bal is None:
            return
        self._bus = world.get_data(WD_BUS)
        self._ensure_tracker(state, bal)

        step = float(world.get_data(WD_STEP, 0.0) or 0.0)
        if step > 0.0:
            state.tank.water = step_water(
                state.tank.water, state.fish_count(), state.tank.filter_level,
                step, bal, offline=False)

        self.water = state.tank.water
        self.factor = quality_factor(state.tank.water, bal)
        self.band = water_band(state.tank.water, bal)
        self._tracker.set(_KEY_BAND, self.band)

    def resync(self, state, bal):
        """离线结算 / 读档之后重置基线，避免补算跨档时补发一堆事件。"""
        self.water = state.tank.water
        self.band = water_band(state.tank.water, bal)
        self.factor = quality_factor(state.tank.water, bal)
        self._tracker = ReactiveTracker({_KEY_BAND: self.band})
        self._tracker.subscribe(_KEY_BAND, self._on_band_changed)
