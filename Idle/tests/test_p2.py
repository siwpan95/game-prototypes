"""
P2/P3 测试：fmt inf 保护、cursor 修复、批量购买、转生预览、纪元首达、存档导入导出。
"""
import math
import time

from engine import GameEngine
from engine.fmt import fmt_num, fmt_gold, fmt_dps
from config import ERAS


class TestFmtInf:
    def test_inf_returns_infinity(self):
        assert fmt_num(float("inf")) == "∞"
        assert fmt_gold(float("inf")) == "∞"
        assert fmt_dps(float("inf")) == "∞"

    def test_nan_returns_infinity(self):
        assert fmt_num(float("nan")) == "∞"

    def test_normal_still_works(self):
        assert fmt_num(1234) == "1,234"


class TestCursorFix:
    def test_cursor_generates_auto_income(self):
        e = GameEngine()
        e.state.click_power = 100
        e.state.upgrades["cursor"] = 5
        e.state.gold = 0.0
        e.state.dps = 0.0
        now = time.time()
        e.state.last_tick = now - 1.0  # 模拟过去 1 秒
        e.tick(now)
        # 光标：click_power(100) × 等级(5) × dt(1) = 500（乘区默认 1）
        assert e.state.gold >= 100 * 5 * 0.9
        # 游戏时长累计
        assert e.state.play_time >= 0.9

    def test_cursor_zero_when_no_cursor(self):
        e = GameEngine()
        e.state.click_power = 100
        e.state.upgrades["cursor"] = 0
        e.state.gold = 0.0
        e.state.dps = 0.0
        now = time.time()
        e.state.last_tick = now - 1.0
        e.tick(now)
        assert e.state.gold == 0.0


class TestBatchBuy:
    def test_geometric_cost_closed_form(self):
        e = GameEngine()
        e.state.gold = 10 ** 9
        # clicker 单价 10，几何级数 1.15^n；买 10 个
        before = e.state.gold
        bought, err = e.buy_multiple("clicker", 10)
        assert err is None
        assert bought == 10
        assert e.state.upgrades["clicker"] == 10
        # 闭式公式：10 × (1.15^10 - 1) / 0.15
        expected = int(10 * (1.15 ** 10 - 1) / 0.15)
        assert before - e.state.gold == expected

    def test_max_buy_affordable(self):
        e = GameEngine()
        e.state.gold = 10 ** 9
        bought, err = e.buy_multiple("clicker", "max")
        assert err is None
        assert bought > 0
        assert e.state.gold >= 0

    def test_limit_caps_quantity(self):
        e = GameEngine()
        e.state.gold = 10 ** 12
        # cps_multiplier 上限 10 且锁定青铜纪元，需先解锁
        e.state.total_gold = ERAS[1]["threshold"] + 1
        e._update_era()
        bought, err = e.buy_multiple("cps_multiplier", 100)
        assert err is None
        assert e.state.upgrades["cps_multiplier"] == 10
        # 再买应提示已达上限
        bought2, err2 = e.buy_multiple("cps_multiplier", 1)
        assert err2 is not None
        assert bought2 == 0

    def test_insufficient_gold_falls_back(self):
        e = GameEngine()
        e.state.gold = 50  # 只够买约 4 个 clicker（首个 10）
        bought, err = e.buy_multiple("clicker", 10)
        assert err is None
        assert 1 <= bought <= 4
        assert e.state.gold >= 0


class TestPrestigePreview:
    def test_preview_returns_projection(self):
        e = GameEngine()
        e.state.total_gold = 8000
        p = e.get_prestige_preview()
        assert p["gain"] > 0
        assert p["will_have"] == p["current_points"] + p["gain"]
        assert isinstance(p["buyable"], list)


class TestEraFirstTimes:
    def test_records_first_reach(self):
        e = GameEngine()
        e.state.total_gold = ERAS[1]["threshold"] + 1  # 抵达青铜
        e._update_era()
        assert 1 in e.state.era_first_times


class TestSaveRoundTrip:
    def test_export_import(self):
        e = GameEngine()
        e.state.gold = 123456
        e.state.total_gold = 999999
        e.state.upgrades["clicker"] = 7
        s = e.export_save()
        e2 = GameEngine()
        e2.import_save(s)
        assert e2.state.gold == 123456
        assert e2.state.total_gold == 999999
        assert e2.state.upgrades["clicker"] == 7
