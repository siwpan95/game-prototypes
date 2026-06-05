"""
可交互组件 — 类型安全版本。

标记实体为可交互的，并定义碰撞体积。
使用 dataclass 实现，类型安全。
"""

from dataclasses import dataclass, field
from typing import Tuple

from core.ecs import Component


@dataclass
class Interactable(Component):
    """
    可交互组件 — 标记实体为可交互的。

    属性：
        hitbox_width: 碰撞箱宽度（像素）
        hitbox_height: 碰撞箱高度（像素）
        interact_radius: 交互半径（格子数，默认 1）
        enabled: 是否启用交互
    """
    hitbox_width: int = 64
    hitbox_height: int = 64
    interact_radius: int = 1
    enabled: bool = True

    @property
    def hitbox_cells(self) -> Tuple[int, int]:
        """
        碰撞箱覆盖的格子数 (cols, rows)。

        基于 CELL=20 计算，用于多格物件判定。
        """
        from core.config import CELL
        cols = max(self.hitbox_width // CELL, 1)
        rows = max(self.hitbox_height // CELL, 1)
        return (cols, rows)

    def contains_grid(self, entity_col: int, entity_row: int,
                     target_col: int, target_row: int) -> bool:
        """
        检查目标格子是否在此交互物的碰撞范围内。

        参数：
            entity_col, entity_row: 此交互物所在格子
            target_col, target_row: 目标格子

        返回：
            是否在碰撞范围内
        """
        cols, rows = self.hitbox_cells
        return (entity_col <= target_col < entity_col + cols and
                entity_row <= target_row < entity_row + rows)

    def __repr__(self) -> str:
        return f"Interactable({self.hitbox_width}x{self.hitbox_height})"
