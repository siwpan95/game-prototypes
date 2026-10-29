"""
geometry — 2D 几何基础工具（无硬依赖）。

提供：
  - Vec2i:   整数二维向量（支持 +, -, ==, hash, 元组转换）
  - AABB2D:  轴对齐包围盒（contains/clamp_point/intersects/width/height）
  - clamp:   数值钳制到 [lo, hi]
  - lerp:    线性插值

遵循 Google 风格注释。确定性、纯函数式，无副作用，可直接被其它模块复用。
"""

from __future__ import annotations

from dataclasses import dataclass


def clamp(value: float, lo: float, hi: float) -> float:
    """将数值钳制到 [lo, hi] 区间（含边界）。

    参数：
        value: 待钳制数值
        lo: 下界（含）
        hi: 上界（含）

    返回：
        钳制后的数值（若 value < lo 返回 lo；若 value > hi 返回 hi；否则原值）
    """
    if value < lo:
        return lo
    if value > hi:
        return hi
    return value


def lerp(a: float, b: float, t: float) -> float:
    """线性插值：result = a + (b - a) * t。

    参数：
        a: 起点值
        b: 终点值
        t: 插值因子（0 → a，1 → b，可超出 [0,1] 做外推）

    返回：
        插值结果
    """
    return a + (b - a) * t


@dataclass(slots=True)
class Vec2i:
    """整数二维向量。

    支持 +, - 运算与 == 比较，并实现了 __hash__，
    因此可作为字典键或集合元素使用（用于坐标索引）。
    """

    x: int = 0
    y: int = 0

    def __add__(self, other: "Vec2i") -> "Vec2i":
        """向量相加，返回新 Vec2i。"""
        return Vec2i(self.x + other.x, self.y + other.y)

    def __sub__(self, other: "Vec2i") -> "Vec2i":
        """向量相减，返回新 Vec2i。"""
        return Vec2i(self.x - other.x, self.y - other.y)

    def __eq__(self, other: object) -> bool:
        """按分量比较相等性。"""
        if not isinstance(other, Vec2i):
            return NotImplemented
        return self.x == other.x and self.y == other.y

    def __hash__(self) -> int:
        """基于 (x, y) 的哈希，保证相等向量哈希一致。"""
        return hash((self.x, self.y))

    def as_tuple(self) -> tuple[int, int]:
        """转为 (x, y) 元组。"""
        return (self.x, self.y)

    @classmethod
    def from_tuple(cls, t: tuple[int, int]) -> "Vec2i":
        """从 (x, y) 元组构造。"""
        return cls(t[0], t[1])

    def __repr__(self) -> str:
        return f"Vec2i(x={self.x}, y={self.y})"


@dataclass(slots=True)
class AABB2D:
    """轴对齐二维包围盒 (Axis-Aligned Bounding Box)。

    坐标约定：min 为左下角，max 为右上角（y 轴向上）。
    内部以 min_x/min_y/max_x/max_y 四个整数存储。
    """

    min_x: int = 0
    min_y: int = 0
    max_x: int = 0
    max_y: int = 0

    def contains(self, x: int, y: int) -> bool:
        """判断点 (x, y) 是否落在包围盒内（含边界）。"""
        return self.min_x <= x <= self.max_x and self.min_y <= y <= self.max_y

    def clamp_point(self, x: int, y: int) -> tuple[int, int]:
        """将点 (x, y) 钳制到包围盒边界内（含边界），返回整数坐标元组。"""
        cx = int(clamp(x, self.min_x, self.max_x))
        cy = int(clamp(y, self.min_y, self.max_y))
        return (cx, cy)

    def intersects(self, other: "AABB2D") -> bool:
        """判断是否与另一个包围盒相交（边界接触也算相交）。"""
        return not (
            other.max_x < self.min_x
            or other.min_x > self.max_x
            or other.max_y < self.min_y
            or other.min_y > self.max_y
        )

    @property
    def width(self) -> int:
        """包围盒宽度（max_x - min_x）。"""
        return self.max_x - self.min_x

    @property
    def height(self) -> int:
        """包围盒高度（max_y - min_y）。"""
        return self.max_y - self.min_y

    def __repr__(self) -> str:
        return (
            f"AABB2D(min_x={self.min_x}, min_y={self.min_y}, "
            f"max_x={self.max_x}, max_y={self.max_y})"
        )
