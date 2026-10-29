"""装饰绘制（12 种 `draw` 分支，子任务 4.8）。

🔴 禁止 `from __future__ import annotations`（E6）。

装饰是**静态图元**：只在布局变更（买入 / 换缸尺寸）时重画一次，
不参与每帧刷新（P0-22 性能约束）。

所有分支同样输出与平台无关的 :class:`~pyapp.fish_painter.Prim`，
方便 XJ380 端复用同一套形状描述。
颜色取自 `decor_data.json` 的 `color` 数组（至少 1 个，通常 2 个）。
"""

import math

from pyapp.fish_painter import (
    KIND_CIRCLE, KIND_ELLIPSE, KIND_POLYGON, Prim,
)

ROLE_MAIN = "d0"
"""用 colors[0]。"""
ROLE_ALT = "d1"
"""用 colors[1]（缺省回退 colors[0]）。"""

_DRAWS = (
    "pebbles", "plants", "driftwood", "bubbler", "bridge", "lantern",
    "coral", "chest", "castle", "jellyfish", "starsand", "shrine",
)
"""decor_data.json 里出现的全部 draw 类型（4.8 要求逐个实现）。"""


def draw_kinds():
    """返回支持的装饰绘制类型元组。"""
    return _DRAWS


def _rect(x0, y0, x1, y1, role):
    """轴对齐矩形（用 polygon 表达，方便 XJ 端三角化）。"""
    return Prim(KIND_POLYGON, role,
                points=[(x0, y0), (x1, y0), (x1, y1), (x0, y1)])


def _tri(p0, p1, p2, role):
    return Prim(KIND_POLYGON, role, points=[p0, p1, p2])


def _pebbles(w, h):
    """鹅卵石底砂：一排大小错落的扁椭圆，不重叠。"""
    out = []
    n = 7
    for i in range(n):
        t = (i + 0.5) / n
        r = w * (0.055 + 0.03 * ((i * 7) % 3) / 2.0)
        out.append(Prim(KIND_ELLIPSE, ROLE_MAIN if i % 2 else ROLE_ALT,
                        cx=(t - 0.5) * w, cy=-r * 0.45,
                        rx=r, ry=r * 0.62))
    return out


def _plants(w, h):
    """水草：三丛高低不一的窄叶。"""
    out = []
    for i, (dx, hh) in enumerate(((-0.30, 0.95), (0.0, 0.70), (0.28, 0.85))):
        bx = dx * w
        top = -h * hh
        out.append(Prim(KIND_POLYGON, ROLE_MAIN if i % 2 else ROLE_ALT, points=[
            (bx - w * 0.045, 0.0),
            (bx + w * 0.010, top),
            (bx + w * 0.055, top * 0.55),
            (bx + w * 0.045, 0.0)]))
    return out


def _driftwood(w, h):
    """沉木：一根斜置主干 + 一根分枝。"""
    return [
        Prim(KIND_POLYGON, ROLE_MAIN, points=[
            (-w * 0.42, 0.0), (-w * 0.20, -h * 0.52),
            (w * 0.30, -h * 0.34), (w * 0.44, 0.0)]),
        Prim(KIND_POLYGON, ROLE_ALT, points=[
            (-w * 0.05, -h * 0.40), (w * 0.14, -h * 0.78),
            (w * 0.24, -h * 0.70), (w * 0.10, -h * 0.34)]),
    ]


def _bubbler(w, h):
    """气泡石：底座 + 一串上升气泡。"""
    out = [Prim(KIND_ELLIPSE, ROLE_MAIN, cx=0.0, cy=-h * 0.08,
                rx=w * 0.20, ry=h * 0.10)]
    for i in range(4):
        t = (i + 1) / 5.0
        out.append(Prim(KIND_CIRCLE, ROLE_ALT,
                        cx=math.sin(i * 1.7) * w * 0.07,
                        cy=-h * (0.18 + 0.78 * t),
                        rx=w * 0.035 * (1.0 - 0.12 * i),
                        ry=w * 0.035 * (1.0 - 0.12 * i)))
    return out


