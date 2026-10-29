"""
平衡校准测试 — 锁定数值一致性不变量，并对后期超大数值（转生公式）做稳定性校验。

说明：本测试不直接调参，而是把「健康的数值结构」编码为断言，使后续任何
数据改动都不能悄悄破坏平衡（成本递减、阈值倒挂、奖励非正等）。同时覆盖
转生公式在 total_gold > 10³⁰⁸（浮点上限）与 inf/nan 时的安全性。
"""
import sys
import os
import math

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine import GameEngine
from engine.upgrade import UpgradeDef
from config import (
    ERAS, UPGRADE_DEFS, HEROES, PRESTIGE_UPGRADES, SKILLS,
    DAILY_TASKS, EVENTS, GOLDEN_VARIANTS, CHALLENGES,
    EQUIP_TIERS, ACHIEVEMENTS,
)


class TestEraBalance:
    """纪元阈值与全局加成须单调递增、且加成不低于基准。"""

    def test_thresholds_strictly_increasing(self):
        ths = [e["threshold"] for e in ERAS]
        assert ths[0] == 0
        assert all(ths[i] < ths[i + 1] for i in range(len(ths) - 1))

    def test_bonuses_at_least_one(self):
        for e in ERAS:
            assert e["bonus_dps"] >= 1.0
            assert e["bonus_click"] >= 1.0


class TestUpgradeBalance:
    """升级成本必须为正且随等级非递减；可见性同样非递减。"""

    def test_keys_unique(self):
        keys = [u["key"] for u in UPGRADE_DEFS]
        assert len(keys) == len(set(keys))

    def test_costs_positive(self):
        for u in UPGRADE_DEFS:
            assert all(c > 0 for c in u["costs"]), u["key"]

    def test_cost_monotonic(self):
        for raw in UPGRADE_DEFS:
            d = UpgradeDef(raw)
            limit = d.limit if d.limit else 30
            prev = d.get_cost(0)
            for q in range(1, limit + 1):
                cur = d.get_cost(q)
                assert cur >= prev, f"{raw['key']} cost not monotonic at {q}"
                prev = cur

    def test_visibility_non_decreasing(self):
        for raw in UPGRADE_DEFS:
            d = UpgradeDef(raw)
            limit = d.limit if d.limit else 30
            prev = d.is_visible(0, 0)
            # 用累积金币扫描，可见性一旦开启不应回退
            cum = 0
            for q in range(limit + 1):
                vis = d.is_visible(cum, q)
                if vis:
                    cum = max(cum, d.visibilities[min(q, len(d.visibilities) - 1)])
                assert vis >= prev or (prev and vis), raw["key"]
                prev = vis


class TestHeroBalance:
    """英雄解锁/升级成本为正，升级倍率 >1；主动技能参数合法。"""

    def test_hero_keys_unique(self):
        keys = [h["key"] for h in HEROES]
        assert len(keys) == len(set(keys))

    def test_core_fields_positive(self):
        for h in HEROES:
            assert h["unlock_gold"] > 0
            assert h["upgrade_cost"] > 0
            assert h["upgrade_mult"] > 1
            assert h["max_level"] > 0

    def test_active_skill_valid(self):
        for h in HEROES:
            s = h["active_skill"]
            assert s["cooldown"] > 0
            if "duration" in s:
                assert s["duration"] > 0
            if "value" in s:
                # 倍率类必 >1，即时/召唤类必 >0
                if s["effect_type"] in ("dps_mult", "click_mult", "combo"):
                    assert s["value"] > 1
                else:
                    assert s["value"] > 0


class TestPrestigeUpgradeBalance:
    def test_fields_positive(self):
        for p in PRESTIGE_UPGRADES:
            assert p["cost"] > 0
            assert p["max_level"] > 0
            assert p["effect_per_level"] > 0


class TestSkillBalance:
    def test_cooldown_and_effects(self):
        for s in SKILLS:
            assert s["cooldown"] > 0
            if "duration" in s:
                assert s["duration"] > 0
            if "charges" in s:
                assert s["charges"] > 0
            if s["effect_type"] in ("dps_mult", "click_mult", "combo"):
                if "value" in s:
                    assert s["value"] > 1
                if s["effect_type"] == "combo":
                    assert s["click_mult"] > 1
                    assert s["dps_mult"] > 1


class TestDailyTaskBalance:
    def test_reward_positive(self):
        for t in DAILY_TASKS:
            assert t["target"] > 0
            assert t["reward"]["value"] > 0


class TestEventBalance:
    def test_multipliers_above_one(self):
        for ev in EVENTS:
            assert ev["duration"] > 0
            assert ev["gap"] > 0
            for _k, v in ev["effects"].items():
                assert v > 1.0


class TestGoldenBalance:
    def test_variants(self):
        for v in GOLDEN_VARIANTS:
            assert v["weight"] > 0
            if v["effect_type"] in ("click_mult", "dps_mult", "gold_mult", "drop_mult"):
                assert v["value"] > 1
            elif v["effect_type"] == "instant":
                assert v["value"] > 0

    def test_upgrade_costs_positive(self):
        for raw in UPGRADE_DEFS:
            if raw.get("category") == "golden":
                assert all(c > 0 for c in raw["costs"])


class TestChallengeBalance:
    def test_prestige_mult_ge_one(self):
        for c in CHALLENGES:
            assert c["prestige_mult"] >= 1.0


class TestEquipmentTierBalance:
    def test_drop_rates_and_bonus(self):
        for t in EQUIP_TIERS:
            assert 0 < t["drop_per_tick"] < 1
            assert t["bonus_min"] > 0
            assert t["bonus_max"] >= t["bonus_min"]


class TestAchievementBalance:
    def test_conditions_and_rewards(self):
        for a in ACHIEVEMENTS:
            assert a["condition"]["value"] > 0
            r = a["reward"]
            assert r["value"] > 0
            if r["type"] in ("dps_mult", "click_mult"):
                # 永久加成乘区，合理上限
                assert 0 < r["value"] <= 1.0


class TestPrestigeFormulaStability:
    """转生公式在超大/溢出数值下不得崩溃，且结果合理。"""

    def test_normal_value(self):
        e = GameEngine()
        e.state.total_gold = 1000
        assert e.get_prestige_formula() == 10  # ∛1000 = 10

    def test_huge_value_no_overflow(self):
        e = GameEngine()
        e.state.total_gold = 10 ** 400  # 远超浮点上限
        g = e.get_prestige_formula()
        assert isinstance(g, int)
        assert g > 0
        # ∛(10^400) ≈ 2.15e133，量级正确
        assert 10 ** 130 < g < 10 ** 140

    def test_inf_safe(self):
        e = GameEngine()
        e.state.total_gold = float("inf")
        # 不得抛 OverflowError，应安全返回 1
        assert e.get_prestige_formula() == 1

    def test_nan_safe(self):
        e = GameEngine()
        e.state.total_gold = float("nan")
        assert e.get_prestige_formula() == 1
