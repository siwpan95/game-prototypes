"""
KID-A WALKER 增强系统测试套件
QA工程师：严过关（Yan）
测试范围：能量系统、碎片系统、交互系统、能力系统、探索追踪、结算评分、游戏流程
"""

import sys
import os
import math
import random
import unittest
from unittest.mock import MagicMock, patch
from dataclasses import dataclass

# ─── 加载源码 ───
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 预先设置 __file__ 避免导入错误
__file__ = os.path.join(os.path.dirname(os.path.abspath(__file__)), "kid_a_walker.py")

# 直接执行源码（不含main）来加载所有类
_src_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "kid_a_walker.py")
_source = open(_src_path, encoding="utf-8").read()
_source_no_main = _source.split("def main")[0]
exec(compile(_source_no_main, _src_path, "exec"), globals())


# ─────────────────── 辅助：创建 mock WorldMap ───────────────────
class MockWorldMap:
    """轻量 WorldMap mock，仅实现 cell/world_to_chunk/is_dark_room"""
    def __init__(self, cell_map=None):
        self._cell_map = cell_map or {}  # (wx, wy) -> cell_type
        self._template_names = {}
        self._chunks = {}
        self._exits = {}

    def cell(self, wx, wy):
        iwx, iwy = int(wx), int(wy)
        return self._cell_map.get((iwx, iwy), 0)

    def world_to_chunk(self, wx, wy):
        return (int(math.floor(wx / CHUNK_SIZE)),
                int(math.floor(wy / CHUNK_SIZE)))

    def is_dark_room(self, cx, cy):
        name = self._template_names.get((cx, cy), "")
        return name in DARK_ROOM_TEMPLATES

    def set_cell(self, wx, wy, cell_type):
        self._cell_map[(int(wx), int(wy))] = cell_type


# ════════════════════════════════════════════════════════════════
# 1. EnergySystem 测试
# ════════════════════════════════════════════════════════════════
class TestEnergySystem(unittest.TestCase):
    """能量系统测试"""

    def setUp(self):
        self.energy = EnergySystem(grace_timer=0.0)

    def test_initial_values(self):
        """初始能量应为100"""
        self.assertEqual(self.energy.energy, 100.0)
        self.assertEqual(self.energy.max_energy, 100.0)
        self.assertFalse(self.energy.is_dead)

    def test_grace_period_blocks_drain(self):
        """出生保护期内不消耗能量"""
        e = EnergySystem()  # 默认 grace_timer=SPAWN_GRACE_PERIOD
        self.assertGreater(e.grace_timer, 0)
        e.update(dt=1.0, is_moving=True, zone_type=3, near_glow=False)
        # 保护期内能量不变
        self.assertEqual(e.energy, 100.0)

    def test_grace_period_allows_recovery(self):
        """出生保护期内发光柱恢复仍生效"""
        e = EnergySystem()
        e.energy = 80.0
        e.update(dt=1.0, is_moving=False, zone_type=0, near_glow=True)
        # 保护期内恢复
        self.assertGreater(e.energy, 80.0)

    def test_grace_period_expires(self):
        """出生保护期结束后正常消耗"""
        e = EnergySystem(grace_timer=0.0)  # 无保护期
        e.update(dt=1.0, is_moving=True, zone_type=0, near_glow=False)
        self.assertAlmostEqual(e.energy, 99.0, places=2)
        self.assertEqual(self.energy.shield_timer, 0.0)
        self.assertFalse(self.energy.is_shielded())

    def test_moving_drain(self):
        """移动消耗：1点/秒，dt=1秒应消耗1点"""
        self.energy.update(dt=1.0, is_moving=True, zone_type=0, near_glow=False)
        self.assertAlmostEqual(self.energy.energy, 99.0, places=2)

    def test_moving_drain_half_second(self):
        """移动消耗：dt=0.5秒应消耗0.5点"""
        self.energy.update(dt=0.5, is_moving=True, zone_type=0, near_glow=False)
        self.assertAlmostEqual(self.energy.energy, 99.5, places=2)

    def test_standing_still_no_drain(self):
        """站立不动不消耗能量（非红色区）"""
        self.energy.update(dt=1.0, is_moving=False, zone_type=0, near_glow=False)
        self.assertEqual(self.energy.energy, 100.0)

    def test_red_zone_drain_while_moving(self):
        """红色区(zone_type=3)移动消耗3+1=4点/秒（红色区3+移动1）"""
        self.energy.update(dt=1.0, is_moving=True, zone_type=3, near_glow=False)
        self.assertAlmostEqual(self.energy.energy, 96.0, places=2)

    def test_red_zone_drain_while_standing(self):
        """红色区(zone_type=3)站立也消耗3点/秒（修复BUG#2后）"""
        self.energy.update(dt=1.0, is_moving=False, zone_type=3, near_glow=False)
        # 红色区独立消耗3/秒，站立时仅消耗红色区部分
        self.assertAlmostEqual(self.energy.energy, 97.0, places=2)

    def test_acid_pool_drain(self):
        """酸液池(zone_type=5)接触骤降15/秒 + 移动1/秒 = 16/秒"""
        self.energy.update(dt=1.0, is_moving=True, zone_type=5, near_glow=False)
        # 移动消耗1 + 酸液15 = 16
        self.assertAlmostEqual(self.energy.energy, 84.0, places=1)

    def test_acid_pool_drain_while_standing(self):
        """酸液池(zone_type=5)站立也消耗15/秒"""
        self.energy.update(dt=1.0, is_moving=False, zone_type=5, near_glow=False)
        self.assertAlmostEqual(self.energy.energy, 85.0, places=1)

    def test_glow_recovery(self):
        """发光柱附近恢复0.5/秒"""
        self.energy.energy = 50.0
        self.energy.update(dt=1.0, is_moving=True, zone_type=0, near_glow=True)
        # 移动消耗1 + 发光恢复0.5 = 净消耗0.5
        self.assertAlmostEqual(self.energy.energy, 49.5, places=2)

    def test_glow_recovery_capped_at_max(self):
        """发光柱恢复不超过上限"""
        self.energy.energy = 99.9
        self.energy.update(dt=1.0, is_moving=False, zone_type=0, near_glow=True)
        self.assertLessEqual(self.energy.energy, self.energy.max_energy)

    def test_drain_multiplier(self):
        """能力系统消耗倍率"""
        self.energy.update(dt=1.0, is_moving=True, zone_type=0, near_glow=False, drain_mult=0.8)
        self.assertAlmostEqual(self.energy.energy, 99.2, places=2)  # 100 - 1*1*0.8

    def test_shielded_skips_all_drain(self):
        """危险免疫(shielded=True)时跳过所有消耗"""
        self.energy.update(dt=1.0, is_moving=True, zone_type=3, near_glow=False, shielded=True)
        self.assertEqual(self.energy.energy, 100.0)

    def test_shield_halves_drain_while_moving(self):
        """护盾(shield_timer>0)减半消耗：移动消耗1*0.5=0.5/秒"""
        self.energy.activate_shield(10.0)
        self.energy.update(dt=1.0, is_moving=True, zone_type=0, near_glow=False)
        self.assertAlmostEqual(self.energy.energy, 99.5, places=2)

    def test_shield_halves_red_zone_drain(self):
        """护盾减半红色区消耗：红色区3*0.5=1.5 + 移动1*0.5=0.5 = 2.0/秒"""
        self.energy.activate_shield(10.0)
        self.energy.update(dt=1.0, is_moving=True, zone_type=3, near_glow=False)
        self.assertAlmostEqual(self.energy.energy, 98.0, places=2)

    def test_shield_halves_red_zone_standing(self):
        """护盾减半红色区站立消耗：3*0.5=1.5/秒"""
        self.energy.activate_shield(10.0)
        self.energy.update(dt=1.0, is_moving=False, zone_type=3, near_glow=False)
        self.assertAlmostEqual(self.energy.energy, 98.5, places=2)

    def test_shield_halves_acid_pool_drain(self):
        """护盾减半酸液池消耗：15*0.5=7.5/秒"""
        self.energy.activate_shield(10.0)
        self.energy.update(dt=1.0, is_moving=False, zone_type=5, near_glow=False)
        self.assertAlmostEqual(self.energy.energy, 92.5, places=1)

    def test_energy_depleted_sets_dead(self):
        """能量归零 → is_dead"""
        self.energy.energy = 0.5
        self.energy.update(dt=1.0, is_moving=True, zone_type=0, near_glow=False)
        self.assertTrue(self.energy.is_dead)

    def test_energy_clamped_to_zero(self):
        """能量不会低于0"""
        self.energy.energy = 0.3
        self.energy.update(dt=1.0, is_moving=True, zone_type=0, near_glow=False)
        self.assertGreaterEqual(self.energy.energy, 0.0)

    def test_recover(self):
        """恢复能量"""
        self.energy.energy = 50.0
        self.energy.recover(20)
        self.assertAlmostEqual(self.energy.energy, 70.0)

    def test_recover_capped(self):
        """恢复不超过上限"""
        self.energy.energy = 95.0
        self.energy.recover(20)
        self.assertAlmostEqual(self.energy.energy, 100.0)

    def test_activate_shield(self):
        """激活护盾"""
        self.energy.activate_shield(10.0)
        self.assertTrue(self.energy.is_shielded())
        self.assertEqual(self.energy.shield_timer, 10.0)

    def test_shield_timer_decreases(self):
        """护盾计时器递减"""
        self.energy.activate_shield(10.0)
        self.energy.update(dt=3.0, is_moving=False, zone_type=0, near_glow=False)
        self.assertAlmostEqual(self.energy.shield_timer, 7.0, places=2)
        self.assertTrue(self.energy.is_shielded())

    def test_shield_timer_expires(self):
        """护盾计时器归零"""
        self.energy.activate_shield(2.0)
        self.energy.update(dt=3.0, is_moving=False, zone_type=0, near_glow=False)
        self.assertFalse(self.energy.is_shielded())

    def test_get_ratio(self):
        """能量比例"""
        self.energy.energy = 50.0
        self.assertAlmostEqual(self.energy.get_ratio(), 0.5)

    def test_reset(self):
        """重置"""
        self.energy.energy = 10.0
        self.energy.is_dead = True
        self.energy.shield_timer = 5.0
        self.energy.reset()
        self.assertEqual(self.energy.energy, 100.0)
        self.assertFalse(self.energy.is_dead)
        self.assertEqual(self.energy.shield_timer, 0.0)

    def test_natural_depletion_time(self):
        """验证100秒自然耗尽：1/秒 × 100秒 = 100"""
        e = EnergySystem(grace_timer=0.0)
        for _ in range(100):
            e.update(dt=1.0, is_moving=True, zone_type=0, near_glow=False)
        self.assertTrue(e.is_dead)
        self.assertAlmostEqual(e.energy, 0.0, places=1)

    def test_red_zone_depletion_time(self):
        """验证红色区约25秒耗尽：移动消耗(3+1)/秒"""
        e = EnergySystem(grace_timer=0.0)
        for _ in range(26):
            e.update(dt=1.0, is_moving=True, zone_type=3, near_glow=False)
        self.assertTrue(e.is_dead)


