# -*- coding: utf-8 -*-
"""DDA 光线投射渲染器（伪 3D）。"""
import math
from typing import Optional

import pygame

from ..config import (
    C_CEIL_BOT,
    C_CEIL_TOP,
    C_FLOOR_B,
    C_FLOOR_T,
    C_FOG,
    C_SCAN,
    C_WALL_FAR,
    C_WALL_NR,
    H,
    K_PX_V,
    MAX_DEPTH,
    NUM_RAYS,
    W,
    _RAY_ANGLES,
    _RAY_CORRECTION,
    _RAY_COS,
    _RAY_SIN,
)
from ..world.worldmap import WorldMap

# ─────────────────────── Raycasting ─────────────────────────
class Renderer:
    def __init__(self, surf):
        self.surf = surf
        self.col_w = max(1, W // NUM_RAYS)
        # 双缓冲：预创建的辅助表面
        self._bg_cache: Optional[pygame.Surface] = None
        self._zbuf_dirty = True
        # 当前相机位姿（project() 用；draw_world 每帧刷新）
        self._cam = (0.0, 0.0, 0.0, 0.0)

    def draw_world(self, px, py, angle, pitch, zbuf, world, max_depth=MAX_DEPTH):
        """渲染一帧世界（背景 + 墙体）。

        这是渲染后端对外的统一入口 —— EnhancedRenderer 与后续接入的
        moderngl 真 3D 渲染器都实现同一个签名，主控无需关心后端。
        基础版忽略 pitch（伪 3D 的 y-shear 俯仰由增强版实现）。
        """
        self._cam = (float(px), float(py), float(angle), float(pitch))
        self.render_bg(use_cache=True)
        self.render_walls(px, py, angle, zbuf, world, max_depth)

    def project(self, wx, wy, wz):
        """世界坐标 → 屏幕坐标 (sx, sy, dist)，raycasting 投影模型。

        供世界坐标粒子使用。相机不可见（背后 / 超出 FOV）时返回 None。
        """
        px, py, ang, pitch = self._cam
        dx, dy = wx - px, wy - py
        dist = math.hypot(dx, dy)
        if dist < 0.05:
            return None
        rel = math.atan2(dy, dx) - ang
        rel = math.atan2(math.sin(rel), math.cos(rel))   # 归一到 [-pi, pi]
        if abs(rel) > 1.45:                              # 超出 ~83°（FOV 60° 留余量）
            return None
        sx = W * 0.5 + math.tan(rel) * (W * 0.5)
        sy = (H * 0.5 + pitch) + (0.5 - wz) * K_PX_V / dist
        return sx, sy, dist

    def present(self, canvas):
        """2D 后端：2D 内容已直接画在 canvas 上，无需合成。"""
        pass

    def _ensure_bg_cache(self):
        """预渲染静态背景"""
        if self._bg_cache is None:
            self._bg_cache = pygame.Surface((W, H))
            # 预渲染天空和地板
            for y in range(0, H // 2, 3):
                t = y / (H // 2)
                pygame.draw.line(self._bg_cache, self._lerp(C_CEIL_TOP, C_CEIL_BOT, t), (0, y), (W, y))
            for y in range(H // 2, H, 3):
                t = (y - H // 2) / (H // 2)
                pygame.draw.line(self._bg_cache, self._lerp(C_FLOOR_T, C_FLOOR_B, t), (0, y), (W, y))
            self._zbuf_dirty = True

    @staticmethod
    def _lerp(a, b, t):
        t = max(0.0, min(1.0, t))
        return (
            int(a[0] + (b[0] - a[0]) * t),
            int(a[1] + (b[1] - a[1]) * t),
            int(a[2] + (b[2] - a[2]) * t),
        )

    def render_bg(self, use_cache=True):
        """渲染背景，使用缓存优化"""
        if use_cache and self._bg_cache:
            self.surf.blit(self._bg_cache, (0, 0))
        else:
            # 无缓存版本（用于首次初始化）
            for y in range(0, H // 2, 3):
                t = y / (H // 2)
                pygame.draw.line(self.surf, self._lerp(C_CEIL_TOP, C_CEIL_BOT, t), (0, y), (W, y))
            for y in range(H // 2, H, 3):
                t = (y - H // 2) / (H // 2)
                pygame.draw.line(self.surf, self._lerp(C_FLOOR_T, C_FLOOR_B, t), (0, y), (W, y))

    def _cast_optimized(self, px: float, py: float, cos_val: float, sin_val: float, world: WorldMap):
        """优化射线投射：使用预计算值"""
        mx, my = int(px), int(py)
        ddx = abs(1.0 / cos_val) if abs(cos_val) > 1e-9 else 1e18
        ddy = abs(1.0 / sin_val) if abs(sin_val) > 1e-9 else 1e18
        sx = 1 if cos_val > 0 else -1
        sy = 1 if sin_val > 0 else -1
        dist_x = (mx + 1 - px) * ddx if cos_val > 0 else (px - mx) * ddx
        dist_y = (my + 1 - py) * ddy if sin_val > 0 else (py - my) * ddy
        side = 0
        for _ in range(MAX_DEPTH * 4):
            if dist_x < dist_y:
                dist_x += ddx; mx += sx; side = 0
            else:
                dist_y += ddy; my += sy; side = 1
            ct = world.cell(mx, my)
            if ct > 0:
                d = (mx - px + (1 - sx) / 2) / cos_val if side == 0 \
                    else (my - py + (1 - sy) / 2) / sin_val
                return abs(d), ct, side
        return float(MAX_DEPTH), 0, 0

    def render_walls(self, px, py, angle, zbuf, world: WorldMap, effective_max_depth: Optional[float] = None):
        """优化的墙面渲染：预计算 + 向量化
        effective_max_depth: 有效最大射线距离，暗室时会缩小
        """
        max_d = effective_max_depth if effective_max_depth is not None else MAX_DEPTH
        # 装饰物颜色映射（移到类级别避免重复创建）
        deco_colors = {
            2: ((0, 255, 200), (0, 200, 160)),
            3: ((200, 60, 60), (160, 40, 40)),
            4: ((220, 190, 80), (180, 150, 50)),
            5: ((60, 220, 120), (40, 180, 80)),
            6: ((180, 100, 240), (140, 70, 200)),
            7: ((255, 150, 60), (220, 120, 30)),
            8: ((120, 120, 130), (90, 90, 100)),
            9: ((80, 220, 255), (50, 180, 220)),
            10: ((100, 180, 255), (70, 140, 220)),
            11: ((160, 100, 220), (120, 70, 180)),
            12: ((255, 255, 100), (200, 200, 60)),   # 传送门 - 金色
        }
        
        for i in range(NUM_RAYS):
            # 使用预计算的角度
            ray_a = angle + _RAY_ANGLES[i]
            # 优化：使用预计算的 sin/cos
            cos_ray = _RAY_COS[i] * math.cos(angle) - _RAY_SIN[i] * math.sin(angle)
            sin_ray = _RAY_SIN[i] * math.cos(angle) + _RAY_COS[i] * math.sin(angle)
            
            raw_d, ct, side = self._cast_optimized(px, py, cos_ray, sin_ray, world)
            # 暗室视野缩短：超出有效距离的射线截断
            if raw_d > max_d:
                raw_d = max_d
                ct = 0
            zbuf[i] = raw_d

            # 优化：使用预计算的校正因子
            dist = max(0.001, raw_d * _RAY_CORRECTION[i])
            h = min(H, int(H / dist))
            top = (H - h) // 2

            # 预计算雾化
            fog_t  = min(1.0, raw_d / max_d) * 0.7
            dark   = 0.65 if side == 1 else 1.0
            bright = max(0.08, dark * (1.0 - raw_d * 0.025))

            # 根据装饰物类型选择颜色
            if ct >= 2:
                base_pair = deco_colors.get(ct, deco_colors[2])
                base = base_pair[0] if side == 0 else base_pair[1]
                fade = max(0.35, 1.0 - raw_d * 0.05)
                col  = tuple(int(c * fade) for c in base)
                col  = self._lerp(col, C_FOG, fog_t ** 1.3)
            else:
                near = tuple(int(c * bright) for c in C_WALL_NR)
                far  = tuple(int(c * bright) for c in C_WALL_FAR)
                col  = self._lerp(near, far, fog_t)
                col  = self._lerp(col, C_FOG, fog_t ** 1.5)

            x = i * self.col_w
            pygame.draw.rect(self.surf, col, (x, top, self.col_w + 1, h))

    def render_scanlines(self):
        # 减弱扫描线效果：间距加大，透明度降低
        for y in range(0, H, 10):
            alpha_surf = pygame.Surface((W, 2), pygame.SRCALPHA)
            alpha_surf.fill((C_SCAN[0], C_SCAN[1], C_SCAN[2], 25))
            self.surf.blit(alpha_surf, (0, y))
