"""ECS 组件 — 麻将牌的坐标与牌面数据结构。

深度 ECS 化：每张牌是引擎 World 中的一个 Entity，
携带 `Tile`（本身即 Component，见 models/tile.py）与 `PositionComponent`（坐标）。
"""
from dataclasses import dataclass
from typing import Tuple

from alloy.core import Component


Pos = Tuple[int, int, int]  # (layer, row, col)


@dataclass
class PositionComponent(Component):
    """棋盘三维坐标组件（layer 0 为最底层）。"""

    layer: int = 0
    row: int = 0
    col: int = 0

    @property
    def pos(self) -> Pos:
        return (self.layer, self.row, self.col)