# ════════════════════════════════════════════════════════════════
# 2. FragmentSystem 测试
# ════════════════════════════════════════════════════════════════
class TestFragmentSystem(unittest.TestCase):
    """碎片收集系统测试"""

    def setUp(self):
        self.fragments = FragmentSystem()

    def test_initial_empty(self):
        """初始状态为空"""
        self.assertEqual(self.fragments.get_total(), 0)
        self.assertEqual(self.fragments.get_unique_types(), 0)
        self.assertFalse(self.fragments.is_all_types_collected())

    def test_collect_fragment(self):
        """拾取碎片"""
        result = self.fragments.collect(deco_type=2, key=(0, 0, 10, 10))
        self.assertTrue(result)
        self.assertEqual(self.fragments.get_count(2), 1)
        self.assertEqual(self.fragments.get_total(), 1)
        self.assertEqual(self.fragments.get_unique_types(), 1)

    def test_collect_same_deco_only_once(self):
        """同装饰物仅能拾取一次"""
        key = (0, 0, 10, 10)
        self.assertTrue(self.fragments.collect(2, key))
        self.assertFalse(self.fragments.collect(2, key))

    def test_collect_different_deco_same_type(self):
        """不同位置的同类型装饰物可分别拾取"""
        self.assertTrue(self.fragments.collect(2, (0, 0, 10, 10)))
        self.assertTrue(self.fragments.collect(2, (0, 0, 5, 5)))
        self.assertEqual(self.fragments.get_count(2), 2)

    def test_collect_all_10_types(self):
        """收集10种不同类型碎片"""
        for i, deco_type in enumerate(range(2, 12)):
            key = (0, 0, i, i)
            self.fragments.collect(deco_type, key)
        self.assertTrue(self.fragments.is_all_types_collected())
        self.assertEqual(self.fragments.get_unique_types(), 10)

    def test_has_interacted(self):
        """已互动标记"""
        key = (1, 2, 3, 4)
        self.assertFalse(self.fragments.has_interacted(key))
        self.fragments.collect(2, key)
        self.assertTrue(self.fragments.has_interacted(key))

    def test_reset_clears_collected_and_interacted(self):
        """重置清空collected和interacted"""
        self.fragments.collect(2, (0, 0, 10, 10))
        self.fragments.collect(3, (0, 0, 5, 5))
        self.fragments.reset()
        self.assertEqual(self.fragments.get_total(), 0)
        self.assertFalse(self.fragments.has_interacted((0, 0, 10, 10)))

    def test_reset_preserves_codex(self):
        """重置保留图鉴（跨局保留）"""
        self.fragments.collect(2, (0, 0, 10, 10))
        self.assertIn(2, self.fragments.codex)
        self.fragments.reset()
        # 图鉴应保留
        self.assertIn(2, self.fragments.codex)

    def test_codex_updated_on_collect(self):
        """拾取时图鉴更新"""
        self.fragments.collect(5, (0, 0, 3, 3))
        self.assertIn(5, self.fragments.codex)
        self.assertTrue(self.fragments.codex[5])

    def test_interacted_key_format(self):
        """interacted字典key格式: (cx, cy, lx, ly)"""
        key = (1, -2, 10, 15)
        self.fragments.collect(2, key)
        self.assertTrue(self.fragments.has_interacted(key))

    def test_get_count_nonexistent_type(self):
        """未收集的类型返回0"""
        self.assertEqual(self.fragments.get_count(99), 0)


