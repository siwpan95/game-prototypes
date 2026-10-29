"""
游戏核心引擎 — 组装所有 Mixin，对外暴露统一的 GameEngine 接口。
"""

import time
import random
import math
from config import (
    UPGRADE_DEFS, SKILLS, GOLDEN_BUFF, TICK_DT_MAX, OFFLINE_CAP_SECONDS,
)
from .state import GameState
from .upgrade import UpgradeDef
from .fmt import fmt_gold, fmt_dps, fmt_num
from ._era import _EraMixin
from ._calc import _CalcMixin
from ._skills import _SkillsMixin
from ._heroes import _HeroesMixin
from ._prestige import _PrestigeMixin
from ._persistence import _PersistenceMixin
from ._golden import _GoldenMixin
from ._equipment import _EquipmentMixin
from ._achievements import _AchievementsMixin
from ._daily import _DailyMixin
from ._events import _EventsMixin
from ._dailytasks import _DailyTasksMixin


CRIT_MULT = 7  # 暴击倍率（来自装备/英雄词条）


class GameEngine(
    _EraMixin,
    _CalcMixin,
    _SkillsMixin,
    _HeroesMixin,
    _PrestigeMixin,
    _PersistenceMixin,
    _GoldenMixin,
    _EquipmentMixin,
    _AchievementsMixin,
    _DailyMixin,
    _EventsMixin,
    _DailyTasksMixin,
):
    """放置英雄核心引擎。"""

    def __init__(self):
        self.state = GameState()
        self._defs: dict[str, UpgradeDef] = {}
        self._dps_gears: list = []

        # 纪元
        self._era_index: int = 0

        # 技能状态
        self._skill_cooldowns: dict[str, float] = {}
        self._skill_active_until: dict[str, float] = {}
        self._crit_charges: int = 0
        self._crit_mult: float = 1.0
        self._auto_click_remaining: float = 0.0
        self._auto_click_rate: float = 0.0
        self._active_dps_mult: float = 1.0
        self._active_click_mult: float = 1.0

        # 黄金按钮
        self._golden_buff_active = False
        self._golden_buff_remaining = 0.0
        self._golden_button_visible = False
        self._golden_button_timer = 0.0
        self._golden_variant: dict | None = None

        # 英雄主动技能
        self._hero_skill_cooldowns: dict[str, float] = {}
        self._hero_skill_active: dict[str, float] = {}
        self._hero_skill_effect: dict[str, tuple] = {}

        # 限时活动
        self._event_cyc: int = 0

        self._load_defs()
        self._init_state()
        self._init_heroes()
        self._equip_drop_timer: float = 0.0
        self._pending_achievements: list = []
        self._offline_seconds: float = 0.0
        self._offline_gold: float = 0.0
        self._prev_challenge_completed: bool = False
        self._load()
        self._update_era()
        self._recalc()
        self._compute_offline()
        self._init_events()
        self._schedule_golden_button()

    # ==================== 金币记账（统一乘区） ====================

    def _gold_gain_mult(self) -> float:
        return (
            self._affix_gold_mult()
            * self._golden_gold_mult()
            * self._event_gold_mult()
        )

    def _add_gold(self, amount: float, lifetime: bool = True) -> float:
        g = amount * self._gold_gain_mult()
        self.state.gold += g
        self.state.total_gold += g
        if lifetime:
            self.state.lifetime_gold += g
        return g

    # ==================== 操作 ====================

    def click(self) -> int:
        gain = self.state.click_power
        # 暴击（装备/英雄词条）
        chance = self._affix_crit_chance()
        crit = chance > 0 and (random.random() < chance)
        if crit:
            gain = int(gain * CRIT_MULT)
        self._add_gold(gain)
        self.state.stats["clicks"] += 1
        self._inc_daily_clicks(1)
        return gain

    # ==================== 离线收益 ====================

    def _compute_offline(self):
        """根据存档时间戳计算离线收益（上限 OFFLINE_CAP_SECONDS）。"""
        ts = self.state.last_save_ts
        now = time.time()
        if ts <= 0 or ts > now:
            return
        elapsed = now - ts
        capped = min(elapsed, OFFLINE_CAP_SECONDS)
        if capped < 60:
            return
        gain = self.state.dps * capped
        self._add_gold(gain)
        self._offline_seconds = capped
        self._offline_gold = gain

    def get_offline_summary(self) -> dict:
        """返回离线结算信息，供 UI 弹窗使用。"""
        return {"seconds": self._offline_seconds, "gold": self._offline_gold}

    def tick(self, now: float) -> float:
        dt = now - self.state.last_tick
        self.state.last_tick = now
        if dt > TICK_DT_MAX:
            dt = TICK_DT_MAX

        # 累计游戏时长（统计页面）
        self.state.play_time += dt

        # DPS 产金
        self._add_gold(self.state.dps * dt)

        # 装备掉落检测
        self._equip_drop_timer += dt
        if self._equip_drop_timer >= 1.0:
            self._equip_drop_timer -= 1.0
            self._try_equip_drop()

        # 主动技能倒计时
        for sk in SKILLS:
            key = sk["key"]
            if self._skill_cooldowns.get(key, 0) > 0:
                self._skill_cooldowns[key] = max(0, self._skill_cooldowns[key] - dt)
            if self._skill_active_until.get(key, 0) > 0:
                self._skill_active_until[key] -= dt
                if self._skill_active_until[key] <= 0:
                    self._deactivate_skill(key)

        # 英雄主动技能
        self._tick_hero_skills(dt)

        # 自动点击
        if self._auto_click_remaining > 0:
            self._auto_click_remaining -= dt
            gold_per_tick = self.state.click_power * self._auto_click_rate * dt
            self._add_gold(gold_per_tick)
            if self._auto_click_remaining <= 0:
                self._auto_click_rate = 0.0

        # 光标：永久自动点击（每秒 click_power × 等级）——修复此前 per_second=0 空转
        cursor_qty = self.state.upgrades.get("cursor", 0)
        if cursor_qty > 0:
            self._add_gold(self.state.click_power * cursor_qty * dt)

        # 黄金 buff
        if self._golden_buff_active:
            self._golden_buff_remaining -= dt
            if self._golden_buff_remaining <= 0:
                self._deactivate_golden()

        # 黄金按钮
        if not self._golden_button_visible:
            self._golden_button_timer -= dt
            if self._golden_button_timer <= 0:
                if self.state.upgrades.get("golden_click", 0) > 0:
                    self._golden_button_visible = True
                    self._golden_button_timer = GOLDEN_BUFF["button_duration"]
        if self._golden_button_visible:
            self._golden_button_timer -= dt
            if self._golden_button_timer <= 0:
                self._golden_button_visible = False
                self._schedule_golden_button()

        # 限时活动
        self.tick_events(dt)
        # 日常任务刷新
        self.refresh_daily_tasks_if_needed()

        # 挑战完成判定
        challenge = self._get_challenge()
        if challenge:
            if challenge.get("time_limit"):
                elapsed = now - self.state.challenge_start_time
                target_era_key = challenge["target_era"]
                if self.is_era_unlocked(target_era_key):
                    self.state.challenge_completed = True
                elif elapsed > challenge["time_limit"]:
                    self.state.challenge_completed = False
            else:
                target = challenge.get("target_era")
                if target:
                    self.state.challenge_completed = self.is_era_unlocked(target)
                else:
                    self.state.challenge_completed = (self._era_index >= 1)
            # 完成瞬间计入今日挑战计数
            if self.state.challenge_completed and not self._prev_challenge_completed:
                self._inc_daily_challenges(1)
            self._prev_challenge_completed = self.state.challenge_completed

        # 纪元检测
        old_era = self._era_index
        self._update_era()
        if self._era_index != old_era:
            self._recalc()

        # 成就检测
        self._check_achievements()

        return dt

    # ==================== 购买 ====================

    def get_cost(self, key: str) -> int:
        d = self._defs.get(key)
        if not d:
            return 0
        return d.get_cost(self.state.upgrades.get(key, 0))

    def can_buy(self, key: str) -> bool:
        d = self._defs.get(key)
        if not d:
            return False
        if not d.can_buy(self.state.upgrades.get(key, 0)):
            return False
        if not self.is_era_unlocked(d.era):
            return False
        if not self.check_prerequisite(d):
            return False
        if d.per_second > 0:
            challenge = self._get_challenge()
            if challenge and challenge.get("restrict_dps"):
                return False
        return self.state.gold >= d.get_cost(self.state.upgrades.get(key, 0))

    def buy(self, key: str) -> str | None:
        """购买 1 个（兼容旧调用）。返回错误字符串或 None。"""
        return self.buy_multiple(key, 1)[1]

    # ==================== 批量购买 ====================

    def _cost_for_n(self, d, qty: int, n: int) -> int:
        """购买 n 个（从当前等级 qty 起）的总花费。"""
        if n <= 0:
            return 0
        if d.limit:
            n = min(n, d.limit - qty)
            if n <= 0:
                return 0
        costs = d.costs
        if len(costs) == 1:
            r = 1.15
            base = costs[0] * (r ** qty)
            return int(base * (r ** n - 1) / (r - 1))
        total = 0
        for i in range(n):
            total += costs[min(qty + i, len(costs) - 1)]
        return total

    def _max_buyable(self, d, qty: int, cap: int) -> int:
        """在当前金币下，从 qty 起最多可购买数量（受上限约束）。"""
        if d.limit:
            cap = min(cap, d.limit - qty)
        if cap <= 0:
            return 0
        if len(d.costs) == 1:
            r = 1.15
            base = d.costs[0] * (r ** qty)
            if base <= 0:
                return 0
            ratio = self.state.gold * (r - 1) / base + 1
            if ratio <= 1:
                return 0
            n = int(math.log(ratio, r))
            # 修正浮点/取整误差
            while n > 0 and self._cost_for_n(d, qty, n) > self.state.gold:
                n -= 1
            while (self._cost_for_n(d, qty, n + 1) <= self.state.gold
                   and (d.limit is None or qty + n + 1 <= d.limit)):
                n += 1
            n = min(n, cap)
            return max(0, n)
        # 固定价目表
        n = 0
        while n < cap and self._cost_for_n(d, qty, n + 1) <= self.state.gold:
            n += 1
        return n

    def buy_multiple(self, key: str, amount) -> tuple:
        """批量购买。amount 为整数或字符串 'max'。
        返回 (实际购买数量, 错误字符串|None)。"""
        d = self._defs.get(key)
        if d is None:
            return (0, "未知升级")
        qty = self.state.upgrades.get(key, 0)
        if d.limit and qty >= d.limit:
            return (0, f"{d.name} 已达上限")
        if not self.is_era_unlocked(d.era):
            return (0, f"{d.name} 尚未在当前纪元解锁")
        if not self.check_prerequisite(d):
            return (0, self.get_prerequisite_text(d))
        challenge = self._get_challenge()
        if d.per_second > 0 and challenge and challenge.get("restrict_dps"):
            return (0, "当前挑战禁用 DPS 装备")

        if amount == "max" or amount >= 10 ** 8:
            amount = self._max_buyable(d, qty, 10 ** 9)
        else:
            amount = int(amount)
            if d.limit:
                amount = min(amount, d.limit - qty)
        amount = max(amount, 0)
        if amount <= 0:
            return (0, "无法购买（已达上限或金币不足）")

        total = self._cost_for_n(d, qty, amount)
        if total > self.state.gold:
            amount = self._max_buyable(d, qty, amount)
            if amount <= 0:
                return (0, f"{d.name} 需要 {fmt_gold(self._cost_for_n(d, qty, 1))} 金币")
            total = self._cost_for_n(d, qty, amount)

        self.state.gold -= total
        self.state.upgrades[key] = qty + amount
        self.state.stats["total_upgrades"] += amount
        self._inc_daily_upgrades(amount)
        if d.empowers:
            self.state.empowered[d.empowers.key] += amount
        if d.callback == "golden":
            for _ in range(amount):
                self._activate_golden(self._pick_golden_variant())
        self._recalc()
        return (amount, None)

    # ==================== 可见/分类 ====================

    def get_def(self, key: str):
        return self._defs.get(key)

    def get_visible_upgrades(self, category: str = "all") -> list:
        result = []
        for d in self._defs.values():
            if not self.is_era_unlocked(d.era):
                continue
            if category != "all" and d.category != category:
                continue
            qty = self.state.upgrades.get(d.key, 0)
            if d.is_visible(self.state.total_gold, qty):
                result.append(d)
        result.sort(key=lambda x: x.get_cost(self.state.upgrades.get(x.key, 0)))
        return result
