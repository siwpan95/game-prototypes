"""Tests for the DiceEngine - d20 rolls, dice notation parsing, crit/mishap."""

import unittest
from unittest.mock import patch

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from models.dice_engine import DiceEngine, DiceResult


class TestDiceResult(unittest.TestCase):
    """Test cases for the DiceResult data class."""

    def test_default_values(self):
        """DiceResult should have sensible defaults."""
        result = DiceResult(total=10, rolls=[3, 4, 3])
        self.assertEqual(result.total, 10)
        self.assertEqual(result.rolls, [3, 4, 3])
        self.assertEqual(result.modifier, 0)
        self.assertFalse(result.is_crit)
        self.assertFalse(result.is_mishap)

    def test_with_modifier(self):
        """DiceResult should store modifier."""
        result = DiceResult(total=10, rolls=[7], modifier=3)
        self.assertEqual(result.modifier, 3)

    def test_crit_flag(self):
        """DiceResult should track is_crit."""
        result = DiceResult(total=20, rolls=[20], is_crit=True)
        self.assertTrue(result.is_crit)

    def test_mishap_flag(self):
        """DiceResult should track is_mishap."""
        result = DiceResult(total=1, rolls=[1], is_mishap=True)
        self.assertTrue(result.is_mishap)


class TestRollD20(unittest.TestCase):
    """Test cases for d20 attack roll."""

    @patch("models.dice_engine.random.randint", return_value=1)
    def test_d20_mishap_roll_1(self, mock_rand):
        """Roll=1 should be a mishap."""
        result = DiceEngine.roll_d20()
        self.assertTrue(result.is_mishap)
        self.assertFalse(result.is_crit)
        self.assertEqual(result.rolls, [1])

    @patch("models.dice_engine.random.randint", return_value=2)
    def test_d20_miss_roll_2(self, mock_rand):
        """Roll=2 should be a miss (total < 6 without modifier)."""
        result = DiceEngine.roll_d20()
        self.assertFalse(result.is_mishap)
        self.assertFalse(result.is_crit)
        self.assertEqual(result.total, 2)

    @patch("models.dice_engine.random.randint", return_value=5)
    def test_d20_miss_roll_5(self, mock_rand):
        """Roll=5 should be a miss (total=5 < 6)."""
        result = DiceEngine.roll_d20()
        self.assertFalse(result.is_mishap)
        self.assertFalse(result.is_crit)
        self.assertEqual(result.total, 5)

    @patch("models.dice_engine.random.randint", return_value=6)
    def test_d20_hit_roll_6(self, mock_rand):
        """Roll=6 should be a hit (total=6 >= 6)."""
        result = DiceEngine.roll_d20()
        self.assertFalse(result.is_mishap)
        self.assertFalse(result.is_crit)
        self.assertEqual(result.total, 6)

    @patch("models.dice_engine.random.randint", return_value=19)
    def test_d20_hit_roll_19(self, mock_rand):
        """Roll=19 should be a hit (not a crit)."""
        result = DiceEngine.roll_d20()
        self.assertFalse(result.is_mishap)
        self.assertFalse(result.is_crit)
        self.assertEqual(result.total, 19)

    @patch("models.dice_engine.random.randint", return_value=20)
    def test_d20_crit_roll_20(self, mock_rand):
        """Roll=20 should be a critical hit."""
        result = DiceEngine.roll_d20()
        self.assertTrue(result.is_crit)
        self.assertFalse(result.is_mishap)
        self.assertEqual(result.rolls, [20])

    @patch("models.dice_engine.random.randint", return_value=10)
    def test_d20_with_modifier(self, mock_rand):
        """d20 with stat modifier should add to total but raw roll stays same."""
        result = DiceEngine.roll_d20(stat_modifier=3)
        self.assertEqual(result.total, 13)  # 10 + 3
        self.assertEqual(result.rolls, [10])
        self.assertEqual(result.modifier, 3)

    @patch("models.dice_engine.random.randint", return_value=1)
    def test_d20_mishap_always_mishap_regardless_of_modifier(self, mock_rand):
        """Even with a modifier, raw=1 should still be mishap."""
        result = DiceEngine.roll_d20(stat_modifier=10)
        self.assertTrue(result.is_mishap)
        self.assertEqual(result.total, 11)  # 1 + 10

    @patch("models.dice_engine.random.randint", return_value=20)
    def test_d20_crit_always_crit_regardless_of_modifier(self, mock_rand):
        """Even with a modifier, raw=20 should still be crit."""
        result = DiceEngine.roll_d20(stat_modifier=-5)
        self.assertTrue(result.is_crit)
        self.assertEqual(result.total, 15)  # 20 + (-5)


