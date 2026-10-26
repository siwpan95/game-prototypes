"""
Progress Quest Multiverse - 核心游戏引擎单元测试
覆盖 GameEngine 与 Character / ProgressBar / Item 等核心对象
"""

import unittest
import sys
import os
import random
import tempfile
import json
from unittest.mock import patch, MagicMock

# 添加 src 到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from core.game_engine_v2 import (
    GameEngine, Character, Item, Monster, Quest, Spell,
    PlotChapter, ActiveTask, GameState, ProgressBar
)


class TestProgressBar(unittest.TestCase):
    """进度条基础测试"""

    def test_initial_state(self):
        bar = ProgressBar("经验", 1200)
        self.assertEqual(bar.current, 0)
        self.assertEqual(bar.max_value, 1200)
        self.assertFalse(bar.is_complete())

    def test_increment(self):
        bar = ProgressBar("任务", 100)
        bar.increment(30)
        self.assertEqual(bar.current, 30)
        bar.increment(80)
        self.assertEqual(bar.current, 100)

    def test_reset_and_set_to_max(self):
        bar = ProgressBar("剧情", 100)
        bar.set_to_max()
        self.assertTrue(bar.is_complete())
        bar.reset()
        self.assertEqual(bar.current, 0)

    def test_get_percent(self):
        bar = ProgressBar("负重", 100)
        bar.current = 25
        self.assertEqual(bar.get_percent(), 25.0)


class TestCharacter(unittest.TestCase):
    """角色与物品相关测试"""

    def test_character_creation(self):
        char = Character("勇者", "人类", "战士")
        self.assertEqual(char.name, "勇者")
        self.assertEqual(char.race, "人类")
        self.assertEqual(char.char_class, "战士")
        self.assertEqual(char.max_encumbrance, 20)  # 10 + STR 10

    def test_add_item_merges_stacks(self):
        char = Character("勇者", "人类", "战士")
        item1 = Item("史莱姆凝胶", 5, "misc")
        item2 = Item("史莱姆凝胶", 5, "misc")
        self.assertTrue(char.add_item(item1))
        self.assertTrue(char.add_item(item2))
        self.assertEqual(len(char.inventory), 1)
        self.assertEqual(char.inventory[0].count, 2)
        self.assertEqual(char.encumbrance, 2)

    def test_encumbrance_limit(self):
        char = Character("勇者", "人类", "战士")
        # 塞满到上限
        for i in range(char.max_encumbrance + 1):
            item = Item(f"物品{i}", 1, "misc")
            ok = char.add_item(item)
            if i < char.max_encumbrance:
                self.assertTrue(ok)
            else:
                self.assertFalse(ok)
        self.assertEqual(char.encumbrance, char.max_encumbrance)

    def test_sell_all_loot(self):
        char = Character("勇者", "人类", "战士")
        char.add_item(Item("狼皮", 5, "misc"))
        char.add_item(Item("狼皮", 5, "misc"))
        char.add_item(Item("狼肉", 3, "misc"))
        gold = char.sell_all_loot()
        self.assertEqual(gold, 13)  # 5*2 + 3
        self.assertEqual(char.gold, 13)
        self.assertEqual(char.encumbrance, 0)
        self.assertEqual(len(char.inventory), 0)

    def test_get_total_stat_with_equipment(self):
        char = Character("勇者", "人类", "战士")
        char.equipment['weapon'] = Item("铁剑", 100, "weapon", {"strength": 3})
        self.assertEqual(char.get_total_stat("strength"), 13)

    def test_level_up_updates_encumbrance(self):
        char = Character("勇者", "人类", "战士")
        original_str = char.strength
        char.exp_to_next_level = 1
        char.exp = 1
        char.level_up()
        self.assertGreaterEqual(char.level, 2)
        self.assertEqual(char.max_encumbrance, 10 + char.strength)

    def test_learn_spell(self):
        char = Character("勇者", "人类", "法师")
        char.spell_pool = ["火球术", "冰霜箭"]
        char._learn_spell()
        self.assertEqual(len(char.spellbook), 1)
        self.assertEqual(char.spellbook[0].name, "火球术")


