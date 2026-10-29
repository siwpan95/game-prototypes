"""EventBus - Simple publish/subscribe event system."""
from typing import Callable, Dict, List


class EventBus:
    """Publish/subscribe event bus for decoupled communication."""

    def __init__(self) -> None:
        self._subscribers: Dict[str, List[Callable]] = {}

    def subscribe(self, event_type: str, callback: Callable) -> None:
        """Subscribe a callback to an event type."""
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        self._subscribers[event_type].append(callback)

    def unsubscribe(self, event_type: str, callback: Callable) -> None:
        """Unsubscribe a callback from an event type."""
        if event_type in self._subscribers:
            try:
                self._subscribers[event_type].remove(callback)
            except ValueError:
                pass

    def publish(self, event_type: str, data: dict = None) -> None:
        """Publish an event, calling all subscribers in order."""
        if data is None:
            data = {}
        if event_type in self._subscribers:
            for callback in self._subscribers[event_type]:
                callback(data)