def _bridge(w, h):
    """拱桥：拱身 + 两个桥墩。"""
    out = []
    steps = 10
    pts = []
    for i in range(steps + 1):
        a = math.pi * (float(i) / steps)
        pts.append((-w * 0.45 + w * 0.90 * (float(i) / steps), -math.sin(a) * h * 0.60))
    for i in range(steps, -1, -1):
        a = math.pi * (float(i) / steps)
        pts.append((-w * 0.45 + w * 0.90 * (float(i) / steps),
                    -math.sin(a) * h * 0.60 + h * 0.14))
    out.append(Prim(KIND_POLYGON, ROLE_MAIN, points=pts))
    out.append(_rect(-w * 0.45, 0.0, -w * 0.33, -h * 0.20, ROLE_ALT))
    out.append(_rect(w * 0.33, 0.0, w * 0.45, -h * 0.20, ROLE_ALT))
    return out


def _lantern(w, h):
    """石灯笼：底座 / 灯室 / 顶盖。"""
    return [
        _rect(-w * 0.16, 0.0, w * 0.16, -h * 0.16, ROLE_MAIN),
        _rect(-w * 0.09, -h * 0.16, w * 0.09, -h * 0.46, ROLE_MAIN),
        _rect(-w * 0.22, -h * 0.46, w * 0.22, -h * 0.66, ROLE_ALT),
        _tri((-w * 0.28, -h * 0.66), (0.0, -h * 0.92), (w * 0.28, -h * 0.66), ROLE_MAIN),
    ]


def _coral(w, h):
    """珊瑚：三根分叉指状枝。"""
    out = []
    for i, dx in enumerate((-0.26, 0.0, 0.26)):
        bx = dx * w
        hh = h * (0.62 + 0.22 * (1 - abs(dx) * 2))
        out.append(Prim(KIND_POLYGON, ROLE_MAIN if i != 1 else ROLE_ALT, points=[
            (bx - w * 0.07, 0.0), (bx - w * 0.03, -hh),
            (bx + w * 0.03, -hh), (bx + w * 0.07, 0.0)]))
        out.append(Prim(KIND_CIRCLE, ROLE_ALT if i != 1 else ROLE_MAIN,
                        cx=bx, cy=-hh, rx=w * 0.055, ry=w * 0.055))
    return out


def _chest(w, h):
    """宝箱：箱体 + 弧形盖 + 锁扣。"""
    out = [_rect(-w * 0.34, 0.0, w * 0.34, -h * 0.38, ROLE_MAIN)]
    steps = 8
    pts = []
    for i in range(steps + 1):
        a = math.pi * (float(i) / steps)
        pts.append((-w * 0.34 + w * 0.68 * (float(i) / steps),
                    -h * 0.38 - math.sin(a) * h * 0.26))
    pts.append((w * 0.34, -h * 0.38))
    pts.append((-w * 0.34, -h * 0.38))
    out.append(Prim(KIND_POLYGON, ROLE_ALT, points=pts))
    out.append(_rect(-w * 0.05, -h * 0.44, w * 0.05, -h * 0.26, ROLE_ALT))
    return out


def _castle(w, h):
    """城堡：主楼 + 两侧塔楼 + 拱门。"""
    out = [
        _rect(-w * 0.24, 0.0, w * 0.24, -h * 0.62, ROLE_MAIN),
        _rect(-w * 0.46, 0.0, -w * 0.26, -h * 0.46, ROLE_MAIN),
        _rect(w * 0.26, 0.0, w * 0.46, -h * 0.46, ROLE_MAIN),
        _tri((-w * 0.50, -h * 0.46), (-w * 0.36, -h * 0.70), (-w * 0.22, -h * 0.46), ROLE_ALT),
        _tri((w * 0.22, -h * 0.46), (w * 0.36, -h * 0.70), (w * 0.50, -h * 0.46), ROLE_ALT),
        _tri((-w * 0.28, -h * 0.62), (0.0, -h * 0.92), (w * 0.28, -h * 0.62), ROLE_ALT),
        Prim(KIND_ELLIPSE, ROLE_ALT, cx=0.0, cy=-h * 0.10,
             rx=w * 0.09, ry=h * 0.13),
    ]
    return out


def _jellyfish(w, h):
    """水母：伞盖 + 触手（挂在中层，anchor 由数据决定）。"""
    out = [Prim(KIND_ELLIPSE, ROLE_MAIN, cx=0.0, cy=-h * 0.62,
                rx=w * 0.30, ry=h * 0.30)]
    for i in range(5):
        dx = (i - 2) * w * 0.11
        out.append(Prim(KIND_POLYGON, ROLE_ALT, points=[
            (dx - w * 0.022, -h * 0.60),
            (dx + math.sin(i) * w * 0.05, -h * 0.10),
            (dx + w * 0.022, -h * 0.60)]))
    return out


