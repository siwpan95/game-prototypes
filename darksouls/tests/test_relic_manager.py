"""Tests for the RelicManager - add, remove, max 5 relics, event bus integration."""

import unittest

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from models.relic import Relic, RelicManager
from game.event_bus import EventBus


def make_relic(relic_id: str = "R001", name: str = "Test Relic",
               trigger: str = "on_battle_start", effect: dict = None) -> Relic:
    """Helper to create a test relic."""
    return Relic(id=relic_id, name=name, trigger=trigger,
                 effect=effect or {"AddMaxHP": 10})


class TestRelicInit(unittest.TestCase):
    """Test Relic initialization."""

    def test_default_values(self):
        """Relic should have sensible defaults."""
        r = Relic()
        self.assertEqual(r.id, "")
        self.assertEqual(r.name, "")
        self.assertEqual(r.trigger, "")
        self.assertEqual(r.effect, {})

    def test_custom_values(self):
        """Relic should accept custom values."""
        r = Relic(id="R001", name="Ring of Favor", trigger="on_battle_start",
                  effect={"AddMaxHP": 15})
        self.assertEqual(r.id, "R001")
        self.assertEqual(r.name, "Ring of Favor")
        self.assertEqual(r.trigger, "on_battle_start")
        self.assertEqual(r.effect, {"AddMaxHP": 15})

    def test_repr(self):
        """repr should show relic id and name."""
        r = Relic(id="R001", name="Ring of Favor")
        self.assertIn("R001", repr(r))
        self.assertIn("Ring of Favor", repr(r))


class TestRelicManagerAdd(unittest.TestCase):
    """Test adding relics."""

    def test_add_relic(self):
        """add should add a relic to the manager."""
        rm = RelicManager()
        relic = make_relic("R001")
        removed = rm.add(relic)
        self.assertIsNone(removed)
        self.assertEqual(len(rm.relics), 1)

    def test_add_multiple_relics(self):
        """Should be able to add multiple relics."""
        rm = RelicManager()
        for i in range(3):
            rm.add(make_relic(f"R{i:03d}"))
        self.assertEqual(len(rm.relics), 3)

    def test_max_5_relics(self):
        """Adding a 6th relic should remove the oldest."""
        rm = RelicManager()
        for i in range(6):
            removed = rm.add(make_relic(f"R{i:03d}"))
            if i == 5:
                self.assertIsNotNone(removed)
                self.assertEqual(removed.id, "R000")
        self.assertEqual(len(rm.relics), 5)

    def test_add_at_max_returns_oldest(self):
        """When at max capacity, add should return the oldest relic."""
        rm = RelicManager()
        rm.add(make_relic("R001", name="First"))
        rm.add(make_relic("R002", name="Second"))
        rm.add(make_relic("R003", name="Third"))
        rm.add(make_relic("R004", name="Fourth"))
        rm.add(make_relic("R005", name="Fifth"))
        removed = rm.add(make_relic("R006", name="Sixth"))
        self.assertIsNotNone(removed)
        self.assertEqual(removed.id, "R001")
        self.assertEqual(removed.name, "First")

    def test_max_relics_constant(self):
        """MAX_RELICS should be 5."""
        self.assertEqual(RelicManager.MAX_RELICS, 5)


class TestRelicManagerRemove(unittest.TestCase):
    """Test removing relics."""

    def test_remove_relic(self):
        """remove should remove a relic by ID."""
        rm = RelicManager()
        rm.add(make_relic("R001"))
        removed = rm.remove("R001")
        self.assertIsNotNone(removed)
        self.assertEqual(removed.id, "R001")
        self.assertEqual(len(rm.relics), 0)

    def test_remove_not_found(self):
        """remove should return None for nonexistent ID."""
        rm = RelicManager()
        removed = rm.remove("R999")
        self.assertIsNone(removed)


class TestRelicManagerHasAndGet(unittest.TestCase):
    """Test has and get methods."""

    def test_has_relic(self):
        """has should return True if relic exists."""
        rm = RelicManager()
        rm.add(make_relic("R001"))
        self.assertTrue(rm.has("R001"))
        self.assertFalse(rm.has("R002"))

    def test_get_relic(self):
        """get should return the relic by ID."""
        rm = RelicManager()
        rm.add(make_relic("R001", name="Ring of Favor"))
        relic = rm.get("R001")
        self.assertIsNotNone(relic)
        self.assertEqual(relic.name, "Ring of Favor")

    def test_get_not_found(self):
        """get should return None for nonexistent ID."""
        rm = RelicManager()
        self.assertIsNone(rm.get("R999"))


class TestRelicManagerClear(unittest.TestCase):
    """Test clearing all relics."""

    def test_clear(self):
        """clear should remove all relics."""
        rm = RelicManager()
        for i in range(3):
            rm.add(make_relic(f"R{i:03d}"))
        rm.clear()
        self.assertEqual(len(rm.relics), 0)


class TestRelicManagerEventBusIntegration(unittest.TestCase):
    """Test RelicManager integration with EventBus."""

    def test_relic_subscribes_on_add(self):
        """Adding a relic should subscribe it to the EventBus."""
        eb = EventBus()
        rm = RelicManager(eb)
        relic = make_relic("R001", trigger="on_battle_start", effect={"AddMaxHP": 15})
        rm.add(relic)
        results = eb.emit("on_battle_start", player=None)
        self.assertEqual(len(results), 1)

    def test_relic_unsubscribes_on_remove(self):
        """Removing a relic should unsubscribe it from the EventBus."""
        eb = EventBus()
        rm = RelicManager(eb)
        relic = make_relic("R001", trigger="on_battle_start")
        rm.add(relic)
        rm.remove("R001")
        results = eb.emit("on_battle_start", player=None)
        self.assertEqual(len(results), 0)

    def test_relic_callback_returns_effect(self):
        """Relic callback should return effect data."""
        eb = EventBus()
        rm = RelicManager(eb)
        relic = make_relic("R001", trigger="on_battle_start", effect={"AddMaxHP": 15})
        rm.add(relic)
        results = eb.emit("on_battle_start", player=None)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["effect"], {"AddMaxHP": 15})

    def test_multiple_relics_different_triggers(self):
        """Multiple relics with different triggers should work independently."""
        eb = EventBus()
        rm = RelicManager(eb)
        rm.add(make_relic("R001", trigger="on_battle_start"))
        rm.add(make_relic("R002", trigger="on_card_played"))
        results_start = eb.emit("on_battle_start")
        results_played = eb.emit("on_card_played")
        self.assertEqual(len(results_start), 1)
        self.assertEqual(len(results_played), 1)

    def test_no_event_bus_graceful(self):
        """RelicManager without EventBus should not crash."""
        rm = RelicManager(None)
        relic = make_relic("R001", trigger="on_battle_start")
        rm.add(relic)  # Should not raise
        rm.remove("R001")  # Should not raise


if __name__ == "__main__":
    unittest.main()
