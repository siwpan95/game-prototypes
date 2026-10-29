"""
每日奖励 Mixin — 登录连击、领取奖励。
本地日期驱动，无需联网；连击中断自动重置。
"""
import time
from datetime import date, timedelta
from config import DAILY_REWARD_SECONDS
from .state import GameState


class _DailyMixin:
    """提供给 GameEngine 的每日奖励相关方法。"""

    state: GameState

    @staticmethod
    def _today() -> str:
        return date.today().isoformat()

    def get_daily_status(self) -> dict:
        """返回当前每日状态：连击数、今天是否已领、下次奖励预览。"""
        today = self._today()
        claimed_today = (self.state.daily_claimed_date == today)
        streak = self.state.daily_streak
        # 若上次领取不是昨天也不是今天，则视为连击已断（展示为 0，领取时重置为 1）
        if self.state.daily_last_date and \
           self.state.daily_last_date != today and \
           self.state.daily_last_date != (date.today() - timedelta(days=1)).isoformat():
            streak = 0
        capped = min(streak + (0 if claimed_today else 1), 7) or 1
        if streak == 0 and not claimed_today:
            capped = 1
        mult = 1 + 0.5 * (capped - 1)  # 第1天 x1，第7天 x4
        preview = self.state.dps * DAILY_REWARD_SECONDS * mult
        return {
            "streak": streak, "claimed_today": claimed_today, "preview": preview,
            "bonus_prestige": (capped == 7),
        }

    def claim_daily(self) -> dict | str:
        """领取每日奖励。返回奖励信息 dict，或错误字符串。"""
        today = self._today()
        if self.state.daily_claimed_date == today:
            return "今天已经领取过了"

        yesterday = (date.today() - timedelta(days=1)).isoformat()
        if self.state.daily_last_date == yesterday:
            self.state.daily_streak += 1
        else:
            self.state.daily_streak = 1

        capped = min(self.state.daily_streak, 7)
        mult = 1 + 0.5 * (capped - 1)
        reward_gold = self.state.dps * DAILY_REWARD_SECONDS * mult

        self.state.gold += reward_gold
        self.state.total_gold += reward_gold
        self.state.lifetime_gold += reward_gold

        bonus_pp = 0
        if self.state.daily_streak % 7 == 0:
            self.state.prestige_points += 1
            bonus_pp = 1

        self.state.daily_last_date = today
        self.state.daily_claimed_date = today
        self._recalc()
        self._check_achievements()
        return {
            "streak": self.state.daily_streak, "gold": reward_gold,
            "bonus_prestige": bonus_pp,
        }
