"""Puzzle2048: classic 2048 sliding tile puzzle."""

import random
from typing import Any
from .base_puzzle import BasePuzzle


class Puzzle2048(BasePuzzle):
    puzzle_name = "2048"
    puzzle_type = "generated"

    def _generate(self) -> None:
        if self.difficulty == "easy":
            size, target = 3, 32
        elif self.difficulty == "medium":
            size, target = 4, 128
        else:
            size, target = 4, 256
        self.data = {
            "size": size,
            "target": target,
            "board": [[0] * size for _ in range(size)],
            "score": 0,
            "win": False,
            "game_over": False,
        }
        self._spawn_tile()
        self._spawn_tile()

    def _spawn_tile(self) -> None:
        empty = [(r, c) for r in range(self.data["size"]) for c in range(self.data["size"])
                 if self.data["board"][r][c] == 0]
        if empty:
            r, c = random.choice(empty)
            self.data["board"][r][c] = 2 if random.random() < 0.9 else 4

    def _move_left(self, row: list[int]) -> tuple[list[int], int]:
        """Merge and slide a row left. Returns (new_row, score_gained)."""
        non_zero = [x for x in row if x != 0]
        merged = []
        score = 0
        i = 0
        while i < len(non_zero):
            if i + 1 < len(non_zero) and non_zero[i] == non_zero[i + 1]:
                merged_val = non_zero[i] * 2
                merged.append(merged_val)
                score += merged_val
                i += 2
            else:
                merged.append(non_zero[i])
                i += 1
        merged += [0] * (len(row) - len(merged))
        return merged, score

    def _check_win(self) -> None:
        target = self.data["target"]
        for row in self.data["board"]:
            if any(cell >= target for cell in row):
                self.data["win"] = True
                return

    def _can_move(self) -> bool:
        size = self.data["size"]
        board = self.data["board"]
        for r in range(size):
            for c in range(size):
                if board[r][c] == 0:
                    return True
                if c + 1 < size and board[r][c] == board[r][c + 1]:
                    return True
                if r + 1 < size and board[r][c] == board[r + 1][c]:
                    return True
        return False

    def move(self, direction: str) -> str:
        """Move in one of: 'up', 'down', 'left', 'right'.
        Returns 'moved', 'unchanged', 'win', or 'game_over'."""
        if self.data["win"] or self.data["game_over"]:
            return "unchanged"

        size = self.data["size"]
        board = self.data["board"]
        moved = False
        total_score = 0

        if direction == "left":
            for r in range(size):
                new_row, s = self._move_left(board[r])
                if new_row != board[r]:
                    moved = True
                board[r] = new_row
                total_score += s
        elif direction == "right":
            for r in range(size):
                reversed_row = board[r][::-1]
                new_row, s = self._move_left(reversed_row)
                new_row = new_row[::-1]
                if new_row != board[r]:
                    moved = True
                board[r] = new_row
                total_score += s
        elif direction == "up":
            for c in range(size):
                col = [board[r][c] for r in range(size)]
                new_col, s = self._move_left(col)
                if new_col != col:
                    moved = True
                for r in range(size):
                    board[r][c] = new_col[r]
                total_score += s
        elif direction == "down":
            for c in range(size):
                col = [board[r][c] for r in range(size)]
                new_col, s = self._move_left(col[::-1])
                new_col = new_col[::-1]
                if new_col != col:
                    moved = True
                for r in range(size):
                    board[r][c] = new_col[r]
                total_score += s
        else:
            return "invalid"

        if moved:
            self.data["score"] += total_score
            self._spawn_tile()
            self._check_win()
            if self.data["win"]:
                return "win"
            if not self._can_move():
                self.data["game_over"] = True
                return "game_over"
            return "moved"
        else:
            if not self._can_move():
                self.data["game_over"] = True
                return "game_over"
            return "unchanged"

    def check_answer(self, answer: Any) -> bool:
        return self.data["win"]

    def get_hint(self) -> str:
        return "朝同一方向滑动来合并方块。试试角落策略！"