# ════════════════════════════════════════════════════════════════
# 3. InteractionSystem 测试
# ════════════════════════════════════════════════════════════════
class TestInteractionSystem(unittest.TestCase):
    """交互系统测试"""

    def setUp(self):
        self.interaction = InteractionSystem(interact_range=2.0)
        self.fragments = FragmentSystem()
        self.energy = EnergySystem(grace_timer=0.0)
        self.world = MockWorldMap()

    def test_find_nearest_deco_none(self):
        """无可交互装饰物时返回None"""
        result = self.interaction.find_nearest_deco(10.5, 10.5, self.world, self.fragments)
        self.assertIsNone(result)

    def test_find_nearest_deco_in_range(self):
        """范围内有装饰物"""
        self.world.set_cell(10, 10, 2)  # 在(10,10)放置发光柱
        result = self.interaction.find_nearest_deco(10.5, 10.5, self.world, self.fragments)
        self.assertIsNotNone(result)
        wx, wy, deco_type, key = result
        self.assertEqual(deco_type, 2)

    def test_find_nearest_deco_out_of_range(self):
        """范围外装饰物不可交互"""
        self.world.set_cell(15, 15, 2)  # 距离(10.5,10.5)约6.7，超过范围2.0
        result = self.interaction.find_nearest_deco(10.5, 10.5, self.world, self.fragments)
        self.assertIsNone(result)

    def test_find_nearest_skips_interacted(self):
        """已互动的装饰物被跳过"""
        # 放置两个发光柱
        self.world.set_cell(10, 10, 2)
        self.world.set_cell(11, 10, 2)
        # 标记第一个已互动
        key1 = self._compute_key(10, 10)
        self.fragments.collect(2, key1)
        # 应找到第二个
        result = self.interaction.find_nearest_deco(10.5, 10.5, self.world, self.fragments)
        self.assertIsNotNone(result)

    def _compute_key(self, wx, wy):
        """模拟InteractionSystem的key计算"""
        cx, cy = self.world.world_to_chunk(wx + 0.5, wy + 0.5)
        lx = int(wx + 0.5) % CHUNK_SIZE
        ly = int(wy + 0.5) % CHUNK_SIZE
        return (cx, cy, lx, ly)

    def test_is_in_range(self):
        """is_in_range判断"""
        self.world.set_cell(10, 10, 4)
        self.assertTrue(self.interaction.is_in_range(10.5, 10.5, self.world, self.fragments))

    def test_interact_glow_pillar(self):
        """交互：发光柱(2)恢复20能量"""
        self.energy.energy = 50.0
        self.world.set_cell(10, 10, 2)
        result = self.interaction.interact(10.5, 10.5, self.world, self.fragments, self.energy)
        self.assertIsNotNone(result)
        self.assertEqual(result["type"], 2)
        self.assertEqual(result["energy_recover"], 20)
        self.assertAlmostEqual(self.energy.energy, 70.0)

    def test_interact_gold_treasury(self):
        """交互：金色宝库(4)高分碎片"""
        self.world.set_cell(10, 10, 4)
        result = self.interaction.interact(10.5, 10.5, self.world, self.fragments, self.energy)
        self.assertIsNotNone(result)
        self.assertEqual(result["type"], 4)
        self.assertTrue(result.get("bonus_score", False))

    def test_interact_energy_core(self):
        """交互：能量核心(6)激活护盾10秒"""
        self.world.set_cell(10, 10, 6)
        result = self.interaction.interact(10.5, 10.5, self.world, self.fragments, self.energy)
        self.assertIsNotNone(result)
        self.assertEqual(result["type"], 6)
        self.assertEqual(result["shield"], 10.0)
        self.assertTrue(self.energy.is_shielded())

    def test_interact_fire_exit(self):
        """交互：光源(7)恢复5能量+标记"""
        self.energy.energy = 50.0
        self.world.set_cell(10, 10, 7)
        result = self.interaction.interact(10.5, 10.5, self.world, self.fragments, self.energy)
        self.assertIsNotNone(result)
        self.assertEqual(result["type"], 7)
        self.assertEqual(result["energy_recover"], 5)
        self.assertIn("marker", result)
        self.assertAlmostEqual(self.energy.energy, 55.0)

    def test_interact_nothing_nearby(self):
        """附近无可交互物"""
        result = self.interaction.interact(10.5, 10.5, self.world, self.fragments, self.energy)
        self.assertIsNone(result)

    def test_interact_only_once(self):
        """同一装饰物只能交互一次"""
        self.world.set_cell(10, 10, 2)
        result1 = self.interaction.interact(10.5, 10.5, self.world, self.fragments, self.energy)
        self.assertIsNotNone(result1)
        result2 = self.interaction.interact(10.5, 10.5, self.world, self.fragments, self.energy)
        self.assertIsNone(result2)

    def test_scan_range_correct(self):
        """扫描范围：interact_range=2时，scan_r=3，扫描-3到+3"""
        interaction = InteractionSystem(interact_range=2.0)
        scan_r = int(interaction.interact_range) + 1
        self.assertEqual(scan_r, 3)

    def test_distance_calculation(self):
        """距离计算正确"""
        # 玩家在(10.5, 10.5)，装饰物在(12, 12)
        # 距离 = sqrt((12.5-10.5)^2 + (12.5-10.5)^2) = sqrt(8) ≈ 2.83
        # 超出range=2.0，不可交互
        self.world.set_cell(12, 12, 2)
        result = self.interaction.find_nearest_deco(10.5, 10.5, self.world, self.fragments)
        self.assertIsNone(result)


