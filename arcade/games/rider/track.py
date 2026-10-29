"""轨道系统 — 贝塞尔曲线 + 真实法线计算 + 碰撞检测"""

import math
from typing import List, Tuple

from config import Material, MATERIALS, DEFAULT_MATERIAL, TRACK_SAMPLE_STEPS

# ─── 纯函数：贝塞尔计算 ──────────────────────────────

def bezier_point(cp: List[Tuple[float, float]], t: float) -> Tuple[float, float]:
    """三次贝塞尔：B(t)"""
    p0, p1, p2, p3 = cp
    u = 1 - t
    x = u**3 * p0[0] + 3 * u**2 * t * p1[0] + 3 * u * t**2 * p2[0] + t**3 * p3[0]
    y = u**3 * p0[1] + 3 * u**2 * t * p1[1] + 3 * u * t**2 * p2[1] + t**3 * p3[1]
    return x, y


def bezier_derivative(cp: List[Tuple[float, float]], t: float) -> Tuple[float, float]:
    """三次贝塞尔一阶导数 B'(t)"""
    p0, p1, p2, p3 = cp
    u = 1 - t
    dx = 3 * u * u * (p1[0] - p0[0]) + 6 * u * t * (p2[0] - p1[0]) + 3 * t * t * (p3[0] - p2[0])
    dy = 3 * u * u * (p1[1] - p0[1]) + 6 * u * t * (p2[1] - p1[1]) + 3 * t * t * (p3[1] - p2[1])
    return dx, dy


def point_to_segment(px: float, py: float,
                     x1: float, y1: float, x2: float, y2: float
                     ) -> Tuple[float, float, float, float]:
    """点到线段最近点 → (距离, 最近x, 最近y, 局部参数u ∈ [0,1])"""
    dx, dy = x2 - x1, y2 - y1
    if dx == 0 and dy == 0:
        return math.hypot(px - x1, py - y1), x1, y1, 0.0
    u = ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy)
    u = max(0.0, min(1.0, u))
    nx, ny = x1 + u * dx, y1 + u * dy
    return math.hypot(px - nx, py - ny), nx, ny, u


# ─── 轨道类 ────────────────────────────────────────

class Track:
    """一段贝塞尔轨道。

    Attributes:
        segments: [(x1, y1, x2, y2, t_start, t_end), ...]
            每个采样线段附有贝塞尔参数 t 范围，用于计算法线。
    """

    def __init__(self, control_points: List[Tuple[float, float]],
                 material_id: int = DEFAULT_MATERIAL):
        self.control_points = control_points  # [P0, P1, P2, P3]
        self.material: Material = MATERIALS[material_id]
        self.segments: List[Tuple] = []       # (x1,y1, x2,y2, t0,t1)
        self._sample()

    def _sample(self):
        """将贝塞尔采样为线段并记录 t 参数"""
        steps = TRACK_SAMPLE_STEPS
        for i in range(steps):
            t0 = i / steps
            t1 = (i + 1) / steps
            x1, y1 = bezier_point(self.control_points, t0)
            x2, y2 = bezier_point(self.control_points, t1)
            self.segments.append((x1, y1, x2, y2, t0, t1))

    def find_nearest(self, wx: float, wy: float
                     ) -> Tuple[float, float, float, float, float, float]:
        """查找离 (wx,wy) 最近的轨道点，返回 (距离, 近点x, 近点y, 切线tx, 切线ty)。

        切线已归一化。用于碰撞检测和物理。
        """
        best_dist = float('inf')
        best_nx = best_ny = 0.0
        best_tx = best_ty = 0.0

        for (x1, y1, x2, y2, t_a, t_b) in self.segments:
            dist, nx, ny, local_u = point_to_segment(wx, wy, x1, y1, x2, y2)
            if dist < best_dist:
                best_dist = dist
                best_nx, best_ny = nx, ny
                # 用 local_u 在 [t_a, t_b] 之间插值，求该点的导数
                t_curve = t_a + local_u * (t_b - t_a)
                dx, dy = bezier_derivative(self.control_points, t_curve)
                length = math.hypot(dx, dy)
                if length > 1e-6:
                    best_tx, best_ty = dx / length, dy / length

        return best_dist, best_nx, best_ny, best_tx, best_ty


def find_best_contact(rider_x: float, rider_y: float, radius: float,
                      tracks: List[Track]
                      ) -> Tuple[bool, Track, float, float, float, float, float, float]:
    """在所有轨道中查找最佳接触点。

    返回: (有接触, 轨道对象, 距离, 最近x, 最近y, 切线tx, 切线ty)

    切线方向是沿轨道表面的方向（已归一化）。
    """
    best_dist = float('inf')
    best_track = None
    best_nx = best_ny = 0.0
    best_tx = best_ty = 1.0, 0.0

    for track in tracks:
        dist, nx, ny, tx, ty = track.find_nearest(rider_x, rider_y)
        if dist < best_dist:
            best_dist = dist
            best_track = track
            best_nx, best_ny = nx, ny
            best_tx, best_ty = tx, ty

    in_contact = best_dist < radius + 5
    return in_contact, best_track, best_dist, best_nx, best_ny, best_tx, best_ty
