"""编排层：只负责驱动循环，可替换策略与渲染器。"""

import random
import unittest

from game2048.app.benchmark import run_batch, summarize
from game2048.app.runner import GameRunner
from game2048.core.board import Board
from game2048.core.direction import Direction
from game2048.core.game import Game
from game2048.core.result import EndReason
from game2048.render.silent import SilentRenderer
from game2048.strategy.base import Strategy
from game2048.strategy.expectimax import GreedyStrategy
from game2048.strategy.fixed_order import FixedOrderStrategy


class AlwaysLeft(Strategy):
    name = "always-left"
    description = "测试替身"

    def choose(self, board):
        return Direction.LEFT


class Refuses(Strategy):
    name = "refuses"
    description = "测试替身"

    def choose(self, board):
        return None


class TestRunnerTermination(unittest.TestCase):
    def test_stops_on_game_over(self):
        game = Game(board=Board.from_rows([[2, 4], [8, 16]]), seed=1)
        result = GameRunner(game, FixedOrderStrategy()).run()
        self.assertIs(result.reason, EndReason.GAME_OVER)
        self.assertEqual(result.moves, 0)

    def test_stops_on_max_moves(self):
        game = Game(seed=1)
        result = GameRunner(game, GreedyStrategy(), max_moves=5).run()
        self.assertIs(result.reason, EndReason.MAX_MOVES)
        self.assertEqual(result.moves, 5)

    def test_stops_when_strategy_gives_up(self):
        game = Game(seed=1)
        result = GameRunner(game, Refuses()).run()
        self.assertIs(result.reason, EndReason.NO_MOVE_CHOSEN)

    def test_stops_when_strategy_returns_invalid_move(self):
        """棋局没结束，但策略给了一个走不动的方向：必须收敛，不能死循环。"""
        # 向左已经贴边，LEFT 不改变棋面；但还有空格，游戏没结束
        game = Game(board=Board.from_rows([[2, 0], [4, 0]]), seed=1)
        self.assertFalse(game.is_over())
        result = GameRunner(game, AlwaysLeft(), max_moves=100).run()
        self.assertIs(result.reason, EndReason.NO_MOVE_CHOSEN)
        self.assertEqual(result.moves, 0)

    def test_negative_max_moves_rejected(self):
        with self.assertRaises(ValueError):
            GameRunner(Game(seed=1), GreedyStrategy(), max_moves=-1)


class TestRunnerWiring(unittest.TestCase):
    def test_renderer_receives_every_frame(self):
        renderer = SilentRenderer()
        game = Game(seed=3)
        result = GameRunner(game, GreedyStrategy(), renderer, max_moves=12).run()
        self.assertEqual(renderer.frames, result.moves)
        self.assertTrue(renderer.finished)

    def test_result_carries_strategy_name(self):
        result = GameRunner(Game(seed=3), GreedyStrategy(), max_moves=3).run()
        self.assertEqual(result.strategy, "greedy")

    def test_default_renderer_is_silent(self):
        runner = GameRunner(Game(seed=1), GreedyStrategy())
        self.assertIsInstance(runner.renderer, SilentRenderer)

    def test_result_fields_consistent(self):
        result = GameRunner(Game(seed=8), GreedyStrategy(), max_moves=30).run()
        self.assertEqual(result.board, result.snapshot.board)
        self.assertEqual(result.max_tile, result.board.max_tile())
        self.assertGreaterEqual(result.score, 0)
        self.assertEqual(len(result.as_row()), 5)


class TestReproducibility(unittest.TestCase):
    def test_same_seed_same_outcome(self):
        """同一 seed + 同一确定性策略 => 完全相同的结果，这是做策略对比的前提。"""

        def play():
            return GameRunner(
                Game(rng=random.Random(2024)), FixedOrderStrategy(), max_moves=500
            ).run()

        a, b = play(), play()
        self.assertEqual(a.score, b.score)
        self.assertEqual(a.moves, b.moves)
        self.assertEqual(a.board, b.board)


class TestBenchmark(unittest.TestCase):
    def test_run_batch_returns_all_games(self):
        results = run_batch(FixedOrderStrategy, games=4, seed=0, max_moves=200)
        self.assertEqual(len(results), 4)

    def test_summary_shapes(self):
        results = run_batch(FixedOrderStrategy, games=4, seed=0, max_moves=200)
        summary = summarize(results)
        self.assertEqual(summary.games, 4)
        self.assertEqual(summary.strategy, "fixed")
        self.assertGreaterEqual(summary.best_score, summary.median_score)
        self.assertIn("fixed", summary.format_line())

    def test_batch_is_reproducible(self):
        first = [r.score for r in run_batch(FixedOrderStrategy, games=3, seed=7, max_moves=200)]
        second = [r.score for r in run_batch(FixedOrderStrategy, games=3, seed=7, max_moves=200)]
        self.assertEqual(first, second)

    def test_rejects_zero_games(self):
        with self.assertRaises(ValueError):
            run_batch(FixedOrderStrategy, games=0)

    def test_summarize_rejects_empty(self):
        with self.assertRaises(ValueError):
            summarize([])


class TestStrategyQuality(unittest.TestCase):
    """拆分的价值要能被量化：新策略必须显著强于原始固定顺序。"""

    def test_greedy_beats_fixed_order(self):
        fixed = summarize(run_batch(FixedOrderStrategy, games=8, seed=100, max_moves=3000))
        greedy = summarize(run_batch(GreedyStrategy, games=8, seed=100, max_moves=3000))
        self.assertGreater(
            greedy.mean_score,
            fixed.mean_score * 1.5,
            f"greedy={greedy.mean_score:.0f} fixed={fixed.mean_score:.0f}",
        )


if __name__ == "__main__":
    unittest.main()
