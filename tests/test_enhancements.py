"""tests/test_enhancements.py — 增强系统回归测试。

覆盖四大支柱：
  - 成长（经验 / 等级 / 升级三选一 perk）
  - 装备稀有度与随机词缀
  - AI Director 动态难度（橡皮筋式调节）
  - 程序化生成集成（trap_types / 远程怪元数据 / 物品词缀）
以及存档/读档往返、词缀格式化修复，与多种子无头自动演示不崩。

运行：
    python tests/test_enhancements.py
或用 unittest 发现：
    python -m unittest discover -s tests
"""
from __future__ import annotations

import os
import sys
import tempfile
import unittest

# 把项目根目录加入 sys.path，使 world_gen / game 等可导入
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import random

from progression import (
    Progression, xp_for_level, compute_perk_mods,
    grant_xp, apply_perk, roll_perk_choices, PERK_MAP,
)
import affixes
from affixes import RARITY_ORDER, roll_rarity, roll_affixes, make_loot
from director import Director
import world_gen as wg
from alloy.core.ecs import World
import savegame as savegame_mod
from game import Game
from entities import MobBrain, build_mob_library


class FakeGame:
    """仅提供 progression / perk_mods / mods / ps / _recompute_mods 的最小桩。"""

    def __init__(self):
        self.progression = Progression()
        self.perk_mods: dict = {}
        self.mods: dict = {}
        self.ps = type("PS", (), {
            "hp": 100, "max_hp": 100,
            "adjust_hp": lambda self, d: None,
        })()

    def _recompute_mods(self):
        pass


class TestProgression(unittest.TestCase):
    def test_xp_curve_increasing(self):
        prev = 0
        for lv in range(1, 20):
            x = xp_for_level(lv)
            self.assertGreater(x, prev)
            prev = x

    def test_grant_xp_crosses_multiple_levels(self):
        g = FakeGame()
        levels = grant_xp(g, 100000)
        self.assertGreater(len(levels), 1)
        self.assertEqual(g.progression.level, levels[-1])
        self.assertGreaterEqual(g.progression.xp, 0)
        self.assertLess(g.progression.xp, g.progression.xp_next)

    def test_compute_perk_mods_aggregates(self):
        mods = compute_perk_mods(["strength", "toughness", "strength"])
        self.assertEqual(mods.get("attack"), 4)
        self.assertEqual(mods.get("defense"), 1)

    def test_apply_perk_mutates_mods(self):
        g = FakeGame()
        apply_perk(g, "strength")
        self.assertEqual(g.perk_mods.get("attack"), 2)
        self.assertIn("strength", g.progression.perks)

    def test_roll_perk_choices_distinct(self):
        rng = random.Random(123)
        choices = roll_perk_choices(rng, 3)
        self.assertEqual(len(choices), 3)
        ids = [c["id"] for c in choices]
        self.assertEqual(len(set(ids)), 3)


class TestAffixes(unittest.TestCase):
    def test_roll_rarity_valid(self):
        rng = random.Random(7)
        for floor in (1, 4, 8):
            for _ in range(50):
                r = roll_rarity(rng, floor, 0)
                self.assertIn(r, RARITY_ORDER)

    def test_roll_rarity_luck_shifts_up(self):
        # 高幸运整体抬升稀有度（统计层面 common 占比下降）
        rng_a = random.Random(1)
        rng_b = random.Random(1)
        common_a = sum(1 for _ in range(400)
                       if roll_rarity(rng_a, 6, 0) == "common")
        common_b = sum(1 for _ in range(400)
                       if roll_rarity(rng_b, 6, 2) == "common")
        self.assertLess(common_b, common_a)

    def test_roll_affixes_count_matches_rarity(self):
        rng = random.Random(5)
        for rid in RARITY_ORDER:
            affs = roll_affixes(rng, rid, "weapon")
            self.assertEqual(len(affs), affixes.RARITY_MAP[rid]["affixes"])
            for a in affs:
                self.assertIn("id", a)
                self.assertIn("value", a)
                self.assertIn("desc", a)

    def test_make_loot_structure(self):
        rng = random.Random(9)
        for kind, iid in (("weapon", "iron_sword"), ("armor", "leather")):
            loot = make_loot(rng, iid, kind, 5, 0)
            self.assertIn(loot["rarity"], RARITY_ORDER)
            self.assertIsInstance(loot["affixes"], list)

    def test_fmt_affix_no_list_leak(self):
        # 锁定此前 bug：{**base} 把 [min,max] 列表覆盖掉已滚定值
        self.assertEqual(
            affixes._fmt_affix({"stat": "special", "value": 0.17,
                                "desc": "特技伤害 +{v}"}),
            "特技伤害 +17%")
        self.assertEqual(
            affixes._fmt_affix({"stat": None, "value": 3, "desc": "反弹 {v}"}),
            "反弹 3")
        # 列表退化到下界，绝不出现 "[2, 5]"
        self.assertNotIn(
            "[", affixes._fmt_affix({"stat": None, "value": [2, 5],
                                     "desc": "反弹 {v}"}))


