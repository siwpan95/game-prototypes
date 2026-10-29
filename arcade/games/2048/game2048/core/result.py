"""一局结束后的结果对象。

放在 core 而不是 app，是为了避免 ``render`` 为了标注类型反过来依赖 ``app``——
那会让层级出现环。这里它只是个纯数据结构，没有任何行为和 I/O，
``render`` 和 ``app`` 同时向下依赖它，依赖图保持无环。
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from game2048.core.board import Board
from game2048.core.game import GameSnapshot

__all__ = ["EndReason", "GameResult"]


class EndReason(Enum):
    """对局终止的原因。"""

    GAME_OVER = "棋盘死锁，无合法移动"
    NO_MOVE_CHOSEN = "策略未给出可行方向"
    MAX_MOVES = "达到步数上限"
    INTERRUPTED = "被用户中断"

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True, slots=True)
class GameResult:
    """一局棋的最终统计。"""

    snapshot: GameSnapshot
    reason: EndReason
    strategy: str = ""

    @property
    def board(self) -> Board:
        return self.snapshot.board

    @property
    def score(self) -> int:
        return self.snapshot.score

    @property
    def moves(self) -> int:
        return self.snapshot.moves

    @property
    def max_tile(self) -> int:
        return self.snapshot.max_tile

    def as_row(self) -> tuple[str, int, int, int, str]:
        """扁平化成一行，供批量统计输出。"""
        return (self.strategy, self.score, self.moves, self.max_tile, str(self.reason))
