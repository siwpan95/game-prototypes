"""棋面评估函数。

单独成文件的原因：评估标准是最容易被反复调参的部分，
把它和搜索算法分开，换权重不需要碰搜索代码，写测试也更容易。

五个评估维度（前四个是初版，第五个「合并潜力」来自联网调研后的增强）：

- **空格数**：空格越多越不容易死，权重最高。
- **单调性**：数值沿行/列尽量单调递增或递减，便于后续合并（"蛇形"是黄金法则）。
- **平滑度**：相邻方块数值（取 log2 后）差异越小越容易合并。
- **角落锚定**：最大方块待在角上，避免它被夹在中间挡路。
- **合并潜力**：相邻且相等、下一步就能合并的方块对越多越好。

权重集中放在 :data:`DEFAULT_WEIGHTS` / :data:`STRONG_WEIGHTS` 两个预设里，
调用 :func:`evaluate` 时传入即可切换，不传则用 ``DEFAULT_WEIGHTS``（与初版行为一致）。

权重取值依据（2026-08 联网调研共识）：

- 几乎所有强 AI 都用 Expectimax + 线性加权启发式；单调性（蛇形）被普遍视为
  最重要的单项特征，权重应最高。
- 「合并潜力」在多个开源实现（如 J4NN0/2048-ai）中被列为关键维度，初版缺失。
- 概率模型用 90% 出 2 / 10% 出 4（实际游戏规则），而不是简化版 50/50。
- 这些绝对值是针对本评估函数定义调出来的，不能直接套用别的实现的数字；
  ``STRONG_WEIGHTS`` 是在 ``DEFAULT_WEIGHTS`` 方向上做的温和上修，已用基准验证有效。
"""

from __future__ import annotations

from dataclasses import dataclass
from math import log2

from game2048.core.board import Board

__all__ = [
    "Weights",
    "DEFAULT_WEIGHTS",
    "STRONG_WEIGHTS",
    "empty_score",
    "monotonicity_score",
    "smoothness_score",
    "corner_score",
    "merge_potential_score",
    "evaluate",
]


@dataclass(frozen=True, slots=True)
class Weights:
    """线性评估中各维度的权重。

    全部为「越大越好」方向：单调性 / 平滑度 / 角落 / 合并潜力内部已是惩罚或奖励
    形态，这里只乘正权重。想关掉某维度把它设成 0 即可。
    """

    empty: float = 270.0
    monotonicity: float = 47.0
    smoothness: float = 11.0
    max_corner: float = 60.0
    merge_potential: float = 0.0


# 初版行为：四个维度，合并潜力权重为 0 —— 保证向后兼容与可复现。
DEFAULT_WEIGHTS = Weights(
    empty=270.0,
    monotonicity=47.0,
    smoothness=11.0,
    max_corner=60.0,
    merge_potential=0.0,
)

# 增强预设（联网调研后的方向性调优）：加入合并潜力，并温和上修单调性与角落权重。
STRONG_WEIGHTS = Weights(
    empty=270.0,
    monotonicity=70.0,
    smoothness=12.0,
    max_corner=80.0,
    merge_potential=55.0,
)


def _log_grid(board: Board) -> list[list[float]]:
    """把棋面换算成 log2 尺度，空格记 0。"""
    return [[log2(v) if v else 0.0 for v in row] for row in board.rows()]


def empty_score(board: Board) -> float:
    """空格数量。"""
    return float(len(board.empty_cells()))


def monotonicity_score(board: Board) -> float:
    """单调性得分（越大越好，取值 <= 0，完全单调时为 0）。

    对每一行/每一列，分别累计"递增方向的落差"和"递减方向的落差"，
    取较小的那个作为惩罚——也就是说只要单调（哪个方向都行）就不扣分。
    """
    grid = _log_grid(board)
    size = board.size
    total = 0.0

    for line in grid:
        up = down = 0.0
        for i in range(size - 1):
            diff = line[i + 1] - line[i]
            if diff > 0:
                up += diff
            else:
                down -= diff
        total -= min(up, down)

    for col in range(size):
        line = [grid[row][col] for row in range(size)]
        up = down = 0.0
        for i in range(size - 1):
            diff = line[i + 1] - line[i]
            if diff > 0:
                up += diff
            else:
                down -= diff
        total -= min(up, down)

    return total


def smoothness_score(board: Board) -> float:
    """平滑度得分（越大越好，取值 <= 0）。

    统计所有相邻非空方块 log2 值之差的绝对值，取负。
    """
    grid = _log_grid(board)
    size = board.size
    penalty = 0.0
    for r in range(size):
        for c in range(size):
            if grid[r][c] == 0.0:
                continue
            if c + 1 < size and grid[r][c + 1] != 0.0:
                penalty += abs(grid[r][c] - grid[r][c + 1])
            if r + 1 < size and grid[r + 1][c] != 0.0:
                penalty += abs(grid[r][c] - grid[r + 1][c])
    return -penalty


def corner_score(board: Board) -> float:
    """最大方块是否位于四角，是则给正奖励。"""
    size = board.size
    biggest = board.max_tile()
    if biggest == 0:
        return 0.0
    corners = ((0, 0), (0, size - 1), (size - 1, 0), (size - 1, size - 1))
    if any(board[pos] == biggest for pos in corners):
        return log2(biggest)
    return 0.0


def merge_potential_score(board: Board) -> float:
    """合并潜力：相邻（右 / 下）且相等、且都非空的方块对数量。

    这些对「下一步走一步就能合并」，越多说明棋面越「攒得住劲」。
    这是初版缺失、联网调研后补上的维度（多个开源强 AI 都把它列为关键特征）。
    评估的是静态棋面——刚合并完的棋盘此项为 0，正说明鼓励保持可合并状态。
    """
    size = board.size
    grid = board.rows()
    pairs = 0
    for r in range(size):
        for c in range(size):
            value = grid[r][c]
            if value == 0:
                continue
            if c + 1 < size and grid[r][c + 1] == value:
                pairs += 1
            if r + 1 < size and grid[r + 1][c] == value:
                pairs += 1
    return float(pairs)


def evaluate(board: Board, weights: Weights = DEFAULT_WEIGHTS) -> float:
    """加权综合评分，越大表示棋面越健康。

    :param weights: 各维度权重；不传则用 :data:`DEFAULT_WEIGHTS`（初版行为）。
    """
    return (
        weights.empty * empty_score(board)
        + weights.monotonicity * monotonicity_score(board)
        + weights.smoothness * smoothness_score(board)
        + weights.max_corner * corner_score(board)
        + weights.merge_potential * merge_potential_score(board)
    )
