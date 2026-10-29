"""命令行入口：只负责解析参数、装配对象、打印结果。

原始版本的入口逻辑（``if __name__ == "__main__"`` 那 13 行）连
"用多大棋盘"都改不了，要换策略只能去改类里的方法。现在全部参数化。
"""

from __future__ import annotations

import argparse
import random
import sys
from typing import Sequence

from game2048.app.benchmark import BenchmarkSummary, run_batch, summarize
from game2048.app.runner import DEFAULT_MAX_MOVES, GameRunner
from game2048.core.game import Game
from game2048.render.console import ConsoleRenderer
from game2048.render.silent import SilentRenderer
from game2048.strategy import base as strategy_base

__all__ = ["build_parser", "main"]


def build_parser() -> argparse.ArgumentParser:
    """构造参数解析器。"""
    names = strategy_base.available_names()
    descriptions = "\n".join(
        f"  {name:<12}{strategy_base.REGISTRY[name].description}" for name in names
    )
    parser = argparse.ArgumentParser(
        prog="2048",
        description="2048 自动对弈",
        epilog="可用策略:\n" + descriptions,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "-s",
        "--strategy",
        default="greedy",
        choices=names,
        help="使用的策略（默认: greedy）",
    )
    parser.add_argument("-n", "--size", type=int, default=4, help="棋盘边长（默认: 4）")
    parser.add_argument("--seed", type=int, default=None, help="随机种子，用于复现对局")
    parser.add_argument(
        "-d", "--delay", type=float, default=0.1, help="每帧停顿秒数（默认: 0.1）"
    )
    parser.add_argument(
        "-m",
        "--max-moves",
        type=int,
        default=DEFAULT_MAX_MOVES,
        help=f"步数上限（默认: {DEFAULT_MAX_MOVES}）",
    )
    parser.add_argument(
        "-q", "--quiet", action="store_true", help="不渲染棋盘，只输出最终结果"
    )
    parser.add_argument("--no-clear", action="store_true", help="每帧不清屏")
    parser.add_argument(
        "-g",
        "--games",
        type=int,
        default=1,
        help="批量跑 N 局并输出统计（>1 时自动静默）",
    )
    parser.add_argument(
        "--compare",
        action="store_true",
        help="在相同种子下对比所有策略，需配合 --games",
    )
    parser.add_argument(
        "--depth",
        type=int,
        default=None,
        help="expectimax 的固定搜索深度（默认: 2；指定后关闭自适应）",
    )
    parser.add_argument(
        "--profile",
        choices=("default", "strong"),
        default="default",
        help="启发式预设：strong 加入合并潜力并强化单调/角落（默认: default）",
    )
    parser.add_argument(
        "--adaptive",
        action="store_true",
        default=False,
        help="expectimax 用自适应深度（--profile strong 时默认开启）",
    )
    parser.add_argument(
        "--no-adaptive",
        dest="adaptive",
        action="store_false",
        help="强制关闭自适应深度",
    )
    parser.add_argument(
        "--max-depth",
        type=int,
        default=None,
        help="自适应深度的上限（默认: 3）",
    )
    parser.add_argument(
        "--iterations",
        type=int,
        default=None,
        help="mcts 的模拟轮数（默认: 100）",
    )
    parser.add_argument(
        "--no-wait", action="store_true", help="不等待回车，直接开始"
    )
    return parser


def _make_strategy(
    name: str,
    depth: int | None,
    profile: str,
    seed: int | None,
    adaptive: bool,
    max_depth: int | None,
    iterations: int | None,
):
    """按名字构造策略实例，补齐各自需要的参数。

    - ``--profile strong`` 默认开启 expectimax 的**自适应深度**：越空搜越浅、越满
      搜越深（见 :func:`~game2048.strategy.expectimax.adaptive_depth`）；深度仍是
      ``--depth`` 控制的独立旋钮——一旦显式指定 ``--depth`` 就退回固定深度。
    - MCTS 是独立策略，用 ``--iterations`` 控制模拟轮数。
    """
    if name == "expectimax":
        if depth is not None:
            # 显式深度 = 固定深度，覆盖自适应
            return strategy_base.create(name, depth=depth, profile=profile, seed=seed)
        use_adaptive = adaptive or (profile == "strong")
        if use_adaptive:
            cap = max_depth if max_depth is not None else 3
            return strategy_base.create(
                name, adaptive=True, max_depth=cap, profile=profile, seed=seed
            )
        return strategy_base.create(name, depth=2, profile=profile, seed=seed)
    if name == "greedy":
        return strategy_base.create(name, profile=profile)
    if name == "mcts":
        it = iterations if iterations is not None else 100
        return strategy_base.create(name, iterations=it, profile=profile, seed=seed)
    if name == "random":
        return strategy_base.create(name, seed=seed)
    return strategy_base.create(name)


def _run_single(args: argparse.Namespace) -> int:
    game = Game(size=args.size, rng=random.Random(args.seed))
    renderer = (
        SilentRenderer()
        if args.quiet
        else ConsoleRenderer(delay=args.delay, clear=not args.no_clear)
    )
    runner = GameRunner(
        game=game,
        strategy=_make_strategy(
            args.strategy,
            args.depth,
            args.profile,
            args.seed,
            args.adaptive,
            args.max_depth,
            args.iterations,
        ),
        renderer=renderer,
        max_moves=args.max_moves,
    )
    result = runner.run()
    if args.quiet:
        print(
            f"策略={result.strategy} 得分={result.score} "
            f"步数={result.moves} 最大块={result.max_tile} 结束={result.reason}"
        )
    return 0


def _run_batch(args: argparse.Namespace) -> int:
    targets = (
        strategy_base.available_names() if args.compare else (args.strategy,)
    )
    summaries: list[BenchmarkSummary] = []
    for name in targets:
        results = run_batch(
            strategy_factory=lambda n=name: _make_strategy(
                n,
                args.depth,
                args.profile,
                args.seed,
                args.adaptive,
                args.max_depth,
                args.iterations,
            ),
            games=args.games,
            size=args.size,
            seed=args.seed if args.seed is not None else 0,
            max_moves=args.max_moves,
        )
        summaries.append(summarize(results))

    print(BenchmarkSummary.header())
    print("-" * len(BenchmarkSummary.header()))
    for summary in summaries:
        print(summary.format_line())
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    """程序入口，返回进程退出码。"""
    args = build_parser().parse_args(argv)

    if args.size < 2:
        print("棋盘边长至少为 2", file=sys.stderr)
        return 2

    try:
        if args.games > 1 or args.compare:
            return _run_batch(args)

        if not args.quiet and not args.no_wait and sys.stdin.isatty():
            print("开始自动运行 2048 游戏...")
            print("按 Ctrl+C 可以中断")
            input("按回车键开始...")
        return _run_single(args)
    except KeyboardInterrupt:
        print("\n\n游戏已被用户中断。")
        return 130
