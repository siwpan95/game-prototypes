"""批量跑分。

有了静默渲染器和可注入的随机种子，才有可能做"同样的牌运下比较不同策略"
这件事——这是原始单文件版本结构上做不到的。
"""

from __future__ import annotations

import random
import statistics
from dataclasses import dataclass

from game2048.app.runner import DEFAULT_MAX_MOVES, GameRunner
from game2048.core.game import Game
from game2048.core.result import GameResult
from game2048.render.silent import SilentRenderer
from game2048.strategy.base import Strategy

__all__ = ["BenchmarkSummary", "run_batch", "summarize"]


@dataclass(frozen=True, slots=True)
class BenchmarkSummary:
    """一组对局的汇总指标。"""

    strategy: str
    games: int
    mean_score: float
    median_score: float
    best_score: int
    mean_moves: float
    best_tile: int
    tile_2048_rate: float

    def format_line(self) -> str:
        return (
            f"{self.strategy:<12}"
            f"{self.games:>6}"
            f"{self.mean_score:>12.1f}"
            f"{self.median_score:>12.1f}"
            f"{self.best_score:>10}"
            f"{self.mean_moves:>10.1f}"
            f"{self.best_tile:>10}"
            f"{self.tile_2048_rate:>10.0%}"
        )

    @staticmethod
    def header() -> str:
        return (
            f"{'策略':<12}"
            f"{'局数':>6}"
            f"{'平均分':>12}"
            f"{'中位分':>12}"
            f"{'最高分':>10}"
            f"{'平均步':>10}"
            f"{'最大块':>10}"
            f"{'达2048':>10}"
        )


def run_batch(
    strategy_factory,
    games: int = 20,
    size: int = 4,
    seed: int | None = None,
    max_moves: int = DEFAULT_MAX_MOVES,
) -> list[GameResult]:
    """连续跑 ``games`` 局，返回每局结果。

    :param strategy_factory: 无参可调用对象，每局新建一个策略实例
                             （避免带状态的策略跨局污染）。
    :param seed: 起始种子；第 i 局用 ``seed + i``，保证不同策略面对同样的牌运。
    """
    if games < 1:
        raise ValueError("games 至少为 1")

    results: list[GameResult] = []
    for index in range(games):
        game_seed = None if seed is None else seed + index
        game = Game(size=size, rng=random.Random(game_seed))
        runner = GameRunner(
            game=game,
            strategy=strategy_factory(),
            renderer=SilentRenderer(),
            max_moves=max_moves,
        )
        results.append(runner.run())
    return results


def summarize(results: list[GameResult]) -> BenchmarkSummary:
    """把一批结果压成一行统计。"""
    if not results:
        raise ValueError("结果列表为空")
    scores = [r.score for r in results]
    moves = [r.moves for r in results]
    tiles = [r.max_tile for r in results]
    return BenchmarkSummary(
        strategy=results[0].strategy,
        games=len(results),
        mean_score=statistics.fmean(scores),
        median_score=statistics.median(scores),
        best_score=max(scores),
        mean_moves=statistics.fmean(moves),
        best_tile=max(tiles),
        tile_2048_rate=sum(1 for t in tiles if t >= 2048) / len(tiles),
    )
