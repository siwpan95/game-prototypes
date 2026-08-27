"""CrosswordPuzzle: mini crossword with predefined layouts."""

import random
from .base_puzzle import BasePuzzle

CROSSWORDS: list[dict] = [
    {
        "size": 5,
        "words": [
            {"word": "SHALE", "row": 0, "col": 0, "dir": "across", "clue": "A type of sedimentary rock"},
            {"word": "HORSE", "row": 0, "col": 1, "dir": "down", "clue": "A large riding animal"},
            {"word": "LEMON", "row": 0, "col": 3, "dir": "down", "clue": "Sour yellow fruit"},
            {"word": "CRAMP", "row": 2, "col": 0, "dir": "across", "clue": "A painful muscle spasm"},
        ],
    },
    {
        "size": 5,
        "words": [
            {"word": "WHELM", "row": 0, "col": 0, "dir": "across", "clue": "To engulf or overwhelm"},
            {"word": "HORSE", "row": 0, "col": 1, "dir": "down", "clue": "A large riding animal"},
            {"word": "LEMON", "row": 0, "col": 3, "dir": "down", "clue": "Sour yellow fruit"},
            {"word": "CRAMP", "row": 2, "col": 0, "dir": "across", "clue": "A painful muscle spasm"},
        ],
    },
    {
        "size": 5,
        "words": [
            {"word": "CRANE", "row": 0, "col": 0, "dir": "across", "clue": "A tall bird or machine"},
            {"word": "RIDER", "row": 0, "col": 1, "dir": "down", "clue": "One who rides"},
            {"word": "NESTS", "row": 0, "col": 3, "dir": "down", "clue": "Bird homes"},
            {"word": "DISH", "row": 2, "col": 1, "dir": "across", "clue": "A plate or bowl"},
        ],
    },
]


class CrosswordPuzzle(BasePuzzle):
    puzzle_name = "Crossword"
    puzzle_type = "mixed"

    def _generate(self) -> None:
        template = random.choice(CROSSWORDS)
        size = template["size"]
        grid = [[None for _ in range(size)] for _ in range(size)]
        numbers: dict[tuple[int, int], int] = {}
        clue_number = 1

        for entry in template["words"]:
            word = entry["word"]
            row, col = entry["row"], entry["col"]
            key = (row, col)
            if key not in numbers:
                numbers[key] = clue_number
                clue_number += 1

            for i, ch in enumerate(word):
                r = row + (i if entry["dir"] == "down" else 0)
                c = col + (i if entry["dir"] == "across" else 0)
                if r < size and c < size:
                    grid[r][c] = ch

        clues_across = []
        clues_down = []
        for entry in template["words"]:
            key = (entry["row"], entry["col"])
            num = numbers[key]
            clue_text = f"{num}. {entry['clue']} ({len(entry['word'])} letters)"
            if entry["dir"] == "across":
                clues_across.append(clue_text)
            else:
                clues_down.append(clue_text)

        self.data = {
            "grid": grid,
            "size": size,
            "words": template["words"],
            "numbers": numbers,
            "clues_across": clues_across,
            "clues_down": clues_down,
            "player_grid": [[None for _ in range(size)] for _ in range(size)],
        }

    def check_answer(self, answer: Any) -> bool:
        """Check if the player grid matches the solution grid."""
        grid = self.data["grid"]
        player = self.data["player_grid"]
        size = self.data["size"]
        for r in range(size):
            for c in range(size):
                if grid[r][c] is not None:
                    if player[r][c] != grid[r][c]:
                        return False
        return True

    def get_hint(self) -> str:
        for entry in self.data["words"]:
            word = entry["word"]
            row, col = entry["row"], entry["col"]
            r = row + (0 if entry["dir"] == "across" else len(word) - 1)
            c = col + (0 if entry["dir"] == "down" else len(word) - 1)
            size = self.data["size"]
            if r < size and c < size:
                if self.data["player_grid"][r][c] != word[-1]:
                    return f"The last letter of '{word}' is '{word[-1]}'"
        return "Look at the clues carefully!"

    def set_cell(self, row: int, col: int, letter: str) -> None:
        size = self.data["size"]
        if 0 <= row < size and 0 <= col < size and self.data["grid"][row][col] is not None:
            self.data["player_grid"][row][col] = letter.upper() if letter else None
