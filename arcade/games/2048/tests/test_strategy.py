"""策略层：接口契约、注册表、以及"策略不得污染棋盘"这条硬约束。"""

import random
import unittest

from game2048.core.board import Board
from game2048.core.direction import Direction
from game2048.strategy import base as registry
from game2048.strategy.expectimax import (
    ExpectimaxStrategy,
    GreedyStrategy,
    adaptive_depth,
)
from game2048.strategy.fixed_order import FixedOrderStrategy
from game2048.strategy.heuristics import (
    DEFAULT_WEIGHTS,
    STRONG_WEIGHTS,
    corner_score,
    empty_score,
    evaluate,
    merge_potential_score,
    monotonicity_score,
    smoothness_score,
)
from game2048.strategy.mcts import MCTSStrategy
from game2048.strategy.random_walk import RandomStrategy

DEAD_BOARD = Board.from_rows(
    [
        [2, 4, 2, 4],
        [4, 2, 4, 2],
        [2, 4, 2, 4],
        [4, 2, 4, 2],
    ]
)

OPEN_BOARD = Board.from_rows(
    [
        [2, 0, 0, 2],
        [0, 4, 0, 0],
        [0, 0, 0, 0],
        [8, 0, 0, 8],
    ]
)


def all_strategies():
    return [
        FixedOrderStrategy(),
        RandomStrategy(seed=1),
        GreedyStrategy(),
        ExpectimaxStrategy(depth=2, spawn_samples=3, seed=1),
        MCTSStrategy(iterations=10, seed=1),
    ]


class TestStrategyContract(unittest.TestCase):
    """所有策略都必须满足的通用契约。"""

    def test_returns_none_on_dead_board(self):
        for strategy in all_strategies():
            with self.subTest(strategy=strategy.name):
                self.assertIsNone(strategy.choose(DEAD_BOARD))

    def test_returns_legal_direction(self):
        for strategy in all_strategies():
            with self.subTest(strategy=strategy.name):
                direction = strategy.choose(OPEN_BOARD)
                self.assertIsInstance(direction, Direction)

    def test_never_mutates_board(self):
        """这是不可变 Board 换来的保障，用测试锁死，防止将来被改回可变实现。"""
        snapshot = Board.from_rows(OPEN_BOARD.rows())
        for strategy in all_strategies():
            with self.subTest(strategy=strategy.name):
                strategy.choose(OPEN_BOARD)
                self.assertEqual(OPEN_BOARD, snapshot)

    def test_every_strategy_has_description(self):
        for name in registry.available_names():
            with self.subTest(name=name):
                self.assertTrue(registry.REGISTRY[name].description)


class TestRegistry(unittest.TestCase):
    def test_builtin_strategies_registered(self):
        self.assertEqual(
            set(registry.available_names()),
            {"fixed", "random", "greedy", "expectimax", "mcts"},
        )

    def test_create_by_name(self):
        self.assertIsInstance(registry.create("greedy"), GreedyStrategy)

    def test_unknown_name_raises(self):
        with self.assertRaises(ValueError):
            registry.create("no-such-strategy")

    def test_duplicate_registration_raises(self):
        class Dup(GreedyStrategy):
            name = "greedy"

        with self.assertRaises(ValueError):
            registry.register(Dup)


class TestFixedOrder(unittest.TestCase):
    def test_follows_declared_priority(self):
        """原始顺序是 右->下->左->上，右可行时必须选右。"""
        self.assertIs(FixedOrderStrategy().choose(OPEN_BOARD), Direction.RIGHT)

    def test_falls_through_when_first_choice_invalid(self):
        board = Board.from_rows([[0, 0], [0, 2]])  # 右不可行，下不可行，左可行
        self.assertIs(FixedOrderStrategy().choose(board), Direction.LEFT)

    def test_custom_order(self):
        strategy = FixedOrderStrategy(order=(Direction.UP, Direction.RIGHT))
        self.assertIs(strategy.choose(OPEN_BOARD), Direction.UP)

    def test_empty_order_rejected(self):
        with self.assertRaises(ValueError):
            FixedOrderStrategy(order=())


class TestExpectimaxConfig(unittest.TestCase):
    def test_depth_must_be_positive(self):
        with self.assertRaises(ValueError):
            ExpectimaxStrategy(depth=0)

    def test_spawn_samples_must_be_positive(self):
        with self.assertRaises(ValueError):
            ExpectimaxStrategy(spawn_samples=0)

    def test_rng_and_seed_exclusive(self):
        with self.assertRaises(ValueError):
            ExpectimaxStrategy(rng=random.Random(1), seed=1)

    def test_avoids_immediate_death(self):
        """只有一条活路时必须选中它。"""
        # 满盘，且纵向没有任何相邻相等 —— 只有横向的两个 8 能合并
        board = Board.from_rows(
            [
                [2, 4, 8, 2],
                [4, 8, 2, 4],
                [8, 2, 4, 16],
                [2, 4, 8, 8],
            ]
        )
        for strategy in (GreedyStrategy(), ExpectimaxStrategy(depth=2, seed=0)):
            with self.subTest(strategy=strategy.name):
                self.assertIn(
                    strategy.choose(board), (Direction.LEFT, Direction.RIGHT)
                )