class TestGameEngineCreation(unittest.TestCase):
    """引擎创建与角色初始化"""

    def test_engine_initial_state(self):
        engine = GameEngine()
        self.assertEqual(engine.state, GameState.STOPPED)
        self.assertIsNone(engine.character)
        self.assertEqual(len(engine.plot_chapters), 9)
        self.assertTrue(engine.plot_chapters[0].is_prologue)

    def test_create_character_unlocks_chapter_one(self):
        engine = GameEngine()
        engine.create_character("勇者", "人类", "战士")
        self.assertIsNotNone(engine.character)
        self.assertTrue(engine.plot_chapters[1].unlocked)
        self.assertEqual(engine._current_chapter_index, 1)
        self.assertIsNotNone(engine.current_quest)
        self.assertIsNotNone(engine.current_monster)
        self.assertGreaterEqual(len(engine.active_tasks), 3)

    def test_start_without_character_raises(self):
        engine = GameEngine()
        with self.assertRaises(ValueError):
            engine.start()


class TestGameEngineCombat(unittest.TestCase):
    """战斗流程测试"""

    def setUp(self):
        self.engine = GameEngine()
        self.engine.create_character("勇者", "人类", "战士")
        # 关闭日志打印
        self.engine.on_log = lambda msg: None

    def test_kill_monster_creates_new_monster(self):
        old_monster = self.engine.current_monster
        self.engine._kill_monster()
        # 由于会攻击，怪物 HP 可能降低；多 tick 几次直到杀死
        for _ in range(50):
            self.engine._kill_monster()
            if self.engine.current_monster is not old_monster:
                break
        self.assertIsNotNone(self.engine.current_monster)

    def test_loot_added_to_inventory(self):
        # 使用一个必定掉落、容易杀死的怪物
        self.engine.current_monster = Monster("测试怪", 1, 1, 10, [
            (Item("测试物品", 1, "misc"), 1.0)
        ])
        self.engine._kill_monster()
        item_names = [item.name for item in self.engine.character.inventory]
        self.assertIn("测试物品", item_names)

    def test_quest_progress_on_kill(self):
        self.engine.current_quest = Quest(
            name="测试", description="", target_monster="测试怪", target_count=1
        )
        self.engine.current_monster = Monster("测试怪", 1, 1, 10, [])
        self.engine._kill_monster()
        self.assertTrue(self.engine.current_quest.is_complete())


class TestGameEngineQuest(unittest.TestCase):
    """任务奖励与剧情推进测试"""

    def setUp(self):
        self.engine = GameEngine()
        self.engine.create_character("勇者", "人类", "战士")
        self.engine.on_log = lambda msg: None
        # 创建一个直接完成的任务
        self.engine.current_quest = Quest(
            name="测试任务", description="", target_monster="测试怪",
            target_count=1, reward_exp=100, reward_gold=50
        )
        self.engine.current_quest.current_count = 1

    def test_complete_quest_gives_exp_gold(self):
        with patch('random.choice', return_value='exp_gold'):
            self.engine._complete_quest()
        self.assertGreater(self.engine.character.exp, 0)
        self.assertEqual(self.engine.character.gold, 50)
        self.assertEqual(self.engine._quests_completed_total, 1)

    def test_complete_quest_unlocks_next_chapter(self):
        # 连续完成多个任务以解锁后续章节
        for _ in range(5):
            self.engine.current_quest = Quest(
                name="测试任务", description="", target_monster="测试怪",
                target_count=1, reward_exp=100, reward_gold=50
            )
            self.engine.current_quest.current_count = 1
            with patch('random.choice', return_value='exp_gold'):
                self.engine._complete_quest()
        self.assertTrue(self.engine.plot_chapters[2].unlocked)

    def test_quest_reward_handlers(self):
        # 分别测试五种奖励分支，直接调用奖励处理器以避免随机选择干扰
        for reward_type in ['exp_gold', 'special_item', 'equipment', 'stat_boost', 'new_spell']:
            engine = GameEngine()
            engine.create_character("勇者", "人类", "战士")
            engine.on_log = lambda msg: None
            engine.current_quest = Quest(
                name="测试任务", description="", target_monster="测试怪",
                target_count=1, reward_exp=100, reward_gold=50
            )
            engine.current_quest.current_count = 1
            with self.subTest(reward_type=reward_type):
                engine._apply_quest_reward(reward_type)
                self.assertEqual(engine._quests_completed_total, 0)


