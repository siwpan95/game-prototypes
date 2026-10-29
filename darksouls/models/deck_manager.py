"""DeckManager - manages draw, discard, exhaust piles and hand."""

import random

from models.card import Card


class DeckManager:
    """Manages a card deck with draw pile, discard pile, exhaust pile,
    and current hand.

    The deck follows Slay the Spire style:
    - Draw from draw_pile
    - Played cards go to discard_pile (unless exhausted)
    - Exhausted cards go to exhaust_pile
    - When draw_pile is empty, shuffle discard_pile into draw_pile
    """

    def __init__(self) -> None:
        self.draw_pile: list[Card] = []
        self.discard_pile: list[Card] = []
        self.exhaust_pile: list[Card] = []
        self.hand: list[Card] = []

    def build_initial_deck(self, cards: list[Card]) -> None:
        """Set up the draw pile with the given cards and shuffle."""
        self.draw_pile = list(cards)
        self.discard_pile.clear()
        self.exhaust_pile.clear()
        self.hand.clear()
        self.shuffle()

    def shuffle(self) -> None:
        """Shuffle the draw pile."""
        random.shuffle(self.draw_pile)

    def shuffle_discard_into_draw(self) -> None:
        """Move all cards from discard pile to draw pile and shuffle."""
        self.draw_pile.extend(self.discard_pile)
        self.discard_pile.clear()
        self.shuffle()

    def draw(self, count: int = 1) -> list[Card]:
        """Draw cards from the draw pile into hand.

        If draw pile is empty, shuffle discard into draw first.
        Returns the list of drawn cards.
        """
        drawn: list[Card] = []
        for _ in range(count):
            if not self.draw_pile:
                if not self.discard_pile:
                    break
                self.shuffle_discard_into_draw()
            if self.draw_pile:
                card = self.draw_pile.pop()
                self.hand.append(card)
                drawn.append(card)
        return drawn

    def discard_card(self, card: Card) -> None:
        """Move a card from hand to discard pile."""
        if card in self.hand:
            self.hand.remove(card)
            self.discard_pile.append(card)

    def exhaust_card(self, card: Card) -> None:
        """Move a card from hand to exhaust pile."""
        if card in self.hand:
            self.hand.remove(card)
            self.exhaust_pile.append(card)

    def consume_card(self, card: Card) -> None:
        """Consume a card (remove from game entirely)."""
        if card in self.hand:
            self.hand.remove(card)
        # Consumed cards are removed from the run entirely

    def discard_hand(self) -> None:
        """Move all cards in hand to discard pile."""
        self.discard_pile.extend(self.hand)
        self.hand.clear()

    def move_to_draw(self, card: Card) -> None:
        """Move a card from discard pile to the top of draw pile."""
        if card in self.discard_pile:
            self.discard_pile.remove(card)
            self.draw_pile.append(card)

    def add_card(self, card: Card) -> None:
        """Add a new card to the discard pile (will be shuffled in later)."""
        self.discard_pile.append(card)

    def remove_card(self, card_id: str) -> Card | None:
        """Remove a card by ID from any pile.

        Returns the removed card, or None if not found.
        """
        for pile in [self.hand, self.draw_pile, self.discard_pile]:
            for i, card in enumerate(pile):
                if card.id == card_id:
                    return pile.pop(i)
        return None

    @property
    def draw_pile_size(self) -> int:
        return len(self.draw_pile)

    @property
    def discard_pile_size(self) -> int:
        return len(self.discard_pile)

    @property
    def exhaust_pile_size(self) -> int:
        return len(self.exhaust_pile)

    @property
    def hand_size(self) -> int:
        return len(self.hand)

    def reset_for_battle(self) -> None:
        """Reset all piles for a new battle, moving everything to draw pile."""
        self.draw_pile.extend(self.hand)
        self.draw_pile.extend(self.discard_pile)
        self.draw_pile.extend(self.exhaust_pile)
        self.hand.clear()
        self.discard_pile.clear()
        self.exhaust_pile.clear()
        self.shuffle()
