"""CrosswordPuzzle: mini crossword with predefined layouts."""

import random
from .base_puzzle import BasePuzzle

CROSSWORDS: list[dict] = [
    {
        "size": 5,
        "words": [
            {"word": "SHALE", "row": 0, "col": 0, "dir": "across", "clue": "一种沉积岩"},
            {"word": "HORSE", "row": 0, "col": 1, "dir": "down", "clue": "大型骑乘动物"},
            {"word": "LEMON", "row": 0, "col": 3, "dir": "down", "clue": "酸酸的黄色水果"},
            {"word": "CRAMP", "row": 2, "col": 0, "dir": "across", "clue": "疼痛的肌肉痉挛"},
        ],
    },
    {
        "size": 5,
        "words": [
            {"word": "WHELM", "row": 0, "col": 0, "dir": "across", "clue": "吞没或压倒"},
            {"word": "HORSE", "row": 0, "col": 1, "dir": "down", "clue": "大型骑乘动物"},
            {"word": "LEMON", "row": 0, "col": 3, "dir": "down", "clue": "酸酸的黄色水果"},
            {"word": "CRAMP", "row": 2, "col": 0, "dir": "across", "clue": "疼痛的肌肉痉挛"},
        ],
    },
    {
        "size": 5,
        "words": [
            {"word": "CRANE", "row": 0, "col": 0, "dir": "across", "clue": "高大的鸟或机器"},
            {"word": "RIDER", "row": 0, "col": 1, "dir": "down", "clue": "骑乘者"},
            {"word": "NESTS", "row": 0, "col": 3, "dir": "down", "clue": "鸟的家"},
            {"word": "DISH", "row": 2, "col": 1, "dir": "across", "clue": "盘子或碗"},
        ],
    },
]


class CrosswordPuzzle(BasePuzzle):
    puzzle_name = "填字游戏"
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
            clue_text = f"{num}. {entry['clue']} ({len(entry['word'])}个字母)"
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
            dir_label = "横向" if entry["dir"] == "across" else "纵向"
            # 检查该单词是否已全部正确填写
            all_correct = True
            for i, ch in enumerate(word):
                r = entry["row"] + (i if entry["dir"] == "down" else 0)
                c = entry["col"] + (i if entry["dir"] == "across" else 0)
                if self.data["player_grid"][r][c] != ch:
                    all_correct = False
                    break
            if not all_correct:
                return f"{dir_label}: {entry['clue']}（{len(word)}个字母）"
        return "所有单词已正确填写！"

    def set_cell(self, row: int, col: int, letter: str) -> None:
        size = self.data["size"]
        if 0 <= row < size and 0 <= col < size and self.data["grid"][row][col] is not None:
            self.data["player_grid"][row][col] = letter.upper() if letter else None
