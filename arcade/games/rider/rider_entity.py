"""Rider 实体 — sled 多边形渲染 + 旋转姿态 + 轨迹"""

import math
import time
import tkinter as tk
from typing import List, Tuple, Optional

from config import (WIDTH, HEIGHT, MATERIALS, TRAIL_LENGTH,
                    SLED_BODY_LOCAL, SLED_RUNNER_FRONT, SLED_RUNNER_REAR,
                    BODY_CENTER, BODY_RADIUS, HEAD_CENTER, HEAD_RADIUS,
                    RIDER_COLLISION_RADIUS)
from camera import Camera


def _rotate_point(x: float, y: float, cos_a: float, sin_a: float) -> Tuple[float, float]:
    """旋转点"""
    return x * cos_a - y * sin_a, x * sin_a + y * cos_a


class Rider:
    """Line Rider 玩家实体。

    物理状态在主循环中由 physics.step_physics() 驱动，
    本类专注：渲染 sled 形状、轨迹、音效参数。
    """

    def __init__(self, canvas: tk.Canvas):
        self.canvas = canvas
        self.mass = 1.0
        self.radius = RIDER_COLLISION_RADIUS

        # 物理状态（由外部更新）
        self.x = 0.0
        self.y = 0.0
        self.vx = 0.0
        self.vy = 0.0
        self.angle = 0.0          # 弧度，0=面向右
        self.on_ground = False
        self.alive = False

        # 上一帧 for transition detection
        self._last_on_ground = False

        # 画布元素 ID
        self._sled_body_id = None
        self._sled_runner_f_id = None
        self._sled_runner_r_id = None
        self._body_id = None
        self._head_id = None

        # 轨迹
        self.trail: List[Tuple[float, float]] = []
        self._trail_id = None

    # ── 生命周期 ───────────────────────────

    def spawn(self, x: float, y: float):
        self.x, self.y = x, y
        self.vx = self.vy = 0.0
        self.angle = 0.0
        self.alive = True
        self.trail.clear()

    def apply_state(self, state: dict):
        """从 physics.step_physics() 结果同步状态"""
        self.x = state['x']
        self.y = state['y']
        self.vx = state['vx']
        self.vy = state['vy']
        self._last_on_ground = self.on_ground
        self.on_ground = state['on_ground']

        # 从切线计算旋转角度
        tx, ty = state.get('tangent', (1.0, 0.0))
        self.angle = math.atan2(ty, tx)

    @property
    def just_took_off(self) -> bool:
        """本帧刚刚离地"""
        return self._last_on_ground and not self.on_ground

    @property
    def speed(self) -> float:
        return math.hypot(self.vx, self.vy)

    # ── 坐标工具 ───────────────────────────

    def _to_screen(self, wx: float, wy: float, cam: Camera) -> Tuple[float, float]:
        return cam.world_to_screen(wx, wy)

    # ── 渲染 ───────────────────────────────

    def render(self, camera: Camera):
        """每帧调用，更新 sled 位置和角度"""
        if not self.alive:
            return

        sx, sy = self._to_screen(self.x, self.y, camera)
        cos_a = math.cos(self.angle)
        sin_a = math.sin(self.angle)

        # ── Sled 滑板主体 ──
        poly_pts = []
        for lx, ly in SLED_BODY_LOCAL:
            rx, ry = _rotate_point(lx, ly, cos_a, sin_a)
            poly_pts.extend([sx + rx, sy + ry])

        if self._sled_body_id is None:
            self._sled_body_id = self.canvas.create_polygon(
                poly_pts, fill="#E8E0D0", outline="#888", width=1)
        else:
            self.canvas.coords(self._sled_body_id, *poly_pts)
            self.canvas.itemconfig(self._sled_body_id, fill="#E8E0D0")

        # ── 滑行刃（前/后） ──
        def _update_line(cid, pts_local, fill="#AAA"):
            rx1, ry1 = _rotate_point(pts_local[0], pts_local[1], cos_a, sin_a)
            rx2, ry2 = _rotate_point(pts_local[2], pts_local[3], cos_a, sin_a)
            coords = [sx + rx1, sy + ry1, sx + rx2, sy + ry2]
            if cid is None:
                return self.canvas.create_line(coords, fill=fill, width=2, capstyle=tk.ROUND)
            else:
                self.canvas.coords(cid, *coords)
                return cid

        self._sled_runner_f_id = _update_line(self._sled_runner_f_id, SLED_RUNNER_FRONT, "#CCC")
        self._sled_runner_r_id = _update_line(self._sled_runner_r_id, SLED_RUNNER_REAR, "#CCC")

        # ── 身体（圆形） ──
        bcx, bcy = _rotate_point(BODY_CENTER[0], BODY_CENTER[1], cos_a, sin_a)
        br = BODY_RADIUS
        body_coords = [sx + bcx - br, sy + bcy - br, sx + bcx + br, sy + bcy + br]
        if self._body_id is None:
            self._body_id = self.canvas.create_oval(body_coords, fill="#4488CC", outline="")
        else:
            self.canvas.coords(self._body_id, *body_coords)

        # ── 头部（圆形） ──
        hcx, hcy = _rotate_point(HEAD_CENTER[0], HEAD_CENTER[1], cos_a, sin_a)
        hr = HEAD_RADIUS
        head_coords = [sx + hcx - hr, sy + hcy - hr, sx + hcx + hr, sy + hcy + hr]
        if self._head_id is None:
            self._head_id = self.canvas.create_oval(head_coords, fill="#FFDDBB", outline="#CC9966", width=1)
        else:
            self.canvas.coords(self._head_id, *head_coords)

        # ── 轨迹尾迹 ──
        self.trail.append((self.x, self.y))
        if len(self.trail) > TRAIL_LENGTH:
            self.trail.pop(0)

        if len(self.trail) >= 2:
            trail_screen = []
            for tx, ty in self.trail:
                tsx, tsy = self._to_screen(tx, ty, camera)
                trail_screen.extend([tsx, tsy])
            if self._trail_id is None:
                self._trail_id = self.canvas.create_line(
                    trail_screen, smooth=True, fill="#00FFFF", width=1)
            else:
                self.canvas.coords(self._trail_id, *trail_screen)

    def clear(self):
        """清除所有画布元素"""
        for cid in [self._sled_body_id, self._sled_runner_f_id,
                     self._sled_runner_r_id, self._body_id,
                     self._head_id, self._trail_id]:
            if cid is not None:
                self.canvas.delete(cid)
                cid = None
        self._sled_body_id = self._sled_runner_f_id = None
        self._sled_runner_r_id = self._body_id = self._head_id = self._trail_id = None

    # ── 声学 ───────────────────────────────

    def get_acoustic_params(self, material) -> dict:
        """将物理状态转换为声学参数"""
        if material is None:
            material = MATERIALS[2]

        speed = self.speed
        height = max(1.0, HEIGHT - self.y)

        base_freq = 110 + (1000 / height) + speed * 0.5
        harmonics = [1.0]
        for i in range(1, material.base_harmonic + 1):
            harmonics.append(1.0 / i)
        volume = min(0.8, speed / 1000)
        chaos = material.chaos_factor
        freq_mod = 1.0 + math.sin(time.time() * 10) * chaos * 0.1

        return {
            'freq': base_freq * freq_mod,
            'harmonics': harmonics,
            'volume': volume,
            'chaos': chaos,
            'on_ground': self.on_ground,
        }
