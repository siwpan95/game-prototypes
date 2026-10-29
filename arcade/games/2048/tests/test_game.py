"""Game 聚合：随机源注入、移动与生成的解耦。"""

import random
import unittest

from game2048.core.board import Board
from game2048.core.direction import Direction
from game2048.core.game import Game


class TestGameSetup(unittest.TestCase):
    def test_new_game_has_two_tiles(self):
        game = Game(seed=1)
        self.assertEqual(len(game.board.empty_cells()), 14)
        self.assertEqual(game.score, 0)
        self.assertEqual(game.moves, 0)

    def test_seed_is_reproducible(self):
        """原始实现直接用全局 random，同一局无法复现；这里必须能复现。"""
        a = Game(seed=42)
        b = Game(seed=42)
        self.assertEqual(a.board, b.board)

    def test_different_seed_differs(self):
        boards = {Game(seed=s).board for s in range(20)}
        self.assertGreater(len(boards), 1)

    def test_rng_and_seed_are_exclusive(self):
        with self.assertRaises(ValueError):
            Game(rng=random.Random(1), seed=1)

    def test_explicit_board_skips_opening(self):
        board = Board.from_rows([[2, 0], [0, 0]])
        game = Game(board=board)
        self.assertEqual(game.board, board)


class TestGameStep(unittest.TestCase):
    def test_step_spawns_exactly_one_tile(self):
        game = Game(board=Board.from_rows([[2, 2, 0, 0]] + [[0] * 4] * 3), seed=7)
        before = game.board.tile_sum()
        self.assertTrue(game.step(Direction.LEFT))
        after = game.board.tile_sum()
        # 合并不改变总和，新增的只能是 2 或 4
        self.assertIn(after - before, (2, 4))

    def test_invalid_move_changes_nothing(self):
        board = Board.from_rows([[2, 4], [8, 16]])
        game = Game(board=board, seed=1)
        self.assertFalse(game.step(Direction.LEFT))
        self.assertEqual(game.board, board)
        self.assertEqual(game.moves, 0)
        self.assertEqual(game.score, 0)

    def test_score_accumulates(self):
        game = Game(board=Board.from_rows([[2, 2, 4, 4]] + [[0] * 4] * 3), seed=3)
        game.step(Direction.LEFT)
        self.assertEqual(game.score, 4 + 8)
        self.assertEqual(game.moves, 1)

    def test_step_accepts_string(self):
        game = Game(board=Board.from_rows([[2, 2], [0, 0]]), seed=5)
        self.assertTrue(game.step("left"))

    def test_full_replay_is_deterministic(self):
        def play(seed):
            game = Game(seed=seed)
            for _ in range(60):
                for direction in Direction:
                    if game.step(direction):
                        break
                else:
                    break
            return game.board, game.score

        self.assertEqual(play(99), play(99))


class TestGameSpawn(unittest.TestCase):
    def test_spawn_fails_on_full_board(self):
        game = Game(board=Board.from_rows([[2, 4], [8, 16]]), seed=1)
        self.assertFalse(game.spawn())

    def test_spawn_only_produces_2_or_4(self):
        game = Game(board=Board.empty(4), rng=random.Random(0))
        for _ in range(16):
            game.spawn()
        values = {v for row in game.board.rows() for v in row}
        self.assertTrue(values <= {2, 4}, f"出现了非法初始值: {values}")


class TestGameSnapshot(unittest.TestCase):
    def test_snapshot_is_detached(self):
        game = Game(board=Board.from_rows([[2, 2], [0, 0]]), seed=1)
        snapshot = game.snapshot()
        game.step(Direction.LEFT)
        self.assertEqual(snapshot.board, Board.from_rows([[2, 2], [0, 0]]))
        self.assertEqual(snapshot.moves, 0)

    def test_snapshot_reports_game_over(self):
        game = Game(board=Board.from_rows([[2, 4], [8, 16]]), seed=1)
        self.assertTrue(game.snapshot().over)


if __name__ == "__main__":
    unittest.main()