class TestDirector(unittest.TestCase):
    def test_metrics_move_in_expected_directions(self):
        d = Director()
        d.on_damage(50)
        self.assertGreater(d.struggle, 0)
        s0 = d.struggle
        d.on_kill()
        self.assertLess(d.struggle, s0)
        d.on_floor_cleared()
        d.on_death()
        self.assertGreaterEqual(d.struggle, 0)

    def test_count_mult_bounds_and_rubberband(self):
        d = Director()
        m = d.monster_count_mult()
        self.assertGreaterEqual(m, 0.6)
        self.assertLessEqual(m, 1.3)
        # 高 struggle → 放宽（计数更少）
        d2 = Director()
        for _ in range(20):
            d2.on_damage(40)
        self.assertLess(d2.monster_count_mult(), d.monster_count_mult())

    def test_from_dict_roundtrip(self):
        d = Director()
        for _ in range(5):
            d.on_kill()
            d.on_damage(10)
        d2 = Director.from_dict(d.snapshot())
        self.assertEqual(d2.kills, d.kills)
        self.assertEqual(d2.struggle, d.struggle)


class TestWorldGenIntegration(unittest.TestCase):
    def test_floor_has_trap_types_and_metadata(self):
        f = wg.generate_floor(World(), 7, 2, 8, director=Director())
        self.assertIsInstance(f["traps"], set)
        self.assertIsInstance(f["trap_types"], dict)
        for pos in f["traps"]:
            self.assertIn(pos, f["trap_types"])
            self.assertIn(f["trap_types"][pos], ("lava", "spike"))
        for it in f["items"]:
            self.assertIn("metadata", it)
            self.assertIn("rarity", it["metadata"])

    def test_director_scales_monster_count(self):
        base = wg.generate_floor(World(), 7, 3, 8, director=None)
        d = Director()
        for _ in range(30):
            d.on_damage(50)
        stressed = wg.generate_floor(World(), 7, 3, 8, director=d)
        self.assertLessEqual(len(stressed["monsters"]),
                             len(base["monsters"]))

    def test_remote_mobs_have_range(self):
        lib = build_mob_library()
        found = False
        for seed in range(1, 40):
            for fi in range(1, 9):
                f = wg.generate_floor(World(), seed, fi, 9,
                                      director=Director())
                for mob in f["monsters"]:
                    br = mob.get(MobBrain)
                    if br.template.mob_type != "boss" and br.attack_range > 1:
                        self.assertIsNotNone(br.ranged_kind)
                        found = True
                        break
            if found:
                break
        self.assertTrue(found, "未在楼层内生成到远程怪（archer/mage）")


class TestSaveLoad(unittest.TestCase):
    def test_roundtrip_preserves_progression_and_director(self):
        g = Game(seed=7, floors=8, autobuild=True)
        g.progression.level = 5
        g.progression.xp = 12
        g.progression.perks = ["strength", "toughness"]
        g.director.on_kill()
        g.director.on_damage(30)
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "save.json")
            savegame_mod.save_game(g, path)
            g2 = savegame_mod.load_game(path)
            self.assertEqual(g2.progression.level, 5)
            self.assertEqual(g2.progression.perks, ["strength", "toughness"])
            self.assertEqual(g2.director.kills, g.director.kills)


class TestAutoRegression(unittest.TestCase):
    def test_seeds_run_without_crash(self):
        for seed in (7, 13, 42):
            g = Game(seed=seed, floors=8, autobuild=True)
            status = g.run_auto()
            self.assertIn(status, ("won", "lost"))
            self.assertGreaterEqual(g.floor_index, 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
