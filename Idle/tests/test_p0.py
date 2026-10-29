"""
P0 系统测试 — 离线收益 / 成就 / 每日 / 里程碑 / 转生保留 / 挑战修复。
"""
import sys
import os
import time
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine import GameEngine
from config import OFFLINE_CAP_SECONDS, MILESTONE_STEPS, ACHIEVEMENTS


class TestOffline:
    def test_offline_grants_gold(self):
        e = GameEngine()
        e.state.dps = 100.0
        e.state.last_save_ts = time.time() - 3600  # 1 小时前
        e._compute_offline()
        # 1 小时 < 上限，应精确结算 100 * 3600 ≈ 360000（允许采样漂移）
        assert abs(e._offline_gold - 100.0 * 3600) < 10
        assert e.state.gold >= 360000

    def test_offline_capped(self):
        e = GameEngine()
        e.state.dps = 100.0
        e.state.last_save_ts = time.time() - (OFFLINE_CAP_SECONDS + 99999)
        e._compute_offline()
        assert e._offline_seconds == OFFLINE_CAP_SECONDS

    def test_offline_no_effect_when_fresh(self):
        e = GameEngine()
        gold0 = e.state.gold
        e._compute_offline()
        assert e.state.gold == gold0  # ts=0 → 不结算

    def test_offline_ignores_tiny_gap(self):
        e = GameEngine()
        e.state.dps = 100.0
        e.state.last_save_ts = time.time() - 10  # 10 秒
        e._compute_offline()
        assert e._offline_gold == 0.0


class TestAchievements:
    def test_check_unlocks_by_clicks(self):
        e = GameEngine()
        e.state.stats["clicks"] = 100
        newly = e._check_achievements()
        assert "百次点击" in newly
        assert e.state.achievements.get("click_100") is True

    def test_dps_bonus_applied(self):
        e = GameEngine()
        e.state.gold = 100
        e.buy("gremlin")  # 5 dps, stone era 无加成
        e._recalc()
        base = e.state.dps
        assert base > 0
        # 解锁一个 dps 类成就后，DPS 应被乘 1.01
        e.state.achievements["first_click"] = True
        e._recalc()
        assert e.state.dps == base * 1.01

    def test_click_bonus_applied(self):
        e = GameEngine()
        e.state.achievements["click_100"] = True
        assert e._achievement_click_mult() == 1.02
        e.state.achievements["click_1000"] = True
        assert e._achievement_click_mult() == 1.02 * 1.05

    def test_progress_count(self):
        e = GameEngine()
        e.state.achievements["first_click"] = True
        done, total = e.achievement_progress()
        assert done == 1 and total == len(ACHIEVEMENTS)


class TestDaily:
    def test_first_claim(self):
        e = GameEngine()
        e.state.dps = 10.0
        res = e.claim_daily()
        assert isinstance(res, dict)
        assert res["streak"] == 1
        assert res["gold"] == 10.0 * 600 * 1.0

    def test_claim_twice_same_day(self):
        e = GameEngine()
        e.state.dps = 10.0
        e.claim_daily()
        err = e.claim_daily()
        assert isinstance(err, str)  # "今天已经领取过了"

    def test_streak_increment(self):
        e = GameEngine()
        e.state.dps = 10.0
        yest = (date.today() - timedelta(days=1)).isoformat()
        e.state.daily_last_date = yest
        e.state.daily_streak = 1
        res = e.claim_daily()
        assert res["streak"] == 2

    def test_seventh_day_bonus(self):
        e = GameEngine()
        e.state.dps = 10.0
        yest = (date.today() - timedelta(days=1)).isoformat()
        e.state.daily_last_date = yest
        e.state.daily_streak = 6
        pp0 = e.state.prestige_points
        res = e.claim_daily()
        assert res["streak"] == 7
        assert res["bonus_prestige"] == 1
        assert e.state.prestige_points == pp0 + 1


class TestMilestones:
    def test_milestone_mult_thresholds(self):
        e = GameEngine()
        assert e._milestone_mult("gremlin", 24) == 1.0
        assert e._milestone_mult("gremlin", 25) == 1.5
        assert e._milestone_mult("gremlin", 50) == 2.0
        assert e._milestone_mult("gremlin", 200) == 5.0

    def test_milestone_boosts_dps(self):
        e = GameEngine()
        e.state.gold = 10 ** 9
        for _ in range(25):
            e.buy("gremlin")
        e._recalc()
        # 25 个 gremlin：5 * 25 * 1.5 = 187.5（石器无其它加成）
        assert abs(e.state.dps - 187.5) < 1e-6


class TestPrestigePreserves:
    def test_permanent_fields_survive_prestige(self):
        e = GameEngine()
        e.state.achievements["first_click"] = True
        e.state.stats["clicks"] = 500
        e.state.lifetime_gold = 5e6
        e.state.max_era_index = 3
        e.state.gold = 100000
        e.state.total_gold = 100000
        e.prestige()
        assert e.state.achievements.get("first_click") is True
        assert e.state.stats["clicks"] == 500
        assert e.state.lifetime_gold == 5e6
        assert e.state.max_era_index == 3
        assert e.state.stats["prestiges"] == 1

    def test_prestige_resets_progress(self):
        e = GameEngine()
        e.state.gold = 100000
        e.state.total_gold = 100000
        e.buy("clicker")
        e.prestige()
        assert e.state.upgrades["clicker"] == 0
        assert e.state.gold < 100000


class TestChallengeFix:
    def test_pacifist_completes_on_bronze(self):
        e = GameEngine()
        e.start_challenge("pacifist")  # 无 time_limit
        assert e.state.challenge_completed is False
        e.state.total_gold = 20000
        e._update_era()
        e.tick(time.time() + 1)
        assert e.state.challenge_completed is True

    def test_pacifist_mult_applies_at_prestige(self):
        e = GameEngine()
        e.start_challenge("pacifist")
        e.state.total_gold = 20000
        e._update_era()
        e.tick(time.time() + 1)
        # 完成 pacifist → 声望公式应乘 1.5
        base = int(e.state.total_gold ** (1 / 3) + 0.5)
        assert e.get_prestige_formula() == int(base * 1.5)
