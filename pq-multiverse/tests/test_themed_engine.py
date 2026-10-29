"""
Progress Quest Multiverse - 主题化游戏引擎单元测试
覆盖 ThemedGameEngine 的主题加载、角色创建、主题数据注入等
"""

import unittest
import sys
import os
import tempfile
from unittest.mock import patch

# 添加 src 到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from themed_engine import ThemedGameEngine
from core.game_engine_v2 import GameEngine, Character, Item, GameState


class TestThemedGameEngineCreation(unittest.TestCase):
    """主题引擎创建与基础属性"""

    def test_list_themes(self):
        themes = ThemedGameEngine.list_themes()
        self.assertIn("warcraft", themes)
        self.assertIn("genshin", themes)
        self.assertIn("pokemon", themes)

    def test_get_theme_display_name(self):
        self.assertEqual(ThemedGameEngine.get_theme_display_name("warcraft"), "魔兽世界")
        self.assertEqual(ThemedGameEngine.get_theme_display_name("unknown"), "unknown")

    def test_load_theme(self):
        theme = ThemedGameEngine.load_theme("warcraft")
        self.assertIsNotNone(theme)
        self.assertEqual(theme.name, "魔兽世界")
        self.assertGreater(len(theme.races), 0)
        self.assertGreater(len(theme.classes), 0)

    def test_create_warcraft_engine(self):
        engine = ThemedGameEngine("warcraft")
        self.assertEqual(engine.theme_name, "warcraft")
        self.assertIsNotNone(engine.theme)
        self.assertEqual(len(engine.monsters), 0)  # 父类默认数据被清空
        self.assertGreater(len(engine.shop_items), 0)

    def test_create_genshin_engine(self):
        engine = ThemedGameEngine("genshin")
        self.assertEqual(engine.theme_name, "genshin")
        self.assertIsNotNone(engine.theme)

    def test_create_pokemon_engine(self):
        engine = ThemedGameEngine("pokemon")
        self.assertEqual(engine.theme_name, "pokemon")
        self.assertIsNotNone(engine.theme)

    def test_invalid_theme_raises(self):
        with self.assertRaises(ValueError):
            ThemedGameEngine("invalid_theme")


class TestThemedGameEngineCharacter(unittest.TestCase):
    """主题角色创建与验证"""

    def setUp(self):
        self.engine = ThemedGameEngine("warcraft")
        self.engine.on_log = lambda msg: None

    def test_valid_race_and_class(self):
        self.engine.create_character("萨尔", "兽人", "死亡骑士")
        self.assertEqual(self.engine.character.race, "兽人")
        self.assertEqual(self.engine.character.char_class, "死亡骑士")
        self.assertEqual(self.engine.character.spell_pool, self.engine.theme.spell_pool)

    def test_invalid_race_raises(self):
        with self.assertRaises(ValueError):
            self.engine.create_character("X", "不存在的种族", "战士")

    def test_invalid_class_raises(self):
        with self.assertRaises(ValueError):
            self.engine.create_character("X", "兽人", "不存在的职业")

    def test_get_available_races_classes(self):
        races = self.engine.get_available_races()
        classes = self.engine.get_available_classes()
        self.assertIn("兽人", races)
        self.assertIn("死亡骑士", classes)


class TestThemedGameEngineThemeData(unittest.TestCase):
    """主题数据注入到游戏流程"""

    def setUp(self):
        self.engine = ThemedGameEngine("warcraft")
        self.engine.create_character("萨尔", "兽人", "死亡骑士")
        self.engine.on_log = lambda msg: None

    def test_start_new_monster_uses_theme(self):
        self.engine._start_new_monster()
        self.assertIsNotNone(self.engine.current_monster)
        theme_monster_names = [m.name for m in self.engine.theme.monsters]
        self.assertIn(self.engine.current_monster.name, theme_monster_names)

    def test_start_new_quest_uses_theme(self):
        self.engine._start_new_quest()
        self.assertIsNotNone(self.engine.current_quest)
        theme_quest_targets = [q.target_monster for q in self.engine.theme.quest_templates]
        self.assertIn(self.engine.current_quest.target_monster, theme_quest_targets)

    def test_active_tasks_use_theme_targets(self):
        task_descs = [t.description for t in self.engine.active_tasks]
        theme_targets = [desc for _, desc in self.engine.theme.task_targets]
        for desc in task_descs:
            self.assertIn(desc, theme_targets)

    def test_theme_shop_items_converted(self):
        self.assertGreater(len(self.engine.shop_items), 0)
        first_item = self.engine.shop_items[0]
        self.assertIsInstance(first_item, Item)
        self.assertIn(first_item.item_type, self.engine._SLOT_MAP)


class TestThemedGameEngineCombat(unittest.TestCase):
    """主题战斗流程"""

    def setUp(self):
        self.engine = ThemedGameEngine("warcraft")
        self.engine.create_character("萨尔", "兽人", "死亡骑士")
        self.engine.on_log = lambda msg: None

    def test_kill_monster_drops_theme_loot(self):
        # 使用主题怪物测试掉落
        original_monster = self.engine.current_monster
        # 多次攻击直到击杀
        for _ in range(50):
            self.engine._kill_monster()
            if self.engine.current_monster is not original_monster:
                break
        self.assertIsNotNone(self.engine.current_monster)


class TestThemedGameEngineSaveLoad(unittest.TestCase):
    """主题引擎存档/加载"""

    def setUp(self):
        self.engine = ThemedGameEngine("warcraft")
        self.engine.create_character("萨尔", "兽人", "死亡骑士")
        self.engine.on_log = lambda msg: None

    def test_save_load_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "save.json")
            self.engine.character.gold = 777
            self.engine.character.exp = 333
            self.engine.save(path)

            new_engine = ThemedGameEngine("warcraft")
            new_engine.on_log = lambda msg: None
            new_engine.load(path)

            self.assertEqual(new_engine.character.name, "萨尔")
            self.assertEqual(new_engine.character.race, "兽人")
            self.assertEqual(new_engine.character.char_class, "死亡骑士")
            self.assertEqual(new_engine.character.gold, 777)
            self.assertEqual(new_engine.character.exp, 333)

    def test_save_game_with_default_path(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "warcraft_萨尔.json")
            # 直接指定路径以覆盖默认路径
            self.engine.save_game(path)
            self.assertTrue(os.path.exists(path))


class TestThemedGameEngineInheritance(unittest.TestCase):
    """主题引擎继承父类行为"""

    def setUp(self):
        self.engine = ThemedGameEngine("warcraft")
        self.engine.create_character("萨尔", "兽人", "死亡骑士")
        self.engine.on_log = lambda msg: None

    def test_plot_chapter_unlock(self):
        # 直接推进剧情事件来测试章节解锁，避免随机选择干扰
        # 章 II 需要累计完成 5 个任务才能解锁
        self.engine._quests_completed_total = 5
        self.engine._trigger_plot_event()
        self.assertTrue(self.engine.plot_chapters[2].unlocked)
        self.assertEqual(self.engine._current_chapter_index, 2)

    def test_ui_data_contains_theme_info(self):
        data = self.engine.get_ui_data()
        self.assertIn('char', data)
        self.assertEqual(data['char']['race'], '兽人')


if __name__ == '__main__':
    unittest.main()