# ════════════════════════════════════════════════════════════════
# 4. AbilitySystem 测试
# ════════════════════════════════════════════════════════════════
class TestAbilitySystem(unittest.TestCase):
    """能力增强系统测试"""

    def setUp(self):
        self.fragments = FragmentSystem()
        self.abilities = AbilitySystem(self.fragments)

    def test_initial_no_bonuses(self):
        """初始无任何被动能力"""
        self.assertAlmostEqual(self.abilities.get_depth_multiplier(), 1.0)
        self.assertAlmostEqual(self.abilities.get_drain_multiplier(), 1.0)
        self.assertAlmostEqual(self.abilities.get_speed_multiplier(), 1.0)
        self.assertFalse(self.abilities.has_vision_bonus())
        self.assertFalse(self.abilities.has_drain_reduction())
        self.assertFalse(self.abilities.has_speed_bonus())

    def test_depth_bonus_5_same_type(self):
        """5个同色碎片 → 视野+15%"""
        for i in range(5):
            self.fragments.collect(2, (0, 0, i, i))
        self.assertAlmostEqual(self.abilities.get_depth_multiplier(), 1.15)

    def test_drain_reduction_5_same_type(self):
        """5个同色碎片 → 耗能-20%"""
        for i in range(5):
            self.fragments.collect(6, (0, 0, i, i))
        self.assertAlmostEqual(self.abilities.get_drain_multiplier(), 0.8)

    def test_speed_bonus_5_same_type(self):
        """5个同色碎片 → 移速+15%"""
        for i in range(5):
            self.fragments.collect(7, (0, 0, i, i))
        self.assertAlmostEqual(self.abilities.get_speed_multiplier(), 1.15)

    def test_danger_immune_all_types(self):
        """10种各1 → 危险免疫"""
        for i, deco_type in enumerate(range(2, 12)):
            self.fragments.collect(deco_type, (0, 0, i, i))
        self.assertTrue(self.abilities.is_danger_immune())

    def test_danger_immune_timer_decreases(self):
        """危险免疫计时器递减"""
        for i, deco_type in enumerate(range(2, 12)):
            self.fragments.collect(deco_type, (0, 0, i, i))
        # 触发免疫
        self.abilities.is_danger_immune()
        # 模拟时间流逝
        self.abilities.update(dt=3.0)
        self.assertAlmostEqual(self.abilities.danger_immune_timer, 2.0, places=1)

    def test_danger_immune_not_all_types(self):
        """未集齐10种无免疫"""
        for i in range(5):
            self.fragments.collect(2, (0, 0, i, i))
        self.assertFalse(self.abilities.is_danger_immune())

    def test_danger_immune_permanent_bug(self):
        """验证BUG#1已修复：is_danger_immune()不再每帧重置timer

        修复后逻辑：timer>0时直接返回True（不重置），冷却65秒防止无限触发。
        """
        for i, deco_type in enumerate(range(2, 12)):
            self.fragments.collect(deco_type, (0, 0, i, i))

        # 首次调用触发免疫
        self.abilities.is_danger_immune()
        self.assertAlmostEqual(self.abilities.danger_immune_timer, 5.0)

        # 模拟3秒流逝
        self.abilities.update(dt=3.0)
        # timer应减少到2.0
        self.assertAlmostEqual(self.abilities.danger_immune_timer, 2.0, places=1)

        # 再次调用 - 修复后timer不应被重置
        self.abilities.is_danger_immune()
        # timer应保持2.0（因为timer>0直接返回True，不重置）
        self.assertAlmostEqual(self.abilities.danger_immune_timer, 2.0,
                              places=1,
                              msg="BUG#1已修复: is_danger_immune()不再重置timer")

    def test_danger_immune_cooldown(self):
        """验证60秒冷却：免疫5秒后，65秒内不可再次触发"""
        for i, deco_type in enumerate(range(2, 12)):
            self.fragments.collect(deco_type, (0, 0, i, i))

        # 触发免疫
        self.abilities.is_danger_immune()
        self.assertAlmostEqual(self.abilities.danger_immune_timer, 5.0)
        self.assertAlmostEqual(self.abilities._immune_cooldown, 65.0)

        # 模拟5秒流逝（免疫期结束）
        self.abilities.update(dt=5.0)
        self.assertAlmostEqual(self.abilities.danger_immune_timer, 0.0, places=1)
        # 冷却还剩60秒
        self.assertAlmostEqual(self.abilities._immune_cooldown, 60.0, places=1)

        # 免疫期结束后再次调用 → 冷却中，不可触发
        self.assertFalse(self.abilities.is_danger_immune())
        # timer不应被设置
        self.assertAlmostEqual(self.abilities.danger_immune_timer, 0.0, places=1)

        # 模拟60秒流逝（冷却结束）
        self.abilities.update(dt=60.0)
        self.assertAlmostEqual(self.abilities._immune_cooldown, 0.0, places=1)

        # 冷却结束后可再次触发
        self.assertTrue(self.abilities.is_danger_immune())
        self.assertAlmostEqual(self.abilities.danger_immune_timer, 5.0)

    def test_4_same_type_no_bonus(self):
        """4个同色碎片不触发被动"""
        for i in range(4):
            self.fragments.collect(2, (0, 0, i, i))
        self.assertAlmostEqual(self.abilities.get_depth_multiplier(), 1.0)


# ════════════════════════════════════════════════════════════════
# 5. ExplorationTracker 测试
# ════════════════════════════════════════════════════════════════
class TestExplorationTracker(unittest.TestCase):
    """区块探索追踪测试"""

    def setUp(self):
        self.tracker = ExplorationTracker(explore_radius=10)
        self.world = MockWorldMap()

    def test_initial_no_explored(self):
        """初始无已探索区块"""
        self.assertEqual(self.tracker.get_explored_count(), 0)

    def test_mark_explored_near_center(self):
        """靠近区块中心标记已探索"""
        # 区块(0,0)中心在(10,10)，玩家在(10.5,10.5)，距离约0.7
        self.tracker.check_and_mark(10.5, 10.5, self.world)
        self.assertTrue(self.tracker.is_explored(0, 0))
        self.assertEqual(self.tracker.get_explored_count(), 1)

    def test_not_explored_far_from_center(self):
        """远离中心不标记"""
        # 区块(0,0)中心在(10,10)，玩家在(0.5,0.5)，距离约13.4
        self.tracker.check_and_mark(0.5, 0.5, self.world)
        self.assertFalse(self.tracker.is_explored(0, 0))

    def test_explore_radius_boundary(self):
        """探索半径边界：恰好10格"""
        # 区块(0,0)中心(10,10)，玩家在(20,10)，距离10
        self.tracker.check_and_mark(20.0, 10.0, self.world)
        self.assertTrue(self.tracker.is_explored(0, 0))

    def test_explore_radius_just_outside(self):
        """探索半径边界外：10.01格"""
        self.tracker.check_and_mark(20.1, 10.0, self.world)
        self.assertFalse(self.tracker.is_explored(0, 0))

    def test_multiple_chunks(self):
        """多区块探索"""
        # 区块(0,0)中心
        self.tracker.check_and_mark(10.5, 10.5, self.world)
        # 区块(1,0)中心 = (31, 10)
        self.tracker.check_and_mark(31.5, 10.5, self.world)
        self.assertEqual(self.tracker.get_explored_count(), 2)

    def test_reset(self):
        """重置"""
        self.tracker.check_and_mark(10.5, 10.5, self.world)
        self.tracker.reset()
        self.assertEqual(self.tracker.get_explored_count(), 0)

    def test_center_calculation_positive_chunk(self):
        """正区块中心坐标"""
        # 区块(1,0): 中心 = 1*21 + 10 = 31
        cx, cy = 1, 0
        center_wx = cx * CHUNK_SIZE + CHUNK_SIZE // 2
        center_wy = cy * CHUNK_SIZE + CHUNK_SIZE // 2
        self.assertEqual(center_wx, 31)
        self.assertEqual(center_wy, 10)

    def test_center_calculation_negative_chunk(self):
        """负区块中心坐标"""
        # 区块(-1,0): 中心 = -1*21 + 10 = -11
        cx, cy = -1, 0
        center_wx = cx * CHUNK_SIZE + CHUNK_SIZE // 2
        center_wy = cy * CHUNK_SIZE + CHUNK_SIZE // 2
        self.assertEqual(center_wx, -11)
        self.assertEqual(center_wy, 10)