class TestRoll3d6(unittest.TestCase):
    """Test cases for 3d6 damage roll."""

    @patch("models.dice_engine.random.randint", return_value=3)
    def test_3d6_all_threes(self, mock_rand):
        """3d6 with all 3s should total 9."""
        result = DiceEngine.roll_3d6()
        self.assertEqual(result.total, 9)
        self.assertEqual(result.rolls, [3, 3, 3])

    @patch("models.dice_engine.random.randint", return_value=6)
    def test_3d6_all_sixes(self, mock_rand):
        """3d6 with all 6s should total 18 (max damage)."""
        result = DiceEngine.roll_3d6()
        self.assertEqual(result.total, 18)
        self.assertEqual(len(result.rolls), 3)

    @patch("models.dice_engine.random.randint", return_value=1)
    def test_3d6_all_ones(self, mock_rand):
        """3d6 with all 1s should total 3 (min damage)."""
        result = DiceEngine.roll_3d6()
        self.assertEqual(result.total, 3)
        self.assertEqual(len(result.rolls), 3)


class TestParseDiceNotation(unittest.TestCase):
    """Test cases for dice notation parsing."""

    @patch("models.dice_engine.random.randint", return_value=3)
    def test_parse_simple(self, mock_rand):
        """'2d6' should roll 2 dice of 6 sides each."""
        result = DiceEngine.parse_dice_notation("2d6")
        self.assertEqual(result.total, 6)  # 3+3
        self.assertEqual(result.rolls, [3, 3])
        self.assertEqual(result.modifier, 0)

    @patch("models.dice_engine.random.randint", return_value=4)
    def test_parse_with_numeric_modifier(self, mock_rand):
        """'1d6+2' should roll 1 die and add 2."""
        result = DiceEngine.parse_dice_notation("1d6+2")
        self.assertEqual(result.total, 6)  # 4+2
        self.assertEqual(result.rolls, [4])
        self.assertEqual(result.modifier, 2)

    @patch("models.dice_engine.random.randint", return_value=2)
    def test_parse_with_str_modifier(self, mock_rand):
        """'2d6+STR' with STR=3 should add 3 to the roll."""
        result = DiceEngine.parse_dice_notation("2d6+STR", str_val=3)
        self.assertEqual(result.total, 7)  # 2+2+3
        self.assertEqual(result.rolls, [2, 2])
        self.assertEqual(result.modifier, 3)

    @patch("models.dice_engine.random.randint", return_value=3)
    def test_parse_with_dex_modifier(self, mock_rand):
        """'1d6+DEX' with DEX=2 should add 2 to the roll."""
        result = DiceEngine.parse_dice_notation("1d6+DEX", dex_val=2)
        self.assertEqual(result.total, 5)  # 3+2
        self.assertEqual(result.modifier, 2)

    @patch("models.dice_engine.random.randint", return_value=4)
    def test_parse_4d6(self, mock_rand):
        """'4d6' should roll 4 dice."""
        result = DiceEngine.parse_dice_notation("4d6")
        self.assertEqual(result.total, 16)  # 4*4
        self.assertEqual(len(result.rolls), 4)

    def test_parse_zero_notation(self):
        """'0' notation should return 0 damage."""
        result = DiceEngine.parse_dice_notation("0")
        self.assertEqual(result.total, 0)
        self.assertEqual(result.rolls, [])

    def test_parse_empty_notation(self):
        """Empty string should return 0 damage."""
        result = DiceEngine.parse_dice_notation("")
        self.assertEqual(result.total, 0)
        self.assertEqual(result.rolls, [])

    def test_parse_invalid_notation(self):
        """Invalid notation should return 0."""
        result = DiceEngine.parse_dice_notation("abc")
        self.assertEqual(result.total, 0)

    @patch("models.dice_engine.random.randint", return_value=5)
    def test_parse_negative_modifier(self, mock_rand):
        """'1d6-2' should subtract 2 from the roll."""
        result = DiceEngine.parse_dice_notation("1d6-2")
        self.assertEqual(result.total, 3)  # 5-2
        self.assertEqual(result.modifier, -2)

    def test_parse_whitespace_stripped(self):
        """Notation with whitespace should still work."""
        with patch("models.dice_engine.random.randint", return_value=3):
            result = DiceEngine.parse_dice_notation("  2d6  ")
            self.assertEqual(result.total, 6)

    @patch("models.dice_engine.random.randint", return_value=2)
    def test_parse_1d6_plus_2(self, mock_rand):
        """'1d6+2' should correctly compute 2+2=4."""
        result = DiceEngine.parse_dice_notation("1d6+2")
        self.assertEqual(result.total, 4)


