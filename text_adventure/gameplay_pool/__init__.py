"""Gameplay pool package."""

from .base_puzzle import BasePuzzle
from .math_puzzle import MathPuzzle
from .riddle_puzzle import RiddlePuzzle
from .crossword_puzzle import CrosswordPuzzle
from .sudoku_puzzle import SudokuPuzzle
from .guess_number import GuessNumberPuzzle
from .word_ladder import WordLadderPuzzle
from .minesweeper_puzzle import MinesweeperPuzzle
from .nonogram_puzzle import NonogramPuzzle
from .anagram_puzzle import AnagramPuzzle
from .memory_puzzle import MemoryPuzzle
from .pattern_puzzle import PatternPuzzle
from .hangman_puzzle import HangmanPuzzle
from .puzzle_2048 import Puzzle2048
from .color_sequence import ColorSequencePuzzle
from .random_pick import PuzzlePicker, RandomPick, PUZZLE_CLASSES

__all__ = [
    "BasePuzzle",
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
    "PuzzlePicker",
    "RandomPick",
    "PUZZLE_CLASSES",
]
