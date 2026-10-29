"""Tests for the KeywordHandler - all 8 keywords."""

import unittest

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from models.keyword_handler import KeywordHandler
from models.card import Card
from models.player import Player
from models.enemy import Enemy
from models.deck_manager import DeckManager
from game.event_bus import EventBus


class TestKeywordDraw(unittest.TestCase):
    """Test Draw keyword."""

    def test_draw_cards(self):
        """Draw N should draw N cards from deck."""
        deck = DeckManager()
        cards = [Card(id=f"C{i:03d}", name=f"Card{i}") for i in range(10)]
        deck.build_initial_deck(cards)
        context = {"deck": deck, "player": Player(), "enemy": Enemy()}
        result = KeywordHandler.resolve("Draw", 2, context)
        self.assertIn("Drew 2 card(s)", result["message"])
        self.assertEqual(result["drawn"], 2)

    def test_draw_no_deck(self):
        """Draw without deck should return error message."""
        context = {"player": Player(), "enemy": Enemy()}
        result = KeywordHandler.resolve("Draw", 1, context)
        self.assertEqual(result["message"], "No deck available")


class TestKeywordExhaust(unittest.TestCase):
    """Test Exhaust keyword."""

    def test_exhaust_card(self):
        """Exhaust should move card to exhaust pile."""
        deck = DeckManager()
        cards = [Card(id=f"C{i:03d}", name=f"Card{i}") for i in range(5)]
        deck.build_initial_deck(cards)
        deck.draw(5)
        card = deck.hand[0]
        context = {"deck": deck, "card": card}
        result = KeywordHandler.resolve("Exhaust", 1, context)
        self.assertIn("exhausted", result["message"])
        self.assertEqual(deck.exhaust_pile_size, 1)

    def test_exhaust_no_card(self):
        """Exhaust without card should fail gracefully."""
        deck = DeckManager()
        context = {"deck": deck}
        result = KeywordHandler.resolve("Exhaust", 1, context)
        self.assertEqual(result["message"], "Exhaust failed")


class TestKeywordRepeat(unittest.TestCase):
    """Test Repeat keyword."""

    def test_repeat_returns_count(self):
        """Repeat should return the repeat count."""
        result = KeywordHandler.resolve("Repeat", 2, {})
        self.assertEqual(result["repeat_count"], 2)

    def test_repeat_message(self):
        """Repeat should include message."""
        result = KeywordHandler.resolve("Repeat", 1, {})
        self.assertIn("Repeats 1 time(s)", result["message"])


class TestKeywordGainStrength(unittest.TestCase):
    """Test GainStrength keyword."""

    def test_gain_strength(self):
        """GainStrength should increase player STR."""
        player = Player()
        context = {"player": player}
        result = KeywordHandler.resolve("GainStrength", 2, context)
        self.assertEqual(player.str, 3)  # 1 + 2
        self.assertIn("Gained 2 Strength", result["message"])

    def test_gain_strength_no_player(self):
        """GainStrength without player should return error."""
        context = {}
        result = KeywordHandler.resolve("GainStrength", 2, context)
        self.assertEqual(result["message"], "No player for GainStrength")


class TestKeywordConsume(unittest.TestCase):
    """Test Consume keyword."""

    def test_consume_card(self):
        """Consume should remove card from the run entirely."""
        deck = DeckManager()
        cards = [Card(id=f"C{i:03d}", name=f"Card{i}") for i in range(5)]
        deck.build_initial_deck(cards)
        deck.draw(5)
        card = deck.hand[0]
        context = {"deck": deck, "card": card}
        result = KeywordHandler.resolve("Consume", 1, context)
        self.assertIn("consumed", result["message"])
        self.assertEqual(deck.hand_size, 4)
        self.assertEqual(deck.exhaust_pile_size, 0)  # Not in exhaust


class TestKeywordStun(unittest.TestCase):
    """Test Stun keyword."""

    def test_stun_enemy(self):
        """Stun should apply stun to enemy."""
        enemy = Enemy()
        context = {"enemy": enemy}
        result = KeywordHandler.resolve("Stun", 2, context)
        self.assertTrue(enemy.is_stunned())
        self.assertEqual(enemy.stun_count, 2)

    def test_stun_no_enemy(self):
        """Stun without enemy should return error."""
        context = {}
        result = KeywordHandler.resolve("Stun", 1, context)
        self.assertEqual(result["message"], "No enemy to stun")


class TestKeywordLifesteal(unittest.TestCase):
    """Test Lifesteal keyword."""

    def test_lifesteal_heals(self):
        """Lifesteal should heal player based on damage dealt percentage."""
        player = Player()
        player.take_damage(30)  # HP=30
        context = {"player": player, "damage_dealt": 20}
        result = KeywordHandler.resolve("Lifesteal", 50, context)
        # 50% of 20 = 10
        self.assertEqual(result["healed"], 10)
        self.assertEqual(player.hp, 40)  # 30 + 10

    def test_lifesteal_minimum_1(self):
        """Lifesteal should heal at least 1 HP when damage dealt > 0."""
        player = Player()
        player.take_damage(50)  # HP=10
        context = {"player": player, "damage_dealt": 1}
        result = KeywordHandler.resolve("Lifesteal", 50, context)
        # 50% of 1 = 0.5 -> max(1, 0) = 1
        self.assertGreaterEqual(result["healed"], 1)

    def test_lifesteal_no_damage(self):
        """Lifesteal with no damage dealt should return message."""
        context = {"player": Player(), "damage_dealt": 0}
        result = KeywordHandler.resolve("Lifesteal", 50, context)
        self.assertEqual(result["message"], "Lifesteal: no damage to steal")

    def test_lifesteal_no_player(self):
        """Lifesteal without player should return message."""
        context = {"damage_dealt": 10}
        result = KeywordHandler.resolve("Lifesteal", 50, context)
        self.assertEqual(result["message"], "Lifesteal: no damage to steal")


class TestKeywordVulnerable(unittest.TestCase):
    """Test Vulnerable keyword."""

    def test_vulnerable_applies(self):
        """Vulnerable should apply to enemy."""
        enemy = Enemy()
        context = {"enemy": enemy}
        result = KeywordHandler.resolve("Vulnerable", 2, context)
        self.assertEqual(enemy.vulnerable, 2)
        self.assertIn("Applied 2 Vulnerable", result["message"])

    def test_vulnerable_no_enemy(self):
        """Vulnerable without enemy should return error."""
        context = {}
        result = KeywordHandler.resolve("Vulnerable", 1, context)
        self.assertEqual(result["message"], "No enemy for Vulnerable")


class TestKeywordUnknown(unittest.TestCase):
    """Test unknown keyword handling."""

    def test_unknown_keyword(self):
        """Unknown keyword should return error message."""
        result = KeywordHandler.resolve("UnknownKeyword", 1, {})
        self.assertIn("Unknown keyword", result["message"])


if __name__ == "__main__":
    unittest.main()
