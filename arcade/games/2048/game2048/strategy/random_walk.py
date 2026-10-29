"""随机策略：在所有合法方向中等概率挑一个。

作用是给启发式策略提供一个"下限"参照——如果一个策略跑不过随机，那它是负优化。
"""

from __future__ import annotations

import random

from game2048.core.board import Board
from game2048.core.direction import Direction
from game2048.core.rules import available_moves
from game2048.strategy.base import Strategy, register

__all__ = ["RandomStrategy"]


@register
class RandomStrategy(Strategy):
    """等概率随机选择一个合法方向。"""

    name = "random"
    description = "在合法方向中随机选择（下限基线）"

    def __init__(
        self, rng: random.Random | None = None, seed: int | None = None
    ) -> None:
        if rng is not None and seed is not None:
            raise ValueError("rng 与 seed 只能二选一")
        self._rng = rng if rng is not None else random.Random(seed)

    def choose(self, board: Board) -> Direction | None:
        options = available_moves(board)
        if not options:
            return None
        return self._rng.choice(options)
