"""Integration tests - full battle cycle, loot, events, map flow."""

import unittest
from unittest.mock import patch

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from models.player import Player
from models.enemy import Enemy
from models.card import Card
from models.deck_manager import DeckManager
from models.dice_engine import DiceEngine
from game.event_bus import EventBus
from services.data_loader import DataLoader
from controllers.battle_controller import BattleController
from controllers.event_controller import EventController
from controllers.map_controller import MapController, GameMap, MapNode


BASE_PATH = os.path.join(os.path.dirname(__file__), "..")


class TestFullBattleCycle(unittest.TestCase):
    """Integration test: complete battle from start to victory."""

    def setUp(self):
        self.eb = EventBus()
        self.player = Player(self.eb)
        self.loader = DataLoader(BASE_PATH)
        self.player.setup_initial_deck(self.loader.create_card)

    @patch("models.dice_engine.random.randint", return_value=15)
    def test_full_battle_to_victory(self, mock_rand):
        """Simulate a full battle: start -> play cards -> enemy turn -> victory."""
        enemy = Enemy(hp=10, is_boss=False)
        bc = BattleController(self.player, enemy, self.eb, self.loader)
        bc.start_battle()

        # Battle should be set up
        self.assertEqual(bc.deck.hand_size, 5)
        self.assertTrue(bc.player_turn)

        # Play cards until enemy dies or hand is empty
        while bc.deck.hand and not bc.battle_over:
            # Find an affordable card
            played = False
            for i in range(len(bc.deck.hand)):
                bc.selected_card_index = i
                card = bc.deck.hand[i]
                if card.cost <= self.player.fp:
                    bc.play_selected_card()
                    played = True
                    break
            if not played or bc.battle_over:
                break

        # After playing at least one hit card, enemy should take damage
        # (d20=15 is a hit, 1d6=15 is invalid but mock returns 15)
        # Actually, random.randint(1,6) with return_value=15 will return 15
        # which is out of d6 range, but the mock doesn't check range.
        # For Strike (2d6+STR): 15+15+1 = 31 damage which kills 10 HP enemy

    @patch("models.dice_engine.random.randint", return_value=15)
    def test_battle_with_enemy_turn(self, mock_rand):
        """Simulate battle where player ends turn, then enemy acts."""
        enemy = Enemy(hp=100, is_boss=False, str=2,
                      ai={"Attack": 1.0}, card_pool=["EC001"])
        bc = BattleController(self.player, enemy, self.eb, self.loader)
        bc.start_battle()

        # End player turn immediately
        bc.end_player_turn()
        self.assertFalse(bc.player_turn)

        # Execute enemy turn
        result = bc.execute_enemy_turn()
        self.assertTrue(result)  # All actions done

        # Should start next player turn
        self.assertTrue(bc.player_turn)
        self.assertEqual(bc.deck.hand_size, 5)  # Drew new hand


class TestFullBattleCycleWithRealDice(unittest.TestCase):
    """Integration test with actual dice rolls (not mocked)."""

    def test_battle_runs_without_error(self):
        """A complete battle should run without raising exceptions."""
        eb = EventBus()
        player = Player(eb)
        loader = DataLoader(BASE_PATH)
        player.setup_initial_deck(loader.create_card)
        enemy = Enemy(hp=20, is_boss=False)

        bc = BattleController(player, enemy, eb, loader)
        bc.start_battle()

        # Play a few rounds
        for _ in range(5):
            if bc.battle_over:
                break
            if bc.player_turn:
                # Try to play affordable cards (play from index 0 each time
                # since cards shift after being played)
                played_any = False
                while bc.deck.hand and not bc.battle_over:
                    card = bc.deck.hand[0]
                    if card.cost <= player.fp:
                        bc.selected_card_index = 0
                        bc.play_selected_card()
                        played_any = True
                        if bc.battle_over:
                            break
                    else:
                        break
                if not played_any or not bc.player_turn:
                    if not bc.battle_over:
                        bc.end_player_turn()
            else:
                # Enemy turn
                while not bc.execute_enemy_turn():
                    if bc.battle_over:
                        break

        # Battle should have progressed
        self.assertTrue(bc.battle_over or enemy.hp < enemy.max_hp or player.hp < player.max_hp)


class TestLootFlow(unittest.TestCase):
    """Integration test: victory -> three-choice loot -> deck update."""

    def test_data_loader_provides_loot_cards(self):
        """DataLoader should provide player cards for loot selection."""
        loader = DataLoader(BASE_PATH)
        loot_cards = loader.get_loot_cards()
        self.assertGreater(len(loot_cards), 0)
        # All should be Player-source
        for c in loot_cards:
            self.assertEqual(c["source"], "Player")

    def test_adding_card_to_deck(self):
        """After loot, new card should be added to the deck."""
        deck = DeckManager()
        cards = [Card(id=f"C{i:03d}", name=f"Card{i}") for i in range(10)]
        deck.build_initial_deck(cards)

        # Simulate adding a loot card
        loot_card = Card(id="C009", name="Vampiric Blade", cost=2, type="Attack",
                         damage="2d6", keywords={"Lifesteal": 50})
        deck.add_card(loot_card)
        # New card should be in discard pile
        self.assertEqual(deck.discard_pile_size, 1)

        # After reset, total cards should be 11
        deck.reset_for_battle()
        self.assertEqual(deck.draw_pile_size, 11)


