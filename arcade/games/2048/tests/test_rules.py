"""规则层：合并语义与四方向归一化。"""

import unittest

from game2048.core.board import Board
from game2048.core.direction import Direction
from game2048.core.rules import (
    apply_move,
    available_moves,
    can_move,
    is_game_over,
    slide_line,
)


class TestSlideLine(unittest.TestCase):
    def test_compacts_without_merge(self):
        self.assertEqual(slide_line((0, 2, 0, 4)), ((2, 4, 0, 0), 0))

    def test_single_merge_scores(self):
        self.assertEqual(slide_line((2, 2, 0, 0)), ((4, 0, 0, 0), 4))

    def test_no_chain_merge_in_one_move(self):
        """[2,2,2,0] 只能合并前两个，产生的 4 不能立刻再和第三个 2 合并。"""
        self.assertEqual(slide_line((2, 2, 2, 0)), ((4, 2, 0, 0), 4))

    def test_pairwise_merge(self):
        self.assertEqual(slide_line((2, 2, 2, 2)), ((4, 4, 0, 0), 8))

    def test_merged_result_does_not_merge_again(self):
        """[4,4,8,0] -> [8,8]，新产生的 8 不能和原有的 8 合并。"""
        self.assertEqual(slide_line((4, 4, 8, 0)), ((8, 8, 0, 0), 8))

    def test_merge_starts_from_front(self):
        self.assertEqual(slide_line((4, 2, 2, 0)), ((4, 4, 0, 0), 4))

    def test_length_preserved(self):
        for line in [(0, 0, 0), (2, 4, 8), (2, 2, 2, 2, 2)]:
            self.assertEqual(len(slide_line(line)[0]), len(line))

    def test_empty_line_is_noop(self):
        self.assertEqual(slide_line((0, 0, 0, 0)), ((0, 0, 0, 0), 0))


class TestApplyMoveDirections(unittest.TestCase):
    """四个方向都归约到 slide_line，这里逐个钉死坐标变换的正确性。"""

    def setUp(self):
        self.board = Board.from_rows(
            [
                [2, 0, 0, 2],
                [0, 4, 0, 0],
                [0, 0, 0, 0],
                [8, 0, 0, 8],
            ]
        )

    def test_left(self):
        outcome = apply_move(self.board, Direction.LEFT)
        self.assertEqual(
            outcome.board,
            Board.from_rows(
                [
                    [4, 0, 0, 0],
                    [4, 0, 0, 0],
                    [0, 0, 0, 0],
                    [16, 0, 0, 0],
                ]
            ),
        )
        self.assertEqual(outcome.gained, 4 + 16)
        self.assertTrue(outcome.moved)

    def test_right(self):
        outcome = apply_move(self.board, Direction.RIGHT)
        self.assertEqual(
            outcome.board,
            Board.from_rows(
                [
                    [0, 0, 0, 4],
                    [0, 0, 0, 4],
                    [0, 0, 0, 0],
                    [0, 0, 0, 16],
                ]
            ),
        )

    def test_up(self):
        outcome = apply_move(self.board, Direction.UP)
        self.assertEqual(
            outcome.board,
            Board.from_rows(
                [
                    [2, 4, 0, 2],
                    [8, 0, 0, 8],
                    [0, 0, 0, 0],
                    [0, 0, 0, 0],
                ]
            ),
        )
        self.assertEqual(outcome.gained, 0)

    def test_down(self):
        outcome = apply_move(self.board, Direction.DOWN)
        self.assertEqual(
            outcome.board,
            Board.from_rows(
                [
                    [0, 0, 0, 0],
                    [0, 0, 0, 0],
                    [2, 0, 0, 2],
                    [8, 4, 0, 8],
                ]
            ),
        )

    def test_down_stacks_toward_bottom(self):
        """单独钉一次 DOWN：它的变换是 transpose+mirror，最容易写反。"""
        board = Board.from_rows([[2, 0], [2, 0]])
        outcome = apply_move(board, Direction.DOWN)
        self.assertEqual(outcome.board, Board.from_rows([[0, 0], [4, 0]]))

    def test_up_stacks_toward_top(self):
        board = Board.from_rows([[0, 0], [2, 0]])
        outcome = apply_move(board, Direction.UP)
        self.assertEqual(outcome.board, Board.from_rows([[2, 0], [0, 0]]))


class TestApplyMovePurity(unittest.TestCase):
    def test_source_board_unchanged(self):
        board = Board.from_rows([[2, 2], [0, 0]])
        snapshot = Board.from_rows([[2, 2], [0, 0]])
        apply_move(board, Direction.LEFT)
        self.assertEqual(board, snapshot)

    def test_no_spawn_happens(self):
        """规则层绝不生成新方块——那是 Game 的职责。"""
        board = Board.from_rows([[2, 2], [0, 0]])
        outcome = apply_move(board, Direction.LEFT)
        self.assertEqual(outcome.board.tile_sum(), 4)

    def test_moved_false_when_nothing_changes(self):
        board = Board.from_rows([[2, 4], [8, 16]])
        outcome = apply_move(board, Direction.LEFT)
        self.assertFalse(outcome.moved)
        self.assertEqual(outcome.gained, 0)

    def test_accepts_string_direction(self):
        board = Board.from_rows([[2, 2], [0, 0]])
        self.assertEqual(
            apply_move(board, "left").board, apply_move(board, Direction.LEFT).board
        )

    def test_rejects_bad_direction(self):
        with self.assertRaises(ValueError):
            apply_move(Board.empty(2), "sideways")


class TestGameOver(unittest.TestCase):
    def test_not_over_with_empty_cell(self):
        self.assertFalse(is_game_over(Board.from_rows([[2, 4], [8, 0]])))

    def test_not_over_with_horizontal_pair(self):
        board = Board.from_rows([[2, 2], [4, 8]])
        self.assertTrue(can_move(board))
        self.assertFalse(is_game_over(board))

    def test_not_over_with_vertical_pair(self):
        self.assertFalse(is_game_over(Board.from_rows([[2, 4], [2, 8]])))

    def test_over_when_locked(self):
        board = Board.from_rows(
            [
                [2, 4, 2, 4],
                [4, 2, 4, 2],
                [2, 4, 2, 4],
                [4, 2, 4, 2],
            ]
        )
        self.assertTrue(is_game_over(board))
        self.assertEqual(available_moves(board), ())

    def test_available_moves_matches_can_move(self):
        board = Board.from_rows([[2, 0], [0, 0]])
        moves = available_moves(board)
        self.assertIn(Direction.RIGHT, moves)
        self.assertIn(Direction.DOWN, moves)
        self.assertNotIn(Direction.LEFT, moves)
        self.assertNotIn(Direction.UP, moves)


if __name__ == "__main__":
    unittest.main()
