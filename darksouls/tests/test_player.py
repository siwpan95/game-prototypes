"""Tests for the Player model - stats, HP/FP, damage/heal/block, deck setup."""

import unittest

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from models.player import Player
from models.card import Card


class TestPlayerInit(unittest.TestCase):
    """Test Player initialization and initial stats."""

    def test_initial_stats(self):
        """Player should start with STR=1, DEX=1, VIT=1, FCS=1."""
        p = Player()
        self.assertEqual(p.str, 1)
        self.assertEqual(p.dex, 1)
        self.assertEqual(p.vit, 1)
        self.assertEqual(p.fcs, 1)

    def test_initial_hp(self):
        """Initial HP should be 50 + VIT*10 = 60."""
        p = Player()
        self.assertEqual(p.max_hp, 60)
        self.assertEqual(p.hp, 60)

    def test_initial_fp(self):
        """Initial FP should be 3 + FCS = 4."""
        p = Player()
        self.assertEqual(p.max_fp, 4)
        self.assertEqual(p.fp, 4)

    def test_initial_block(self):
        """Player should start with 0 block."""
        p = Player()
        self.assertEqual(p.block, 0)

    def test_initial_souls(self):
        """Player should start with 0 souls."""
        p = Player()
        self.assertEqual(p.souls, 0)


class TestPlayerHPManipulation(unittest.TestCase):
    """Test HP modification methods."""

    def test_take_damage_no_block(self):
        """Taking damage without block should reduce HP directly."""
        p = Player()
        damage = p.take_damage(10)
        self.assertEqual(p.hp, 50)  # 60 - 10
        self.assertEqual(damage, 10)  # actual HP damage

    def test_take_damage_with_block(self):
        """Taking damage with block should reduce block first."""
        p = Player()
        p.gain_block(5)
        damage = p.take_damage(10)
        self.assertEqual(p.block, 0)
        self.assertEqual(p.hp, 55)  # 60 - (10-5)
        self.assertEqual(damage, 5)

    def test_take_damage_block_absorbs_all(self):
        """Block should absorb damage up to its value."""
        p = Player()
        p.gain_block(10)
        damage = p.take_damage(5)
        self.assertEqual(p.block, 5)  # 10-5 remaining
        self.assertEqual(p.hp, 60)  # no HP damage
        self.assertEqual(damage, 0)  # no HP damage dealt

    def test_take_damage_hp_min_zero(self):
        """HP should not go below 0."""
        p = Player()
        p.take_damage(100)
        self.assertEqual(p.hp, 0)

    def test_is_dead(self):
        """is_dead should return True when HP <= 0."""
        p = Player()
        self.assertFalse(p.is_dead())
        p.take_damage(60)
        self.assertTrue(p.is_dead())

    def test_heal(self):
        """Healing should increase HP up to max_hp."""
        p = Player()
        p.take_damage(20)
        healed = p.heal(10)
        self.assertEqual(p.hp, 50)  # 40 + 10
        self.assertEqual(healed, 10)

    def test_heal_capped_at_max(self):
        """Healing should not exceed max_hp."""
        p = Player()
        p.take_damage(5)
        healed = p.heal(100)
        self.assertEqual(p.hp, 60)
        self.assertEqual(healed, 5)  # only 5 actually healed

    def test_heal_percent(self):
        """heal_percent should heal a percentage of max HP."""
        p = Player()
        p.take_damage(30)  # HP=30
        healed = p.heal_percent(0.5)  # 50% of 60 = 30
        self.assertEqual(p.hp, 60)  # 30 + 30
        self.assertEqual(healed, 30)


class TestPlayerBlock(unittest.TestCase):
    """Test block mechanics."""

    def test_gain_block(self):
        """gain_block should add to block."""
        p = Player()
        result = p.gain_block(5)
        self.assertEqual(p.block, 5)
        self.assertEqual(result, 5)

    def test_gain_block_stacking(self):
        """Block should stack additively."""
        p = Player()
        p.gain_block(3)
        p.gain_block(4)
        self.assertEqual(p.block, 7)

    def test_reset_block(self):
        """reset_block should set block to 0."""
        p = Player()
        p.gain_block(10)
        p.reset_block()
        self.assertEqual(p.block, 0)

    def test_block_resets_each_turn(self):
        """Block should reset at start of each turn (simulate turn cycle)."""
        p = Player()
        p.gain_block(10)
        p.reset_block()  # End of turn
        self.assertEqual(p.block, 0)


