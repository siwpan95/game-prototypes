"""The unified puzzle pool: one implementation, many languages.

This package replaced two parallel implementations (``text_adventure/gameplay_pool``
and ``text_adventure_zh/gameplay_pool``). Measuring them showed 17 twin files whose
divergence was ~200 lines and almost entirely user-facing text, so the text moved
into :mod:`gameplay_pool.messages` and the logic stayed here, once.

``PUZZLE_CLASSES`` is the registry used by :mod:`puzzle_service.registry` and by the
pygame clients; the order is preserved from the old builds so a seeded run picks the
same kind it used to.

Language is a constructor argument::

    MathPuzzle(difficulty="easy", lang="zh").puzzle_name   # '数学题'
    MathPuzzle(difficulty="easy", lang="en").puzzle_name   # 'Math Puzzle'
"""

from __future__ import annotations

from .anagram_puzzle import AnagramPuzzle
from .base_puzzle import BasePuzzle
from .color_sequence import ColorSequencePuzzle
from .crossword_puzzle import CrosswordPuzzle
from .guess_number import GuessNumberPuzzle
from .hangman_puzzle import HangmanPuzzle
from .math_puzzle import MathPuzzle
from .memory_puzzle import MemoryPuzzle
from .minesweeper_puzzle import MinesweeperPuzzle
from .nonogram_puzzle import NonogramPuzzle
from .pattern_puzzle import PatternPuzzle
from .puzzle_2048 import Puzzle2048
from .random_pick import PUZZLE_CLASSES, PuzzlePicker, RandomPick
from .riddle_puzzle import RiddlePuzzle
from .sudoku_puzzle import SudokuPuzzle
from .word_ladder import WordLadderPuzzle

__all__ = [
    "BasePuzzle",
    "PUZZLE_CLASSES",
    "PuzzlePicker",
    "RandomPick",
    "MathPuzzle",
    "RiddlePuzzle",
    "CrosswordPuzzle",
    "SudokuPuzzle",
    "GuessNumberPuzzle",
    "WordLadderPuzzle",
    "MinesweeperPuzzle",
    "NonogramPuzzle",
    "AnagramPuzzle",
    "MemoryPuzzle",
    "PatternPuzzle",
    "HangmanPuzzle",
    "Puzzle2048",
    "ColorSequencePuzzle",
]
