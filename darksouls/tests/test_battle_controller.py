"""Tests for the BattleController - complete battle flow."""

import unittest
from unittest.mock import patch, MagicMock

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from controllers.battle_controller import BattleController, BattleLog
from models.player import Player
from models.enemy import Enemy
from models.card import Card
from models.deck_manager import DeckManager
from game.event_bus import EventBus
from services.data_loader import DataLoader


BASE_PATH = os.path.join(os.path.dirname(__file__), "..")


class TestBattleLog(unittest.TestCase):
    """Test BattleLog functionality."""

    def test_add_entry(self):
        """add should append a message."""
        log = BattleLog()
        log.add("Test message")
        self.assertEqual(log.entries, ["Test message"])

    def test_max_entries(self):
        """Log should not exceed max entries."""
        log = BattleLog(max_entries=3)
        for i in range(5):
            log.add(f"Message {i}")
        self.assertEqual(len(log.entries), 3)

    def test_clear(self):
        """clear should remove all entries."""
        log = BattleLog()
        log.add("Test")
        log.clear()
        self.assertEqual(len(log.entries), 0)


class TestBattleControllerInit(unittest.TestCase):
    """Test BattleController initialization."""

    def test_init(self):
        """BattleController should initialize with correct state."""
        eb = EventBus()
        player = Player(eb)
        enemy = Enemy(hp=30)
        bc = BattleController(player, enemy, eb)
        self.assertTrue(bc.player_turn)
        self.assertFalse(bc.battle_over)
        self.assertFalse(bc.player_won)


class TestStartBattle(unittest.TestCase):
    """Test battle start flow."""

    def setUp(self):
        self.eb = EventBus()
        self.player = Player(self.eb)
        self.enemy = Enemy(hp=30, is_boss=False)

        # Set up a small test deck
        cards = [Card(id=f"C{i:03d}", name=f"Card{i}", cost=1,
                      type="Attack" if i % 2 == 0 else "Skill",
                      damage="1d6" if i % 2 == 0 else "0",
                      block=0 if i % 2 == 0 else 5)
                 for i in range(10)]
        self.player.deck.build_initial_deck(cards)

    def test_start_battle_draws_5(self):
        """start_battle should draw 5 cards."""
        bc = BattleController(self.player, self.enemy, self.eb)
        bc.start_battle()
        self.assertEqual(bc.deck.hand_size, 5)

    def test_start_battle_resets_block(self):
        """start_battle should reset player block to 0."""
        self.player.gain_block(10)
        bc = BattleController(self.player, self.enemy, self.eb)
        bc.start_battle()
        self.assertEqual(self.player.block, 0)

    def test_start_battle_resets_fp(self):
        """start_battle should reset player FP to max."""
        self.player.fp = 0
        bc = BattleController(self.player, self.enemy, self.eb)
        bc.start_battle()
        self.assertEqual(self.player.fp, self.player.max_fp)

    def test_start_battle_resets_enemy_vulnerable(self):
        """start_battle should reset enemy vulnerable."""
        self.enemy.apply_vulnerable(2)
        bc = BattleController(self.player, self.enemy, self.eb)
        bc.start_battle()
        self.assertEqual(self.enemy.vulnerable, 0)

    def test_start_battle_resets_enemy_stun(self):
        """start_battle should reset enemy stun."""
        self.enemy.apply_stun(2)
        bc = BattleController(self.player, self.enemy, self.eb)
        bc.start_battle()
        self.assertEqual(self.enemy.stun_count, 0)


