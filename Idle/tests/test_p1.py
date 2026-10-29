"""
P1 系统测试 — 模组加载 / 装备(部位·词条·套装) / 英雄主动技能 / 黄金变体 /
限时活动 / 日常任务 / 挑战扩容 / 统一金币记账。
"""
import sys
import os
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine import GameEngine
from config import (
    HEROES, CHALLENGES, GOLDEN_VARIANTS, EVENTS, DAILY_TASKS,
    EQUIPMENT_SLOTS, EQUIPMENT_AFFIXES, EQUIPMENT_SETS, ACHIEVEMENTS,
)


def fresh_engine():
    """构造一个干净的引擎（不加载任何本地存档）。"""
    return GameEngine()


class TestContentModules:
    def test_module_merge_counts(self):
        assert len(HEROES) == 5
        assert len(CHALLENGES) == 6
        assert len(GOLDEN_VARIANTS) == 5
        assert len(EVENTS) == 5
        assert len(DAILY_TASKS) == 6
        assert len(EQUIPMENT_SLOTS) == 4
        assert len(EQUIPMENT_AFFIXES) == 6
        assert len(EQUIPMENT_SETS) == 3
        assert len(ACHIEVEMENTS) == 34

    def test_no_duplicate_keys_in_modules(self):
        from config import CONTENT_ISSUES
        assert CONTENT_ISSUES == []


class TestEquipment:
    def test_roll_equipment_has_slot_and_affixes(self):
        e = fresh_engine()
        tier = {"rarity": "legendary", "name": "传说", "color": "#f59e0b",
                "drop_per_tick": 0, "bonus_min": 20, "bonus_max": 100}
        item = e._roll_equipment(tier)
        assert "slot" in item and item["slot"] in {s["key"] for s in EQUIPMENT_SLOTS}
        assert isinstance(item["affixes"], list)
        assert "set_id" in item

    def test_equip_places_into_slot(self):
        e = fresh_engine()
        e.state.gold = 10 ** 9
        e.unlock_hero("mage")
        item = {"name": "测试", "rarity": "common", "bonus": 5, "color": "#aaa",
                "slot": "weapon", "affixes": [], "set_id": None, "set_name": ""}
        e.state.equipment_inventory.append(item)
        err = e.equip_to_hero(0, "mage")
        assert err is None
        slots = e.get_hero_slots("mage")
        assert slots.get("weapon") is not None

    def test_set_bonus_counted_once(self):
        e = fresh_engine()
        e.state.heroes["mage"] = {
            "level": 1,
            "equipped": {
                "weapon": {"name": "x", "rarity": "legendary", "bonus": 0,
                           "color": "#fff", "slot": "weapon", "affixes": [],
                           "set_id": "dragon", "set_name": "龙裔套装"},
                "armor": {"name": "y", "rarity": "legendary", "bonus": 0,
                          "color": "#fff", "slot": "armor", "affixes": [],
                          "set_id": "dragon", "set_name": "龙裔套装"},
            },
        }
        # 龙裔 2 件套 dps_pct +25% —— 两件应只计一次
        assert abs(e._hero_affix_factor(e.state.heroes["mage"], "dps_pct") - 1.25) < 1e-9


class TestHeroSkills:
    def test_activate_dps_mult_skill(self):
        e = fresh_engine()
        e.state.gold = 10 ** 9
        e.unlock_hero("mage")
        e.state.dps = 100.0
        e._recalc()
        before = e.state.dps
        err = e.activate_hero_skill("mage")
        assert err is None
        e._recalc()
        assert abs(e.state.dps - before * 2) < 1e-6  # 奥术新星 x2
        assert e.get_hero_skill_cooldown("mage") > 0

    def test_necromancer_summon_additive(self):
        e = fresh_engine()
        e.state.gold = 10 ** 9
        e.unlock_hero("necromancer")
        e.state.dps = 0.0
        e._recalc()
        base = e.state.dps
        e.activate_hero_skill("necromancer")
        e._recalc()
        # 亡灵军团：5 × 等级(1) 的附加 DPS
        assert abs(e.state.dps - (base + 5)) < 1e-6


class TestGolden:
    def test_variant_click_mult_applied(self):
        e = fresh_engine()
        e.state.gold = 10 ** 9
        e.buy("golden_click")
        # 强制 frenzy 变体
        frenzy = next(v for v in GOLDEN_VARIANTS if v["effect_type"] == "click_mult")
        e._activate_golden(frenzy)
        assert e._golden_click_mult() == 1024.0

    def test_golden_upgrade_scales_duration(self):
        e = fresh_engine()
        e.state.upgrades["golden_duration"] = 1  # +20%
        frenzy = next(v for v in GOLDEN_VARIANTS if v["effect_type"] == "click_mult")
        e._activate_golden(frenzy)
        assert abs(e.golden_buff_remaining - frenzy["duration"] * 1.2) < 1e-6

    def test_disable_golden_challenge_blocks_schedule(self):
        e = fresh_engine()
        e.start_challenge("no_golden")
        e._golden_button_timer = 0.0
        # 挑战下不应刷新黄金按钮
        e._schedule_golden_button()
        assert e._golden_button_timer == 999999


class TestEvents:
    def test_event_applies_dps_mult(self):
        e = fresh_engine()
        e.state.gold = 100
        e.buy("gremlin")  # 5 dps 基础产出
        before = e.state.dps
        e._start_event("double_output")
        e._recalc()
        assert abs(e.state.dps - before * 2) < 1e-6  # 双倍产出 x2

    def test_event_tick_cycles(self):
        e = fresh_engine()
        e.state.event_key = None
        e.state.event_gap = 0.0
        e._init_events()
        e.state.event_gap = 0.1
        e.tick_events(0.2)
        assert e.state.event_key is not None  # 活动已启动


class TestDailyTasks:
    def test_refresh_resets_on_date_change(self):
        e = fresh_engine()
        e.state.daily_tasks_date = "2000-01-01"
        e.state.daily_clicks = 999
        e.refresh_daily_tasks_if_needed()
        assert e.state.daily_clicks == 0
        assert e.state.daily_tasks_date != "2000-01-01"

    def test_claim_grants_reward(self):
        e = fresh_engine()
        e.state.gold = 0
        e.refresh_daily_tasks_if_needed()  # 先初始化今日的任务集
        e.state.daily_clicks = 500         # 再写入今日进度（避免被刷新重置）
        res = e.claim_daily_task("dt_click")
        assert isinstance(res, dict)
        assert e.state.gold > 0
        assert e.state.daily_tasks["dt_click"] is True


class TestChallengeExpansion:
    def test_endless_global_dps_mult(self):
        e = fresh_engine()
        e.start_challenge("endless")
        assert e._challenge_global_dps_mult() == 0.5

    def test_blitz_is_time_limited(self):
        ch = next(c for c in CHALLENGES if c["key"] == "blitz")
        assert ch.get("time_limit") is not None
        assert ch.get("target_era") == "iron"

    def test_no_golden_disables(self):
        ch = next(c for c in CHALLENGES if c["key"] == "no_golden")
        assert ch.get("disable_golden") is True


class TestGoldAccounting:
    def test_event_gold_mult_applied(self):
        e = fresh_engine()
        e._start_event("lucky_day")  # gold_mult 2
        gained = e._add_gold(100.0)
        assert gained == 200.0
