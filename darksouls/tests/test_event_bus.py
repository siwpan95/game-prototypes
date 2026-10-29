"""Tests for the EventBus - subscribe, unsubscribe, emit."""

import unittest

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from game.event_bus import EventBus


class TestEventBusInit(unittest.TestCase):
    """Test EventBus initialization."""

    def test_empty_on_init(self):
        """EventBus should have no listeners on creation."""
        eb = EventBus()
        self.assertEqual(eb._listeners, {})


class TestEventBusSubscribe(unittest.TestCase):
    """Test subscribing to events."""

    def test_subscribe(self):
        """subscribe should add a callback to the event."""
        eb = EventBus()
        called = []
        eb.subscribe("test_event", lambda: called.append(True))
        eb.emit("test_event")
        self.assertEqual(len(called), 1)

    def test_subscribe_multiple(self):
        """Multiple callbacks can subscribe to the same event."""
        eb = EventBus()
        results = []
        eb.subscribe("test_event", lambda: results.append("a"))
        eb.subscribe("test_event", lambda: results.append("b"))
        eb.emit("test_event")
        self.assertEqual(results, ["a", "b"])


class TestEventBusUnsubscribe(unittest.TestCase):
    """Test unsubscribing from events."""

    def test_unsubscribe(self):
        """unsubscribe should remove the callback."""
        eb = EventBus()
        called = []
        callback = lambda: called.append(True)
        eb.subscribe("test_event", callback)
        eb.unsubscribe("test_event", callback)
        eb.emit("test_event")
        self.assertEqual(len(called), 0)

    def test_unsubscribe_nonexistent_event(self):
        """unsubscribe from a nonexistent event should not raise."""
        eb = EventBus()
        eb.unsubscribe("no_event", lambda: None)

    def test_unsubscribe_wrong_callback(self):
        """unsubscribe with a different callback should not remove existing ones."""
        eb = EventBus()
        called = []
        eb.subscribe("test_event", lambda: called.append(True))
        eb.unsubscribe("test_event", lambda: called.append(False))
        eb.emit("test_event")
        self.assertEqual(len(called), 1)


class TestEventBusEmit(unittest.TestCase):
    """Test emitting events."""

    def test_emit_with_kwargs(self):
        """emit should pass keyword arguments to callbacks."""
        eb = EventBus()
        received = {}
        def callback(**kwargs):
            received.update(kwargs)
        eb.subscribe("test_event", callback)
        eb.emit("test_event", x=1, y="hello")
        self.assertEqual(received, {"x": 1, "y": "hello"})

    def test_emit_collects_results(self):
        """emit should collect non-None results from callbacks."""
        eb = EventBus()
        eb.subscribe("test_event", lambda: 42)
        eb.subscribe("test_event", lambda: None)
        eb.subscribe("test_event", lambda: "hello")
        results = eb.emit("test_event")
        self.assertEqual(results, [42, "hello"])

    def test_emit_no_listeners(self):
        """emit with no listeners should return empty list."""
        eb = EventBus()
        results = eb.emit("no_event")
        self.assertEqual(results, [])

    def test_emit_multiple_events_independent(self):
        """Different events should have independent listener lists."""
        eb = EventBus()
        results_a = []
        results_b = []
        eb.subscribe("event_a", lambda: results_a.append(True))
        eb.subscribe("event_b", lambda: results_b.append(True))
        eb.emit("event_a")
        self.assertEqual(len(results_a), 1)
        self.assertEqual(len(results_b), 0)


if __name__ == "__main__":
    unittest.main()