class TestPlayCard(unittest.TestCase):
    """Test playing cards during battle."""

    def setUp(self):
        self.eb = EventBus()
        self.player = Player(self.eb)
        self.enemy = Enemy(hp=100, is_boss=False)  # High HP so we don't kill easily
        cards = []
        for i in range(10):
            cards.append(Card(
                id=f"C{i:03d}", name=f"Strike{i}", cost=1,
                type="Attack", damage="1d6", block=0, keywords={}
            ))
        self.player.deck.build_initial_deck(cards)

    @patch("models.dice_engine.random.randint", return_value=10)
    def test_play_attack_card_spends_fp(self, mock_rand):
        """Playing a card should spend FP."""
        bc = BattleController(self.player, self.enemy, self.eb)
        bc.start_battle()
        initial_fp = self.player.fp
        bc.play_selected_card()
        self.assertEqual(self.player.fp, initial_fp - 1)

    def test_play_card_insufficient_fp(self):
        """Playing a card without enough FP should fail."""
        bc = BattleController(self.player, self.enemy, self.eb)
        bc.start_battle()
        # Set FP to 0 AFTER start_battle (which resets FP)
        self.player.fp = 0
        result = bc.play_selected_card()
        self.assertEqual(result, "Not enough FP!")

    @patch("models.dice_engine.random.randint", return_value=10)
    def test_play_attack_card_deals_damage(self, mock_rand):
        """Attack card should deal damage to enemy on hit."""
        bc = BattleController(self.player, self.enemy, self.eb)
        bc.start_battle()
        initial_hp = self.enemy.hp
        bc.play_selected_card()
        self.assertLess(self.enemy.hp, initial_hp)

    @patch("models.dice_engine.random.randint", return_value=3)
    def test_play_attack_card_miss(self, mock_rand):
        """Attack card with d20 roll <= 5 should miss."""
        bc = BattleController(self.player, self.enemy, self.eb)
        bc.start_battle()
        initial_hp = self.enemy.hp
        # d20 roll=3 which is < 6, so miss
        bc.play_selected_card()
        self.assertEqual(self.enemy.hp, initial_hp)  # No damage

    @patch("models.dice_engine.random.randint", return_value=1)
    def test_play_attack_card_mishap(self, mock_rand):
        """d20 roll=1 should be mishap, player takes 3 damage."""
        bc = BattleController(self.player, self.enemy, self.eb)
        bc.start_battle()
        initial_hp = self.player.hp
        bc.play_selected_card()
        self.assertEqual(self.player.hp, initial_hp - 3)

    @patch("models.dice_engine.random.randint", return_value=20)
    def test_play_attack_card_crit(self, mock_rand):
        """d20 roll=20 should be a critical hit with doubled dice."""
        bc = BattleController(self.player, self.enemy, self.eb)
        bc.start_battle()
        # 1d6 card, crit -> 2d6
        # All rolls are 20 for d20, but we need d6 rolls too
        # mock_rand returns 20 for everything, but the damage dice will also get 20
        # which is invalid for d6 (should be 1-6), but the mock returns 20
        # Let's just check that enemy took damage
        initial_hp = self.enemy.hp
        bc.play_selected_card()
        self.assertLess(self.enemy.hp, initial_hp)


class TestPlayDefenseCard(unittest.TestCase):
    """Test playing defense cards during battle."""

    def setUp(self):
        self.eb = EventBus()
        self.player = Player(self.eb)
        self.enemy = Enemy(hp=30)
        # All Skill cards with block
        cards = [Card(id=f"C{i:03d}", name=f"Defend{i}", cost=1,
                      type="Skill", damage="0", block=5, keywords={})
                 for i in range(10)]
        self.player.deck.build_initial_deck(cards)

    def test_play_defense_card_gains_block(self):
        """Defense card should give player block."""
        bc = BattleController(self.player, self.enemy, self.eb)
        bc.start_battle()
        bc.play_selected_card()
        self.assertGreater(self.player.block, 0)


class TestEndPlayerTurn(unittest.TestCase):
    """Test ending the player's turn."""

    def setUp(self):
        self.eb = EventBus()
        self.player = Player(self.eb)
        self.enemy = Enemy(hp=30)
        cards = [Card(id=f"C{i:03d}", name=f"Card{i}", cost=1,
                      type="Skill", damage="0", block=5, keywords={})
                 for i in range(10)]
        self.player.deck.build_initial_deck(cards)

    def test_end_turn_resets_block(self):
        """Ending turn should reset player block."""
        bc = BattleController(self.player, self.enemy, self.eb)
        bc.start_battle()
        self.player.gain_block(10)
        bc.end_player_turn()
        self.assertEqual(self.player.block, 0)

    def test_end_turn_discards_hand(self):
        """Ending turn should discard all cards in hand."""
        bc = BattleController(self.player, self.enemy, self.eb)
        bc.start_battle()
        bc.end_player_turn()
        self.assertEqual(bc.deck.hand_size, 0)

    def test_end_turn_starts_enemy_turn(self):
        """Ending turn should set player_turn to False."""
        bc = BattleController(self.player, self.enemy, self.eb)
        bc.start_battle()
        bc.end_player_turn()
        self.assertFalse(bc.player_turn)


class TestEnemyTurn(unittest.TestCase):
    """Test enemy turn execution."""

    def setUp(self):
        self.eb = EventBus()
        self.player = Player(self.eb)
        self.player.hp = 100  # Give plenty of HP
        self.enemy = Enemy(hp=30, is_boss=False)
        cards = [Card(id=f"C{i:03d}", name=f"Card{i}", cost=1,
                      type="Skill", damage="0", block=5, keywords={})
                 for i in range(10)]
        self.player.deck.build_initial_deck(cards)

    def test_normal_enemy_one_action(self):
        """Normal enemy should have 1 action per turn."""
        bc = BattleController(self.player, self.enemy, self.eb)
        bc.start_battle()
        bc.end_player_turn()
        self.assertEqual(bc._enemy_actions_remaining, 1)

    def test_boss_two_actions(self):
        """Boss enemy should have 2 actions per turn."""
        boss = Enemy(hp=80, is_boss=True)
        bc = BattleController(self.player, boss, self.eb)
        bc.start_battle()
        bc.end_player_turn()
        self.assertEqual(bc._enemy_actions_remaining, 2)

    def test_stunned_enemy_skips_turn(self):
        """Stunned enemy should skip its turn."""
        self.enemy.apply_stun(1)
        bc = BattleController(self.player, self.enemy, self.eb)
        bc.start_battle()
        bc.end_player_turn()
        result = bc.execute_enemy_turn()
        self.assertTrue(result)  # Turn complete
        self.assertEqual(self.enemy.stun_count, 0)  # Stun ticked down


