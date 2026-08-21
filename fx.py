# -*- coding: utf-8 -*-
"""视觉层：预烘焙精灵、旋转帧缓存、粒子系统、屏幕震动。

性能原则：一切静态外观只画一次（烘焙成 Surface），
运行时只做 blit + 预生成的旋转帧，不在主循环里画矢量。
"""
import math
import random

import pygame

from settings import COL


# ---------------------------------------------------------------- 烘焙工具
def bake_circle(radius, color, outline=None, glow=False, eyes=None):
    """俯视角圆形实体底图。eyes: (颜色, 半径比, 间距比) 画一对眼睛。"""
    pad = 4 if not glow else radius + 4
    size = int((radius + pad) * 2)
    s = pygame.Surface((size, size), pygame.SRCALPHA)
    cx = cy = size // 2
    if glow:
        for i in range(3, 0, -1):
            g = tuple(min(255, c + (14 * i)) for c in color)
            pygame.draw.circle(s, g + (50,), (cx, cy), int(radius * (1 + 0.16 * i)), 2)
    pygame.draw.circle(s, color, (cx, cy), radius)
    # 顶部高光，压出体积感
    hl = tuple(min(255, c + 34) for c in color)
    pygame.draw.circle(s, hl, (cx - radius // 4, cy - radius // 4), max(2, radius // 3))
    if outline:
        pygame.draw.circle(s, outline, (cx, cy), radius, 3)
    if eyes:
        ec, rr, gap = eyes
        er = max(2, int(radius * rr))
        off = int(radius * gap)
        pygame.draw.circle(s, ec, (cx - off, cy - radius // 3), er)
        pygame.draw.circle(s, ec, (cx + off, cy - radius // 3), er)
    return s


def bake_diamond(radius, color, inner=None):
    """经验宝石菱形。"""
    size = int(radius * 2 + 6)
    s = pygame.Surface((size, size), pygame.SRCALPHA)
    c = size // 2
    pts = [(c, c - radius), (c + radius, c), (c, c + radius), (c - radius, c)]
    pygame.draw.polygon(s, color, pts)
    if inner:
        r2 = max(2, radius - 3)
        pts2 = [(c, c - r2), (c + r2, c), (c, c + r2), (c - r2, c)]
        pygame.draw.polygon(s, inner, pts2)
    return s


def bake_axe(size, color):
    """战斧：柄 + 单侧刃。"""
    w = size * 2 + 8
    s = pygame.Surface((w, w), pygame.SRCALPHA)
    c = w // 2
    pygame.draw.line(s, (120, 84, 54), (c, c - size), (c, c + size), max(3, size // 3))
    pygame.draw.polygon(s, color, [
        (c + 1, c - size), (c + size, c - size // 2),
        (c + size, c + size // 3), (c + 1, c - size // 4),
    ])
    pygame.draw.polygon(s, tuple(min(255, x + 30) for x in color), [
        (c + 1, c - size), (c + size - 3, c - size // 2 + 2),
        (c + size - 6, c - size // 2 + 6), (c + 1, c - size // 4 + 3),
    ])
    return s


def bake_hammer(size, color):
    """雷锤：粗柄 + 双头锤体。"""
    w = size * 2 + 6
    s = pygame.Surface((w, w), pygame.SRCALPHA)
    c = w // 2
    pygame.draw.line(s, (110, 80, 50), (c, c - size), (c, c + size), max(3, size // 4))
    hw, hh = size, size // 2
    pygame.draw.rect(s, color, (c - hw, c - hh, hw * 2, hh * 2), border_radius=3)
    pygame.draw.rect(s, tuple(min(255, x + 40) for x in color),
                     (c - hw, c - hh, hw * 2, 4), border_radius=2)
    return s


def bake_spear(size, color):
    """冈格尼尔：细长枪身+枪头（朝右）。"""
    w = size * 5
    h = size + 6
    s = pygame.Surface((w, h), pygame.SRCALPHA)
    cy = h // 2
    pygame.draw.line(s, (140, 120, 90), (0, cy), (w - size, cy), max(2, size // 3))
    pygame.draw.polygon(s, color, [
        (w - size, cy - size // 2), (w, cy), (w - size, cy + size // 2),
    ])
    return s


def bake_raven(size, color):
    """渡鸦：菱形身体+双翼（朝右）。"""
    w = size * 3
    h = size * 2 + 4
    s = pygame.Surface((w, h), pygame.SRCALPHA)
    cx, cy = w // 2, h // 2
    pygame.draw.polygon(s, color, [(cx - size, cy), (cx + size, cy - size // 2),
                                   (cx + size, cy + size // 2)])
    pygame.draw.polygon(s, tuple(min(255, x + 25) for x in color),
                        [(cx - size // 2, cy), (cx, cy - size), (cx + size // 4, cy - size // 5)])
    pygame.draw.polygon(s, tuple(min(255, x + 25) for x in color),
                        [(cx - size // 2, cy), (cx, cy + size), (cx + size // 4, cy + size // 5)])
    return s


def bake_arrow(size, color):
    """寒冬之弓的箭（朝右）：细杆+镞+尾羽。"""
    w = size * 4
    h = size + 8
    s = pygame.Surface((w, h), pygame.SRCALPHA)
    cy = h // 2
    pygame.draw.line(s, (150, 130, 100), (2, cy), (w - size, cy), max(2, size // 3))
    pygame.draw.polygon(s, color, [(w - size, cy - size // 2), (w, cy),
                                   (w - size, cy + size // 2)])
    hl = tuple(min(255, c + 40) for c in color)
    for dy in (-1, 1):
        pygame.draw.polygon(s, hl, [(2, cy), (size, cy + dy * size),
                                    (size, cy + dy * (size // 2))])
    return s


def bake_scythe(size, color):
    """海拉之镰：长柄+内弯月刃。"""
    w = size * 2 + 8
    s = pygame.Surface((w, w), pygame.SRCALPHA)
    c = w // 2
    pygame.draw.line(s, (110, 84, 60), (c - 4, c + size // 2),
                     (c - 4, c - size), max(3, size // 4))
    pygame.draw.arc(s, color, (c - size, c - size, size * 2, size * 2), 200, 320, 5)
    hl = tuple(min(255, x + 40) for x in color)
    pygame.draw.arc(s, hl, (c - size + 3, c - size + 3, size * 2 - 6, size * 2 - 6),
                    205, 315, 2)
    return s


class RotCache:
    """把一张底图预旋成 N 帧，运行期按角度取帧（最近邻）。"""

    def __init__(self, base, n=24):
        self.frames = []
        self.n = n
        for i in range(n):
            ang = i * 360.0 / n
            self.frames.append(pygame.transform.rotozoom(base, ang, 1.0))

    def get(self, angle_deg):
        idx = int((-angle_deg) % 360 / (360.0 / self.n) + 0.5) % self.n
        return self.frames[idx]


# ---------------------------------------------------------------- 粒子
class Particles:
    """简单圆粒子池：pos, vel, life, size, color, drag。"""

    __slots__ = ("items",)

    def __init__(self):
        self.items = []

    def burst(self, x, y, color, n=8, speed=140.0, life=0.5, size=4.0, drag=3.0):
        for _ in range(n):
            a = random.uniform(0, math.tau)
            sp = random.uniform(0.35, 1.0) * speed
            self.items.append((x, y, math.cos(a) * sp, math.sin(a) * sp,
                               life * random.uniform(0.6, 1.2),
                               size * random.uniform(0.6, 1.3), color, drag))

    def ring(self, x, y, color, n=14, speed=190.0, life=0.45, size=3.0, drag=2.0):
        for i in range(n):
            a = i * math.tau / n + random.uniform(-0.12, 0.12)
            self.items.append((x, y, math.cos(a) * speed, math.sin(a) * speed,
                               life, size, color, drag))

    def update(self, dt):
        alive = []
        for x, y, vx, vy, life, size, color, drag in self.items:
            life -= dt
            if life <= 0:
                continue
            d = max(0.0, 1.0 - drag * dt)
            vx *= d
            vy *= d
            alive.append((x + vx * dt, y + vy * dt, vx, vy, life, size, color, drag))
        self.items = alive

    def draw(self, surf, cam_x, cam_y, w, h):
        blits = []
        for x, y, vx, vy, life, size, color, drag in self.items:
            sx, sy = x - cam_x, y - cam_y
            if -8 <= sx <= w + 8 and -8 <= sy <= h + 8:
                k = life if life < 1 else 1.0
                r = max(1, int(size * k))
                blits.append((_dot(color, r), (int(sx - r), int(sy - r))))
        surf.blits(blits)


_DOT_CACHE = {}


def _dot(color, r):
    key = (color, r)
    s = _DOT_CACHE.get(key)
    if s is None:
        s = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
        pygame.draw.circle(s, color, (r, r), r)
        _DOT_CACHE[key] = s
    return s


# ---------------------------------------------------------------- 屏震
class CameraShake:
    def __init__(self):
        self.trauma = 0.0

    def add(self, amount):
        self.trauma = min(1.0, self.trauma + amount)

    def offset(self):
        if self.trauma <= 0:
            return 0.0, 0.0
        t2 = self.trauma * self.trauma
        return (random.uniform(-1, 1) * 14 * t2,
                random.uniform(-1, 1) * 14 * t2)

    def update(self, dt):
        self.trauma = max(0.0, self.trauma - 2.2 * dt)


# ---------------------------------------------------------------- 地面
def bake_ground_tile(theme=None, tile=256):
    """主题地砖：底色 + 噪点 + 裂纹。平铺无缝。

    theme: dict(ground, line) —— 雪夜/熔岩两套配色；None 用默认雪夜。
    """
    rng = random.Random(20260821)
    s = pygame.Surface((tile, tile))
    ground = theme["ground"] if theme else COL["ground"]
    line = theme["line"] if theme else COL["ground_line"]
    s.fill(ground)
    lava = theme is not None and theme.get("lava", False)
    speck = (70, 32, 22) if lava else (33, 38, 50)
    for _ in range(120):                       # 斑点（雪斑/余烬）
        x, y = rng.randrange(tile), rng.randrange(tile)
        r = rng.randrange(1, 3)
        pygame.draw.circle(s, speck, (x, y), r)
    for _ in range(60):                        # 暗噪点
        x, y = rng.randrange(tile), rng.randrange(tile)
        pygame.draw.circle(s, line, (x, y), rng.randrange(1, 4))
    for _ in range(5):                          # 裂纹（越界部分自然裁剪）
        x, y = rng.randrange(tile), rng.randrange(tile)
        pts = [(x, y)]
        for _ in range(rng.randrange(3, 6)):
            x += rng.randrange(-30, 31)
            y += rng.randrange(-30, 31)
            pts.append((x, y))
        crack = (90, 40, 24) if lava else (30, 33, 44)
        pygame.draw.lines(s, crack, False, pts, 1)
    if lava:                                    # 熔岩细脉
        for _ in range(3):
            x, y = rng.randrange(tile), rng.randrange(tile)
            pts = [(x, y)]
            for _ in range(rng.randrange(3, 5)):
                x += rng.randrange(-40, 41)
                y += rng.randrange(-40, 41)
                pts.append((x, y))
            pygame.draw.lines(s, (200, 90, 40), False, pts, 2)
    return s


def hash_seed(a, b):
    """确定性 chunk 种子：同块装饰永远一致。"""
    h = (a * 374761393 + b * 668265263) & 0x7FFFFFFF
    h = (h ^ (h >> 13)) * 1274126177 & 0x7FFFFFFF
    return h ^ (h >> 16)


def decorations_for_chunk(cx, cy, cell=520, kinds=None):
    """按世界坐标块生成装饰，返回 [(sx, sy, kind, rot, scale)]。"""
    kinds = kinds or ("rune", "bone", "snow", "rock")
    rng = random.Random(hash_seed(cx, cy))
    out = []
    for _ in range(rng.randrange(2, 5)):
        x = cx * cell + rng.uniform(30, cell - 30)
        y = cy * cell + rng.uniform(30, cell - 30)
        kind = rng.choice(kinds)
        out.append((x, y, kind, rng.uniform(0, 360), rng.uniform(0.8, 1.3)))
    return out


def bake_decoration(kind):
    s = pygame.Surface((44, 44), pygame.SRCALPHA)
    if kind == "rune":      # 符文石碑
        pygame.draw.rect(s, (58, 64, 82), (14, 8, 16, 30), border_radius=3)
        pygame.draw.rect(s, (72, 80, 100), (14, 8, 16, 5), border_radius=2)
        pygame.draw.line(s, COL["rune"], (22, 14), (22, 32), 2)
        pygame.draw.line(s, COL["rune"], (17, 20), (27, 20), 2)
        pygame.draw.line(s, COL["rune"], (18, 27), (26, 27), 1)
    elif kind == "bone":
        pygame.draw.line(s, (196, 192, 178), (10, 26), (34, 18), 3)
        pygame.draw.circle(s, (206, 202, 188), (10, 26), 3)
        pygame.draw.circle(s, (206, 202, 188), (34, 18), 3)
    elif kind == "bones":   # 骨堆（熔岩图）
        pygame.draw.line(s, (180, 172, 156), (8, 30), (36, 24), 3)
        pygame.draw.line(s, (196, 188, 172), (12, 20), (30, 32), 3)
        pygame.draw.circle(s, (206, 198, 182), (8, 30), 3)
        pygame.draw.circle(s, (206, 198, 182), (36, 24), 3)
        pygame.draw.circle(s, (190, 182, 166), (22, 18), 4)
    elif kind == "rock":
        pygame.draw.polygon(s, (48, 54, 68), [(12, 30), (18, 14), (32, 12), (36, 30)])
        pygame.draw.polygon(s, (60, 66, 82), [(18, 14), (32, 12), (34, 22), (20, 24)])
    elif kind == "lava":    # 熔岩池：暗壳+亮芯
        pygame.draw.ellipse(s, (70, 34, 24), (6, 14, 32, 20))
        pygame.draw.ellipse(s, (200, 80, 30), (11, 18, 22, 12))
        pygame.draw.ellipse(s, (255, 160, 60), (15, 21, 14, 7))
    elif kind == "charcoal":  # 焦木
        pygame.draw.line(s, (40, 34, 32), (10, 34), (34, 12), 5)
        pygame.draw.line(s, (52, 44, 40), (18, 28), (30, 34), 3)
        pygame.draw.circle(s, (255, 120, 40), (34, 12), 2)
    else:                    # snow 雪堆
        pygame.draw.ellipse(s, (36, 42, 56), (8, 18, 28, 14))
        pygame.draw.ellipse(s, (44, 50, 66), (12, 20, 18, 8))
    return s
