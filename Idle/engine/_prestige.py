"""
转生与挑战系统 Mixin — 转生重置、挑战模式、声望商店。
"""
import math
import time
from config import PRESTIGE_UPGRADES, CHALLENGES
from .state import GameState
from .types import ChallengeDef, PrestigeUpgradeDef


def _int_cbrt(n: int) -> int:
    """整数立方根（向下取整），对任意大整数安全，不会触发浮点溢出。

    普通的 ``n ** (1/3)`` 在 n > 10³⁰⁸ 时溢出为 inf，再 ``int(inf)`` 会崩溃；
    此处用整数牛顿迭代，规模无关的纯整数运算。
    """
    if n < 2:
        return n
    x = 1 << ((n.bit_length() + 2) // 3)  # 按位长给出量级初值
    while True:
        y = (2 * x + n // (x * x)) // 3
        if y >= x:
            break
        x = y
    return x


class _PrestigeMixin:
    """提供给 GameEngine 的转生与挑战相关方法。"""

    state: GameState
    _skill_cooldowns: dict
    _skill_active_until: dict
    _crit_charges: int
    _crit_mult: float
    _auto_click_remaining: float
    _auto_click_rate: float
    _active_dps_mult: float
    _active_click_mult: float
    _golden_buff_active: bool
    _golden_buff_remaining: float
    _golden_button_visible: bool
    _golden_button_timer: float
    _equip_drop_timer: float

    def get_challenges(self) -> list:
        return CHALLENGES

    def get_active_challenge(self) -> ChallengeDef | None:
        """公开查询当前活跃的挑战。"""
        return self._get_challenge()

    def _get_challenge(self) -> ChallengeDef | None:
        if not self.state.active_challenge:
            return None
        for ch in CHALLENGES:
            if ch["key"] == self.state.active_challenge:
                return ch
        return None

    def _challenge_global_dps_mult(self) -> float:
        ch = self._get_challenge()
        if ch:
            return ch.get("global_dps_mult", 1.0)
        return 1.0

    def _challenge_global_click_mult(self) -> float:
        ch = self._get_challenge()
        if ch:
            return ch.get("global_click_mult", 1.0)
        return 1.0

    def start_challenge(self, challenge_key: str) -> str | None:
        ch = None
        for c in CHALLENGES:
            if c["key"] == challenge_key:
                ch = c
                break
        if ch is None:
            return "未知挑战"
        self._do_prestige_reset()
        self.state.active_challenge = challenge_key
        self.state.challenge_start_time = time.time()
        self.state.challenge_completed = False
        self._update_era()
        self._recalc()
        return None

    def get_prestige_formula(self) -> int:
        tg = self.state.total_gold
        # 防御：极后期乘区叠加可能让 total_gold 溢出为 inf/nan，
        # 直接给 1，避免 int(inf) 崩溃（见 _int_cbrt 注）。
        if isinstance(tg, float) and (math.isinf(tg) or math.isnan(tg)):
            base = 1
        else:
            base = _int_cbrt(int(tg)) if tg >= 0 else 0
        mult = 1.0
        ch = self._get_challenge()
        if ch and self.state.challenge_completed:
            mult = ch.get("prestige_mult", 1.0)
        return max(int(base * mult), 1)

    def get_prestige_preview(self) -> dict:
        """转生预览：将获得的声望、当前声望、可购买的声望项。"""
        gain = self.get_prestige_formula()
        buyable = []
        for pdef in PRESTIGE_UPGRADES:
            lv = self.state.prestige_upgrades.get(pdef["key"], 0)
            if lv < pdef["max_level"]:
                cost = pdef["cost"] * (lv + 1)
                next_prestige = self.state.prestige_points + gain
                buyable.append({
                    "name": pdef["name"],
                    "cost": cost,
                    "affordable": next_prestige >= cost,
                })
        return {
            "gain": gain,
            "current_points": self.state.prestige_points,
            "will_have": self.state.prestige_points + gain,
            "buyable": buyable,
        }

    def prestige(self) -> str | None:
        if self.state.total_gold < 1000:
            return "总收益太低，需要至少 1000 金币才能转生"
        ch = self._get_challenge()
        if ch and self.state.challenge_completed:
            self.state.stats["challenges"] += 1
        pts = self.get_prestige_formula()
        self.state.prestige_points += pts
        self.state.stats["prestiges"] += 1
        self._do_prestige_reset()
        self._update_era()
        self._recalc()
        return None

    def _do_prestige_reset(self):
        """重置游戏进度，保留声望与永久/累积字段。"""
        pts = self.state.prestige_points
        p_upgs = dict(self.state.prestige_upgrades)
        # ---- 永久/累积字段：跨转生保留 ----
        ach = dict(self.state.achievements)
        stats = dict(self.state.stats)
        lg = self.state.lifetime_gold
        mei = self.state.max_era_index
        dl = self.state.daily_last_date
        ds = self.state.daily_streak
        dc = self.state.daily_claimed_date
        # ---- P1：日常任务 / 活动（按日期或全局，跨转生保留）----
        dtasks = dict(self.state.daily_tasks)
        dtasks_date = self.state.daily_tasks_date
        dclicks = self.state.daily_clicks
        dupgs = self.state.daily_upgrades
        dchalls = self.state.daily_challenges
        ev_key = self.state.event_key
        ev_rem = self.state.event_remaining
        ev_gap = self.state.event_gap

        self.state = GameState()
        self.state.prestige_points = pts
        self.state.prestige_upgrades = p_upgs
        self.state.achievements = ach
        self.state.stats = stats
        self.state.lifetime_gold = lg
        self.state.max_era_index = mei
        self.state.daily_last_date = dl
        self.state.daily_streak = ds
        self.state.daily_claimed_date = dc
        self.state.daily_tasks = dtasks
        self.state.daily_tasks_date = dtasks_date
        self.state.daily_clicks = dclicks
        self.state.daily_upgrades = dupgs
        self.state.daily_challenges = dchalls
        self.state.event_key = ev_key
        self.state.event_remaining = ev_rem
        self.state.event_gap = ev_gap
        self._init_state()
        self._init_heroes()
        self._init_events()
        self._equip_drop_timer = 0.0
        self._skill_cooldowns = {k: 0.0 for k in self._skill_cooldowns}
        self._skill_active_until = {k: 0.0 for k in self._skill_active_until}
        self._crit_charges = 0
        self._crit_mult = 1.0
        self._auto_click_remaining = 0.0
        self._auto_click_rate = 0.0
        self._active_dps_mult = 1.0
        self._active_click_mult = 1.0
        self._golden_buff_active = False
        self._golden_buff_remaining = 0.0
        self._golden_button_visible = False
        self._golden_button_timer = 0.0
        self._golden_variant = None
        self._hero_skill_cooldowns = {}
        self._hero_skill_active = {}
        self._hero_skill_effect = {}
        self._schedule_golden_button()
        # 声望起始金币
        for pdef in PRESTIGE_UPGRADES:
            lv = self.state.prestige_upgrades.get(pdef["key"], 0)
            if lv > 0 and pdef["effect_type"] == "start_gold":
                self.state.gold += int(pdef["effect_per_level"] * lv)

    def get_prestige_upgrades(self) -> list:
        return PRESTIGE_UPGRADES

    def buy_prestige_upgrade(self, key: str) -> str | None:
        pdef = None
        for pd in PRESTIGE_UPGRADES:
            if pd["key"] == key:
                pdef = pd
                break
        if pdef is None:
            return "未知声望升级"
        cur_lv = self.state.prestige_upgrades.get(key, 0)
        if cur_lv >= pdef["max_level"]:
            return "已达最大等级"
        cost = pdef["cost"] * (cur_lv + 1)
        if self.state.prestige_points < cost:
            return f"声望不足 (需要 {cost})"
        self.state.prestige_points -= cost
        self.state.prestige_upgrades[key] = cur_lv + 1
        self._recalc()
        return None