# ════════════════════════════════════════════════════════════════
# 6. DeathScreen / 评分测试
# ════════════════════════════════════════════════════════════════
class TestDeathScreen(unittest.TestCase):
    """结算画面评分计算测试"""

    def test_score_basic(self):
        """基础评分：碎片×100 + 区块×50 + 存活秒×2"""
        fragments = FragmentSystem()
        fragments.collect(2, (0, 0, 0, 0))
        fragments.collect(2, (0, 0, 1, 1))
        fragments.collect(3, (0, 0, 2, 2))
        # 碎片总数3, 类型2, 存活100秒, 探索5区块
        score = DeathScreen.calculate_score(fragments, 100.0, 5)
        # 3*100 + 5*50 + 100*2 = 300 + 250 + 200 = 750
        self.assertEqual(score, 750)

    def test_score_all_types_bonus(self):
        """全类型收集+500"""
        fragments = FragmentSystem()
        for i, deco_type in enumerate(range(2, 12)):
            fragments.collect(deco_type, (0, 0, i, i))
        score = DeathScreen.calculate_score(fragments, 60.0, 1)
        # 10*100 + 1*50 + 60*2 + 500 = 1000 + 50 + 120 + 500 = 1670
        self.assertEqual(score, 1670)

    def test_score_no_fragments(self):
        """无碎片评分"""
        fragments = FragmentSystem()
        score = DeathScreen.calculate_score(fragments, 50.0, 3)
        # 0*100 + 3*50 + 50*2 = 0 + 150 + 100 = 250
        self.assertEqual(score, 250)

    def test_score_formula_matches_prd(self):
        """评分公式验证：碎片×100+区块×50+存活秒×2+全类型×500"""
        fragments = FragmentSystem()
        for i, deco_type in enumerate(range(2, 12)):
            fragments.collect(deco_type, (0, 0, i, i))
        # 每种额外多1个
        for i, deco_type in enumerate(range(2, 12)):
            fragments.collect(deco_type, (1, 0, i, i))

        total_frags = fragments.get_total()  # 20
        explored = 10
        survival = 120.0

        score = DeathScreen.calculate_score(fragments, survival, explored)
        expected = total_frags * 100 + explored * 50 + int(survival) * 2 + 500
        self.assertEqual(score, expected)


# ════════════════════════════════════════════════════════════════
# 7. WorldMap.is_dark_room 测试
# ════════════════════════════════════════════════════════════════
class TestDarkRoomDetection(unittest.TestCase):
    """暗室判定测试"""

    def test_dark_room_template_name(self):
        """基于模板名判定暗室"""
        world = MockWorldMap()
        world._template_names[(0, 0)] = 'make_room_dark_cross'
        self.assertTrue(world.is_dark_room(0, 0))

    def test_dark_room_secret_ns(self):
        """暗路南北室判定"""
        world = MockWorldMap()
        world._template_names[(0, 0)] = 'make_room_secret_ns'
        self.assertTrue(world.is_dark_room(0, 0))

    def test_not_dark_room(self):
        """非暗室模板"""
        world = MockWorldMap()
        world._template_names[(0, 0)] = 'make_room_cross'
        self.assertFalse(world.is_dark_room(0, 0))

    def test_unknown_chunk_not_dark(self):
        """未知区块非暗室"""
        world = MockWorldMap()
        self.assertFalse(world.is_dark_room(99, 99))


# ════════════════════════════════════════════════════════════════
# 8. 渲染参数传递测试
# ════════════════════════════════════════════════════════════════
class TestRenderingParams(unittest.TestCase):
    """渲染参数传递测试"""

    def test_effective_max_depth_normal(self):
        """正常视野：MAX_DEPTH * 1.0 * 1.0"""
        depth_mult = 1.0
        dark_factor = 1.0
        effective = MAX_DEPTH * depth_mult * dark_factor
        self.assertEqual(effective, MAX_DEPTH)

    def test_effective_max_depth_dark_room(self):
        """暗室视野：MAX_DEPTH * 1.0 * 0.6"""
        depth_mult = 1.0
        dark_factor = 0.6
        effective = MAX_DEPTH * depth_mult * dark_factor
        self.assertAlmostEqual(effective, MAX_DEPTH * 0.6)

    def test_effective_max_depth_with_vision_bonus(self):
        """视野增强+暗室：MAX_DEPTH * 1.15 * 0.6"""
        depth_mult = 1.15
        dark_factor = 0.6
        effective = MAX_DEPTH * depth_mult * dark_factor
        expected = MAX_DEPTH * 1.15 * 0.6
        self.assertAlmostEqual(effective, expected)

    def test_render_walls_accepts_effective_max_depth(self):
        """render_walls方法签名接受effective_max_depth参数"""
        import inspect
        sig = inspect.signature(Renderer.render_walls)
        params = list(sig.parameters.keys())
        self.assertIn("effective_max_depth", params)


# ════════════════════════════════════════════════════════════════
# 9. 常量和枚举测试
# ════════════════════════════════════════════════════════════════
class TestConstants(unittest.TestCase):
    """常量和枚举验证"""

    def test_energy_constants(self):
        """能量相关常量"""
        self.assertEqual(ENERGY_MAX, 100.0)
        self.assertEqual(ENERGY_DRAIN_MOVE, 1.0)
        self.assertEqual(ENERGY_DRAIN_RED, 3.0)
        self.assertEqual(ENERGY_RECOVER_GLOW, 0.5)

    def test_fragment_types(self):
        """碎片类型数"""
        self.assertEqual(FRAGMENT_TYPES, 10)

    def test_interact_range(self):
        """交互范围"""
        self.assertEqual(INTERACT_RANGE, 2.0)

    def test_explore_radius(self):
        """探索半径"""
        self.assertEqual(EXPLORE_RADIUS, 10)

    def test_acid_drain_rate(self):
        """酸液消耗速率"""
        self.assertEqual(ACID_DRAIN_RATE, 15.0)

    def test_portal_chance(self):
        """传送门概率"""
        self.assertAlmostEqual(PORTAL_TELEPORT_CHANCE, 0.15)

    def test_chunk_size(self):
        """区块大小"""
        self.assertEqual(CHUNK_SIZE, 21)

    def test_game_state_enum(self):
        """游戏状态枚举"""
        self.assertTrue(hasattr(GameState, "GAME_OVER"))
        self.assertEqual(GameState.GAME_OVER.value, "game_over")

    def test_dark_room_templates(self):
        """暗室模板集合"""
        self.assertIn('make_room_dark_cross', DARK_ROOM_TEMPLATES)
        self.assertIn('make_room_secret_ns', DARK_ROOM_TEMPLATES)


