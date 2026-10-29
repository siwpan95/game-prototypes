"""Tests for the Enemy model - AI, intent, damage, stun, vulnerable."""

import unittest
from unittest.mock import patch

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from models.enemy import Enemy
from models.card import Card


class TestEnemyInit(unittest.TestCase):
    """Test Enemy initialization."""

    def test_default_enemy(self):
        """Default enemy should have standard values."""
        e = Enemy()
        self.assertEqual(e.id, "")
        self.assertEqual(e.name, "")
        self.assertEqual(e.hp, 30)
        self.assertEqual(e.max_hp, 30)
        self.assertEqual(e.block, 0)
        self.assertFalse(e.is_boss)

    def test_boss_has_2_actions(self):
        """Boss enemies should have 2 actions per turn."""
        boss = Enemy(is_boss=True)
        self.assertEqual(boss.actions_per_turn, 2)

    def test_normal_enemy_has_1_action(self):
        """Normal enemies should have 1 action per turn."""
        normal = Enemy(is_boss=False)
        self.assertEqual(normal.actions_per_turn, 1)

    def test_custom_enemy(self):
        """Custom enemy should accept all parameters."""
        e = Enemy(
            id="E001", name="Lothric Knight", hp=45,
            str=3, dex=2, ai={"Attack": 0.7, "Defend": 0.3},
            card_pool=["EC001", "EC002"], act=1,
            is_boss=False, souls=30
        )
        self.assertEqual(e.id, "E001")
        self.assertEqual(e.name, "Lothric Knight")
        self.assertEqual(e.hp, 45)
        self.assertEqual(e.max_hp, 45)
        self.assertEqual(e.str, 3)
        self.assertEqual(e.souls, 30)
        self.assertFalse(e.is_boss)


class TestEnemyDamage(unittest.TestCase):
    """Test enemy damage mechanics."""

    def test_take_damage_no_block(self):
        """Taking damage without block should reduce HP."""
        e = Enemy(hp=30)
        damage = e.take_damage(10)
        self.assertEqual(e.hp, 20)
        self.assertEqual(damage, 10)

    def test_take_damage_with_block(self):
        """Block should absorb damage first."""
        e = Enemy(hp=30)
        e.gain_block(5)
        damage = e.take_damage(10)
        self.assertEqual(e.hp, 25)  # 30 - (10-5)
        self.assertEqual(e.block, 0)
        self.assertEqual(damage, 5)

    def test_take_damage_block_absorbs_all(self):
        """Block should absorb all damage if sufficient."""
        e = Enemy(hp=30)
        e.gain_block(15)
        damage = e.take_damage(10)
        self.assertEqual(e.hp, 30)
        self.assertEqual(e.block, 5)
        self.assertEqual(damage, 0)

    def test_take_damage_vulnerable(self):
        """Vulnerable enemies should take 50% more damage."""
        e = Enemy(hp=30)
        e.apply_vulnerable(1)
        damage = e.take_damage(10)
        self.assertEqual(damage, 15)  # 10 * 1.5
        self.assertEqual(e.hp, 15)  # 30 - 15

    def test_take_damage_hp_min_zero(self):
        """HP should not go below 0."""
        e = Enemy(hp=10)
        e.take_damage(50)
        self.assertEqual(e.hp, 0)

    def test_is_dead(self):
        """is_dead should return True when HP <= 0."""
        e = Enemy(hp=10)
        self.assertFalse(e.is_dead())
        e.take_damage(10)
        self.assertTrue(e.is_dead())


class TestEnemyBlock(unittest.TestCase):
    """Test enemy block mechanics."""

    def test_gain_block(self):
        """gain_block should increase block."""
        e = Enemy()
        result = e.gain_block(5)
        self.assertEqual(e.block, 5)
        self.assertEqual(result, 5)

    def test_reset_block(self):
        """reset_block should set block to 0."""
        e = Enemy()
        e.gain_block(10)
        e.reset_block()
        self.assertEqual(e.block, 0)