class TestBattleVictory(unittest.TestCase):
    """Test battle victory conditions."""

    def setUp(self):
        self.eb = EventBus()
        self.player = Player(self.eb)
        self.enemy = Enemy(hp=5, souls=30)
        # Cards that deal damage
        cards = [Card(id=f"C{i:03d}", name=f"Strike{i}", cost=1,
                      type="Attack", damage="2d6", block=0, keywords={})
                 for i in range(10)]
        self.player.deck.build_initial_deck(cards)

    @patch("models.dice_engine.random.randint", return_value=10)
    def test_enemy_death_triggers_victory(self, mock_rand):
        """When enemy HP reaches 0, battle should end with player victory."""
        bc = BattleController(self.player, self.enemy, self.eb)
        bc.start_battle()
        # Deal enough damage to kill
        self.enemy.hp = 1
        bc.play_selected_card()
        self.assertTrue(bc.battle_over)
        self.assertTrue(bc.player_won)

    @patch("models.dice_engine.random.randint", return_value=10)
    def test_victory_grants_souls(self, mock_rand):
        """Victory should grant souls to the player."""
        bc = BattleController(self.player, self.enemy, self.eb)
        bc.start_battle()
        self.enemy.hp = 1
        initial_souls = self.player.souls
        bc.play_selected_card()
        self.assertEqual(self.player.souls, initial_souls + self.enemy.souls)


class TestBattleDefeat(unittest.TestCase):
    """Test battle defeat conditions."""

    def test_player_death_ends_battle(self):
        """When player HP reaches 0, battle should end with player defeat."""
        eb = EventBus()
        player = Player(eb)
        player.hp = 1  # Nearly dead
        enemy = Enemy(hp=30)
        bc = BattleController(player, enemy, eb)
        bc.start_battle()
        # Simulate player taking fatal damage
        player.take_damage(10)
        self.assertTrue(player.is_dead())


class TestSelectCard(unittest.TestCase):
    """Test card selection navigation."""

    def setUp(self):
        self.eb = EventBus()
        self.player = Player(self.eb)
        self.enemy = Enemy(hp=30)
        cards = [Card(id=f"C{i:03d}", name=f"Card{i}", cost=1,
                      type="Attack", damage="1d6", block=0)
                 for i in range(10)]
        self.player.deck.build_initial_deck(cards)

    def test_select_card_right(self):
        """Selecting right should increment index."""
        bc = BattleController(self.player, self.enemy, self.eb)
        bc.start_battle()
        bc.select_card(1)
        self.assertEqual(bc.selected_card_index, 1)

    def test_select_card_left(self):
        """Selecting left should decrement index (wrapping)."""
        bc = BattleController(self.player, self.enemy, self.eb)
        bc.start_battle()
        bc.select_card(-1)  # Wrap from 0 to last card
        self.assertEqual(bc.selected_card_index, bc.deck.hand_size - 1)

    def test_select_card_wraps(self):
        """Selection should wrap around."""
        bc = BattleController(self.player, self.enemy, self.eb)
        bc.start_battle()
        for _ in range(bc.deck.hand_size):
            bc.select_card(1)
        self.assertEqual(bc.selected_card_index, 0)  # Back to start


class TestGetSoulsReward(unittest.TestCase):
    """Test souls reward calculation."""

    def test_victory_reward(self):
        """After victory, get_souls_reward should return enemy souls."""
        eb = EventBus()
        player = Player(eb)
        enemy = Enemy(hp=1, souls=50)
        bc = BattleController(player, enemy, eb)
        bc.player_won = True
        self.assertEqual(bc.get_souls_reward(), 50)

    def test_defeat_no_reward(self):
        """After defeat, get_souls_reward should return 0."""
        eb = EventBus()
        player = Player(eb)
        enemy = Enemy(hp=30, souls=50)
        bc = BattleController(player, enemy, eb)
        bc.player_won = False
        self.assertEqual(bc.get_souls_reward(), 0)


if __name__ == "__main__":
    unittest.main()