class TestHeuristics(unittest.TestCase):
    def test_empty_score_counts_zeros(self):
        self.assertEqual(empty_score(Board.from_rows([[0, 2], [0, 0]])), 3.0)

    def test_monotonic_board_has_no_penalty(self):
        board = Board.from_rows([[2, 4, 8, 16]] * 4)
        self.assertEqual(monotonicity_score(board), 0.0)

    def test_monotonic_beats_shuffled(self):
        board = Board.from_rows([[2, 4, 8, 16]] * 4)
        shuffled = Board.from_rows([[8, 2, 16, 4]] * 4)
        self.assertGreater(monotonicity_score(board), monotonicity_score(shuffled))

    def test_smoothness_prefers_similar_neighbors(self):
        smooth = Board.from_rows([[4, 4], [4, 4]])
        rough = Board.from_rows([[2, 1024], [1024, 2]])
        self.assertGreater(smoothness_score(smooth), smoothness_score(rough))

    def test_corner_bonus_when_max_in_corner(self):
        board = Board.from_rows(
            [
                [512, 4, 8, 16],
                [4, 8, 16, 2],
                [8, 16, 32, 4],
                [2, 4, 8, 16],
            ]
        )
        self.assertEqual(corner_score(board), 9.0)  # log2(512)

    def test_corner_bonus_zero_when_max_in_center(self):
        board = Board.from_rows(
            [
                [2, 4, 8, 16],
                [4, 512, 8, 2],
                [8, 16, 32, 4],
                [2, 4, 8, 16],
            ]
        )
        self.assertEqual(corner_score(board), 0.0)

    def test_evaluate_prefers_emptier_board(self):
        emptier = Board.from_rows([[2, 0], [0, 0]])
        fuller = Board.from_rows([[2, 4], [8, 16]])
        self.assertGreater(evaluate(emptier), evaluate(fuller))

    def test_empty_board_corner_score_is_zero(self):
        self.assertEqual(corner_score(Board.empty(3)), 0.0)


class TestProfile(unittest.TestCase):
    """权重预设的注入与校验。"""

    def test_expectimax_strong_returns_legal_move(self):
        strategy = ExpectimaxStrategy(depth=2, profile="strong", seed=1)
        direction = strategy.choose(OPEN_BOARD)
        self.assertIsInstance(direction, Direction)

    def test_greedy_accepts_profile(self):
        strategy = GreedyStrategy(profile="strong")
        self.assertIsInstance(strategy.choose(OPEN_BOARD), Direction)

    def test_weights_and_profile_mutually_exclusive(self):
        with self.assertRaises(ValueError):
            ExpectimaxStrategy(weights=STRONG_WEIGHTS, profile="strong")

    def test_unknown_profile_raises(self):
        with self.assertRaises(ValueError):
            ExpectimaxStrategy(profile="legendary")

    def test_explicit_weights_overrides_default(self):
        strategy = GreedyStrategy(weights=STRONG_WEIGHTS)
        # 注入 STRONG 后，一个「攒满可合并对」的棋盘应优于「无对」的
        paired = Board.from_rows([[2, 2, 4, 4], [8, 8, 16, 16], [32, 32, 64, 64], [128, 128, 256, 256]])
        flat = Board.from_rows([[2, 4, 8, 16], [32, 64, 128, 256], [512, 1024, 2, 4], [8, 16, 32, 64]])
        self.assertGreater(
            evaluate(paired, strategy._weights), evaluate(flat, strategy._weights)
        )

    def test_merge_potential_counts_adjacent_equal_pairs(self):
        """相邻且相等、且都非空的方块对，横竖都算。"""
        board = Board.from_rows(
            [
                [2, 2, 4, 0],
                [4, 4, 0, 0],
                [8, 8, 8, 8],  # 横向 3 对 + 纵向 2 对 = 5
                [0, 0, 0, 0],
            ]
        )
        # 第一行: (2,2) 横 1 对；第二行: (4,4) 横 1 对
        # 第三行: (8,8)(8,8)(8,8) 横 3 对；纵向全部无相等非空对
        self.assertEqual(merge_potential_score(board), 5.0)

    def test_merge_potential_zero_when_no_pairs(self):
        board = Board.from_rows(
            [
                [2, 4, 2, 4],
                [4, 2, 4, 2],
                [2, 4, 2, 4],
                [4, 2, 4, 2],
            ]
        )
        self.assertEqual(merge_potential_score(board), 0.0)

    def test_strong_preset_prefers_snake_over_mess(self):
        """增强预设必须更偏好「蛇形单调 + 有可合并对」的棋面。"""
        snake = Board.from_rows(
            [
                [512, 256, 128, 64],
                [64, 128, 256, 32],
                [32, 16, 8, 16],
                [8, 4, 8, 4],  # 末尾凑一对可合并的 8/4... 这里放 8,8 更像样
            ]
        )
        # 用一份确定更好的蛇形（右下角最大、递减、含可合并对）
        good = Board.from_rows(
            [
                [1024, 512, 256, 128],
                [512, 256, 128, 64],
                [256, 128, 64, 32],
                [128, 64, 32, 32],  # 末尾 32,32 是一对合并潜力
            ]
        )
        mess = Board.from_rows(
            [
                [2, 1024, 4, 512],
                [512, 8, 256, 16],
                [32, 256, 64, 2],
                [4, 128, 8, 16],
            ]
        )
        self.assertGreater(evaluate(good, STRONG_WEIGHTS), evaluate(mess, STRONG_WEIGHTS))
        # 同一份好棋面，增强预设不应比默认预设打分更低
        self.assertGreaterEqual(evaluate(good, STRONG_WEIGHTS), evaluate(good, DEFAULT_WEIGHTS))

    def test_default_weights_keep_merge_out(self):
        """默认预设合并潜力权重为 0，与初版行为一致。"""
        self.assertEqual(DEFAULT_WEIGHTS.merge_potential, 0.0)
        board = Board.from_rows([[2, 2, 4, 8], [4, 8, 16, 32], [8, 16, 32, 64], [16, 32, 64, 128]])
        # 给一个明显更"攒劲"的棋盘，默认权重下合并潜力不贡献
        other = Board.from_rows([[2, 0, 4, 8], [4, 8, 16, 32], [8, 16, 32, 64], [16, 32, 64, 128]])
        self.assertEqual(
            evaluate(board, DEFAULT_WEIGHTS) - evaluate(other, DEFAULT_WEIGHTS),
            evaluate(board) - evaluate(other),
        )