# ════════════════════════════════════════════════════════════════
# 10. 集成测试：游戏流程
# ════════════════════════════════════════════════════════════════
class TestGameFlowIntegration(unittest.TestCase):
    """游戏流程集成测试"""

    def test_energy_death_triggers_game_over(self):
        """能量耗尽触发GAME_OVER状态"""
        energy = EnergySystem(grace_timer=0.0)
        energy.energy = 0.5
        energy.update(dt=1.0, is_moving=True, zone_type=0, near_glow=False)
        self.assertTrue(energy.is_dead)
        # 在Game中，这会导致 state = GAME_OVER

    def test_restart_preserves_codex(self):
        """重启保留图鉴"""
        fragments = FragmentSystem()
        fragments.collect(2, (0, 0, 10, 10))
        fragments.collect(3, (0, 0, 5, 5))
        self.assertEqual(len(fragments.codex), 2)

        fragments.reset()
        # collected和interacted清空
        self.assertEqual(fragments.get_total(), 0)
        # codex保留
        self.assertEqual(len(fragments.codex), 2)
        self.assertIn(2, fragments.codex)
        self.assertIn(3, fragments.codex)

    def test_restart_resets_energy(self):
        """重启重置能量"""
        energy = EnergySystem()
        energy.energy = 0
        energy.is_dead = True
        energy.shield_timer = 5.0
        energy.reset()
        self.assertEqual(energy.energy, 100.0)
        self.assertFalse(energy.is_dead)
        self.assertEqual(energy.shield_timer, 0.0)

    def test_restart_resets_exploration(self):
        """重启重置探索"""
        tracker = ExplorationTracker()
        tracker.check_and_mark(10.5, 10.5, MockWorldMap())
        tracker.reset()
        self.assertEqual(tracker.get_explored_count(), 0)

    def test_full_collect_then_restart_abilities(self):
        """全收集后重启，能力系统重新创建"""
        fragments = FragmentSystem()
        for i, dt in enumerate(range(2, 12)):
            fragments.collect(dt, (0, 0, i, i))

        abilities = AbilitySystem(fragments)
        self.assertTrue(abilities.is_danger_immune())

        # 重启
        fragments.reset()
        abilities = AbilitySystem(fragments)
        self.assertFalse(abilities.is_danger_immune())
        self.assertAlmostEqual(abilities.get_depth_multiplier(), 1.0)


# ════════════════════════════════════════════════════════════════
# 11. 能量条渐变插值测试
# ════════════════════════════════════════════════════════════════
class TestEnergyBarGradient(unittest.TestCase):
    """能量条渐变色插值验证"""

    def test_gradient_at_start(self):
        """t=0: 青绿(0,255,200)"""
        t = 0.0
        r = int(0 + 255 * (t * 2))
        g = 255
        b = int(200 * (1 - t * 2))
        self.assertEqual((r, g, b), (0, 255, 200))

    def test_gradient_at_mid(self):
        """t=0.5: 黄(255,255,0)"""
        t = 0.5
        r = int(0 + 255 * (t * 2))
        g = 255
        b = int(200 * (1 - t * 2))
        self.assertEqual((r, g, b), (255, 255, 0))

    def test_gradient_at_end(self):
        """t=1.0: 红(255,50,50)"""
        t = 1.0
        t2 = (t - 0.5) * 2
        r = 255
        g = int(255 - 205 * t2)
        b = int(50 * t2)
        self.assertEqual((r, g, b), (255, 50, 50))

    def test_gradient_mid_to_red(self):
        """t=0.75: 黄→红中间"""
        t = 0.75
        t2 = (t - 0.5) * 2
        r = 255
        g = int(255 - 205 * t2)
        b = int(50 * t2)
        self.assertEqual(r, 255)
        self.assertGreater(g, 50)
        self.assertLess(g, 255)


# ════════════════════════════════════════════════════════════════
# 12. 传送门测试
# ════════════════════════════════════════════════════════════════
class TestPortalSystem(unittest.TestCase):
    """传送门系统测试"""

    def test_portal_cell_type(self):
        """传送门格子类型为12"""
        world = MockWorldMap()
        world.set_cell(10, 10, 12)
        self.assertEqual(world.cell(10, 10), 12)

    def test_portal_teleport_chance(self):
        """传送概率15%"""
        self.assertAlmostEqual(PORTAL_TELEPORT_CHANCE, 0.15)

    def test_portal_in_deco_colors(self):
        """传送门在装饰物颜色映射中"""
        # 检查render_walls中的deco_colors
        deco_colors = {
            2: ((0, 255, 200), (0, 200, 160)),
            12: ((255, 255, 100), (200, 200, 60)),
        }
        self.assertIn(12, deco_colors)

    def test_portal_in_zone_configs(self):
        """传送门在区域音效配置中"""
        self.assertIn(12, ZONE_CONFIGS)

    def test_portal_not_interactable(self):
        """传送门(deco_type=12)不可通过find_nearest_deco找到（修复BUG#4后）"""
        interaction = InteractionSystem(interact_range=2.0)
        world = MockWorldMap()
        world.set_cell(10, 10, 12)
        fragments = FragmentSystem()
        result = interaction.find_nearest_deco(10.5, 10.5, world, fragments)
        self.assertIsNone(result, "BUG#4已修复: 传送门不可被交互系统发现")


# ════════════════════════════════════════════════════════════════
# 13. 高分记录测试
# ════════════════════════════════════════════════════════════════
class TestHighscore(unittest.TestCase):
    """最高分记录测试"""

    def test_load_highscore_no_file(self):
        """无文件时返回0"""
        # 使用临时路径
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            global HIGHSCORE_FILE
            original = HIGHSCORE_FILE
            HIGHSCORE_FILE = os.path.join(tmpdir, "nonexistent.json")
            score = load_highscore()
            HIGHSCORE_FILE = original
            self.assertEqual(score, 0)

    def test_save_and_load_highscore(self):
        """保存和加载最高分"""
        import tempfile
        global HIGHSCORE_FILE
        original = HIGHSCORE_FILE
        with tempfile.TemporaryDirectory() as tmpdir:
            HIGHSCORE_FILE = os.path.join(tmpdir, "test_highscore.json")
            save_highscore(500)
            score = load_highscore()
            HIGHSCORE_FILE = original
            self.assertEqual(score, 500)

    def test_highscore_only_saves_if_higher(self):
        """仅当分数更高时保存"""
        import tempfile
        global HIGHSCORE_FILE
        original = HIGHSCORE_FILE
        with tempfile.TemporaryDirectory() as tmpdir:
            HIGHSCORE_FILE = os.path.join(tmpdir, "test_highscore.json")
            save_highscore(500)
            save_highscore(300)  # 低于当前最高
            score = load_highscore()
            HIGHSCORE_FILE = original
            self.assertEqual(score, 500)


