"""
限时活动 Mixin — 按调度轮换触发活动，提供全局乘区。
"""
from config import EVENTS


class _EventsMixin:
    """提供给 GameEngine 的限时活动相关方法。"""

    state: object
    _event_cyc: int

    def _init_events(self):
        self._event_cyc = 0
        if self.state.event_gap <= 0 and EVENTS:
            self.state.event_gap = EVENTS[0]["gap"]

    def tick_events(self, dt: float):
        if not EVENTS:
            return
        if self.state.event_key is None:
            self.state.event_gap -= dt
            if self.state.event_gap <= 0:
                self._start_event(EVENTS[self._event_cyc % len(EVENTS)]["key"])
                self._event_cyc += 1
        else:
            self.state.event_remaining -= dt
            if self.state.event_remaining <= 0:
                self.state.event_key = None
                ev = self._get_event(self.state.event_key)  # None
                gap = EVENTS[(self._event_cyc - 1) % len(EVENTS)]["gap"]
                self.state.event_gap = gap
                self._recalc()

    def _start_event(self, key: str):
        ev = self._get_event(key)
        if not ev:
            return
        self.state.event_key = key
        self.state.event_remaining = ev["duration"]
        self._recalc()

    def _get_event(self, key: str | None) -> dict | None:
        if not key:
            return None
        for e in EVENTS:
            if e["key"] == key:
                return e
        return None

    def get_active_event(self) -> dict | None:
        return self._get_event(self.state.event_key)

    def _event_effects(self) -> dict:
        ev = self.get_active_event()
        return ev.get("effects", {}) if ev else {}

    def _event_dps_mult(self) -> float:
        return self._event_effects().get("dps_mult", 1.0)

    def _event_click_mult(self) -> float:
        return self._event_effects().get("click_mult", 1.0)

    def _event_gold_mult(self) -> float:
        return self._event_effects().get("gold_mult", 1.0)

    def _event_drop_mult(self) -> float:
        return self._event_effects().get("drop_mult", 1.0)

    def _event_golden_freq_mult(self) -> float:
        return self._event_effects().get("golden_freq_mult", 1.0)
