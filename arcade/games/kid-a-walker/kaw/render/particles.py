# -*- coding: utf-8 -*-
"""世界坐标粒子（Stage 3）。

粒子现在存**世界坐标** (x, y, z)，漂移也在世界空间进行；
绘制时由当前渲染后端投影到屏幕（`renderer.project()`）：
- gl       ：透视矩阵投影（真 3D，距离越远越小）
- enhanced / raycast：沿用 raycasting 的屏幕投影模型

这样同一个粒子系统在三个后端下都几何正确，不再硬编码 raycast 的屏幕公式。
"""
import math
import random

import pygame

# ─────────────────────── 粒子（支持多彩） ─────────────────────────
# 装饰物对应的粒子颜色
DECO_PARTICLE_COLORS = {
    2: [(0, 255, 200), (50, 200, 180)],
    3: [(220, 80, 60), (180, 50, 40)],
    4: [(230, 200, 100), (200, 160, 60)],
    5: [(80, 220, 140), (50, 180, 100)],
    6: [(200, 120, 255), (160, 80, 220)],
    7: [(255, 170, 80), (220, 130, 50)],
    8: [(140, 140, 150), (100, 100, 110)],
    9: [(100, 230, 255), (70, 190, 220)],
    10: [(120, 200, 255), (90, 160, 220)],
    11: [(180, 120, 240), (140, 80, 200)],
    12: [(255, 255, 100), (200, 200, 50)],   # 传送门 - 金色闪光
}

# 半径透视缩放参考距离：dist=REF_DIST 时半径即原始 r（1~3 px）
_PARTICLE_REF_DIST = 3.0


class Particle:
    __slots__ = ('x', 'y', 'z', 'vx', 'vy', 'vz', 'life', 'max_life', 'r', 'col')

    def __init__(self, x, y, deco_type=2, z=None):
        # x, y, z 为世界坐标（一格 = 1 世界单位，z 向上）
        self.x, self.y = float(x), float(y)
        self.z = 0.5 if z is None else float(z)
        a = random.uniform(0, 2 * math.pi)
        s = random.uniform(0.004, 0.020)          # 世界单位 / 帧
        self.vx = math.cos(a) * s
        self.vy = math.sin(a) * s
        self.vz = random.uniform(-0.002, 0.004)
        self.life = self.max_life = random.randint(25, 70)
        self.r = random.randint(1, 3)
        colors = DECO_PARTICLE_COLORS.get(deco_type, DECO_PARTICLE_COLORS[2])
        self.col = random.choice(colors)

    def update(self):
        self.x += self.vx
        self.y += self.vy
        self.z += self.vz
        self.vz -= 0.00015                        # 轻微下坠（对应旧版 vy += 0.05 像素）
        self.vx *= 0.96
        self.vy *= 0.96
        self.life -= 1
        return self.life > 0

    def draw(self, surf, renderer=None):
        """投影到屏幕并绘制。renderer 为 None 时按原样把 (x,y) 当屏幕坐标用。"""
        if renderer is not None and hasattr(renderer, "project"):
            pr = renderer.project(self.x, self.y, self.z)
            if pr is None:
                return
            sx, sy, dist = pr
            if not (0 <= sx < surf.get_width() and 0 <= sy < surf.get_height()):
                return
            rad = max(1, int(round(self.r * _PARTICLE_REF_DIST / max(dist, 0.6))))
        else:
            sx, sy, rad = self.x, self.y, self.r

        ratio = self.life / self.max_life
        if self.col and len(self.col) >= 3:
            col = tuple(max(0, min(255, int(c * ratio + 40))) for c in self.col[:3])
        else:
            col = (0, 255, 200)  # 默认青色
        pygame.draw.circle(surf, col, (int(sx), int(sy)), rad)
