"""DataLoader - JSON loading and object factory for cards, enemies, relics, events, acts."""

import json
import os

from models.card import Card
from models.enemy import Enemy
from models.relic import Relic


class DataLoader:
    """Loads game data from JSON files and creates game objects.

    All JSON files are located in the data/ directory relative to the
    project root.
    """

    def __init__(self, base_path: str = "") -> None:
        """Initialize with the base path to the project root.

        Args:
            base_path: Absolute path to the project root containing
                       the data/ directory.
        """
        self._base_path = base_path
        self._data_path = os.path.join(base_path, "data")

        # Cached raw data
        self._cards_data: list[dict] | None = None
        self._enemies_data: list[dict] | None = None
        self._relics_data: list[dict] | None = None
        self._events_data: list[dict] | None = None
        self._acts_data: list[dict] | None = None

        # Card lookup cache (id -> dict)
        self._card_lookup: dict[str, dict] = {}
        self._enemy_lookup: dict[str, dict] = {}
        self._relic_lookup: dict[str, dict] = {}
        self._event_lookup: dict[str, dict] = {}

    def _load_json(self, filename: str) -> list[dict]:
        """Load and parse a JSON file from the data directory."""
        filepath = os.path.join(self._data_path, filename)
        if not os.path.exists(filepath):
            return []
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)

    # --- Cards ---

    def load_cards(self) -> list[dict]:
        """Load all card data from cards.json."""
        if self._cards_data is None:
            self._cards_data = self._load_json("cards.json")
            self._card_lookup = {c["id"]: c for c in self._cards_data}
        return self._cards_data

    def get_card_data(self, card_id: str) -> dict | None:
        """Get raw card data dict by ID."""
        self.load_cards()
        return self._card_lookup.get(card_id)

    def create_card(self, card_id: str) -> Card | None:
        """Create a Card instance from card data by ID."""
        data = self.get_card_data(card_id)
        if data is None:
            return None
        return Card(
            id=data["id"],
            name=data["name"],
            cost=data["cost"],
            type=data["type"],
            damage=data.get("damage", "0"),
            block=data.get("block", 0),
            keywords=data.get("keywords", {}),
            description=data.get("description", ""),
            source=data.get("source", "Player"),
        )

    def get_player_cards(self) -> list[dict]:
        """Get all card data for Player-source cards."""
        return [c for c in self.load_cards() if c.get("source") == "Player"]

    def get_loot_cards(self) -> list[dict]:
        """Get all Player-source cards for loot selection."""
        return self.get_player_cards()

    # --- Enemies ---

    def load_enemies(self) -> list[dict]:
        """Load all enemy data from enemies.json."""
        if self._enemies_data is None:
            self._enemies_data = self._load_json("enemies.json")
            self._enemy_lookup = {e["id"]: e for e in self._enemies_data}
        return self._enemies_data

    def get_enemy_data(self, enemy_id: str) -> dict | None:
        """Get raw enemy data dict by ID."""
        self.load_enemies()
        return self._enemy_lookup.get(enemy_id)

    def create_enemy(self, enemy_id: str) -> Enemy | None:
        """Create an Enemy instance from enemy data by ID."""
        data = self.get_enemy_data(enemy_id)
        if data is None:
            return None
        return Enemy(
            id=data["id"],
            name=data["name"],
            hp=data["hp"],
            str=data["str"],
            dex=data["dex"],
            ai=data["ai"],
            card_pool=data["card_pool"],
            act=data["act"],
            is_boss=data["is_boss"],
            souls=data["souls"],
        )

    def get_enemies_for_act(self, act: int) -> list[dict]:
        """Get all non-boss enemy data for a given act."""
        return [e for e in self.load_enemies() if e["act"] == act and not e["is_boss"]]

    def get_boss_for_act(self, act: int) -> dict | None:
        """Get boss data for a given act."""
        for e in self.load_enemies():
            if e["act"] == act and e["is_boss"]:
                return e
        return None

    # --- Relics ---

    def load_relics(self) -> list[dict]:
        """Load all relic data from relics.json."""
        if self._relics_data is None:
            self._relics_data = self._load_json("relics.json")
            self._relic_lookup = {r["id"]: r for r in self._relics_data}
        return self._relics_data

    def get_relic_data(self, relic_id: str) -> dict | None:
        """Get raw relic data dict by ID."""
        self.load_relics()
        return self._relic_lookup.get(relic_id)

    def create_relic(self, relic_id: str) -> Relic | None:
        """Create a Relic instance from relic data by ID."""
        data = self.get_relic_data(relic_id)
        if data is None:
            return None
        return Relic(
            id=data["id"],
            name=data["name"],
            trigger=data["trigger"],
            effect=data["effect"],
            description=data["description"],
        )

    # --- Events ---

    def load_events(self) -> list[dict]:
        """Load all event data from events.json."""
        if self._events_data is None:
            self._events_data = self._load_json("events.json")
            self._event_lookup = {e["id"]: e for e in self._events_data}
        return self._events_data

    def get_event_data(self, event_id: str) -> dict | None:
        """Get raw event data dict by ID."""
        self.load_events()
        return self._event_lookup.get(event_id)

    def get_events_for_act(self, act: int) -> list[dict]:
        """Get all event data for a given act (currently events are shared)."""
        return self.load_events()

    # --- Acts ---

    def load_acts(self) -> list[dict]:
        """Load all act data from acts.json."""
        if self._acts_data is None:
            self._acts_data = self._load_json("acts.json")
        return self._acts_data

    def get_act_data(self, act_num: int) -> dict | None:
        """Get act data by act number."""
        for act in self.load_acts():
            if act["act"] == act_num:
                return act
        return None
