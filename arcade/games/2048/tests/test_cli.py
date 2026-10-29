"""CLI：参数解析与装配，不含业务逻辑。"""

import contextlib
import io
import unittest

from game2048.cli import build_parser, main
from game2048.strategy import ExpectimaxStrategy, MCTSStrategy


def run_cli(*argv) -> tuple[int, str]:
    """跑一次 CLI，同时吃掉 stderr，避免污染测试输出。"""
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer), contextlib.redirect_stderr(io.StringIO()):
        code = main(list(argv))
    return code, buffer.getvalue()


class TestParser(unittest.TestCase):
    def test_defaults(self):
        args = build_parser().parse_args([])
        self.assertEqual(args.strategy, "greedy")
        self.assertEqual(args.size, 4)
        self.assertEqual(args.games, 1)

    def test_strategy_choices_come_from_registry(self):
        args = build_parser().parse_args(["-s", "fixed"])
        self.assertEqual(args.strategy, "fixed")

    def test_rejects_unknown_strategy(self):
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                build_parser().parse_args(["-s", "nope"])

    def test_help_lists_strategies(self):
        text = build_parser().format_help()
        for name in ("fixed", "random", "greedy", "expectimax", "mcts"):
            self.assertIn(name, text)

    def test_adaptive_and_iterations_flags_parse(self):
        args = build_parser().parse_args(
            ["-s", "expectimax", "--adaptive", "--max-depth", "4", "--iterations", "50"]
        )
        self.assertTrue(args.adaptive)
        self.assertEqual(args.max_depth, 4)
        self.assertEqual(args.iterations, 50)

    def test_no_adaptive_overrides_strong(self):
        args = build_parser().parse_args(
            ["-s", "expectimax", "--profile", "strong", "--no-adaptive"]
        )
        self.assertFalse(args.adaptive)


class TestMakeStrategy(unittest.TestCase):
    def test_strong_default_enables_adaptive(self):
        from game2048.cli import _make_strategy

        strategy = _make_strategy("expectimax", None, "strong", 1, False, None, None)
        self.assertIsInstance(strategy, ExpectimaxStrategy)
        self.assertTrue(strategy.adaptive)

    def test_default_profile_fixed_depth(self):
        from game2048.cli import _make_strategy

        strategy = _make_strategy("expectimax", None, "default", 1, False, None, None)
        self.assertFalse(strategy.adaptive)
        self.assertEqual(strategy.depth, 2)

    def test_explicit_depth_disables_adaptive(self):
        from game2048.cli import _make_strategy

        strategy = _make_strategy("expectimax", 2, "strong", 1, False, None, None)
        self.assertFalse(strategy.adaptive)
        self.assertEqual(strategy.depth, 2)

    def test_mcts_factory(self):
        from game2048.cli import _make_strategy

        strategy = _make_strategy("mcts", None, "default", 1, False, None, 50)
        self.assertIsInstance(strategy, MCTSStrategy)
        self.assertEqual(strategy.iterations, 50)


class TestSingleRun(unittest.TestCase):
    def test_quiet_run_prints_one_summary_line(self):
        code, output = run_cli(
            "-q", "--no-wait", "-s", "fixed", "--seed", "1", "-m", "50"
        )
        self.assertEqual(code, 0)
        self.assertIn("策略=fixed", output)
        self.assertIn("得分=", output)

    def test_mcts_runs_and_reports(self):
        code, output = run_cli(
            "-q", "--no-wait", "-s", "mcts", "--iterations", "4",
            "--seed", "1", "-m", "60",
        )
        self.assertEqual(code, 0)
        self.assertIn("策略=mcts", output)
        self.assertIn("得分=", output)

    def test_seed_makes_output_reproducible(self):
        args = ("-q", "--no-wait", "-s", "fixed", "--seed", "77", "-m", "300")
        self.assertEqual(run_cli(*args)[1], run_cli(*args)[1])

    def test_custom_size(self):
        code, output = run_cli(
            "-q", "--no-wait", "-n", "5", "-s", "fixed", "--seed", "2", "-m", "30"
        )
        self.assertEqual(code, 0)
        self.assertIn("策略=fixed", output)

    def test_size_too_small_is_rejected(self):
        code, _ = run_cli("-q", "--no-wait", "-n", "1")
        self.assertEqual(code, 2)


class TestBatchRun(unittest.TestCase):
    def test_batch_prints_table(self):
        code, output = run_cli(
            "-g", "3", "-s", "fixed", "--seed", "5", "-m", "300"
        )
        self.assertEqual(code, 0)
        self.assertIn("策略", output)
        self.assertIn("fixed", output)
        self.assertEqual(len(output.strip().split("\n")), 3)  # 表头 + 分隔 + 1 行

    def test_compare_covers_all_strategies(self):
        code, output = run_cli(
            "--compare", "-g", "2", "--seed", "5", "-m", "120",
            "--depth", "1", "--iterations", "4",
        )
        self.assertEqual(code, 0)
        for name in ("fixed", "random", "greedy", "expectimax", "mcts"):
            self.assertIn(name, output)


if __name__ == "__main__":
    unittest.main()