class TestAdaptiveDepth(unittest.TestCase):
    """自适应深度的调度表：越空越浅、越满越深，并受 cap 约束。"""

    def test_schedule_default_cap(self):
        self.assertEqual(adaptive_depth(7), 1)   # 早期很空
        self.assertEqual(adaptive_depth(5), 2)
        self.assertEqual(adaptive_depth(3), 3)
        self.assertEqual(adaptive_depth(1), 3)   # 默认 cap=3，raw=4 被夹到 3
        self.assertEqual(adaptive_depth(0), 3)

    def test_schedule_respects_cap(self):
        self.assertEqual(adaptive_depth(1, cap=4), 4)   # 终局更深
        self.assertEqual(adaptive_depth(0, cap=4), 4)
        self.assertEqual(adaptive_depth(8, cap=2), 1)   # 空盘被夹到 1
        self.assertEqual(adaptive_depth(2, cap=2), 2)   # raw=3 被夹到 2

    def test_always_within_bounds(self):
        for empty in range(0, 17):
            d = adaptive_depth(empty, cap=3)
            self.assertGreaterEqual(d, 1)
            self.assertLessEqual(d, 3)

    def test_adaptive_expectimax_matches_greedy_at_depth1(self):
        """自适应上限为 1 时等价于一步前瞻（贪心）。"""
        board = Board.from_rows(
            [
                [2, 2, 0, 0],
                [0, 0, 0, 0],
                [0, 0, 0, 0],
                [0, 0, 0, 0],
            ]
        )
        adaptive = ExpectimaxStrategy(adaptive=True, max_depth=1, seed=0)
        greedy = GreedyStrategy()
        self.assertEqual(adaptive.choose(board), greedy.choose(board))

    def test_adaptive_returns_legal_move(self):
        strategy = ExpectimaxStrategy(adaptive=True, max_depth=3, seed=1)
        self.assertIsInstance(strategy.choose(OPEN_BOARD), Direction)

    def test_adaptive_max_depth_rejects_nonpositive(self):
        with self.assertRaises(ValueError):
            ExpectimaxStrategy(adaptive=True, max_depth=0)


class TestMCTS(unittest.TestCase):
    """独立策略：采样式 MCTS。"""

    def test_registered_as_mcts(self):
        self.assertIs(registry.REGISTRY["mcts"], MCTSStrategy)

    def test_returns_legal_direction(self):
        strategy = MCTSStrategy(iterations=10, seed=1)
        self.assertIsInstance(strategy.choose(OPEN_BOARD), Direction)

    def test_returns_none_on_dead_board(self):
        strategy = MCTSStrategy(iterations=5, seed=1)
        self.assertIsNone(strategy.choose(DEAD_BOARD))

    def test_never_mutates_board(self):
        snapshot = Board.from_rows(OPEN_BOARD.rows())
        MCTSStrategy(iterations=5, seed=1).choose(OPEN_BOARD)
        self.assertEqual(OPEN_BOARD, snapshot)

    def test_reproducible_with_seed(self):
        a = MCTSStrategy(iterations=20, seed=42).choose(OPEN_BOARD)
        b = MCTSStrategy(iterations=20, seed=42).choose(OPEN_BOARD)
        self.assertEqual(a, b)

    def test_iterations_must_be_positive(self):
        with self.assertRaises(ValueError):
            MCTSStrategy(iterations=0)

    def test_accepts_profile(self):
        strategy = MCTSStrategy(iterations=5, profile="strong")
        self.assertIsInstance(strategy.choose(OPEN_BOARD), Direction)


if __name__ == "__main__":
    unittest.main()
