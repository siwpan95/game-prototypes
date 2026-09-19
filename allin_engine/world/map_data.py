"""
字符网格地图数据 — 支持运行时替换的二维字符网格。

支持 get/set 原子操作、区域批量替换、存档序列化。
"""

from __future__ import annotations

from dataclasses import dataclass


DEFAULT_FILL_CHAR = "#"  # 默认填充字符（墙壁）


@dataclass
class MapData:
    """可变的字符网格地图。

    属性:
        grid: 二维字符列表 [row][col]
        cols: 列数
        rows: 行数
        fill_char: 边界外填充字符

    用法:
        md = MapData()
        md.load_from_file("maps/dungeon.txt")
        md.set(5, 3, ".")
        region = md.get_region(0, 0, 10, 10)
    """

    grid: list[list[str]] | None = None
    cols: int = 0
    rows: int = 0
    fill_char: str = DEFAULT_FILL_CHAR

    def __init__(
        self,
        grid: list[list[str]] | None = None,
        fill_char: str = DEFAULT_FILL_CHAR,
    ):
        self.fill_char = fill_char
        if grid:
            self.grid = grid
            self.rows = len(grid)
            self.cols = len(grid[0]) if self.rows > 0 else 0
        else:
            self.grid = []
            self.rows = 0
            self.cols = 0

    # ================================================================
    # 文件加载
    # ================================================================

    def load_from_file(self, path: str) -> None:
        """从文本文件加载地图。

        文件每行对应一行，读取所有行。列数取最长行的长度。
        """
        with open(path, encoding="utf-8") as f:
            raw = f.read()
        lines = raw.rstrip("\n").split("\n")
        self._load_from_lines(lines)

    def load_from_string(self, text: str) -> None:
        """从字符串加载地图。"""
        lines = text.rstrip("\n").split("\n")
        self._load_from_lines(lines)

    @classmethod
    def from_string(cls, text_map: str) -> "MapData":
        """从多行字符串创建 MapData（类方法，兼容渲染器）。

        参数:
            text_map: 多行字符串，每行代表地图一行
        返回:
            MapData 实例
        """
        lines = text_map.strip().split("\n")
        max_cols = max(len(line) for line in lines) if lines else 0
        grid = [list(line.ljust(max_cols)) for line in lines]
        return cls(grid=grid)

    def _load_from_lines(self, lines: list[str]) -> None:
        """从行列表加载地图。"""
        if not lines:
            self.grid = []
            self.rows = 0
            self.cols = 0
            return

        max_cols = max(len(line) for line in lines)
        self.cols = max_cols
        self.rows = len(lines)

        grid: list[list[str]] = []
        for line in lines:
            row = list(line)
            while len(row) < max_cols:
                row.append(self.fill_char)
            grid.append(row)
        self.grid = grid

    def reload(self, path: str) -> None:
        """重新加载地图文件（用于地图切换）。"""
        self.load_from_file(path)

    # ================================================================
    # 基础访问
    # ================================================================

    def get(self, col: int, row: int) -> str:
        """获取 (col, row) 处的字符，越界返回 fill_char。"""
        if 0 <= col < self.cols and 0 <= row < self.rows:
            return self.grid[row][col]
        return self.fill_char

    def set(self, col: int, row: int, char: str) -> None:
        """设置 (col, row) 处的字符。越界无操作。"""
        if 0 <= col < self.cols and 0 <= row < self.rows:
            self.grid[row][col] = char

    def in_bounds(self, col: int, row: int) -> bool:
        """检查坐标是否在地图范围内。"""
        return 0 <= col < self.cols and 0 <= row < self.rows

    # ================================================================
    # 批量替换
    # ================================================================

    def replace_at(self, col: int, row: int, old: str, new: str) -> None:
        """若 (col, row) 处字符等于 old，则替换为 new。"""
        if self.get(col, row) == old:
            self.set(col, row, new)

    def replace_region(
        self,
        col_start: int,
        col_end: int,
        row_start: int,
        row_end: int,
        old: str,
        new: str,
    ) -> None:
        """矩形区域内所有等于 old 的字符替换为 new（闭区间）。"""
        for r in range(row_start, row_end + 1):
            for c in range(col_start, col_end + 1):
                self.replace_at(c, r, old, new)

    def replace_area(
        self,
        col_start: int,
        col_end: int,
        row_start: int,
        row_end: int,
        targets: set[str],
        replacement: str,
    ) -> None:
        """矩形区域内所有属于 targets 中任意字符的格子替换为 replacement。"""
        for r in range(row_start, row_end + 1):
            for c in range(col_start, col_end + 1):
                if self.get(c, r) in targets:
                    self.set(c, r, replacement)

    # ================================================================
    # 区域查询
    # ================================================================

    def get_region(
        self,
        col_start: int,
        col_end: int,
        row_start: int,
        row_end: int,
    ) -> list[list[str]]:
        """返回矩形区域的字符网格副本。

        超出边界的部分用 fill_char 填充。
        """
        result: list[list[str]] = []
        for r in range(row_start, row_end + 1):
            row: list[str] = []
            for c in range(col_start, col_end + 1):
                row.append(self.get(c, r))
            result.append(row)
        return result

    def find_all(self, char: str) -> list[tuple[int, int]]:
        """查找地图中所有等于 char 的坐标。"""
        positions: list[tuple[int, int]] = []
        for r in range(self.rows):
            for c in range(self.cols):
                if self.grid[r][c] == char:
                    positions.append((c, r))
        return positions

    def find_any(self, chars: set[str]) -> list[tuple[int, int]]:
        """查找地图中所有属于 chars 集合的坐标。"""
        positions: list[tuple[int, int]] = []
        for r in range(self.rows):
            for c in range(self.cols):
                if self.grid[r][c] in chars:
                    positions.append((c, r))
        return positions

    # ================================================================
    # 整图操作
    # ================================================================

    def to_string(self) -> str:
        """将地图转为换行分隔的字符串。"""
        if not self.grid:
            return ""
        return "\n".join("".join(row) for row in self.grid)

    # ================================================================
    # 序列化（存档用）
    # ================================================================

    def to_dict(self) -> dict:
        """序列化为字典。"""
        return {
            "cols": self.cols,
            "rows": self.rows,
            "fill_char": self.fill_char,
            "grid": ["".join(row) for row in self.grid] if self.grid else [],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "MapData":
        """从字典反序列化。"""
        fill_char = data.get("fill_char", DEFAULT_FILL_CHAR)
        grid_lines = data.get("grid", [])
        if grid_lines:
            grid = [list(line) for line in grid_lines]
            return cls(grid=grid, fill_char=fill_char)
        return cls(fill_char=fill_char)

    @classmethod
    def empty(cls, cols: int, rows: int, fill_char: str = " ", fill: str | None = None) -> "MapData":
        """创建一个指定尺寸的空白地图。

        参数:
            cols: 列数
            rows: 行数
            fill_char: 填充字符（也可用 fill 参数兼容渲染器）
        """
        ch = fill if fill is not None else fill_char
        grid = [[ch] * cols for _ in range(rows)]
        return cls(grid=grid, fill_char=ch)

    @property
    def width(self) -> int:
        """地图宽度（cols 别名，兼容渲染器）。"""
        return self.cols

    @property
    def height(self) -> int:
        """地图高度（rows 别名，兼容渲染器）。"""
        return self.rows

    def __repr__(self) -> str:
        return f"MapData({self.cols}x{self.rows})"