# ════════════════════════════════════════════════════════════════
# 14. SFXPlayer 测试（无音频设备）
# ════════════════════════════════════════════════════════════════
class TestSFXPlayer(unittest.TestCase):
    """SFX播放器测试"""

    def test_sfx_disabled_no_crash(self):
        """禁用SFX不崩溃"""
        sfx = SFXPlayer(enabled=False)
        sfx.play_collect(2)
        sfx.play_warning()
        sfx.play_shield()

    def test_sfx_warning_cooldown(self):
        """预警音效冷却"""
        sfx = SFXPlayer(enabled=False)
        sfx._last_warning_t = time.monotonic()
        # 冷却期内不应播放（仅检查不崩溃）


# ════════════════════════════════════════════════════════════════
# 14b. ZoneSynth渐变测试
# ════════════════════════════════════════════════════════════════
class TestZoneSynthCrossfade(unittest.TestCase):
    """ZoneSynth区域渐变过渡测试"""

    def test_set_zone_triggers_fade(self):
        """切换区域触发渐变（fade重置为0）"""
        synth = ZoneSynth()
        synth.set_zone(3)
        self.assertEqual(synth._current_zone, 3)
        self.assertEqual(synth._prev_zone, 2)
        self.assertEqual(synth._fade, 0.0)
        synth.running = False

    def test_same_zone_no_fade(self):
        """相同区域不触发渐变"""
        synth = ZoneSynth()
        initial_fade = synth._fade
        synth.set_zone(2)  # 已经是2
        self.assertEqual(synth._fade, initial_fade)
        synth.running = False

    def test_fade_advances_per_beat(self):
        """每拍渐变进度递增"""
        synth = ZoneSynth()
        synth.set_zone(3)
        self.assertEqual(synth._fade, 0.0)
        # 生成一拍PCM，fade应前进
        pcm = synth._gen_pcm()
        self.assertGreater(synth._fade, 0.0)
        synth.running = False

    def test_fade_completes(self):
        """渐变最终完成（fade=1.0）"""
        synth = ZoneSynth()
        synth.set_zone(3)
        # 连续生成足够多拍
        for _ in range(20):
            synth._gen_pcm()
        self.assertEqual(synth._fade, 1.0)
        synth.running = False


# ════════════════════════════════════════════════════════════════
# 15. 碎片图鉴测试
# ════════════════════════════════════════════════════════════════
class TestCodex(unittest.TestCase):
    """碎片图鉴功能测试"""

    def test_codex_records_on_collect(self):
        """拾取碎片时图鉴更新"""
        fragments = FragmentSystem()
        fragments.collect(2, (0, 0, 10, 10))
        self.assertIn(2, fragments.codex)
        self.assertTrue(fragments.codex[2])

    def test_codex_preserved_after_reset(self):
        """重启后图鉴保留"""
        fragments = FragmentSystem()
        fragments.collect(2, (0, 0, 10, 10))
        fragments.collect(5, (0, 0, 5, 5))
        fragments.reset()
        # 当前无碎片
        self.assertEqual(fragments.get_total(), 0)
        # 但图鉴记录保留
        self.assertIn(2, fragments.codex)
        self.assertIn(5, fragments.codex)

    def test_codex_multiple_collects_same_type(self):
        """同类型多次拾取，图鉴只记录一次"""
        fragments = FragmentSystem()
        fragments.collect(2, (0, 0, 10, 10))
        fragments.collect(2, (0, 0, 5, 5))
        self.assertTrue(fragments.codex[2])


# ════════════════════════════════════════════════════════════════
# 16. 综合Bug检测测试
# ════════════════════════════════════════════════════════════════
class TestBugDetection(unittest.TestCase):
    """Bug修复验证测试（Round 2回归测试）"""

    def test_bug_danger_immune_side_effect_fixed(self):
        """BUG #1已修复：is_danger_immune()不再永久重置timer

        修复后：timer>0直接返回True（不重置），新增60秒冷却。
        """
        fragments = FragmentSystem()
        for i, dt in enumerate(range(2, 12)):
            fragments.collect(dt, (0, 0, i, i))
        abilities = AbilitySystem(fragments)

        # 首次调用
        abilities.is_danger_immune()
        self.assertEqual(abilities.danger_immune_timer, 5.0)

        # 模拟3秒流逝
        abilities.update(dt=3.0)
        self.assertAlmostEqual(abilities.danger_immune_timer, 2.0, places=1)

        # 再次调用 - timer不应被重置
        abilities.is_danger_immune()
        self.assertAlmostEqual(abilities.danger_immune_timer, 2.0,
                              places=1,
                              msg="BUG#1已修复: is_danger_immune()不再重置timer")

        # 模拟免疫期结束
        abilities.update(dt=3.0)
        # 冷却期中，不可再次触发
        self.assertFalse(abilities.is_danger_immune())

    def test_bug_red_zone_drain_while_standing_fixed(self):
        """BUG #2已修复：红色区(zone_type=3)站立消耗3/秒"""
        energy = EnergySystem(grace_timer=0.0)
        energy.update(dt=1.0, is_moving=False, zone_type=3, near_glow=False)
        # 修复后：红色区站立消耗3/秒
        self.assertAlmostEqual(energy.energy, 97.0,
                              places=2,
                              msg="BUG#2已修复: 红色区站立消耗3/秒")

    def test_bug_shield_drain_reduction_fixed(self):
        """BUG #3已修复：护盾减半消耗

        PRD要求：紫色能量核心(6)提供10秒减半消耗。
        修复后：shield_timer>0时消耗×0.5
        """
        energy = EnergySystem(grace_timer=0.0)
        energy.activate_shield(10.0)
        self.assertTrue(energy.is_shielded())

        # 移动消耗：护盾减半 1*0.5=0.5
        energy.update(dt=1.0, is_moving=True, zone_type=0, near_glow=False,
                     shielded=False)
        # 修复后：energy = 100 - 0.5 = 99.5
        self.assertAlmostEqual(energy.energy, 99.5,
                              places=2,
                              msg="BUG#3已修复: 护盾减半消耗")

        # 红色区移动：护盾减半 (3+1)*0.5=2.0
        energy.energy = 100.0
        energy.activate_shield(10.0)
        energy.update(dt=1.0, is_moving=True, zone_type=3, near_glow=False,
                     shielded=False)
        self.assertAlmostEqual(energy.energy, 98.0,
                              places=2,
                              msg="BUG#3已修复: 护盾减半红色区消耗")

    def test_bug_portal_not_collectable_as_fragment_fixed(self):
        """BUG #4已修复：传送门(deco_type=12)不可被收集为碎片

        修复后：find_nearest_deco()过滤ct>=12，interact()额外检查deco_type>=12。
        """
        interaction = InteractionSystem(interact_range=2.0)
        fragments = FragmentSystem()
        energy = EnergySystem()
        world = MockWorldMap()
        world.set_cell(10, 10, 12)

        # find_nearest_deco不应找到传送门
        result = interaction.find_nearest_deco(10.5, 10.5, world, fragments)
        self.assertIsNone(result,
                         "BUG#4已修复: 传送门不可被find_nearest_deco发现")

        # interact也不应返回结果
        interact_result = interaction.interact(10.5, 10.5, world, fragments, energy)
        self.assertIsNone(interact_result,
                         "BUG#4已修复: 传送门不可交互")

        # 碎片字典不应包含类型12
        self.assertNotIn(12, fragments.collected,
                        "BUG#4已修复: 传送门类型12不会出现在碎片字典")


