"""
文字网格坐标 (col, row) — 替代像素 Transform。

使用 dataclass 实现，类型安全，支持默认值。
"""

from dataclasses import dataclass

from core.ecs import Component


@dataclass
class GridPosition(Component):
    """实体在文字网格上的位置。"""
    col: int = 0
    row: int = 0

    def __repr__(self) -> str:
        return f"GridPosition({self.col}, {self.row})"