class TestEnemyVulnerable(unittest.TestCase):
    """Test enemy vulnerable status."""

    def test_apply_vulnerable(self):
        """apply_vulnerable should increase vulnerable counter."""
        e = Enemy()
        e.apply_vulnerable(2)
        self.assertEqual(e.vulnerable, 2)

    def test_tick_vulnerable(self):
        """tick_vulnerable should decrease vulnerable by 1."""
        e = Enemy()
        e.apply_vulnerable(2)
        e.tick_vulnerable()
        self.assertEqual(e.vulnerable, 1)

    def test_tick_vulnerable_at_zero(self):
        """tick_vulnerable at 0 should not go negative."""
        e = Enemy()
        e.tick_vulnerable()
        self.assertEqual(e.vulnerable, 0)


class TestEnemyStun(unittest.TestCase):
    """Test enemy stun mechanics."""

    def test_apply_stun(self):
        """apply_stun should set stun count."""
        e = Enemy()
        e.apply_stun(2)
        self.assertEqual(e.stun_count, 2)
        self.assertTrue(e.is_stunned())

    def test_tick_stun(self):
        """tick_stun should decrease stun count."""
        e = Enemy()
        e.apply_stun(1)
        e.tick_stun()
        self.assertEqual(e.stun_count, 0)
        self.assertFalse(e.is_stunned())

    def test_tick_stun_at_zero(self):
        """tick_stun at 0 should not go negative."""
        e = Enemy()
        e.tick_stun()
        self.assertEqual(e.stun_count, 0)

    def test_not_stunned_by_default(self):
        """Enemy should not be stunned by default."""
        e = Enemy()
        self.assertFalse(e.is_stunned())


class TestEnemySetIntent(unittest.TestCase):
    """Test enemy intent setting (AI)."""

    @patch("models.enemy.random.choices")
    def test_set_intent_attack(self, mock_choices):
        """set_intent should set Attack intent based on AI weights."""
        e = Enemy(ai={"Attack": 0.8, "Defend": 0.2})
        mock_choices.return_value = ["Attack"]
        e.set_intent()
        self.assertEqual(e.intent, "Attack")

    @patch("models.enemy.random.choices")
    def test_set_intent_defend(self, mock_choices):
        """set_intent should set Defend intent."""
        e = Enemy(ai={"Attack": 0.2, "Defend": 0.8})
        mock_choices.return_value = ["Defend"]
        e.set_intent()
        self.assertEqual(e.intent, "Defend")

    @patch("models.enemy.random.choices")
    def test_set_intent_with_card_lookup(self, mock_choices):
        """set_intent should use card_lookup to set intent_value."""
        e = Enemy(
            ai={"Attack": 0.8, "Defend": 0.2},
            card_pool=["EC001"]
        )
        mock_choices.return_value = ["Attack"]

        def card_lookup(cid):
            if cid == "EC001":
                return Card(id="EC001", name="Knight Thrust", type="Attack", damage="1d6+2")
            return None

        e.set_intent(card_lookup)
        self.assertEqual(e.intent, "Attack")
        self.assertEqual(e.intent_value, "1d6+2")

    @patch("models.enemy.random.choices")
    def test_set_intent_defend_card(self, mock_choices):
        """set_intent with Defend should show Block intent_value."""
        e = Enemy(
            ai={"Attack": 0.2, "Defend": 0.8},
            card_pool=["EC002"]
        )
        mock_choices.return_value = ["Defend"]

        def card_lookup(cid):
            if cid == "EC002":
                return Card(id="EC002", name="Knight Shield", type="Skill", block=4)
            return None

        e.set_intent(card_lookup)
        self.assertEqual(e.intent, "Defend")
        self.assertEqual(e.intent_value, "Block 4")


class TestEnemyRepr(unittest.TestCase):
    """Test Enemy repr."""

    def test_repr(self):
        """repr should show id, name, and HP."""
        e = Enemy(id="E001", name="Lothric Knight", hp=45)
        self.assertIn("E001", repr(e))
        self.assertIn("Lothric Knight", repr(e))


if __name__ == "__main__":
    unittest.main()
