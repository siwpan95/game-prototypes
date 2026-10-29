"""Dark Souls: Card Chronicles - A Roguelike Card Game.

Entry point for the game. Run with: python main.py
"""

import os
import sys

# Add the project root to sys.path so imports work correctly
project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from game import Game


def main() -> None:
    """Create and run the game."""
    base_path = os.path.dirname(os.path.abspath(__file__))
    game = Game(base_path=base_path)
    game.run()


if __name__ == "__main__":
    main()
