"""
黄金按钮 Mixin — 多变体黄金增益、调度、黄金升级、属性查询。
"""
import random
from config import GOLDEN_BUFF, GOLDEN_VARIANTS


class _GoldenMixin:
    """提供给 GameEngine 的黄金按钮相关方法。"""

    _golden_buff_active: bool
    _golden_buff_remaining: float
    _golden_button_visible: bool
    _golden_button_timer: float
    _golden_variant: dict | None

    def _schedule_golden_button(self):
        # 禁金挑战下不刷新
        ch = self._get_challenge()
        if ch and ch.get("disable_golden"):
            self._golden_button_timer = 999999
            return
        delay = random.randint(GOLDEN_BUFF["button_delay_min"], GOLDEN_BUFF["button_delay_max"])
        freq_lv = self.state.upgrades.get("golden_freq", 0)
        delay *= max(0.3, 1 - 0.15 * freq_lv)
        delay /= self._event_golden_freq_mult()
        self._golden_button_timer = delay

    def golden_button_clicked(self):
        if not self._golden_button_visible:
            return
        variant = self._pick_golden_variant()
        self._activate_golden(variant)

    def _pick_golden_variant(self) -> dict:
        luck_lv = self.state.upgrades.get("golden_luck", 0)
        weights = []
        for v in GOLDEN_VARIANTS:
            w = v.get("weight", 1)
            if v["effect_type"] == "instant":
                w *= (1 + 0.6 * luck_lv)
            weights.append(w)
        return random.choices(GOLDEN_VARIANTS, weights=weights, k=1)[0]

    def _activate_golden(self, variant: dict):
        self._golden_variant = variant
        self._golden_button_visible = False
        if variant["effect_type"] == "instant":
            dur_lv = self.state.upgrades.get("golden_duration", 0)
            power = self._golden_power_factor()
            gain = self.state.dps * variant["value"] * power
            self._add_gold(gain)
            # 即时类无持续增益，短暂展示后调度下一个
            self._golden_buff_active = True
            self._golden_buff_remaining = 1.0
        else:
            dur_lv = self.state.upgrades.get("golden_duration", 0)
            self._golden_buff_active = True
            self._golden_buff_remaining = variant["duration"] * (1 + 0.2 * dur_lv)
        self._schedule_golden_button()
        self._recalc()

    def _deactivate_golden(self):
        self._golden_buff_active = False
        self._golden_variant = None
        self._recalc()

    def _golden_power_factor(self) -> float:
        lv = self.state.upgrades.get("golden_power", 0)
        return 1 + 0.25 * lv

    def _golden_gold_mult(self) -> float:
        if self._golden_buff_active and self._golden_variant:
            if self._golden_variant["effect_type"] == "gold_mult":
                return self._golden_variant["value"] * self._golden_power_factor()
        return 1.0

    def _golden_drop_mult(self) -> float:
        if self._golden_buff_active and self._golden_variant:
            if self._golden_variant["effect_type"] == "drop_mult":
                return self._golden_variant["value"]
        return 1.0

    @property
    def golden_buff_active(self) -> bool:
        return self._golden_buff_active

    @property
    def golden_button_visible(self) -> bool:
        return self._golden_button_visible

    @property
    def golden_buff_remaining(self) -> float:
        return self._golden_buff_remaining

    @property
    def golden_variant(self) -> dict | None:
        return self._golden_variant
