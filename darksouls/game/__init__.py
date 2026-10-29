"""Game package exports.

NOTE: Only import specific submodules (e.g., game.event_bus) from outside
this package. Importing game.game at module level causes circular imports
because game.game imports from controllers which imports from game.event_bus.
The Game class is imported lazily in main.py instead.
"""


def __getattr__(name):
    """Lazy import to avoid circular dependencies."""
    if name == "Game":
        from game.game import Game
        return Game
    raise AttributeError(f"module 'game' has no attribute {name}")


__all__ = ["Game"]