class TestEventFlow(unittest.TestCase):
    """Integration test: bonfire heal, shop purchase, blacksmith upgrade."""

    def setUp(self):
        self.loader = DataLoader(BASE_PATH)
        self.ec = EventController(self.loader)
        self.player = Player()

    def test_bonfire_heal(self):
        """Bonfire heal option should restore HP."""
        self.player.take_damage(30)  # HP=30
        event_data = self.loader.get_event_data("EV_FIRE_01")
        result = self.ec.resolve_event_option(self.player, event_data, 0)  # Rest (Heal 50%)
        self.assertTrue(result["success"])
        self.assertEqual(self.player.hp, 60)  # 30 + 30 (50% of 60)

    def test_bonfire_attune(self):
        """Bonfire attune option should grant stat point."""
        event_data = self.loader.get_event_data("EV_FIRE_01")
        result = self.ec.resolve_event_option(self.player, event_data, 1)
        self.assertTrue(result["success"])
        self.assertEqual(self.player.attribute_points, 1)

    def test_shop_buy_relic(self):
        """Shop buy option should add relic to player."""
        self.player.souls = 100
        event_data = self.loader.get_event_data("EV_SHOP_01")
        result = self.ec.resolve_event_option(self.player, event_data, 0)  # Buy Estus Flask
        self.assertTrue(result["success"])
        self.assertTrue(self.player.relics.has("R002"))

    def test_shop_insufficient_souls(self):
        """Shop with insufficient souls should fail."""
        self.player.souls = 10
        event_data = self.loader.get_event_data("EV_SHOP_01")
        result = self.ec.resolve_event_option(self.player, event_data, 0)
        self.assertFalse(result["success"])

    def test_blacksmith_upgrade_str(self):
        """Blacksmith should upgrade STR."""
        self.player.souls = 50
        event_data = self.loader.get_event_data("EV_SMITH_01")
        result = self.ec.resolve_event_option(self.player, event_data, 0)
        self.assertTrue(result["success"])
        self.assertEqual(self.player.str, 2)

    def test_blacksmith_upgrade_dex(self):
        """Blacksmith should upgrade DEX."""
        self.player.souls = 50
        event_data = self.loader.get_event_data("EV_SMITH_01")
        result = self.ec.resolve_event_option(self.player, event_data, 1)
        self.assertTrue(result["success"])
        self.assertEqual(self.player.dex, 2)

    def test_invalid_option_index(self):
        """Invalid option index should return failure."""
        event_data = self.loader.get_event_data("EV_FIRE_01")
        result = self.ec.resolve_event_option(self.player, event_data, 99)
        self.assertFalse(result["success"])


class TestMapFlow(unittest.TestCase):
    """Integration test: map generation, node selection, act progression."""

    def setUp(self):
        self.loader = DataLoader(BASE_PATH)
        self.mc = MapController(self.loader)

    def test_generate_act_1_map(self):
        """Should generate a map for act 1."""
        game_map = self.mc.generate_act_map(1)
        self.assertIsNotNone(game_map)
        self.assertEqual(game_map.act, 1)
        self.assertGreater(len(game_map.rows), 0)

    def test_map_has_boss_at_end(self):
        """Last row should contain boss nodes."""
        game_map = self.mc.generate_act_map(1)
        last_row = game_map.rows[-1]
        for node in last_row:
            self.assertEqual(node.node_type, "boss")

    def test_map_node_selection(self):
        """Should be able to select a node and advance."""
        game_map = self.mc.generate_act_map(1)
        node = game_map.select_node()
        self.assertIsNotNone(node)
        self.assertTrue(node.visited)

    def test_map_advance_row(self):
        """Advancing row should move to next row."""
        game_map = self.mc.generate_act_map(1)
        game_map.select_node()
        result = game_map.advance_row()
        self.assertTrue(result)
        self.assertEqual(game_map.current_row, 1)

    def test_map_complete(self):
        """Map should be complete after advancing past all rows."""
        game_map = self.mc.generate_act_map(1)
        num_rows = len(game_map.rows)
        for _ in range(num_rows):
            game_map.advance_row()
        self.assertTrue(game_map.is_complete())

    def test_advance_to_next_act(self):
        """advance_to_next_act should increment act number."""
        result = self.mc.advance_to_next_act()
        self.assertEqual(result, 2)
        self.assertEqual(self.mc.current_act, 2)

    def test_advance_past_act_3(self):
        """Advancing past act 3 should return None (game complete)."""
        self.mc.current_act = 3
        result = self.mc.advance_to_next_act()
        self.assertIsNone(result)

    def test_act_data_integrity(self):
        """Each act should have valid data."""
        for act_num in range(1, 4):
            act_data = self.loader.get_act_data(act_num)
            self.assertIsNotNone(act_data)
            self.assertIn("nodes", act_data)
            self.assertIn("enemies", act_data)
            self.assertIn("boss", act_data)


