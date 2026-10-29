"""Tests for the DeckManager - draw, discard, exhaust, shuffle, reset."""

import unittest

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from models.card import Card
from models.deck_manager import DeckManager


def make_card(card_id: str = "C001", name: str = "Test") -> Card:
    """Helper to create a test card."""
    return Card(id=card_id, name=name)


class TestDeckManagerInit(unittest.TestCase):
    """Test DeckManager initialization."""

    def test_initial_state(self):
        """All piles should be empty on creation."""
        dm = DeckManager()
        self.assertEqual(dm.draw_pile_size, 0)
        self.assertEqual(dm.discard_pile_size, 0)
        self.assertEqual(dm.exhaust_pile_size, 0)
        self.assertEqual(dm.hand_size, 0)


class TestBuildInitialDeck(unittest.TestCase):
    """Test building the initial deck."""

    def test_build_initial_deck(self):
        """build_initial_deck should populate draw pile and clear others."""
        dm = DeckManager()
        cards = [make_card(f"C{i:03d}") for i in range(10)]
        dm.build_initial_deck(cards)
        self.assertEqual(dm.draw_pile_size, 10)
        self.assertEqual(dm.discard_pile_size, 0)
        self.assertEqual(dm.exhaust_pile_size, 0)
        self.assertEqual(dm.hand_size, 0)

    def test_build_initial_deck_clears_old_state(self):
        """build_initial_deck should clear existing cards from all piles."""
        dm = DeckManager()
        cards = [make_card("C001")]
        dm.build_initial_deck(cards)
        dm.draw(1)
        dm.discard_card(dm.hand[0])

        # Build new deck
        new_cards = [make_card(f"C{i:03d}") for i in range(5)]
        dm.build_initial_deck(new_cards)
        self.assertEqual(dm.draw_pile_size, 5)
        self.assertEqual(dm.discard_pile_size, 0)
        self.assertEqual(dm.hand_size, 0)

    def test_initial_deck_10_cards(self):
        """Initial deck should have 10 cards (5 Strike + 3 Defend + 2 Backstab)."""
        dm = DeckManager()
        cards = []
        for _ in range(5):
            cards.append(Card(id="C001", name="Strike"))
        for _ in range(3):
            cards.append(Card(id="C007", name="Defend"))
        for _ in range(2):
            cards.append(Card(id="C006", name="Backstab"))
        dm.build_initial_deck(cards)
        self.assertEqual(dm.draw_pile_size, 10)


class TestDraw(unittest.TestCase):
    """Test drawing cards from the deck."""

    def test_draw_one_card(self):
        """Drawing 1 card should move it from draw pile to hand."""
        dm = DeckManager()
        cards = [make_card(f"C{i:03d}") for i in range(5)]
        dm.build_initial_deck(cards)
        drawn = dm.draw(1)
        self.assertEqual(len(drawn), 1)
        self.assertEqual(dm.hand_size, 1)
        self.assertEqual(dm.draw_pile_size, 4)

    def test_draw_five_cards(self):
        """Drawing 5 cards (typical hand size) should work."""
        dm = DeckManager()
        cards = [make_card(f"C{i:03d}") for i in range(10)]
        dm.build_initial_deck(cards)
        drawn = dm.draw(5)
        self.assertEqual(len(drawn), 5)
        self.assertEqual(dm.hand_size, 5)
        self.assertEqual(dm.draw_pile_size, 5)

    def test_draw_more_than_available(self):
        """Drawing more cards than in draw pile (with discard available) should reshuffle."""
        dm = DeckManager()
        cards = [make_card(f"C{i:03d}") for i in range(3)]
        dm.build_initial_deck(cards)
        dm.draw(3)
        # All in hand, discard them
        dm.discard_hand()
        # Now draw pile is empty, discard has 3
        self.assertEqual(dm.draw_pile_size, 0)
        self.assertEqual(dm.discard_pile_size, 3)
        # Drawing should reshuffle
        drawn = dm.draw(2)
        self.assertEqual(len(drawn), 2)
        self.assertEqual(dm.hand_size, 2)

    def test_draw_with_empty_piles(self):
        """Drawing when both draw and discard are empty should return nothing."""
        dm = DeckManager()
        drawn = dm.draw(5)
        self.assertEqual(len(drawn), 0)

    def test_draw_partial_from_reshuffled(self):
        """Drawing from reshuffled discard should give correct cards."""
        dm = DeckManager()
        cards = [make_card(f"C{i:03d}") for i in range(5)]
        dm.build_initial_deck(cards)
        dm.draw(5)
        dm.discard_hand()
        # All 5 in discard, 0 in draw
        drawn = dm.draw(3)
        self.assertEqual(len(drawn), 3)
        self.assertEqual(dm.hand_size, 3)
        self.assertEqual(dm.draw_pile_size, 2)  # 5 reshuffled - 3 drawn


