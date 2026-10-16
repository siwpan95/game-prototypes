"""SudokuPuzzle: algorithmically generated sudoku at multiple sizes."""

import random
from .base_puzzle import BasePuzzle


class SudokuPuzzle(BasePuzzle):
    puzzle_name = "Sudoku"
    puzzle_type = "generated"

    def _generate(self) -> None:
        if self.difficulty == "easy":
            size = 4
            reveal_count = 8
        elif self.difficulty == "medium":
            size = 6
            reveal_count = 12
        else:  # hard
            size = 9
            reveal_count = 25

        box_h, box_w = self._box_dims(size)
        # The generator must be passed explicitly: _generate_solution is a static
        # method, so it has no `self` to read the seeded rng from. Without this the
        # solution came out different every run and the daily puzzle was not
        # reproducible for sudoku (measured 2026-10-16).
        solution = self._generate_solution(size, box_h, box_w, rng=self._rng())
        puzzle = [row[:] for row in solution]

        cells = [(r, c) for r in range(size) for c in range(size)]
        self._rng().shuffle(cells)
        hidden = cells[: len(cells) - reveal_count]
        for r, c in hidden:
            puzzle[r][c] = 0

        self.data = {
            "size": size,
            "box_h": box_h,
            "box_w": box_w,
            "solution": solution,
            "puzzle": puzzle,
            "player_grid": [row[:] for row in puzzle],
        }

    @staticmethod
    def _box_dims(size: int) -> tuple[int, int]:
        if size == 4:
            return 2, 2
        elif size == 6:
            return 2, 3
        else:
            return 3, 3

    @staticmethod
    def _generate_solution(size: int, box_h: int, box_w: int, rng=None) -> list[list[int]]:
        if rng is None:
            rng = random
        base = list(range(1, size + 1))
        rng.shuffle(base)
        solution = [[0] * size for _ in range(size)]

        def valid(r: int, c: int, n: int) -> bool:
            if n in solution[r]:
                return False
            if any(solution[i][c] == n for i in range(size)):
                return False
            br, bc = (r // box_h) * box_h, (c // box_w) * box_w
            for i in range(br, br + box_h):
                for j in range(bc, bc + box_w):
                    if solution[i][j] == n:
                        return False
            return True

        def fill(pos: int) -> bool:
            if pos == size * size:
                return True
            r, c = pos // size, pos % size
            nums = base[:]
            rng.shuffle(nums)
            for n in nums:
                if valid(r, c, n):
                    solution[r][c] = n
                    if fill(pos + 1):
                        return True
                    solution[r][c] = 0
            return False

        fill(0)
        return solution

    def check_answer(self, answer: Any) -> bool:
        size = self.data["size"]
        for r in range(size):
            for c in range(size):
                if self.data["player_grid"][r][c] != self.data["solution"][r][c]:
                    return False
        return True

    def get_hint(self) -> str:
        size = self.data["size"]
        for r in range(size):
            for c in range(size):
                if self.data["player_grid"][r][c] == 0:
                    val = self.data["solution"][r][c]
                    self.data["player_grid"][r][c] = val
                    return f"Row {r + 1}, Col {c + 1} is {val}"
        return "The grid is already filled!"

    def set_cell(self, row: int, col: int, num: int) -> None:
        size = self.data["size"]
        if 0 <= row < size and 0 <= col < size and self.data["puzzle"][row][col] == 0:
            self.data["player_grid"][row][col] = num
