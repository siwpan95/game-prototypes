"""NonogramPuzzle: logic drawing puzzle (picross)."""

import random
from .base_puzzle import BasePuzzle


class NonogramPuzzle(BasePuzzle):
    puzzle_name = "Nonogram"
    puzzle_type = "generated"

    def _generate(self) -> None:
        if self.difficulty == "easy":
            size = 5
            fill_rate = 0.55
        elif self.difficulty == "medium":
            size = 8
            fill_rate = 0.5
        else:
            size = 10
            fill_rate = 0.45

        solution = [
            [1 if random.random() < fill_rate else 0 for _ in range(size)]
            for _ in range(size)
        ]

        # Ensure at least one filled cell per row/col (re-roll empty)
        for r in range(size):
            if all(solution[r][c] == 0 for c in range(size)):
                solution[r][random.randint(0, size - 1)] = 1
        for c in range(size):
            if all(solution[r][c] == 0 for r in range(size)):
                solution[random.randint(0, size - 1)][c] = 1

        row_clues = [self._calc_clues(solution[r]) for r in range(size)]
        col_clues = [self._calc_clues([solution[r][c] for r in range(size)]) for c in range(size)]

        self.data = {
            "size": size,
            "solution": solution,
            "row_clues": row_clues,
            "col_clues": col_clues,
            "player_grid": [[0] * size for _ in range(size)],  # 0=empty, 1=filled, 2=crossed
        }

    @staticmethod
    def _calc_clues(line: list[int]) -> list[int]:
        clues = []
        count = 0
        for val in line:
            if val == 1:
                count += 1
            else:
                if count > 0:
                    clues.append(count)
                count = 0
        if count > 0:
            clues.append(count)
        return clues if clues else [0]

    def check_answer(self, answer: Any) -> bool:
        size = self.data["size"]
        for r in range(size):
            for c in range(size):
                filled = self.data["player_grid"][r][c] == 1
                if filled != (self.data["solution"][r][c] == 1):
                    return False
        return True

    def get_hint(self) -> str:
        size = self.data["size"]
        for r in range(size):
            for c in range(size):
                if self.data["solution"][r][c] == 1 and self.data["player_grid"][r][c] != 1:
                    return f"Row {r + 1}, Col {c + 1} should be filled"
        return "Grid looks good!"

    def toggle_cell(self, row: int, col: int) -> None:
        size = self.data["size"]
        if 0 <= row < size and 0 <= col < size:
            current = self.data["player_grid"][row][col]
            self.data["player_grid"][row][col] = (current + 1) % 3  # 0->1->2->0
