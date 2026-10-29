"""
GameEngine 核心计算 单元测试 — DPS、点击力、纪元、购买。
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine import GameEngine


class TestEngineEra:
    """纪元系统测试。"""

    def test_initial_era_is_stone(self):
        e = GameEngine()
        assert e.get_current_era()["key"] == "stone"

    def test_era_progress_zero(self):
        e = GameEngine()
        p = e.get_era_progress()
        assert 0.0 <= p <= 1.0

    def test_next_era_is_bronze(self):
        e = GameEngine()
        nxt = e.get_next_era()
        assert nxt["key"] == "bronze"

    def test_is_era_unlocked_stone(self):
        e = GameEngine()
        assert e.is_era_unlocked("stone") is True

    def test_max_era_no_next(self):
        """达到最高纪元时 get_next_era 返回 None。"""
        e = GameEngine()
        e.state.total_gold = 10 ** 20  # 远超太空时代阈值
        e._update_era()
        assert e.get_next_era() is None
        assert e.get_era_progress() == 1.0


class TestEngineCalc:
    """DPS / 点击力计算测试。"""

    def test_initial_dps_zero(self):
        e = GameEngine()
        assert e.state.dps == 0.0

    def test_initial_click_power(self):
        e = GameEngine()
        assert e.state.click_power >= 1

    def test_recalc_after_buy_dps_item(self):
        """购买 DPS 装备后 DPS 应增加。"""
        e = GameEngine()
        e.state.gold = 100
        err = e.buy("gremlin")  # 5 dps
        assert err is None
        assert e.state.dps > 0

    def test_dps_scales_with_quantity(self):
        """多数量叠加 DPS。"""
        e = GameEngine()
        e.state.gold = 200
        e.buy("gremlin")
        e.buy("gremlin")
        # 2 个 gremlin = 5*2 = 10 base，×1.15 成本递增
        assert e.state.dps >= 10

    def test_click_power_increases_with_clicker(self):
        """点击手升级后点击力增加。"""
        e = GameEngine()
        initial = e.state.click_power
        e.state.gold = 100
        e.buy("clicker")
        assert e.state.click_power > initial


class TestEngineBuy:
    """购买逻辑测试。"""

    def test_buy_reduces_gold(self):
        e = GameEngine()
        e.state.gold = 100
        e.buy("clicker")  # cost=10
        assert e.state.gold < 100

    def test_buy_increases_quantity(self):
        e = GameEngine()
        e.state.gold = 100
        e.buy("clicker")
        assert e.state.upgrades["clicker"] == 1

    def test_cannot_buy_without_gold(self):
        e = GameEngine()
        e.state.gold = 0
        err = e.buy("clicker")  # cost=10
        assert err is not None

    def test_can_buy_returns_false_without_gold(self):
        e = GameEngine()
        e.state.gold = 0
        assert e.can_buy("clicker") is False

    def test_can_buy_returns_true_with_gold(self):
        e = GameEngine()
        e.state.gold = 100
        assert e.can_buy("clicker") is True

    def test_buy_unknown_key_returns_error(self):
        e = GameEngine()
        err = e.buy("nonexistent")
        assert "未知" in err

    def test_buy_at_limit_returns_error(self):
        e = GameEngine()
        e.state.gold = 10000
        # noob_training 限制 5 级
        e.state.upgrades["noob_clicker"] = 1
        for _ in range(5):
            e.buy("noob_training")
        err = e.buy("noob_training")
        assert "上限" in err


class TestEngineTick:
    """tick 方法测试。"""

    def test_tick_accumulates_gold(self):
        e = GameEngine()
        e.state.dps = 10.0
        e.state.last_tick = 0.0
        e.tick(1.0)  # dt=1.0
        assert e.state.gold >= 10.0

    def test_tick_clamps_dt(self):
        """dt > 1.0 时截断到 1.0。"""
        e = GameEngine()
        e.state.dps = 10.0
        e.state.last_tick = 0.0
        dt = e.tick(100.0)  # 请求 100s，应截断
        assert dt == 1.0
        assert e.state.gold == 10.0  # 只产 1 秒

    def test_tick_updates_last_tick(self):
        e = GameEngine()
        e.state.last_tick = 0.0
        e.tick(5.0)
        assert e.state.last_tick == 5.0  # 在截断前就更新了

    def test_tick_detects_era_change(self):
        """累计收益达标时纪元自动进阶。"""
        e = GameEngine()
        e.state.total_gold = 50000  # 超过青铜阈值 10000
        e.state.last_tick = 0.0
        e.tick(0.1)
        assert e.get_current_era()["key"] == "bronze"


class TestEngineSkills:
    """技能系统测试。"""

    def test_get_skills_returns_list(self):
        e = GameEngine()
        skills = e.get_skills()
        assert len(skills) == 5

    def test_skill_not_available_before_era(self):
        """纪元未解锁时无法激活技能。"""
        e = GameEngine()
        # 暴击连击需要铁器时代，初始是石器
        assert e.can_activate_skill("crit_strike") is False

    def test_skill_cooldown_after_activation(self):
        """激活技能后进入冷却。"""
        e = GameEngine()
        e.state.total_gold = 10 ** 20
        e._update_era()  # 解锁所有纪元
        e.activate_skill("gold_rain")
        assert e.get_skill_cooldown("gold_rain") > 0
