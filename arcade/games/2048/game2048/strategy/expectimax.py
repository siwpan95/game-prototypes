"""前瞻搜索策略（贪心 / Expectimax）。

**这一层是拆分带来的直接收益。** 原始实现的 ``move()`` 会就地修改棋盘并
顺手生成新方块，任何"先试一步看看"的想法都会破坏真实棋局，所以原来只能写
死板的固定顺序。core 层改成不可变棋盘 + 纯函数之后，模拟任意深度都不会有副作用。

树的结构：

- **Max 节点**（我方回合）：在四个方向里挑期望收益最高的。
- **Chance 节点**（系统落子）：新方块位置随机、数值 90% 是 2 / 10% 是 4，
  按概率加权求期望；空格太多时抽样，避免分支爆炸。
"""

from __future__ import annotations

import random

from game2048.core.board import Board
from game2048.core.direction import Direction
from game2048.core.rules import apply_move, is_game_over
from game2048.strategy.base import Strategy, register
from game2048.strategy.heuristics import (
    DEFAULT_WEIGHTS,
    STRONG_WEIGHTS,
    Weights,
    evaluate,
)

__all__ = ["GreedyStrategy", "ExpectimaxStrategy", "adaptive_depth"]

_DEAD_PENALTY = -1e9
"""走进死局的惩罚，保证任何活路都优于它。"""

_SPAWN_CANDIDATES: tuple[tuple[int, float], ...] = ((2, 0.9), (4, 0.1))


def adaptive_depth(empty_cells: int, cap: int = 3) -> int:
    """自适应搜索深度：棋面越空（早期）搜越浅，越满（终局）搜越深。

    早期空格多，chance 节点分支爆炸且当前落子影响小；终局空格少，每步都关键、
    且分支受限，值得更深搜索。这样用「浅搜早期 + 深搜终局」替代「全程固定深度」，
    在不损失（甚至提升）强度的前提下大幅提速——正是 ``--profile strong`` 想做的。

    :param empty_cells: 当前空格数量。
    :param cap:         深度上限，终局也不会超过它。
    """
    if empty_cells >= 6:
        raw = 1
    elif empty_cells >= 4:
        raw = 2
    elif empty_cells >= 2:
        raw = 3
    else:
        raw = 4
    return max(1, min(raw, cap))


def _resolve_weights(
    weights: Weights | None, profile: str | None
) -> Weights:
    """把 weights / profile 二选一（或都默认）归一成具体的 Weights 实例。"""
    if weights is not None:
        if profile is not None:
            raise ValueError("weights 与 profile 只能二选一")
        return weights
    if profile == "strong":
        return STRONG_WEIGHTS
    if profile is not None and profile != "default":
        raise ValueError(f"未知 profile {profile!r}，可选: default / strong")
    return DEFAULT_WEIGHTS


@register
class GreedyStrategy(Strategy):
    """一步前瞻：直接用启发式评估四个方向的落点，选最好的。

    速度快、代码短，作为 :class:`ExpectimaxStrategy` 的退化版本存在。
    """

    name = "greedy"
    description = "一步前瞻 + 启发式评估（快）"

    def __init__(
        self,
        weights: Weights | None = None,
        profile: str | None = None,
    ) -> None:
        self._weights = _resolve_weights(weights, profile)

    def choose(self, board: Board) -> Direction | None:
        best: Direction | None = None
        best_value = float("-inf")
        for direction in Direction:
            outcome = apply_move(board, direction)
            if not outcome.moved:
                continue
            value = outcome.gained + evaluate(outcome.board, self._weights)
            if is_game_over(outcome.board):
                value += _DEAD_PENALTY
            if value > best_value:
                best_value = value
                best = direction
        return best


@register
class ExpectimaxStrategy(Strategy):
    """多步 Expectimax 搜索。

    :param depth:        固定搜索深度（1 等价于贪心）；仅在不开启 ``adaptive`` 时生效。
    :param spawn_samples: Chance 节点最多展开多少个空格，其余随机抽样；
                          ``None`` 表示全部展开。
    :param adaptive:     开启后，每一步的实际深度由当前空格数动态决定
                         （见 :func:`adaptive_depth`），``depth`` 不再生效。
    :param max_depth:    自适应模式下的深度上限。
    """

    name = "expectimax"
    description = "Expectimax 多步搜索（默认深度 2；--profile strong 时自适应深度）"

    def __init__(
        self,
        depth: int = 2,
        spawn_samples: int | None = 6,
        weights: Weights | None = None,
        profile: str | None = None,
        rng: random.Random | None = None,
        seed: int | None = None,
        adaptive: bool = False,
        max_depth: int = 3,
    ) -> None:
        if depth < 1:
            raise ValueError("depth 至少为 1")
        if spawn_samples is not None and spawn_samples < 1:
            raise ValueError("spawn_samples 至少为 1")
        if max_depth < 1:
            raise ValueError("max_depth 至少为 1")
        if rng is not None and seed is not None:
            raise ValueError("rng 与 seed 只能二选一")
        self.depth = depth
        self.spawn_samples = spawn_samples
        self._weights = _resolve_weights(weights, profile)
        self._rng = rng if rng is not None else random.Random(seed)
        self.adaptive = adaptive
        self.max_depth = max_depth

    # -------------------------------------------------------------- 对外接口

    def choose(self, board: Board) -> Direction | None:
        # 自适应模式下，每一步的实际深度由当前空格数决定：越空越浅、越满越深。
        depth = (
            adaptive_depth(len(board.empty_cells()), self.max_depth)
            if self.adaptive
            else self.depth
        )
        best: Direction | None = None
        best_value = float("-inf")
        for direction in Direction:
            outcome = apply_move(board, direction)
            if not outcome.moved:
                continue
            value = outcome.gained + self._chance_node(outcome.board, depth - 1)
            if value > best_value:
                best_value = value
                best = direction
        return best

    # ---------------------------------------------------------------- 搜索树

    def _max_node(self, board: Board, depth: int) -> float:
        """我方回合：取最优方向的价值。"""
        if depth <= 0:
            return evaluate(board, self._weights)

        best = float("-inf")
        for direction in Direction:
            outcome = apply_move(board, direction)
            if not outcome.moved:
                continue
            best = max(
                best, outcome.gained + self._chance_node(outcome.board, depth - 1)
            )

        if best == float("-inf"):  # 无路可走
            return _DEAD_PENALTY
        return best

    def _chance_node(self, board: Board, depth: int) -> float:
        """系统落子：对所有可能的新方块求期望。"""
        if depth <= 0:
            return evaluate(board, self._weights)

        empties = board.empty_cells()
        if not empties:
            return _DEAD_PENALTY if is_game_over(board) else self._max_node(board, depth)

        sampled = empties
        if self.spawn_samples is not None and len(empties) > self.spawn_samples:
            sampled = tuple(self._rng.sample(empties, self.spawn_samples))

        total = 0.0
        for row, col in sampled:
            for value, probability in _SPAWN_CANDIDATES:
                child = board.with_tile(row, col, value)
                total += probability * self._max_node(child, depth)
        return total / len(sampled)
