"""fov.py — 递归阴影投射 (Recursive Shadowcasting) 视野 / 战争迷雾算法。

算法来源：RogueBasin《Python shadowcasting implementation》
（Björn Bergström 的 recursive shadowcasting 的 Python 移植，社区广泛验证可用）。

为什么用它（来自 roguelike 设计共识）：
  - 经典 roguelike 的「灵魂」之一是探索感——玩家只看见周围，
    已探索区域作为记忆显示，未探索为迷雾。
  - 递归阴影投射性能好（O(半径²) 量级）、对称、无漏光/多光瑕疵，
    是 libtcod / rot.js 采用的同族算法。

使用：
    f = Shadowcaster(W, H, blocked_fn)          # blocked_fn(x,y)->bool 墙挡视线
    visible = f.compute(px, py, radius)         # -> set[(x,y)] 当前可见格
游戏层维护 explored |= visible，渲染时区分「可见 / 记忆 / 迷雾」三态。
"""
from __future__ import annotations

from typing import Callable, Set, Tuple

# 8 个象限的坐标变换矩阵（RogueBasin 标准四行八列 mult）
_MULT = [
    [1, 0, 0, -1, -1, 0, 0, 1],
    [0, 1, -1, 0, 0, -1, 1, 0],
    [0, 1, 1, 0, 0, -1, -1, 0],
    [1, 0, 0, 1, -1, 0, 0, -1],
]


class Shadowcaster:
    """递归阴影投射视野计算。"""

    def __init__(self, width: int, height: int,
                 blocked: Callable[[int, int], bool]) -> None:
        self.W = width
        self.H = height
        self._blocked = blocked
        self._visible: Set[Tuple[int, int]] = set()

    def _is_blocked(self, x: int, y: int) -> bool:
        if not (0 <= x < self.W and 0 <= y < self.H):
            return True  # 边界外视为挡光，避免投射到地图外
        return self._blocked(x, y)

    def _set_lit(self, x: int, y: int) -> None:
        if 0 <= x < self.W and 0 <= y < self.H:
            self._visible.add((x, y))

    def compute(self, ox: int, oy: int, radius: int) -> Set[Tuple[int, int]]:
        """以 (ox,oy) 为中心、radius 为半径计算可见格集合。"""
        self._visible = {(ox, oy)}
        self._set_lit(ox, oy)
        if radius <= 0:
            return self._visible
        for octant in range(8):
            xx = _MULT[0][octant]
            xy = _MULT[1][octant]
            yx = _MULT[2][octant]
            yy = _MULT[3][octant]
            self._cast_light(ox, oy, 1, 1.0, 0.0, radius, xx, xy, yx, yy)
        return self._visible

    def _cast_light(self, cx: int, cy: int, row: int, start: float, end: float,
                    radius: int, xx: int, xy: int, yx: int, yy: int) -> None:
        if start < end:
            return
        radius_sq = radius * radius
        j = 0
        blocked = False
        new_start = 0.0
        for j in range(row, radius + 1):
            dx = -j - 1
            dy = -j
            blocked = False
            while dx <= 0:
                dx += 1
                # 把 dx,dy 局部坐标变换到地图坐标
                X = cx + dx * xx + dy * xy
                Y = cy + dx * yx + dy * yy
                l_slope = (dx - 0.5) / (dy + 0.5)
                r_slope = (dx + 0.5) / (dy - 0.5)
                if start < r_slope:
                    continue
                elif end > l_slope:
                    break
                else:
                    if dx * dx + dy * dy < radius_sq:
                        self._set_lit(X, Y)
                if blocked:
                    # 正在扫描一排挡光的格子
                    if self._is_blocked(X, Y):
                        new_start = r_slope
                        continue
                    else:
                        blocked = False
                        start = new_start
                else:
                    if self._is_blocked(X, Y) and j < radius:
                        # 遇到挡光格，开启一次子扫描
                        blocked = True
                        self._cast_light(cx, cy, j + 1, start, l_slope,
                                        radius, xx, xy, yx, yy)
                        new_start = r_slope
            if blocked:
                break


def compute_fov(ox: int, oy: int, radius: int,
                blocked: Callable[[int, int], bool],
                width: int, height: int) -> Set[Tuple[int, int]]:
    """便捷函数：直接返回 (ox,oy) 半径 radius 内的可见格集合。"""
    return Shadowcaster(width, height, blocked).compute(ox, oy, radius)