class TestDiscard(unittest.TestCase):
    """Test discarding cards."""

    def test_discard_card(self):
        """Discarding a card should move it from hand to discard pile."""
        dm = DeckManager()
        cards = [make_card(f"C{i:03d}") for i in range(3)]
        dm.build_initial_deck(cards)
        drawn = dm.draw(3)
        card = drawn[0]
        dm.discard_card(card)
        self.assertEqual(dm.hand_size, 2)
        self.assertEqual(dm.discard_pile_size, 1)

    def test_discard_card_not_in_hand(self):
        """Discarding a card not in hand should do nothing."""
        dm = DeckManager()
        cards = [make_card(f"C{i:03d}") for i in range(3)]
        dm.build_initial_deck(cards)
        dm.draw(1)
        outside_card = make_card("C999")
        dm.discard_card(outside_card)
        self.assertEqual(dm.hand_size, 1)
        self.assertEqual(dm.discard_pile_size, 0)

    def test_discard_hand(self):
        """discard_hand should move all hand cards to discard."""
        dm = DeckManager()
        cards = [make_card(f"C{i:03d}") for i in range(5)]
        dm.build_initial_deck(cards)
        dm.draw(5)
        dm.discard_hand()
        self.assertEqual(dm.hand_size, 0)
        self.assertEqual(dm.discard_pile_size, 5)


class TestExhaust(unittest.TestCase):
    """Test exhausting cards."""

    def test_exhaust_card(self):
        """Exhausting a card should move it from hand to exhaust pile."""
        dm = DeckManager()
        cards = [make_card(f"C{i:03d}") for i in range(3)]
        dm.build_initial_deck(cards)
        drawn = dm.draw(3)
        card = drawn[0]
        dm.exhaust_card(card)
        self.assertEqual(dm.hand_size, 2)
        self.assertEqual(dm.exhaust_pile_size, 1)
        self.assertEqual(dm.discard_pile_size, 0)


class TestConsume(unittest.TestCase):
    """Test consuming cards (remove from game)."""

    def test_consume_card(self):
        """Consuming a card should remove it from hand entirely."""
        dm = DeckManager()
        cards = [make_card(f"C{i:03d}") for i in range(3)]
        dm.build_initial_deck(cards)
        drawn = dm.draw(3)
        card = drawn[0]
        dm.consume_card(card)
        self.assertEqual(dm.hand_size, 2)
        self.assertEqual(dm.exhaust_pile_size, 0)
        self.assertEqual(dm.discard_pile_size, 0)
        # Total cards in all piles should be 2 (remaining in hand) + 0 (draw)
        total = dm.draw_pile_size + dm.discard_pile_size + dm.exhaust_pile_size + dm.hand_size
        self.assertEqual(total, 2)


class TestAddRemoveCard(unittest.TestCase):
    """Test adding and removing cards from the deck."""

    def test_add_card_to_discard(self):
        """add_card should add to discard pile."""
        dm = DeckManager()
        new_card = make_card("C100")
        dm.add_card(new_card)
        self.assertEqual(dm.discard_pile_size, 1)

    def test_remove_card_by_id(self):
        """remove_card should find and remove card from any pile."""
        dm = DeckManager()
        cards = [make_card(f"C{i:03d}") for i in range(3)]
        dm.build_initial_deck(cards)
        dm.draw(3)
        removed = dm.remove_card("C001")
        self.assertIsNotNone(removed)
        self.assertEqual(removed.id, "C001")
        self.assertEqual(dm.hand_size, 2)

    def test_remove_card_not_found(self):
        """remove_card should return None if card not found."""
        dm = DeckManager()
        result = dm.remove_card("C999")
        self.assertIsNone(result)


class TestResetForBattle(unittest.TestCase):
    """Test resetting the deck for a new battle."""

    def test_reset_gathers_all_cards(self):
        """reset_for_battle should move all cards back to draw pile."""
        dm = DeckManager()
        cards = [make_card(f"C{i:03d}") for i in range(10)]
        dm.build_initial_deck(cards)
        dm.draw(5)
        dm.discard_hand()
        dm.draw(3)
        dm.exhaust_card(dm.hand[0])

        # Now cards are scattered
        total_before = dm.draw_pile_size + dm.discard_pile_size + dm.exhaust_pile_size + dm.hand_size

        dm.reset_for_battle()
        total_after = dm.draw_pile_size + dm.discard_pile_size + dm.exhaust_pile_size + dm.hand_size

        self.assertEqual(total_before, total_after)
        self.assertEqual(dm.draw_pile_size, total_after)
        self.assertEqual(dm.discard_pile_size, 0)
        self.assertEqual(dm.exhaust_pile_size, 0)
        self.assertEqual(dm.hand_size, 0)


class TestMoveToDraw(unittest.TestCase):
    """Test moving a card from discard to top of draw pile."""

    def test_move_to_draw(self):
        """move_to_draw should move card from discard to draw pile."""
        dm = DeckManager()
        cards = [make_card(f"C{i:03d}") for i in range(3)]
        dm.build_initial_deck(cards)
        dm.draw(3)
        card = dm.hand[0]
        dm.discard_card(card)
        dm.move_to_draw(card)
        self.assertEqual(dm.draw_pile_size, 1)
        self.assertEqual(dm.discard_pile_size, 0)


if __name__ == "__main__":
    unittest.main()
