"""Tests for the DataLoader - JSON loading and object factory methods."""

import unittest

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from services.data_loader import DataLoader
from models.card import Card
from models.enemy import Enemy
from models.relic import Relic


BASE_PATH = os.path.join(os.path.dirname(__file__), "..")


class TestDataLoaderCards(unittest.TestCase):
    """Test card data loading and factory."""

    def setUp(self):
        self.loader = DataLoader(BASE_PATH)

    def test_load_cards(self):
        """load_cards should return a list of card dicts."""
        cards = self.loader.load_cards()
        self.assertIsInstance(cards, list)
        self.assertGreater(len(cards), 0)

    def test_get_card_data(self):
        """get_card_data should return a specific card dict."""
        data = self.loader.get_card_data("C001")
        self.assertIsNotNone(data)
        self.assertEqual(data["id"], "C001")
        self.assertEqual(data["name"], "Strike")

    def test_get_card_data_not_found(self):
        """get_card_data should return None for nonexistent ID."""
        data = self.loader.get_card_data("C999")
        self.assertIsNone(data)

    def test_create_card(self):
        """create_card should return a Card instance."""
        card = self.loader.create_card("C001")
        self.assertIsInstance(card, Card)
        self.assertEqual(card.id, "C001")
        self.assertEqual(card.name, "Strike")
        self.assertEqual(card.cost, 1)
        self.assertEqual(card.type, "Attack")
        self.assertEqual(card.damage, "2d6+STR")
        self.assertEqual(card.block, 0)

    def test_create_card_not_found(self):
        """create_card should return None for nonexistent ID."""
        card = self.loader.create_card("C999")
        self.assertIsNone(card)

    def test_create_defend_card(self):
        """create_card should create Defend card correctly."""
        card = self.loader.create_card("C007")
        self.assertIsNotNone(card)
        self.assertEqual(card.name, "Defend")
        self.assertEqual(card.block, 5)
        self.assertEqual(card.type, "Skill")

    def test_get_player_cards(self):
        """get_player_cards should only return Player-source cards."""
        cards = self.loader.get_player_cards()
        for c in cards:
            self.assertEqual(c["source"], "Player")

    def test_card_has_keywords(self):
        """Cards from JSON should have keywords dict."""
        card = self.loader.create_card("C001")
        self.assertIsNotNone(card.keywords)
        self.assertIn("Draw", card.keywords)
        self.assertEqual(card.keywords["Draw"], 1)


class TestDataLoaderEnemies(unittest.TestCase):
    """Test enemy data loading and factory."""

    def setUp(self):
        self.loader = DataLoader(BASE_PATH)

    def test_load_enemies(self):
        """load_enemies should return a list of enemy dicts."""
        enemies = self.loader.load_enemies()
        self.assertIsInstance(enemies, list)
        self.assertGreater(len(enemies), 0)

    def test_create_enemy(self):
        """create_enemy should return an Enemy instance."""
        enemy = self.loader.create_enemy("E001")
        self.assertIsInstance(enemy, Enemy)
        self.assertEqual(enemy.name, "Lothric Knight")
        self.assertEqual(enemy.hp, 45)
        self.assertEqual(enemy.str, 3)
        self.assertFalse(enemy.is_boss)

    def test_create_boss(self):
        """create_enemy for a boss ID should set is_boss=True."""
        boss = self.loader.create_enemy("B001")
        self.assertIsNotNone(boss)
        self.assertTrue(boss.is_boss)
        self.assertEqual(boss.name, "Abyss Watchers")
        self.assertEqual(boss.actions_per_turn, 2)

    def test_create_enemy_not_found(self):
        """create_enemy should return None for nonexistent ID."""
        enemy = self.loader.create_enemy("E999")
        self.assertIsNone(enemy)

    def test_get_enemies_for_act(self):
        """get_enemies_for_act should return non-boss enemies for that act."""
        enemies = self.loader.get_enemies_for_act(1)
        self.assertGreater(len(enemies), 0)
        for e in enemies:
            self.assertEqual(e["act"], 1)
            self.assertFalse(e["is_boss"])

    def test_get_boss_for_act(self):
        """get_boss_for_act should return the boss for that act."""
        boss = self.loader.get_boss_for_act(1)
        self.assertIsNotNone(boss)
        self.assertTrue(boss["is_boss"])
        self.assertEqual(boss["act"], 1)

    def test_get_boss_for_act_none(self):
        """get_boss_for_act should return None for nonexistent act."""
        boss = self.loader.get_boss_for_act(99)
        self.assertIsNone(boss)


class TestDataLoaderRelics(unittest.TestCase):
    """Test relic data loading and factory."""

    def setUp(self):
        self.loader = DataLoader(BASE_PATH)

    def test_create_relic(self):
        """create_relic should return a Relic instance."""
        relic = self.loader.create_relic("R001")
        self.assertIsInstance(relic, Relic)
        self.assertEqual(relic.name, "Ring of Favor")
        self.assertEqual(relic.trigger, "on_battle_start")

    def test_create_relic_not_found(self):
        """create_relic should return None for nonexistent ID."""
        relic = self.loader.create_relic("R999")
        self.assertIsNone(relic)

    def test_relic_has_effect(self):
        """Relics should have effect dicts."""
        relic = self.loader.create_relic("R001")
        self.assertIn("AddMaxHP", relic.effect)
        self.assertEqual(relic.effect["AddMaxHP"], 15)


class TestDataLoaderEvents(unittest.TestCase):
    """Test event data loading."""

    def setUp(self):
        self.loader = DataLoader(BASE_PATH)

    def test_load_events(self):
        """load_events should return a list of event dicts."""
        events = self.loader.load_events()
        self.assertIsInstance(events, list)
        self.assertGreater(len(events), 0)

    def test_get_event_data(self):
        """get_event_data should return specific event dict."""
        data = self.loader.get_event_data("EV_FIRE_01")
        self.assertIsNotNone(data)
        self.assertEqual(data["type"], "bonfire")

    def test_get_events_for_act(self):
        """get_events_for_act should return events (currently shared across acts)."""
        events = self.loader.get_events_for_act(1)
        self.assertGreater(len(events), 0)


class TestDataLoaderActs(unittest.TestCase):
    """Test act data loading."""

    def setUp(self):
        self.loader = DataLoader(BASE_PATH)

    def test_load_acts(self):
        """load_acts should return a list of act dicts."""
        acts = self.loader.load_acts()
        self.assertIsInstance(acts, list)
        self.assertEqual(len(acts), 3)

    def test_get_act_data(self):
        """get_act_data should return specific act dict."""
        act = self.loader.get_act_data(1)
        self.assertIsNotNone(act)
        self.assertEqual(act["name"], "Lothric Wall")

    def test_get_act_data_not_found(self):
        """get_act_data should return None for nonexistent act."""
        act = self.loader.get_act_data(99)
        self.assertIsNone(act)


class TestDataLoaderCaching(unittest.TestCase):
    """Test that DataLoader caches data properly."""

    def test_cards_cached(self):
        """Second call to load_cards should return same object."""
        loader = DataLoader(BASE_PATH)
        first = loader.load_cards()
        second = loader.load_cards()
        self.assertIs(first, second)


if __name__ == "__main__":
    unittest.main()