class TestRollAttackDamage(unittest.TestCase):
    """Test cases for roll_attack_damage with crit handling."""

    @patch("models.dice_engine.random.randint", return_value=3)
    def test_non_crit_normal_damage(self, mock_rand):
        """Non-crit should roll normally."""
        result = DiceEngine.roll_attack_damage("2d6+STR", is_crit=False, str_val=2)
        self.assertEqual(result.total, 8)  # 3+3+2
        self.assertEqual(result.rolls, [3, 3])

    @patch("models.dice_engine.random.randint", return_value=3)
    def test_crit_doubles_dice(self, mock_rand):
        """Crit should double the number of dice (before modifier)."""
        result = DiceEngine.roll_attack_damage("2d6+STR", is_crit=True, str_val=2)
        # Crit: 2 dice * 2 = 4 dice, each rolling 3
        self.assertEqual(result.total, 14)  # 3+3+3+3+2
        self.assertEqual(len(result.rolls), 4)

    @patch("models.dice_engine.random.randint", return_value=4)
    def test_crit_4d6(self, mock_rand):
        """Crit on '4d6' should produce 8 dice."""
        result = DiceEngine.roll_attack_damage("4d6", is_crit=True)
        self.assertEqual(len(result.rolls), 8)
        self.assertEqual(result.total, 32)  # 8*4

    def test_zero_notation_returns_zero(self):
        """'0' notation should return 0 damage."""
        result = DiceEngine.roll_attack_damage("0", is_crit=True)
        self.assertEqual(result.total, 0)

    def test_empty_notation_returns_zero(self):
        """Empty notation should return 0 damage."""
        result = DiceEngine.roll_attack_damage("", is_crit=True)
        self.assertEqual(result.total, 0)

    @patch("models.dice_engine.random.randint", return_value=5)
    def test_non_crit_1d6_plus_2(self, mock_rand):
        """Non-crit '1d6+2' should roll 1 die and add 2."""
        result = DiceEngine.roll_attack_damage("1d6+2", is_crit=False)
        self.assertEqual(result.total, 7)  # 5+2
        self.assertEqual(result.rolls, [5])

    @patch("models.dice_engine.random.randint", return_value=5)
    def test_crit_1d6_plus_2_doubles_dice_only(self, mock_rand):
        """Crit '1d6+2' should roll 2 dice and add 2 (modifier NOT doubled)."""
        result = DiceEngine.roll_attack_damage("1d6+2", is_crit=True)
        self.assertEqual(result.total, 12)  # 5+5+2
        self.assertEqual(len(result.rolls), 2)


if __name__ == "__main__":
    unittest.main()
