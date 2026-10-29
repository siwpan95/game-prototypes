"""与拆分前 ``2048.py`` 的行为等价性对拍。

拆分不是"把代码搬个地方"，必须证明规则语义没有被改坏。
下面 :func:`legacy_move` 是从原始 ``SimpleAuto2048.move`` 逐行转写的**参考实现**
（去掉了对 self 的依赖和 spawn 副作用），
:func:`legacy_game_over` 同理来自原始 ``game_over``。

测试用随机棋面对拍上万次，任何差异都会立刻暴露。
"""

import random
import unittest

from game2048.core.board import Board
from game2048.core.direction import Direction
from game2048.core.rules import apply_move, is_game_over

SIZE = 4


def legacy_move(grid: list[list[int]], direction: str) -> tuple[list[list[int]], int, bool]:
    """原始 ``move()`` 的逐行转写（不含 add_random）。"""
    size = len(grid)
    board = [list(row) for row in grid]
    score = 0
    moved = False

    if direction in ("left", "right"):
        for i in range(size):
            row = [x for x in board[i] if x != 0]
            if direction == "right":
                row = row[::-1]

            j = 0
            while j < len(row) - 1:
                if row[j] == row[j + 1]:
                    row[j] *= 2
                    score += row[j]
                    row.pop(j + 1)
                j += 1

            row += [0] * (size - len(row))

            if direction == "right":
                row = row[::-1]

            if board[i] != row:
                moved = True
            board[i] = row

    elif direction in ("up", "down"):
        for j in range(size):
            col = [board[i][j] for i in range(size) if board[i][j] != 0]
            if direction == "down":
                col = col[::-1]

            k = 0
            while k < len(col) - 1:
                if col[k] == col[k + 1]:
                    col[k] *= 2
                    score += col[k]
                    col.pop(k + 1)
                k += 1

            col += [0] * (size - len(col))

            if direction == "down":
                col = col[::-1]

            for i in range(size):
                if board[i][j] != col[i]:
                    moved = True
                board[i][j] = col[i]

    return board, score, moved


def legacy_game_over(grid: list[list[int]]) -> bool:
    """原始 ``game_over()`` 的逐行转写。"""
    size = len(grid)
    for i in range(size):
        for j in range(size):
            if grid[i][j] == 0:
                return False
            if j < size - 1 and grid[i][j] == grid[i][j + 1]:
                return False
            if i < size - 1 and grid[i][j] == grid[i + 1][j]:
                return False
    return True


def random_grid(rng: random.Random, size: int = SIZE) -> list[list[int]]:
    """生成一个合法的随机棋面（含较多重复值以制造合并机会）。"""
    pool = [0, 0, 0, 2, 2, 2, 4, 4, 8, 16, 32, 64, 128]
    return [[rng.choice(pool) for _ in range(size)] for _ in range(size)]


def perturbed_checkerboard(rng: random.Random, size: int = SIZE) -> list[list[int]]:
    """棋盘格（天然死局）+ 少量随机扰动，用来大量制造"接近死局"的边界样本。"""
    a, b = rng.choice([(2, 4), (4, 8), (8, 16), (16, 32)])
    grid = [[a if (r + c) % 2 == 0 else b for c in range(size)] for r in range(size)]
    for _ in range(rng.randint(0, 2)):
        r, c = rng.randrange(size), rng.randrange(size)
        grid[r][c] = rng.choice([0, a, b, 1024])
    return grid


class TestLegacyParity(unittest.TestCase):
    CASES = 3000

    def test_move_matches_legacy(self):
        rng = random.Random(20260803)
        for case in range(self.CASES):
            grid = random_grid(rng)
            board = Board.from_rows(grid)
            for direction in Direction:
                expected_grid, expected_score, expected_moved = legacy_move(
                    grid, direction.value
                )
                outcome = apply_move(board, direction)

                self.assertEqual(
                    outcome.board,
                    Board.from_rows(expected_grid),
                    f"棋面不一致 case={case} dir={direction.value} grid={grid}",
                )
                self.assertEqual(
                    outcome.gained,
                    expected_score,
                    f"得分不一致 case={case} dir={direction.value} grid={grid}",
                )
                self.assertEqual(
                    outcome.moved,
                    expected_moved,
                    f"moved 标志不一致 case={case} dir={direction.value} grid={grid}",
                )

    def test_game_over_matches_legacy(self):
        """死局是稀有事件，纯随机采样几乎采不到，所以一半样本从棋盘格扰动而来。"""
        rng = random.Random(11)
        deadlocks = 0
        for index in range(2000):
            if index % 2 == 0:
                grid = random_grid(rng)
            else:
                grid = perturbed_checkerboard(rng)
            board = Board.from_rows(grid)
            expected = legacy_game_over(grid)
            self.assertEqual(is_game_over(board), expected, f"grid={grid}")
            deadlocks += int(expected)
        # 确认样本里确实覆盖到了"已结束"的情况，否则这个测试是空转
        self.assertGreater(deadlocks, 0, "样本中没有出现死局，用例覆盖不足")

    def test_full_board_deadlock_parity(self):
        """专门构造满盘死局，确保覆盖到 True 分支。"""
        grid = [
            [2, 4, 2, 4],
            [4, 2, 4, 2],
            [2, 4, 2, 4],
            [4, 2, 4, 2],
        ]
        self.assertTrue(legacy_game_over(grid))
        self.assertTrue(is_game_over(Board.from_rows(grid)))


if __name__ == "__main__":
    unittest.main()
