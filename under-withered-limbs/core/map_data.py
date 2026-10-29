"""
共享地图数据 — 所有系统共用的动态地图网格。
支持运行时替换字符（墙壁打开、黑暗消散等）。
"""
from core.config import COLS, ROWS, FILL_CHAR
from core.paths import ROOT


class MapData:
    """可变的字符网格地图，TextRenderer / PlayerController / MechanismSystem 共享同一实例。"""

    def __init__(self, map_path=None):
        if map_path is None:
            map_path = ROOT / "data" / "mansion_map.txt"
        self._map_path = map_path
        self.grid = self._load(map_path)

    def reload(self, map_path):
        """重新加载地图文件（地图切换时使用）。"""
        self._map_path = map_path
        self.grid = self._load(map_path)

    def _load(self, path):
        with open(path, encoding="utf-8") as f:
            raw = f.read()
        lines = raw.strip("\n").split("\n")
        grid = []
        for row_idx, line in enumerate(lines):
            if row_idx >= ROWS:
                break
            row_chars = []
            for col_idx, ch in enumerate(line):
                if col_idx >= COLS:
                    break
                row_chars.append(ch)
            while len(row_chars) < COLS:
                row_chars.append(FILL_CHAR)
            grid.append(row_chars)
        while len(grid) < ROWS:
            grid.append([FILL_CHAR] * COLS)
        return grid

    def get(self, col, row):
        """获取 (col, row) 处的字符，越界返回填充字符（墙壁）。"""
        if 0 <= col < COLS and 0 <= row < ROWS:
            return self.grid[row][col]
        return FILL_CHAR

    def set(self, col, row, char):
        """设置 (col, row) 处的字符。"""
        if 0 <= col < COLS and 0 <= row < ROWS:
            self.grid[row][col] = char

    def replace_at(self, col, row, old, new):
        """如果 (col, row) 处字符为 old，则替换为 new。"""
        if self.get(col, row) == old:
            self.set(col, row, new)

    def replace_region(self, col_start, col_end, row_start, row_end, old, new):
        """将矩形区域内所有等于 old 的字符替换为 new。"""
        for r in range(row_start, row_end + 1):
            for c in range(col_start, col_end + 1):
                self.replace_at(c, r, old, new)

    def replace_area(self, col_start, col_end, row_start, row_end, target, replacement):
        """将矩形区域内所有等于 target 的字符替换为 replacement（集合版）。"""
        for r in range(row_start, row_end + 1):
            for c in range(col_start, col_end + 1):
                if self.get(c, r) in target:
                    self.set(c, r, replacement)
