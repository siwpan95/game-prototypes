"""EventBus: simple publish/subscribe event system."""


class EventBus:
    """Central event bus for game-wide communication."""

    def __init__(self):
        self._listeners: dict[str, list] = {}

    def subscribe(self, event_type: str, callback) -> None:
        if event_type not in self._listeners:
            self._listeners[event_type] = []
        self._listeners[event_type].append(callback)

    def unsubscribe(self, event_type: str, callback) -> None:
        if event_type in self._listeners:
            self._listeners[event_type] = [
                cb for cb in self._listeners[event_type] if cb != callback
            ]

    def publish(self, event_type: str, data: dict | None = None) -> None:
        if event_type in self._listeners:
            for callback in self._listeners[event_type]:
                callback(data or {})
