"""领域核心层：棋盘、方向、规则、对局聚合。

本层的硬性约束：

1. 不 import 任何上层模块（strategy / render / app / cli）。
2. 不做 I/O（不 print、不 sleep、不清屏、不读写文件）。
3. ``rules`` 中的函数全部是纯函数，同样的输入永远得到同样的输出。
4. 随机性只允许通过显式注入的 ``random.Random`` 进入 ``Game``。
"""

from game2048.core.board import Board
from game2048.core.direction import Direction
from game2048.core.game import Game, GameSnapshot
from game2048.core.result import EndReason, GameResult
from game2048.core.rules import (
    MoveOutcome,
    apply_move,
    available_moves,
    is_game_over,
    slide_line,
)

__all__ = [
    "Board",
    "Direction",
    "EndReason",
    "Game",
    "GameResult",
    "GameSnapshot",
    "MoveOutcome",
    "apply_move",
    "available_moves",
    "is_game_over",
    "slide_line",
]
