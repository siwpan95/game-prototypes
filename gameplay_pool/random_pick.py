"""RandomPick and PuzzlePicker: intelligent puzzle selection."""

import random
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

PUZZLE_CLASSES: list[type[BasePuzzle]] = [
    MathPuzzle,
    RiddlePuzzle,
    CrosswordPuzzle,
    SudokuPuzzle,
    GuessNumberPuzzle,
    WordLadderPuzzle,
    MinesweeperPuzzle,
    NonogramPuzzle,
    AnagramPuzzle,
    MemoryPuzzle,
    PatternPuzzle,
    HangmanPuzzle,
    Puzzle2048,
    ColorSequencePuzzle,
]

CONTENT_PUZZLES = [cls for cls in PUZZLE_CLASSES if cls.puzzle_type == "content"]
MIXED_PUZZLES = [cls for cls in PUZZLE_CLASSES if cls.puzzle_type == "mixed"]
GENERATED_PUZZLES = [cls for cls in PUZZLE_CLASSES if cls.puzzle_type == "generated"]

MODE_WEIGHTS = {
    "content_heavy": (70, 20, 10),
    "balanced": (33, 34, 33),
    "generated_heavy": (10, 20, 70),
}


class PuzzlePicker:
    """Intelligent puzzle selector based on mode and difficulty."""

    def __init__(self, mode: str = "balanced", difficulty: str = "medium"):
        self.mode = mode
        self.difficulty = difficulty
        self._history: list[type[BasePuzzle]] = []

    def pick(self, lang: str | None = None) -> BasePuzzle:
        """Build one puzzle from the weighted pools.

        ``lang`` reaches the puzzle so the whole game — interface, hints and content —
        speaks one language. It used to be decided at import time by which copy of
        this package happened to be installed.
        """
        weights = MODE_WEIGHTS.get(self.mode, (33, 34, 33))
        difficulty = self.difficulty
        if difficulty == "random":
            difficulty = random.choice(["easy", "medium", "hard"])

        pool_weights = [
            (CONTENT_PUZZLES, weights[0]),
            (MIXED_PUZZLES, weights[1]),
            (GENERATED_PUZZLES, weights[2]),
        ]

        chosen_pool = random.choices(
            [pw[0] for pw in pool_weights],
            weights=[pw[1] for pw in pool_weights],
            k=1,
        )[0]

        puzzle_cls = random.choice(chosen_pool)
        self._history.append(puzzle_cls)
        return puzzle_cls(difficulty=difficulty, lang=lang)

    def reset_history(self) -> None:
        self._history.clear()


class RandomPick:
    """Completely random puzzle selection (uniform distribution)."""

    def __init__(self, difficulty: str = "medium"):
        self.difficulty = difficulty

    def pick(self, lang: str | None = None) -> BasePuzzle:
        """Build one puzzle, uniformly at random, in *lang*."""
        difficulty = self.difficulty
        if difficulty == "random":
            difficulty = random.choice(["easy", "medium", "hard"])
        puzzle_cls = random.choice(PUZZLE_CLASSES)
        return puzzle_cls(difficulty=difficulty, lang=lang)
