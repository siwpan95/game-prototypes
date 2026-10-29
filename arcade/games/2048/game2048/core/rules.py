"""2048 的规则——全部是纯函数。

## 为什么这一层要单独拆出来

原始实现的 ``move()`` 里，"左/右"和"上/下"各写了一遍几乎相同的
压缩-合并-补零逻辑（约 50 行重复代码），改一处就得记得同步改另一处。

这里改用**方向归一化**：任何方向都先把棋盘变换成"向左移动"的等价形态，
只用一份 :func:`slide_line` 处理，再把变换逆回去。四个方向共用同一份规则，
重复逻辑从 4 份降到 1 份。

## 合并规则

一次移动中，每个方块最多参与一次合并，且合并从移动方向的前端开始。
例如向左移动：

- ``[2, 2, 2, 0]`` -> ``[4, 2, 0, 0]``  （前两个合并，第三个不再连锁）
- ``[2, 2, 2, 2]`` -> ``[4, 4, 0, 0]``  （两两配对）
- ``[4, 4, 8, 0]`` -> ``[8, 8, 0, 0]``  （合并产生的 8 不再和原有的 8 合并）
"""

from __future__ import annotations

from dataclasses import dataclass

from game2048.core.board import Board
from game2048.core.direction import Direction

__all__ = [
    "MoveOutcome",
    "slide_line",
    "apply_move",
    "available_moves",
    "can_move",
    "is_game_over",
]


@dataclass(frozen=True, slots=True)
class MoveOutcome:
    """一次移动的结果。

    :param board:  移动后的棋盘（未生成新方块）。
    :param gained: 本次移动获得的分数。
    :param moved:  棋面是否真的发生了变化。
    """

    board: Board
    gained: int
    moved: bool


def slide_line(line: tuple[int, ...]) -> tuple[tuple[int, ...], int]:
    """把一行**向左**压缩并合并。

    这是整个规则层唯一的原子操作，其余方向都归约到它。

    :param line: 一行数值，0 表示空格。
    :return: ``(新行, 本次得分)``，新行长度与输入一致。
    """
    tiles = [value for value in line if value != 0]
    merged: list[int] = []
    gained = 0

    index = 0
    while index < len(tiles):
        # 相邻且相等 -> 合并，并跳过下一个，保证每块只合并一次
        if index + 1 < len(tiles) and tiles[index] == tiles[index + 1]:
            value = tiles[index] * 2
            merged.append(value)
            gained += value
            index += 2
        else:
            merged.append(tiles[index])
            index += 1

    merged.extend([0] * (len(line) - len(merged)))
    return tuple(merged), gained


def _to_left_frame(board: Board, direction: Direction) -> Board:
    """把棋盘变换到"向左移动"的等价形态。"""
    if direction is Direction.LEFT:
        return board
    if direction is Direction.RIGHT:
        return board.mirrored()
    if direction is Direction.UP:
        return board.transposed()
    if direction is Direction.DOWN:
        return board.transposed().mirrored()
    raise ValueError(f"未知方向: {direction!r}")


def _from_left_frame(board: Board, direction: Direction) -> Board:
    """把"向左移动"形态逆变换回原坐标系（与 :func:`_to_left_frame` 互逆）。"""
    if direction is Direction.LEFT:
        return board
    if direction is Direction.RIGHT:
        return board.mirrored()
    if direction is Direction.UP:
        return board.transposed()
    if direction is Direction.DOWN:
        return board.mirrored().transposed()
    raise ValueError(f"未知方向: {direction!r}")


def apply_move(board: Board, direction: Direction) -> MoveOutcome:
    """在 ``board`` 上执行一次移动，返回新棋盘与得分。

    注意：**不会**生成新方块。生成新方块是有随机性的操作，
    属于 :class:`~game2048.core.game.Game` 的职责，不放在纯函数里。
    """
    direction = Direction.parse(direction)
    framed = _to_left_frame(board, direction)

    new_rows: list[tuple[int, ...]] = []
    gained = 0
    for row in framed.rows():
        slid, points = slide_line(row)
        new_rows.append(slid)
        gained += points

    result = _from_left_frame(Board(tuple(new_rows)), direction)
    return MoveOutcome(board=result, gained=gained, moved=result != board)


def available_moves(board: Board) -> tuple[Direction, ...]:
    """返回所有能改变棋面的方向，顺序固定为 上/下/左/右 的枚举声明序。"""
    return tuple(d for d in Direction if apply_move(board, d).moved)


def can_move(board: Board) -> bool:
    """是否还存在任何合法移动。"""
    if not board.is_full():
        return True
    size = board.size
    cells = board.rows()
    for r in range(size):
        for c in range(size):
            value = cells[r][c]
            if c + 1 < size and value == cells[r][c + 1]:
                return True
            if r + 1 < size and value == cells[r + 1][c]:
                return True
    return False


def is_game_over(board: Board) -> bool:
    """棋局是否结束（无空格且无相邻可合并）。"""
    return not can_move(board)
