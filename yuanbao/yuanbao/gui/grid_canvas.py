"""网格画布：把 :class:`CellularAutomaton` 的状态渲染成方格图。

每个活细胞按其标签涂色，死亡格保持背景色。为减小重绘开销，每次 ``refresh``
直接 ``delete('all')`` 后按活细胞数量 ``create_rectangle``——对 20x20 量级
网格完全够用；如需扩展到上百规模，可改为只更新变化的格子。
"""
from __future__ import annotations

import tkinter as tk
from typing import Dict, List

from yuanbao.core.automaton import CellularAutomaton

# 标签名 -> 显示色（light 主题下饱和度适中的色板）
TAG_COLORS: Dict[str, str] = {
    'red': '#E5484D',
    'green': '#30A46C',
    'blue': '#3E63DD',
    'yellow': '#F5A524',
}

# 画布背景（死亡格）
CANVAS_BG = '#F4F4F5'
GRID_LINE = '#E4E4E7'


class GridCanvas(tk.Canvas):
    """以方格形式绘制 CA 网格的画布控件。"""

    def __init__(self, master, ca: CellularAutomaton, cell_size: int = 20, **kwargs):
        self.ca = ca
        self.cell_size = cell_size
        self.size = ca.size
        bg = kwargs.pop('bg', CANVAS_BG)
        super().__init__(
            master,
            width=self.size * cell_size,
            height=self.size * cell_size,
            bg=bg,
            highlightthickness=1,
            highlightbackground='#D4D4D8',
            **kwargs,
        )
        # 索引 0 = 背景（死亡），1..n = 各标签色
        self._colors: List[str] = [CANVAS_BG]
        for tag in ca.config.TAGS:
            self._colors.append(TAG_COLORS.get(tag, '#71717A'))
        self._draw_grid_lines()
        self._draw()

    def refresh(self) -> None:
        """重绘画布。"""
        self.delete('cell')
        self._draw()

    def _draw(self) -> None:
        cs = self.cell_size
        for i in range(self.size):
            for j in range(self.size):
                if self.ca.grid[i][j] == 1:
                    color = self._colors[self.ca.tag_grid[i][j]]
                    x0, y0 = j * cs, i * cs
                    self.create_rectangle(
                        x0, y0, x0 + cs, y0 + cs,
                        fill=color, outline='', tags='cell',
                    )
        # 确保网格线在细胞之上
        self.tag_raise('gridline')

    def _draw_grid_lines(self) -> None:
        cs = self.cell_size
        total = self.size * cs
        for k in range(self.size + 1):
            self.create_line(k * cs, 0, k * cs, total, fill=GRID_LINE, tags='gridline')
            self.create_line(0, k * cs, total, k * cs, fill=GRID_LINE, tags='gridline')
