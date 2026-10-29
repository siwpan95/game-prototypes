"""Enemy class - represents a hostile entity in battle."""

import random

from models.card import Card


class Enemy:
    """Represents an enemy with stats, AI, and combat intent.

    Attributes:
        id: Unique enemy identifier.
        name: Display name.
        hp: Current hit points.
        max_hp: Maximum hit points.
        str: Strength stat (damage modifier).
        dex: Dexterity stat.
        ai: AI behavior weights (e.g., {'Attack': 0.7, 'Defend': 0.3}).
        card_pool: List of card IDs this enemy can use.
        act: Which act this enemy appears in.
        is_boss: Whether this is a boss enemy.
        souls: Souls awarded on defeat.
        block: Current block value.
        intent: Current intended action type.
        intent_value: Current intended action value/description.
        vulnerable: Turns of vulnerable remaining.
        stun_count: Turns of stun remaining.
    """

    def __init__(
        self,
        id: str = "",
        name: str = "",
        hp: int = 30,
        str: int = 2,
        dex: int = 1,
        ai: dict | None = None,
        card_pool: list[str] | None = None,
        act: int = 1,
        is_boss: bool = False,
        souls: int = 20,
    ) -> None:
        self.id = id
        self.name = name
        self.hp = hp
        self.max_hp = hp
        self.str = str
        self.dex = dex
        self.ai = ai if ai is not None else {"Attack": 0.8, "Defend": 0.2}
        self.card_pool = card_pool if card_pool is not None else []
        self.act = act
        self.is_boss = is_boss
        self.souls = souls

        # Combat state
        self.block: int = 0
        self.intent: str = "Attack"
        self.intent_value: str = ""
        self.vulnerable: int = 0
        self.stun_count: int = 0
        self._actions_per_turn: int = 2 if is_boss else 1

    def set_intent(self, card_lookup=None) -> None:
        """Determine and set the enemy's intent for next turn.

        Uses AI weights to randomly select an action type, then
        looks up the corresponding card from the card pool.
        """
        action_types = list(self.ai.keys())
        weights = list(self.ai.values())

        chosen_type = random.choices(action_types, weights=weights, k=1)[0]
        self.intent = chosen_type

        # Try to find a matching card in the card pool
        if card_lookup and self.card_pool:
            matching = []
            for card_id in self.card_pool:
                card = card_lookup(card_id)
                if card is not None:
                    if chosen_type == "Attack" and card.is_attack():
                        matching.append(card)
                    elif chosen_type == "Defend" and card.is_skill() and card.block > 0:
                        matching.append(card)
                    elif chosen_type == "Special":
                        matching.append(card)

            if matching:
                chosen_card = random.choice(matching)
                if chosen_card.is_attack():
                    self.intent = "Attack"
                    self.intent_value = f"{chosen_card.damage}"
                elif chosen_card.block > 0:
                    self.intent = "Defend"
                    self.intent_value = f"Block {chosen_card.block}"
                else:
                    self.intent = "Special"
                    self.intent_value = chosen_card.name
            else:
                self.intent_value = chosen_type
        else:
            self.intent_value = chosen_type

    def take_damage(self, amount: int) -> int:
        """Take damage, reducing block first.

        Vulnerable enemies take 50% more damage.

        Returns the actual HP damage dealt.
        """
        if self.vulnerable > 0:
            amount = int(amount * 1.5)

        remaining = amount
        if self.block > 0:
            absorbed = min(self.block, remaining)
            self.block -= absorbed
            remaining -= absorbed
        self.hp = max(0, self.hp - remaining)
        return remaining

    def gain_block(self, amount: int) -> int:
        """Gain block. Returns the new block value."""
        self.block += amount
        return self.block

    def reset_block(self) -> None:
        """Reset block to 0."""
        self.block = 0

    def is_dead(self) -> bool:
        """Check if the enemy is dead."""
        return self.hp <= 0

    def apply_vulnerable(self, turns: int = 1) -> None:
        """Apply vulnerable status for a number of turns."""
        self.vulnerable += turns

    def tick_vulnerable(self) -> None:
        """Reduce vulnerable by 1 at end of turn."""
        if self.vulnerable > 0:
            self.vulnerable -= 1

    def apply_stun(self, turns: int = 1) -> None:
        """Stun the enemy for a number of turns."""
        self.stun_count += turns

    def is_stunned(self) -> bool:
        """Check if the enemy is currently stunned."""
        return self.stun_count > 0

    def tick_stun(self) -> None:
        """Reduce stun count by 1."""
        if self.stun_count > 0:
            self.stun_count -= 1

    @property
    def actions_per_turn(self) -> int:
        """Number of actions the enemy takes per turn."""
        return self._actions_per_turn

    def __repr__(self) -> str:
        return f"Enemy({self.id}: {self.name} HP:{self.hp}/{self.max_hp})"
