"""Player class - represents the player character."""

from models.deck_manager import DeckManager
from models.relic import Relic, RelicManager


class Player:
    """Represents the player character with stats, deck, relics, and inventory.

    Initial stats:
        STR=1, DEX=1, VIT=1, FCS=1
        HP = 50 + VIT * 10
        FP = 3 + FCS * 1
    """

    def __init__(self, event_bus=None) -> None:
        # Core stats
        self.str: int = 1
        self.dex: int = 1
        self.vit: int = 1
        self.fcs: int = 1
        self.level: int = 1
        self.attribute_points: int = 0

        # Derived stats
        self._max_hp: int = 50 + self.vit * 10
        self.hp: int = self._max_hp
        self._max_fp: int = 3 + self.fcs
        self.fp: int = self._max_fp

        # Combat state
        self.block: int = 0
        self.souls: int = 0
        self.current_act: int = 1

        # Components
        self.deck: DeckManager = DeckManager()
        self.relics: RelicManager = RelicManager(event_bus)

    @property
    def max_hp(self) -> int:
        return self._max_hp

    @max_hp.setter
    def max_hp(self, value: int) -> None:
        self._max_hp = max(1, value)
        if self.hp > self._max_hp:
            self.hp = self._max_hp

    @property
    def max_fp(self) -> int:
        return self._max_fp

    @max_fp.setter
    def max_fp(self, value: int) -> None:
        self._max_fp = max(1, value)
        if self.fp > self._max_fp:
            self.fp = self._max_fp

    def recalculate_derived_stats(self) -> None:
        """Recalculate max_hp and max_fp from base stats."""
        self._max_hp = 50 + self.vit * 10
        self._max_fp = 3 + self.fcs
        if self.hp > self._max_hp:
            self.hp = self._max_hp
        if self.fp > self._max_fp:
            self.fp = self._max_fp

    def take_damage(self, amount: int) -> int:
        """Take damage, reducing block first.

        Returns the actual HP damage dealt.
        """
        remaining = amount
        if self.block > 0:
            absorbed = min(self.block, remaining)
            self.block -= absorbed
            remaining -= absorbed
        self.hp = max(0, self.hp - remaining)
        return remaining

    def heal(self, amount: int) -> int:
        """Heal HP. Returns actual amount healed."""
        old_hp = self.hp
        self.hp = min(self.max_hp, self.hp + amount)
        return self.hp - old_hp

    def heal_percent(self, pct: float) -> int:
        """Heal a percentage of max HP. Returns actual amount healed."""
        amount = int(self.max_hp * pct)
        return self.heal(amount)

    def gain_block(self, amount: int) -> int:
        """Gain block. Returns the new block value."""
        self.block += amount
        return self.block

    def reset_block(self) -> None:
        """Reset block to 0 (called at start of each turn)."""
        self.block = 0

    def reset_fp(self) -> None:
        """Reset FP to max_fp (called at start of each turn)."""
        self.fp = self.max_fp

    def is_dead(self) -> bool:
        """Check if the player is dead."""
        return self.hp <= 0

    def spend_souls(self, amount: int) -> bool:
        """Spend souls if the player has enough. Returns True if successful."""
        if self.souls >= amount:
            self.souls -= amount
            return True
        return False

    def add_stat_point(self, stat: str, amount: int = 1) -> None:
        """Add to a stat and recalculate derived stats."""
        stat = stat.lower()
        if stat == "str":
            self.str += amount
        elif stat == "dex":
            self.dex += amount
        elif stat == "vit":
            self.vit += amount
            self.recalculate_derived_stats()
        elif stat == "fcs":
            self.fcs += amount
            self.recalculate_derived_stats()

    def setup_initial_deck(self, card_factory) -> None:
        """Build the starting deck: 5 Strike + 3 Defend + 2 Backstab."""
        cards: list = []
        for _ in range(5):
            cards.append(card_factory("C001"))  # Strike
        for _ in range(3):
            cards.append(card_factory("C007"))  # Defend
        for _ in range(2):
            cards.append(card_factory("C006"))  # Backstab
        self.deck.build_initial_deck(cards)
