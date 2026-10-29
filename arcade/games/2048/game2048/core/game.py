"""对局聚合：把纯规则 + 受控随机性组合成一个有状态的棋局。

与原始实现的关键差别：

1. **随机源注入**。原来直接调模块级的 ``random``，同一份代码永远无法复现
   同一局棋。这里通过构造函数注入 :class:`random.Random`，给定 seed 就能
   完全复现，测试和策略对比才有意义。
2. **移动与生成解耦**。原来 ``move()`` 内部偷偷 spawn 了新方块，
   导致"移动"这个动作不可预测。现在 :func:`~game2048.core.rules.apply_move`
   是纯的，spawn 由 :meth:`Game.step` 在移动成功之后显式触发。
3. **对外只暴露快照**。渲染层拿到的是 :class:`GameSnapshot`，
   不持有可变引用，不可能反向篡改棋局。
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from game2048.core.board import Board
from game2048.core.direction import Direction
from game2048.core.rules import apply_move, available_moves, is_game_over

__all__ = ["Game", "GameSnapshot", "SPAWN_FOUR_PROBABILITY"]

SPAWN_FOUR_PROBABILITY = 0.1
"""新方块为 4 的概率，其余情况为 2（与官方 2048 一致）。"""


@dataclass(frozen=True, slots=True)
class GameSnapshot:
    """棋局在某一时刻的只读切片，供渲染层与策略层消费。"""

    board: Board
    score: int
    moves: int
    over: bool

    @property
    def max_tile(self) -> int:
        return self.board.max_tile()


class Game:
    """一局 2048。

    :param size:   棋盘边长。
    :param rng:    随机源；不传则新建一个 :class:`random.Random`。
    :param seed:   便捷参数，等价于 ``rng=random.Random(seed)``。
    :param board:  从指定棋面开始（用于测试或复盘）；给了就不再自动开局。
    """

    __slots__ = ("_board", "_score", "_moves", "_rng")

    def __init__(
        self,
        size: int = 4,
        *,
        rng: random.Random | None = None,
        seed: int | None = None,
        board: Board | None = None,
    ) -> None:
        if rng is not None and seed is not None:
            raise ValueError("rng 与 seed 只能二选一")
        self._rng = rng if rng is not None else random.Random(seed)
        self._score = 0
        self._moves = 0

        if board is not None:
            self._board = board
        else:
            self._board = Board.empty(size)
            self.spawn()
            self.spawn()

    # ------------------------------------------------------------------ 状态

    @property
    def board(self) -> Board:
        return self._board

    @property
    def score(self) -> int:
        return self._score

    @property
    def moves(self) -> int:
        return self._moves

    @property
    def size(self) -> int:
        return self._board.size

    def is_over(self) -> bool:
        """棋局是否已经无路可走。"""
        return is_game_over(self._board)

    def available_moves(self) -> tuple[Direction, ...]:
        """当前所有有效方向。"""
        return available_moves(self._board)

    def snapshot(self) -> GameSnapshot:
        """导出只读快照。"""
        return GameSnapshot(
            board=self._board,
            score=self._score,
            moves=self._moves,
            over=self.is_over(),
        )

    # ------------------------------------------------------------------ 动作

    def spawn(self) -> bool:
        """在随机空格生成一个新方块。

        :return: 是否成功生成（棋盘已满时返回 ``False``）。
        """
        empty = self._board.empty_cells()
        if not empty:
            return False
        row, col = self._rng.choice(empty)
        value = 4 if self._rng.random() < SPAWN_FOUR_PROBABILITY else 2
        self._board = self._board.with_tile(row, col, value)
        return True

    def step(self, direction: Direction | str) -> bool:
        """执行一步：移动 -> 计分 -> 生成新方块。

        :return: 该方向是否有效（无效时棋局状态完全不变）。
        """
        outcome = apply_move(self._board, Direction.parse(direction))
        if not outcome.moved:
            return False
        self._board = outcome.board
        self._score += outcome.gained
        self._moves += 1
        self.spawn()
        return True

    def __repr__(self) -> str:  # pragma: no cover - 调试用
        return (
            f"Game(size={self.size}, score={self._score}, "
            f"moves={self._moves}, max_tile={self._board.max_tile()})"
        )