class TestPlayerFP(unittest.TestCase):
    """Test FP (Focus Points) mechanics."""

    def test_reset_fp(self):
        """reset_fp should restore FP to max_fp."""
        p = Player()
        p.fp -= 2
        p.reset_fp()
        self.assertEqual(p.fp, p.max_fp)

    def test_fp_resets_each_turn(self):
        """FP should reset at start of each turn."""
        p = Player()
        p.fp -= 3
        p.reset_fp()
        self.assertEqual(p.fp, 4)  # max_fp = 3 + 1 = 4


class TestPlayerDerivedStats(unittest.TestCase):
    """Test derived stat recalculation."""

    def test_recalculate_after_vit_increase(self):
        """Increasing VIT should increase max_hp."""
        p = Player()
        p.add_stat_point("vit", 2)
        self.assertEqual(p.max_hp, 80)  # 50 + (1+2)*10

    def test_recalculate_after_fcs_increase(self):
        """Increasing FCS should increase max_fp."""
        p = Player()
        p.add_stat_point("fcs", 2)
        self.assertEqual(p.max_fp, 6)  # 3 + (1+2)

    def test_add_stat_str(self):
        """add_stat_point should increase STR."""
        p = Player()
        p.add_stat_point("str", 3)
        self.assertEqual(p.str, 4)

    def test_add_stat_dex(self):
        """add_stat_point should increase DEX."""
        p = Player()
        p.add_stat_point("dex", 2)
        self.assertEqual(p.dex, 3)

    def test_add_stat_case_insensitive(self):
        """add_stat_point should be case-insensitive."""
        p = Player()
        p.add_stat_point("STR", 1)
        self.assertEqual(p.str, 2)

    def test_max_hp_setter_caps_hp(self):
        """Setting max_hp below current hp should cap hp."""
        p = Player()
        p.max_hp = 30
        self.assertEqual(p.hp, 30)  # capped to new max

    def test_max_hp_setter_minimum_1(self):
        """max_hp should not go below 1."""
        p = Player()
        p.max_hp = -5
        self.assertEqual(p.max_hp, 1)

    def test_max_fp_setter_caps_fp(self):
        """Setting max_fp below current fp should cap fp."""
        p = Player()
        p.max_fp = 1
        self.assertEqual(p.fp, 1)

    def test_max_fp_setter_minimum_1(self):
        """max_fp should not go below 1."""
        p = Player()
        p.max_fp = -5
        self.assertEqual(p.max_fp, 1)


class TestPlayerSouls(unittest.TestCase):
    """Test souls spending."""

    def test_spend_souls_success(self):
        """spend_souls should deduct souls and return True."""
        p = Player()
        p.souls = 100
        result = p.spend_souls(30)
        self.assertTrue(result)
        self.assertEqual(p.souls, 70)

    def test_spend_souls_insufficient(self):
        """spend_souls should return False if not enough."""
        p = Player()
        p.souls = 20
        result = p.spend_souls(30)
        self.assertFalse(result)
        self.assertEqual(p.souls, 20)

    def test_spend_souls_exact_amount(self):
        """spend_souls with exact amount should succeed."""
        p = Player()
        p.souls = 50
        result = p.spend_souls(50)
        self.assertTrue(result)
        self.assertEqual(p.souls, 0)


class TestPlayerDeckSetup(unittest.TestCase):
    """Test initial deck setup."""

    def test_setup_initial_deck(self):
        """setup_initial_deck should create 5 Strike + 3 Defend + 2 Backstab."""
        p = Player()

        def card_factory(card_id):
            if card_id == "C001":
                return Card(id="C001", name="Strike")
            elif card_id == "C007":
                return Card(id="C007", name="Defend")
            elif card_id == "C006":
                return Card(id="C006", name="Backstab")
            return None

        p.setup_initial_deck(card_factory)
        # All 10 cards should be in the draw pile (shuffled)
        total = p.deck.draw_pile_size + p.deck.hand_size + p.deck.discard_pile_size
        self.assertEqual(total, 10)


if __name__ == "__main__":
    unittest.main()