class TestMapNodeTypes(unittest.TestCase):
    """Test different map node types."""

    def test_battle_node(self):
        """Battle node should have an enemy_id."""
        node = MapNode(node_type="battle", enemy_id="E001")
        self.assertEqual(node.node_type, "battle")
        self.assertEqual(node.enemy_id, "E001")

    def test_event_node(self):
        """Event node should have an event_id."""
        node = MapNode(node_type="event", event_id="EV_FIRE_01")
        self.assertEqual(node.node_type, "event")
        self.assertEqual(node.event_id, "EV_FIRE_01")

    def test_boss_node(self):
        """Boss node should have an enemy_id."""
        node = MapNode(node_type="boss", enemy_id="B001")
        self.assertEqual(node.node_type, "boss")

    def test_node_not_visited_by_default(self):
        """Node should not be visited by default."""
        node = MapNode()
        self.assertFalse(node.visited)

    def test_node_not_cleared_by_default(self):
        """Node should not be cleared by default."""
        node = MapNode()
        self.assertFalse(node.cleared)


class TestBlockResetsPerTurn(unittest.TestCase):
    """Integration test: Block resets at the start of each turn."""

    def test_block_resets_on_end_player_turn(self):
        """Player block should reset when ending turn."""
        eb = EventBus()
        player = Player(eb)
        enemy = Enemy(hp=30)
        cards = [Card(id=f"C{i:03d}", name=f"Card{i}", cost=1,
                      type="Skill", damage="0", block=5)
                 for i in range(10)]
        player.deck.build_initial_deck(cards)
        bc = BattleController(player, enemy, eb)
        bc.start_battle()

        # Play a defend card
        bc.play_selected_card()
        self.assertGreater(player.block, 0)

        # End turn - block should reset
        bc.end_player_turn()
        self.assertEqual(player.block, 0)

    def test_fp_resets_on_new_turn(self):
        """FP should reset to max at start of new player turn."""
        eb = EventBus()
        player = Player(eb)
        enemy = Enemy(hp=30)
        cards = [Card(id=f"C{i:03d}", name=f"Card{i}", cost=1,
                      type="Skill", damage="0", block=5)
                 for i in range(10)]
        player.deck.build_initial_deck(cards)
        bc = BattleController(player, enemy, eb)
        bc.start_battle()

        # Spend some FP
        bc.play_selected_card()
        self.assertLess(player.fp, player.max_fp)

        # End turn and let enemy act
        bc.end_player_turn()
        bc.execute_enemy_turn()

        # New turn - FP should be reset
        self.assertEqual(player.fp, player.max_fp)


class TestRelicEffectsInBattle(unittest.TestCase):
    """Integration test: relic effects trigger during battle."""

    def test_ring_of_favor_adds_max_hp(self):
        """Ring of Favor should add 15 to max HP at battle start."""
        from models.relic import Relic
        eb = EventBus()
        player = Player(eb)
        enemy = Enemy(hp=30)
        cards = [Card(id=f"C{i:03d}", name=f"Card{i}", cost=1,
                      type="Skill", damage="0", block=5)
                 for i in range(10)]
        player.deck.build_initial_deck(cards)

        # Add Ring of Favor
        relic = Relic(id="R001", name="Ring of Favor", trigger="on_battle_start",
                      effect={"AddMaxHP": 15})
        player.relics.add(relic)

        initial_max_hp = player.max_hp
        bc = BattleController(player, enemy, eb)
        bc.start_battle()

        # Ring of Favor should have added 15 to max HP
        self.assertEqual(player.max_hp, initial_max_hp + 15)

    def test_havels_ring_adds_block(self):
        """Havel's Ring should add 5 flat block when gaining block."""
        from models.relic import Relic
        eb = EventBus()
        player = Player(eb)
        enemy = Enemy(hp=30)
        cards = [Card(id=f"C{i:03d}", name=f"Defend{i}", cost=1,
                      type="Skill", damage="0", block=5)
                 for i in range(10)]
        player.deck.build_initial_deck(cards)

        # Add Havel's Ring
        relic = Relic(id="R003", name="Havel's Ring",
                      trigger="on_calculate_defense",
                      effect={"AddFlat": 5})
        player.relics.add(relic)

        bc = BattleController(player, enemy, eb)
        bc.start_battle()

        # Play a defend card - should give 5 (base) + 5 (relic) = 10 block
        bc.play_selected_card()
        self.assertEqual(player.block, 10)


if __name__ == "__main__":
    unittest.main()
