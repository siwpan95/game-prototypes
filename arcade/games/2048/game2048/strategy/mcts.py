"""蒙特卡洛树搜索（MCTS）策略。

与 Expectimax 的本质区别：
Expectimax 对 chance 节点**穷举**所有新方块、按概率求精确期望（树是确定性的）；
MCTS 则在每个模拟里**抽样**生成新方块，用大量随机模拟去估计每个走法的期望价值
（树是采样驱动的）。两者都建立在 core 层的不可变棋盘上，共享同一套启发式评估。

树结构（只展开我方决策点，落子的随机性折叠进边）：

- 节点 = 一个「轮到我走」的棋面；
- 子节点 = 选某个方向走一步 + 随后随机落一个方块 之后的新棋面；
- 选择阶段用 UCB1 在子节点间权衡「利用 / 探索」；
- 模拟阶段用一个轻量启发式默认策略（贪心）把棋面走到死局或深度上限；
- 回溯阶段把模拟得到的评估值沿路径累加。

这是 2048 这类「随机对手 + 大分支」游戏里常用的 MCTS 变体（determinized / 采样式）。
"""

from __future__ import annotations

import math
import random

from game2048.core.board import Board
from game2048.core.direction import Direction
from game2048.core.rules import apply_move, available_moves, is_game_over
from game2048.strategy.base import Strategy, register
from game2048.strategy.expectimax import _SPAWN_CANDIDATES, _resolve_weights
from game2048.strategy.heuristics import evaluate

__all__ = ["MCTSStrategy"]

_UCB_CONSTANT = 1.2
"""UCB1 探索系数。"""


class _Node:
    """MCTS 树节点：一个「轮到我走」的棋面决策点。"""

    __slots__ = ("board", "parent", "children", "move", "visits", "value", "untried")

    def __init__(self, board: Board, parent: "_Node | None" = None, move=None) -> None:
        self.board = board
        self.parent = parent
        self.children: list["_Node"] = []
        self.move = move  # 走到这个节点所用的方向（根节点为 None）
        self.visits = 0
        self.value = 0.0
        self.untried: tuple[Direction, ...] = available_moves(board)

    @property
    def mean(self) -> float:
        return self.value / self.visits if self.visits else 0.0

    def ucb(self, parent_visits: int, constant: float = _UCB_CONSTANT) -> float:
        if self.visits == 0:
            return float("inf")  # 未访问过的节点优先探索
        return self.mean + constant * math.sqrt(math.log(parent_visits) / self.visits)


@register
class MCTSStrategy(Strategy):
    """蒙特卡洛树搜索。

    :param iterations: 每次 ``choose`` 跑多少轮模拟（越多越强越慢）。
    :param rollout_depth: 单次模拟最多走多少步。
    :param weights/profile: 评估函数权重（同其他策略）。
    :param seed/rng: 随机源，用于复现。
    """

    name = "mcts"
    description = "蒙特卡洛树搜索（采样估计期望，与 Expectimax 思路不同）"

    def __init__(
        self,
        iterations: int = 100,
        rollout_depth: int = 24,
        weights: object = None,
        profile: str | None = None,
        rng: random.Random | None = None,
        seed: int | None = None,
    ) -> None:
        if iterations < 1:
            raise ValueError("iterations 至少为 1")
        if rollout_depth < 1:
            raise ValueError("rollout_depth 至少为 1")
        if rng is not None and seed is not None:
            raise ValueError("rng 与 seed 只能二选一")
        self.iterations = iterations
        self.rollout_depth = rollout_depth
        self._weights = _resolve_weights(weights, profile)  # type: ignore[arg-type]
        self._rng = rng if rng is not None else random.Random(seed)

    # -------------------------------------------------------------- 对外接口

    def choose(self, board: Board) -> Direction | None:
        moves = available_moves(board)
        if not moves:
            return None

        root = _Node(board)
        for _ in range(self.iterations):
            leaf, value = self._simulate(root)
            self._backpropagate(leaf, value)

        # 选访问最多（被验证得最充分）的根子节点对应的方向。
        best_child = max(root.children, key=lambda c: (c.visits, c.value))
        return best_child.move

    # ---------------------------------------------------------------- 搜索树

    def _select(self, root: _Node) -> tuple[_Node, float]:
        """从根走一条路径到待扩展 / 叶节点，返回 (叶节点, 该叶的评估值)。"""
        node = root
        while True:
            if node.untried:
                # 扩展一个未尝试的方向：走一步 + 随机落子，得到新的决策点
                move = node.untried[0]
                node.untried = node.untried[1:]
                child_board = self._step_with_spawn(apply_move(node.board, move).board)
                child = _Node(child_board, parent=node, move=move)
                node.children.append(child)
                return child, evaluate(child_board, self._weights)
            if not node.children:
                # 死局节点：没有可走方向也没有子节点
                return node, evaluate(node.board, self._weights)
            node = max(node.children, key=lambda c: c.ucb(node.visits))

    def _simulate(self, root: _Node) -> tuple[_Node, float]:
        leaf, leaf_value = self._select(root)
        if not leaf.children and not leaf.untried:
            # 已经是终局，直接用它自己的评估值
            return leaf, leaf_value
        return leaf, self._rollout(leaf.board)

    def _rollout(self, board: Board) -> float:
        """默认策略：贪心（按「得分 + 启发式评估」选方向）+ 随机落子，走到死局或深度上限。

        返回值是「本次模拟累计的合并得分 + 终局棋面评估」——必须包含合并得分，
        否则默认策略会为了多留空格而刻意不合并，正好与 2048 的胜利条件相反。
        """
        current = board
        total_gained = 0
        for _ in range(self.rollout_depth):
            candidates = [
                (direction, outcome)
                for direction in Direction
                if (outcome := apply_move(current, direction)).moved
            ]
            if not candidates:
                break
            best_direction, best_outcome = max(
                candidates,
                key=lambda dc: dc[1].gained + evaluate(dc[1].board, self._weights),
            )
            total_gained += best_outcome.gained
            current = self._step_with_spawn(best_outcome.board)
        return total_gained + evaluate(current, self._weights)

    def _step_with_spawn(self, board: Board) -> Board:
        """在棋面随机空位落一个方块（90% 出 2 / 10% 出 4），返回新棋盘。"""
        empties = board.empty_cells()
        row, col = self._rng.choice(empties)
        value = self._rng.choices(
            [v for v, _ in _SPAWN_CANDIDATES],
            weights=[p for _, p in _SPAWN_CANDIDATES],
            k=1,
        )[0]
        return board.with_tile(row, col, value)

    @staticmethod
    def _backpropagate(node: _Node, value: float) -> None:
        while node is not None:
            node.visits += 1
            node.value += value
            node = node.parent
