"""Relic dataclass and RelicManager for managing player relics."""

from __future__ import annotations


class Relic:
    """Represents a single relic item.

    Attributes:
        id: Unique relic identifier.
        name: Display name.
        trigger: Event name that activates this relic.
        effect: Effect definition dict.
        description: Flavor description.
    """

    def __init__(
        self,
        id: str = "",
        name: str = "",
        trigger: str = "",
        effect: dict | None = None,
        description: str = "",
    ) -> None:
        self.id = id
        self.name = name
        self.trigger = trigger
        self.effect = effect if effect is not None else {}
        self.description = description

    def __repr__(self) -> str:
        return f"Relic({self.id}: {self.name})"


class RelicManager:
    """Manages a collection of relics with a maximum capacity.

    Relics are triggered via the EventBus by subscribing to their
    trigger events. Max 5 relics; if exceeded, the oldest is removed.
    """

    MAX_RELICS = 5

    def __init__(self, event_bus=None) -> None:
        self._relics: list[Relic] = []
        self._event_bus = event_bus

    @property
    def relics(self) -> list[Relic]:
        """Return a copy of the current relic list."""
        return list(self._relics)

    def add(self, relic: Relic) -> Relic | None:
        """Add a relic. If at max capacity, remove and return the oldest.

        Returns:
            The removed relic if capacity was exceeded, else None.
        """
        removed = None
        if len(self._relics) >= self.MAX_RELICS:
            removed = self._relics.pop(0)
            self._unsubscribe_relic(removed)
        self._relics.append(relic)
        self._subscribe_relic(relic)
        return removed

    def remove(self, relic_id: str) -> Relic | None:
        """Remove a relic by ID. Returns the removed relic or None."""
        for i, relic in enumerate(self._relics):
            if relic.id == relic_id:
                removed = self._relics.pop(i)
                self._unsubscribe_relic(removed)
                return removed
        return None

    def has(self, relic_id: str) -> bool:
        """Check if a relic with the given ID is owned."""
        return any(r.id == relic_id for r in self._relics)

    def get(self, relic_id: str) -> Relic | None:
        """Get a relic by ID, or None."""
        for r in self._relics:
            if r.id == relic_id:
                return r
        return None

    def clear(self) -> None:
        """Remove all relics."""
        for relic in self._relics:
            self._unsubscribe_relic(relic)
        self._relics.clear()

    def _subscribe_relic(self, relic: Relic) -> None:
        """Subscribe this relic's effect to the EventBus."""
        if self._event_bus is None:
            return
        callback = self._make_callback(relic)
        self._event_bus.subscribe(relic.trigger, callback)
        relic._callback = callback  # type: ignore[attr-defined]

    def _unsubscribe_relic(self, relic: Relic) -> None:
        """Unsubscribe this relic's effect from the EventBus."""
        if self._event_bus is None:
            return
        callback = getattr(relic, "_callback", None)
        if callback is not None:
            self._event_bus.unsubscribe(relic.trigger, callback)

    def _make_callback(self, relic: Relic):
        """Create a callback function for this relic's trigger."""
        def callback(**kwargs):
            return {"relic": relic, "effect": relic.effect, "context": kwargs}
        return callback
