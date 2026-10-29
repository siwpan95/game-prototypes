"""固定顺序策略——原始 ``2048.py`` 中 ``auto_play_simple`` 的等价实现。

保留它是为了做基线对照：新策略必须能跑赢它，否则说明没有进步。
"""

from __future__ import annotations

from game2048.core.board import Board
from game2048.core.direction import Direction
from game2048.core.rules import apply_move
from game2048.strategy.base import Strategy, register

__all__ = ["FixedOrderStrategy"]

DEFAULT_ORDER: tuple[Direction, ...] = (
    Direction.RIGHT,
    Direction.DOWN,
    Direction.LEFT,
    Direction.UP,
)
"""与原始实现完全一致的尝试顺序。"""


@register
class FixedOrderStrategy(Strategy):
    """按固定优先级依次尝试，选中第一个能改变棋面的方向。"""

    name = "fixed"
    description = "按 右->下->左->上 顺序尝试（原始版本的行为）"

    def __init__(self, order: tuple[Direction, ...] = DEFAULT_ORDER) -> None:
        if not order:
            raise ValueError("方向顺序不能为空")
        self.order = tuple(Direction.parse(d) for d in order)

    def choose(self, board: Board) -> Direction | None:
        for direction in self.order:
            if apply_move(board, direction).moved:
                return direction
        return None
