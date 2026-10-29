"""Board 值对象的行为约束。"""

import unittest

from game2048.core.board import Board


class TestBoardConstruction(unittest.TestCase):
    def test_empty_board_is_all_zero(self):
        board = Board.empty(4)
        self.assertEqual(board.size, 4)
        self.assertEqual(board.tile_sum(), 0)
        self.assertEqual(len(board.empty_cells()), 16)

    def test_rejects_non_square(self):
        with self.assertRaises(ValueError):
            Board.from_rows([[1, 2, 3], [1, 2, 3]])

    def test_rejects_negative_value(self):
        with self.assertRaises(ValueError):
            Board.from_rows([[0, -2], [0, 0]])

    def test_rejects_zero_size(self):
        with self.assertRaises(ValueError):
            Board(())


class TestBoardImmutability(unittest.TestCase):
    """不可变是整个策略层能做前瞻的前提，必须锁死。"""

    def test_with_tile_does_not_mutate_source(self):
        original = Board.from_rows([[0, 0], [0, 0]])
        modified = original.with_tile(0, 1, 4)
        self.assertEqual(original, Board.from_rows([[0, 0], [0, 0]]))
        self.assertEqual(modified, Board.from_rows([[0, 4], [0, 0]]))

    def test_cannot_assign_attribute(self):
        board = Board.empty(2)
        with self.assertRaises(Exception):
            board.cells = ((1, 1), (1, 1))  # type: ignore[misc]

    def test_is_hashable_and_value_equal(self):
        a = Board.from_rows([[2, 0], [0, 2]])
        b = Board.from_rows([[2, 0], [0, 2]])
        self.assertEqual(a, b)
        self.assertEqual(len({a, b}), 1)

    def test_with_tile_out_of_range(self):
        with self.assertRaises(IndexError):
            Board.empty(3).with_tile(3, 0, 2)


class TestBoardTransforms(unittest.TestCase):
    def test_transpose_is_involution(self):
        board = Board.from_rows([[1, 2], [3, 4]])
        self.assertEqual(board.transposed(), Board.from_rows([[1, 3], [2, 4]]))
        self.assertEqual(board.transposed().transposed(), board)

    def test_mirror_is_involution(self):
        board = Board.from_rows([[1, 2], [3, 4]])
        self.assertEqual(board.mirrored(), Board.from_rows([[2, 1], [4, 3]]))
        self.assertEqual(board.mirrored().mirrored(), board)


class TestBoardQueries(unittest.TestCase):
    def test_max_tile_and_sum(self):
        board = Board.from_rows([[2, 4], [8, 0]])
        self.assertEqual(board.max_tile(), 8)
        self.assertEqual(board.tile_sum(), 14)

    def test_is_full(self):
        self.assertFalse(Board.from_rows([[2, 0], [4, 8]]).is_full())
        self.assertTrue(Board.from_rows([[2, 4], [4, 8]]).is_full())

    def test_empty_cells_order_is_row_major(self):
        board = Board.from_rows([[0, 2], [0, 0]])
        self.assertEqual(board.empty_cells(), ((0, 0), (1, 0), (1, 1)))


if __name__ == "__main__":
    unittest.main()