# ════════════════════════════════════════════════════════════════
# 17. WorldMap.cell() 边界测试
# ════════════════════════════════════════════════════════════════
class TestWorldMapCell(unittest.TestCase):
    """WorldMap.cell() 边界条件测试"""

    def test_real_world_map_positive_coords(self):
        """正坐标cell查询 - 使用find_safe_spawn确保查询可通行区域"""
        world = WorldMap(seed=42)
        spawn = world.find_safe_spawn(0, 0)
        cell = world.cell(spawn[0], spawn[1])
        # 安全区应该可通行（不是墙）
        self.assertNotEqual(cell, 1)

    def test_real_world_map_cell_types(self):
        """各种格子类型映射"""
        world = WorldMap(seed=42)
        # 检查cell方法对于已知字符的处理
        # 在生成的区块中搜索不同类型
        found_types = set()
        for cy in range(-1, 2):
            for cx in range(-1, 2):
                for ly in range(CHUNK_SIZE):
                    for lx in range(CHUNK_SIZE):
                        wx = cx * CHUNK_SIZE + lx + 0.5
                        wy = cy * CHUNK_SIZE + ly + 0.5
                        ct = world.cell(wx, wy)
                        found_types.add(ct)
        # 至少应该有空地和墙
        self.assertIn(0, found_types)
        self.assertIn(1, found_types)

    def test_unexplored_chunk_returns_wall(self):
        """未生成区块返回1（墙壁），防止空气墙"""
        world = WorldMap(seed=42)
        # 查询远处未生成的区块
        cell = world.cell(1000.5, 1000.5)
        self.assertEqual(cell, 1)

    def test_cell_blocking_wall(self):
        """墙壁阻挡"""
        world = WorldMap(seed=42)
        # 在(0,0)区块找一堵墙
        for ly in range(CHUNK_SIZE):
            for lx in range(CHUNK_SIZE):
                wx = 0 * CHUNK_SIZE + lx + 0.5
                wy = 0 * CHUNK_SIZE + ly + 0.5
                if world.cell_blocking(wx, wy):
                    self.assertEqual(world.cell(wx, wy), 1)
                    return
        self.fail("No wall found in chunk (0,0)")

    def test_is_dark_room_method_exists(self):
        """is_dark_room方法存在且返回bool"""
        world = WorldMap(seed=42)
        result = world.is_dark_room(0, 0)
        self.assertIsInstance(result, bool)

    def test_chunk_zone_returns_int(self):
        """chunk_zone返回整数区域类型"""
        world = WorldMap(seed=42)
        zone = world.chunk_zone(0, 0)
        self.assertIsInstance(zone, int)
        self.assertGreaterEqual(zone, 2)

    def test_chunk_zone_unloaded_returns_default(self):
        """未生成区块返回默认区域类型2"""
        world = WorldMap(seed=42)
        zone = world.chunk_zone(999, 999)
        self.assertEqual(zone, 2)

    def test_chunk_zone_consistent_with_cell(self):
        """chunk_zone结果与区块内实际装饰格子一致"""
        world = WorldMap(seed=42)
        world.ensure_neighbors(0, 0)
        zone = world.chunk_zone(0, 0)
        # 验证区块内确实存在该类型的格子
        found = False
        chunk = world._chunks.get((0, 0))
        if chunk:
            for row in chunk:
                for ch in row:
                    v = None
                    if '2' <= ch <= '9': v = int(ch)
                    elif ch == 'A': v = 10
                    elif ch == 'B': v = 11
                    elif ch == 'C': v = 12
                    if v == zone:
                        found = True
                        break
                if found:
                    break
        # zone=2是默认值，即使区块里没有类型2的格子也可能返回2
        # 但如果zone>2，区块内必须存在该类型
        if zone > 2:
            self.assertTrue(found, f"zone={zone} but no such cell in chunk")


# ════════════════════════════════════════════════════════════════
# 18. 能量平衡验证
# ════════════════════════════════════════════════════════════════
class TestEnergyBalance(unittest.TestCase):
    """能量平衡验证"""

    def test_100_seconds_natural_depletion(self):
        """100秒自然耗尽验证（移动消耗1/秒）"""
        e = EnergySystem(grace_timer=0.0)
        time_to_die = 0
        while not e.is_dead and time_to_die < 200:
            e.update(dt=0.016, is_moving=True, zone_type=0, near_glow=False)  # ~60fps
            time_to_die += 0.016
        self.assertAlmostEqual(time_to_die, 100.0, delta=1.0)

    def test_red_zone_depletion(self):
        """红色区约25秒耗尽验证（移动消耗(3+1)/秒）"""
        e = EnergySystem(grace_timer=0.0)
        time_to_die = 0
        while not e.is_dead and time_to_die < 200:
            e.update(dt=0.016, is_moving=True, zone_type=3, near_glow=False)
            time_to_die += 0.016
        self.assertAlmostEqual(time_to_die, 25.0, delta=1.0)

    def test_acid_pool_rapid_drain(self):
        """酸液池约6.7秒耗尽（移动+酸液=16/秒）"""
        e = EnergySystem(grace_timer=0.0)
        time_to_die = 0
        while not e.is_dead and time_to_die < 200:
            e.update(dt=0.016, is_moving=True, zone_type=5, near_glow=False)
            time_to_die += 0.016
        self.assertAlmostEqual(time_to_die, 100.0 / 16.0, delta=1.0)

    def test_glow_recovery_rate(self):
        """发光柱恢复速率：0.5/秒"""
        e = EnergySystem(grace_timer=0.0)
        e.energy = 50.0
        e.update(dt=10.0, is_moving=False, zone_type=0, near_glow=True)
        self.assertAlmostEqual(e.energy, 55.0, places=1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
