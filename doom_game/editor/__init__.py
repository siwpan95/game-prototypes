"""Editor sub-package: in-game level editor for the raycaster.

The editor is only instantiated from play mode (via the ``E`` key) and never
under headless runs (architecture rule: headless-safe). It reads and writes the
same level format as :mod:`doom_game.world.level_io`, so a level saved in-game
loads directly with ``python main.py --map <file>``.
"""
from doom_game.editor.level_editor import LevelEditor

__all__ = ["LevelEditor"]