def _starsand(w, h):
    """星砂：贴底的一层小星点。"""
    out = []
    for i in range(9):
        t = (i + 0.5) / 9.0
        r = w * (0.016 + 0.010 * ((i * 5) % 3))
        out.append(Prim(KIND_CIRCLE, ROLE_MAIN if i % 3 else ROLE_ALT,
                        cx=(t - 0.5) * w, cy=-r - h * 0.01 * (i % 2),
                        rx=r, ry=r))
    return out


def _shrine(w, h):
    """鸟居神社：两根立柱 + 双横梁。"""
    return [
        _rect(-w * 0.30, 0.0, -w * 0.21, -h * 0.72, ROLE_MAIN),
        _rect(w * 0.21, 0.0, w * 0.30, -h * 0.72, ROLE_MAIN),
        _rect(-w * 0.44, -h * 0.72, w * 0.44, -h * 0.84, ROLE_ALT),
        _rect(-w * 0.34, -h * 0.56, w * 0.34, -h * 0.64, ROLE_ALT),
    ]


_DISPATCH = {
    "pebbles": _pebbles,
    "plants": _plants,
    "driftwood": _driftwood,
    "bubbler": _bubbler,
    "bridge": _bridge,
    "lantern": _lantern,
    "coral": _coral,
    "chest": _chest,
    "castle": _castle,
    "jellyfish": _jellyfish,
    "starsand": _starsand,
    "shrine": _shrine,
}


def geometry(draw, w, h):
    """生成一件装饰的图元列表。

    坐标系：原点在装饰的**底部中心**，`-y` 向上，单位 = 像素。

    :param draw: 12 种类型之一；未知类型退化成一块小石头（绝不抛异常）
    :param w: 装饰占位宽（像素）
    :param h: 装饰占位高（像素）
    :returns: :class:`~pyapp.fish_painter.Prim` 列表
    """
    w = max(1.0, float(w))
    h = max(1.0, float(h))
    fn = _DISPATCH.get(str(draw or "").lower())
    if fn is None:
        return [Prim(KIND_ELLIPSE, ROLE_MAIN, cx=0.0, cy=-h * 0.12,
                     rx=w * 0.22, ry=h * 0.12)]
    return fn(w, h)


class DecorPainter(object):
    """把装饰图元画到 Canvas（静态，只在布局变更时重画）。"""

    def __init__(self, canvas, theme):
        self.canvas = canvas
        self.theme = theme
        self._items = []

    def color_of(self, role, colors):
        """按角色从数据里的调色板取色。"""
        pal = [str(c) for c in (colors or []) if c]
        if not pal:
            return "#6E665C"
        if role == ROLE_ALT and len(pal) > 1:
            return pal[1]
        return pal[0]

    def clear(self):
        """删掉全部装饰图元。"""
        for item in self._items:
            self.canvas.delete(item)
        self._items = []

    def redraw(self, views, width, height, size_ratio=0.22):
        """按装饰快照列表整体重画。

        :param views: `game.decor_views()` 的结果
        :param width: 画布宽（像素）
        :param height: 画布高（像素）
        :param size_ratio: 单件装饰高度占画布高的比例
        """
        self.clear()
        if not views:
            return 0
        dh = height * float(size_ratio)
        dw = dh * 1.4
        for v in views:
            ox = float(v.get("x", 0.5)) * width
            oy = float(v.get("y", 0.95)) * height
            colors = v.get("colors", [])
            for prim in geometry(v.get("draw", ""), dw, dh):
                color = self.color_of(prim.role, colors)
                item = self._create(prim, ox, oy, color)
                if item is not None:
                    self._items.append(item)
        return len(self._items)

    def _create(self, prim, ox, oy, color):
        """建单个 canvas item。"""
        cv = self.canvas
        if prim.points:
            flat = []
            for (px, py) in prim.points:
                flat.append(ox + px)
                flat.append(oy + py)
            if len(flat) < 6:
                return None
            return cv.create_polygon(*flat, fill=color, outline="", tags="decor")
        return cv.create_oval(ox + prim.cx - prim.rx, oy + prim.cy - prim.ry,
                              ox + prim.cx + prim.rx, oy + prim.cy + prim.ry,
                              fill=color, outline="", tags="decor")
