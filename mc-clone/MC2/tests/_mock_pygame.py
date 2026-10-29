# -*- coding: utf-8 -*-
"""_mock_pygame — 最小 pygame mock，供 M6 纹理测试在无真实 pygame 时运行。

提供 mock Surface / draw / PixelArray，足以让 fx_tiles 的 TileTextureFactory.make()
不抛异常，且纹理确定性断言（PixelArray 坐标取色、颜色多样性）仍然成立。
"""

from __future__ import annotations


class MockSurface:
    """模拟 pygame.Surface：存储像素二维数组 + alpha。"""

    def __init__(self, size):
        w, h = size
        self._w = w
        self._h = h
        # 像素存储：(r, g, b) 或 (r, g, b, a)
        self._pixels = [[(0, 0, 0)] * w for _ in range(h)]
        self._alpha = 255

    def fill(self, color, rect=None):
        if rect is None:
            x0, y0, rw, rh = 0, 0, self._w, self._h
        else:
            x0, y0, rw, rh = rect
        for y in range(y0, y0 + rh):
            if not (0 <= y < self._h):
                continue
            row = self._pixels[y]
            for x in range(x0, x0 + rw):
                if 0 <= x < self._w:
                    row[x] = color

    def set_alpha(self, val):
        self._alpha = val

    def set_at(self, pos, color):
        x, y = int(pos[0]), int(pos[1])
        if 0 <= y < self._h and 0 <= x < self._w:
            self._pixels[y][x] = color

    def get_width(self):
        return self._w

    def get_height(self):
        return self._h

    def get_size(self):
        return (self._w, self._h)


class _MockDraw:
    """模拟 pygame.draw（rect + line）。"""

    @staticmethod
    def rect(surf, color, rect, *args, **kwargs):
        surf.fill(color, rect)

    @staticmethod
    def line(surf, color, start, end, *args, **kwargs):
        x0, y0 = int(start[0]), int(start[1])
        x1, y1 = int(end[0]), int(end[1])
        dx = abs(x1 - x0)
        dy = abs(y1 - y0)
        steps = max(dx, dy, 1)
        for i in range(steps + 1):
            t = i / steps
            x = int(x0 + t * (x1 - x0))
            y = int(y0 + t * (y1 - y0))
            if 0 <= y < surf._h and 0 <= x < surf._w:
                surf._pixels[y][x] = color


class MockPixelArray:
    """模拟 pygame.PixelArray：坐标取色。"""

    def __init__(self, surf):
        self._surf = surf
        # 将 pygame 颜色 int 映射到 Surface 的 RGB tuple
        self._color_map = {}

    def _encode(self, rgb):
        """将 RGB tuple 映射到 pygame 风格的 32-bit 颜色 int。"""
        key = tuple(rgb)
        if key not in self._color_map:
            r, g, b = key
            self._color_map[key] = (r << 16) | (g << 8) | b
        return self._color_map[key]

    def __getitem__(self, idx):
        x, y = idx
        return self._encode(self._surf._pixels[y][x])

    def __setitem__(self, idx, color):
        x, y = idx
        r = (color >> 16) & 0xFF
        g = (color >> 8) & 0xFF
        b = color & 0xFF
        self._surf._pixels[y][x] = (r, g, b)


# ── 模块级导出（模拟 pygame 包）──
Surface = MockSurface
PixelArray = MockPixelArray
draw = _MockDraw()


def init():
    pass


def quit():
    pass
