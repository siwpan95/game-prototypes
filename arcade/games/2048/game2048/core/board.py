"""棋盘值对象。

设计要点——为什么必须是**不可变**的：

原始实现里 ``move()`` 直接原地改 ``self.board``，并且顺手 spawn 了一个新方块。
这导致任何"先假设走这一步、看看结果好不好"的策略都无法实现，
因为一旦模拟就把真实棋局破坏了。

把棋盘做成 frozen 的值对象后：

- 所有规则函数都返回**新**棋盘，旧棋盘原封不动；
- 策略层可以自由地做前瞻搜索（见 ``strategy/greedy.py``）；
- 棋盘可哈希，可以直接做 ``set`` 去重或当缓存 key；
- 判断"这一步有没有改变棋面"退化成一次 ``==``，不用再手工设 ``moved`` 标志。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence

__all__ = ["Board", "Grid"]

Grid = tuple[tuple[int, ...], ...]
"""棋盘底层表示：行的元组，0 表示空格。"""


@dataclass(frozen=True, slots=True)
class Board:
    """一个不可变的 N x N 棋盘快照。"""

    cells: Grid

    # ------------------------------------------------------------------ 构造

    def __post_init__(self) -> None:
        size = len(self.cells)
        if size == 0:
            raise ValueError("棋盘尺寸必须大于 0")
        for row in self.cells:
            if len(row) != size:
                raise ValueError(f"棋盘必须是方阵，收到 {size} 行但某行有 {len(row)} 列")
            for value in row:
                if value < 0:
                    raise ValueError(f"格子的值不能为负数: {value}")

    @classmethod
    def empty(cls, size: int = 4) -> "Board":
        """构造一个全空棋盘。"""
        return cls(tuple((0,) * size for _ in range(size)))

    @classmethod
    def from_rows(cls, rows: Iterable[Sequence[int]]) -> "Board":
        """从任意可迭代的二维序列构造（会做深拷贝成元组）。"""
        return cls(tuple(tuple(int(v) for v in row) for row in rows))

    # ------------------------------------------------------------------ 查询

    @property
    def size(self) -> int:
        """边长。"""
        return len(self.cells)

    def __getitem__(self, position: tuple[int, int]) -> int:
        row, col = position
        return self.cells[row][col]

    def rows(self) -> Grid:
        """按行返回。"""
        return self.cells

    def empty_cells(self) -> tuple[tuple[int, int], ...]:
        """所有空格坐标，顺序稳定（行优先）。"""
        return tuple(
            (r, c)
            for r, row in enumerate(self.cells)
            for c, value in enumerate(row)
            if value == 0
        )

    def is_full(self) -> bool:
        """是否已无空格。"""
        return not any(0 in row for row in self.cells)

    def max_tile(self) -> int:
        """最大方块。"""
        return max(max(row) for row in self.cells)

    def tile_sum(self) -> int:
        """所有方块之和。"""
        return sum(sum(row) for row in self.cells)

    # ------------------------------------------------------------ 变换（纯）

    def transposed(self) -> "Board":
        """转置：把"竖着走"变成"横着走"。"""
        return Board(tuple(zip(*self.cells)))

    def mirrored(self) -> "Board":
        """左右镜像：把"向右走"变成"向左走"。"""
        return Board(tuple(tuple(reversed(row)) for row in self.cells))

    def with_tile(self, row: int, col: int, value: int) -> "Board":
        """返回在 ``(row, col)`` 落子后的新棋盘，自身不变。"""
        if not (0 <= row < self.size and 0 <= col < self.size):
            raise IndexError(f"坐标越界: ({row}, {col})，棋盘尺寸为 {self.size}")
        mutable = [list(r) for r in self.cells]
        mutable[row][col] = value
        return Board.from_rows(mutable)

    def with_rows(self, rows: Iterable[Sequence[int]]) -> "Board":
        """用新的行集合构造同尺寸棋盘（内部变换用）。"""
        return Board.from_rows(rows)
