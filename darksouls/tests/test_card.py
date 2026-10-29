"""Tests for the Card model."""

import unittest

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from models.card import Card


class TestCard(unittest.TestCase):
    """Test cases for the Card dataclass."""

    def test_card_default_values(self):
        """Card should have sensible defaults."""
        card = Card()
        self.assertEqual(card.id, "")
        self.assertEqual(card.name, "")
        self.assertEqual(card.cost, 0)
        self.assertEqual(card.type, "Attack")
        self.assertEqual(card.damage, "0")
        self.assertEqual(card.block, 0)
        self.assertEqual(card.keywords, {})
        self.assertEqual(card.description, "")
        self.assertEqual(card.source, "Player")

    def test_card_custom_values(self):
        """Card should accept custom values."""
        card = Card(
            id="C001", name="Strike", cost=1, type="Attack",
            damage="2d6+STR", block=0, keywords={"Draw": 1},
            description="Basic attack", source="Player"
        )
        self.assertEqual(card.id, "C001")
        self.assertEqual(card.name, "Strike")
        self.assertEqual(card.cost, 1)
        self.assertEqual(card.type, "Attack")
        self.assertEqual(card.damage, "2d6+STR")
        self.assertEqual(card.block, 0)
        self.assertEqual(card.keywords, {"Draw": 1})
        self.assertEqual(card.description, "Basic attack")
        self.assertEqual(card.source, "Player")

    def test_card_keywords_default_empty_dict(self):
        """Each Card should get its own keywords dict, not share one."""
        card1 = Card()
        card2 = Card()
        card1.keywords["Draw"] = 1
        self.assertEqual(card2.keywords, {})

    def test_is_attack(self):
        """is_attack should return True only for Attack type cards."""
        attack = Card(type="Attack")
        skill = Card(type="Skill")
        power = Card(type="Power")
        self.assertTrue(attack.is_attack())
        self.assertFalse(skill.is_attack())
        self.assertFalse(power.is_attack())

    def test_is_skill(self):
        """is_skill should return True only for Skill type cards."""
        attack = Card(type="Attack")
        skill = Card(type="Skill")
        power = Card(type="Power")
        self.assertFalse(attack.is_skill())
        self.assertTrue(skill.is_skill())
        self.assertFalse(power.is_skill())

    def test_has_keyword_true(self):
        """has_keyword should return True if keyword exists."""
        card = Card(keywords={"Draw": 1, "Exhaust": 1})
        self.assertTrue(card.has_keyword("Draw"))
        self.assertTrue(card.has_keyword("Exhaust"))

    def test_has_keyword_false(self):
        """has_keyword should return False if keyword does not exist."""
        card = Card(keywords={"Draw": 1})
        self.assertFalse(card.has_keyword("Stun"))
        self.assertFalse(card.has_keyword(""))

    def test_has_keyword_empty_keywords(self):
        """has_keyword should return False for empty keywords dict."""
        card = Card(keywords={})
        self.assertFalse(card.has_keyword("Draw"))

    def test_repr(self):
        """repr should show card id and name."""
        card = Card(id="C001", name="Strike")
        self.assertEqual(repr(card), "Card(C001: Strike)")


if __name__ == "__main__":
    unittest.main()