class TestGameEngineLevelUp(unittest.TestCase):
    """升级流程测试"""

    def setUp(self):
        self.engine = GameEngine()
        self.engine.create_character("勇者", "人类", "战士")
        self.engine.on_log = lambda msg: None

    def test_level_up(self):
        self.engine.character.exp = self.engine.exp_bar.max_value
        self.engine._level_up()
        self.assertEqual(self.engine.character.level, 2)
        self.assertGreater(self.engine.exp_bar.max_value, 1200)

    def test_game_tick_triggers_level_up(self):
        self.engine.character.exp = self.engine.exp_bar.max_value - 1
        self.engine._game_tick()
        self.assertGreaterEqual(self.engine.character.level, 2)


class TestGameEngineSaveLoad(unittest.TestCase):
    """存档/加载测试"""

    def setUp(self):
        self.engine = GameEngine()
        self.engine.create_character("勇者", "人类", "战士")
        self.engine.on_log = lambda msg: None

    def test_save_and_load_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "save.json")
            # 人为改变一些状态
            self.engine.character.gold = 999
            self.engine.character.exp = 500
            self.engine._quests_completed_total = 5
            self.engine.plot_chapters[2].unlocked = True
            self.engine.save(path)

            new_engine = GameEngine()
            new_engine.on_log = lambda msg: None
            new_engine.load(path)

            self.assertEqual(new_engine.character.name, "勇者")
            self.assertEqual(new_engine.character.gold, 999)
            self.assertEqual(new_engine.character.exp, 500)
            self.assertEqual(new_engine._quests_completed_total, 5)
            self.assertTrue(new_engine.plot_chapters[2].unlocked)
            self.assertEqual(len(new_engine.plot_chapters), len(self.engine.plot_chapters))

    def test_load_file_not_found(self):
        with self.assertRaises(FileNotFoundError):
            self.engine.load("不存在的存档.json")

    def test_save_without_character_raises(self):
        engine = GameEngine()
        with self.assertRaises(ValueError):
            engine.save("任意路径.json")


class TestGameEngineUIHelpers(unittest.TestCase):
    """UI 辅助方法测试"""

    def setUp(self):
        self.engine = GameEngine()
        self.engine.create_character("勇者", "人类", "战士")
        self.engine.on_log = lambda msg: None

    def test_get_ui_data_structure(self):
        data = self.engine.get_ui_data()
        self.assertIn('char', data)
        self.assertIn('equipment', data)
        self.assertIn('spellbook', data)
        self.assertIn('inventory', data)
        self.assertIn('bars', data)
        self.assertIn('quest', data)
        self.assertIn('monster', data)

    def test_get_bars(self):
        bars = self.engine.get_bars()
        self.assertIn('exp', bars)
        self.assertIn('plot', bars)
        self.assertIn('quest', bars)
        self.assertIn('encum', bars)

    def test_get_status_contains_character(self):
        status = self.engine.get_status()
        self.assertIn("勇者", status)
        self.assertIn("Lv.1", status)


class TestGameEngineEquipment(unittest.TestCase):
    """装备购买与装备槽测试"""

    def setUp(self):
        self.engine = GameEngine()
        self.engine.create_character("勇者", "人类", "战士")
        self.engine.on_log = lambda msg: None

    def test_buy_equipment_equips_weapon(self):
        self.engine.character.gold = 10000
        self.engine._buy_equipment()
        # 至少武器应该有装备（因为第一个商店物品是铁剑）
        self.assertIsNotNone(self.engine.character.equipment['weapon'])

    def test_find_possible_slots(self):
        item = Item("测试盔", 1, "helmet")
        slots = self.engine._get_possible_slots(item)
        self.assertEqual(slots, ['helm'])

    def test_equip_item_maps_correct_slot(self):
        item = Item("铁匠锤", 100, "weapon", {"strength": 3})
        self.engine._equip_item(item)
        self.assertEqual(self.engine.character.equipment['weapon'].name, "铁匠锤")


class TestGameEngineLifecycle(unittest.TestCase):
    """游戏生命周期控制"""

    def setUp(self):
        self.engine = GameEngine()
        self.engine.create_character("勇者", "人类", "战士")
        self.engine.on_log = lambda msg: None

    def test_pause_resume(self):
        self.engine.start()
        self.engine.pause()
        self.assertEqual(self.engine.state, GameState.PAUSED)
        self.assertTrue(self.engine._paused)
        self.engine.resume()
        self.assertEqual(self.engine.state, GameState.RUNNING)
        self.assertFalse(self.engine._paused)
        self.engine.stop()

    def test_stop(self):
        self.engine.start()
        self.engine.stop()
        self.assertEqual(self.engine.state, GameState.STOPPED)
        self.assertFalse(self.engine._running)


if __name__ == '__main__':
    unittest.main()
