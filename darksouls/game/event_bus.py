"""EventBus - publish/subscribe system for relic triggers."""


class EventBus:
    """Pub/sub event bus for game-wide communication, primarily used
    for relic trigger resolution."""

    def __init__(self) -> None:
        self._listeners: dict[str, list] = {}

    def subscribe(self, event_name: str, callback) -> None:
        """Subscribe a callback to an event."""
        if event_name not in self._listeners:
            self._listeners[event_name] = []
        self._listeners[event_name].append(callback)

    def unsubscribe(self, event_name: str, callback) -> None:
        """Remove a callback from an event."""
        if event_name in self._listeners:
            self._listeners[event_name] = [
                cb for cb in self._listeners[event_name] if cb != callback
            ]

    def emit(self, event_name: str, **kwargs) -> list:
        """Emit an event and collect all results from listeners.

        Returns a list of results from all listeners that return a value.
        """
        results: list = []
        if event_name in self._listeners:
            for callback in self._listeners[event_name]:
                result = callback(**kwargs)
                if result is not None:
                    results.append(result)
        return results
