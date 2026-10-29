"""物理引擎 — 力基摩擦 + CCD 子步碰撞 + 混沌扰动"""

import math
import time
import random
from typing import Tuple

from config import (DT, GRAVITY_PPS2, AIR_DENSITY, DRAG_COEFF,
                    SUBDIVISIONS_PER_FRAME, RIDER_COLLISION_RADIUS, SURFACE_THICKNESS)
from track import find_best_contact


class ChaoticPhysics:
    """混沌物理引擎——管理全局物理参数和力模型。"""

    def __init__(self):
        self.gravity = GRAVITY_PPS2
        self.air_density = AIR_DENSITY
        self.drag_coeff = DRAG_COEFF
        self.turbulence = 0.0          # 湍流强度
        self.wind = 0.0                # 水平风力

    def apply_free_forces(self, vx: float, vy: float, rider_radius: float,
                           rider_mass: float) -> Tuple[float, float]:
        """施加与地面无关的力：重力 + 空气阻力。

        返回力向量 (fx, fy)。调用方自行用 dt 积分。
        """
        fx, fy = 0.0, self.gravity * rider_mass  # 重力

        # 空气阻力: F = 0.5 * ρ * v² * C_d * A
        speed = math.hypot(vx, vy)
        if speed > 0.001:
            area = math.pi * (rider_radius ** 2) / 10000
            drag_force = 0.5 * self.air_density * speed * speed * self.drag_coeff * area
            fx += -(vx / speed) * drag_force
            fy += -(vy / speed) * drag_force

        return fx, fy

    def apply_ground_forces(self, vx: float, vy: float,
                            tangent_x: float, tangent_y: float,
                            friction_coeff: float, rider_mass: float
                            ) -> Tuple[float, float]:
        """施加地面接触力：法向约束 + 切向摩擦力。

        物理模型：
        - 法向力 = mass * gravity（简化，假设平坦接触面）
        - 摩擦力 = μ * N，方向沿切向与速度相反
        - 返回力向量 (fx, fy)
        """
        # 切向速度分量
        vt = vx * tangent_x + vy * tangent_y
        v_tx = vt * tangent_x
        v_ty = vt * tangent_y

        # 法向力 = mass * gravity（轨道法向分量，简化用垂直分量）
        normal_force = rider_mass * self.gravity

        # 摩擦力沿切向，与切向速度相反
        friction_magnitude = (1.0 - friction_coeff) * normal_force
        if abs(vt) > 0.001:
            friction_fx = -(v_tx / abs(vt)) * friction_magnitude
            friction_fy = -(v_ty / abs(vt)) * friction_magnitude
        else:
            friction_fx = friction_fy = 0.0

        return friction_fx, friction_fy

    def chaos_perturbation(self, world_x: float, world_y: float) -> Tuple[float, float]:
        """混沌速度扰动（湍流 + 风）"""
        chaos_x = (math.sin(time.time() * 5 + world_x * 0.01) * self.turbulence
                   + self.wind)
        chaos_y = math.cos(time.time() * 3 + world_y * 0.01) * self.turbulence * 0.5
        return chaos_x * DT, chaos_y * DT


def step_physics(rider_x: float, rider_y: float,
                 vx: float, vy: float,
                 rider_radius: float, rider_mass: float,
                 tracks, physics: ChaoticPhysics
                 ) -> dict:
    """CCD 物理一步。

    将一帧的 DT 分成 SUBDIVISIONS_PER_FRAME 个子步，
    每子步内：自由力 → 位置推进 → 碰撞检测 → 地面力 → 反弹 → 混沌。

    Returns:
        dict with keys: x, y, vx, vy, on_ground, material, tangent
    """
    sub_dt = DT / SUBDIVISIONS_PER_FRAME
    x, y = rider_x, rider_y
    on_ground = False
    last_material = None
    last_tangent = (1.0, 0.0)

    for _ in range(SUBDIVISIONS_PER_FRAME):
        # 1) 自由力
        free_fx, free_fy = physics.apply_free_forces(vx, vy, rider_radius, rider_mass)

        # 2) 位置预测
        ax = free_fx / rider_mass
        ay = free_fy / rider_mass
        vx += ax * sub_dt
        vy += ay * sub_dt
        nx = x + vx * sub_dt
        ny = y + vy * sub_dt

        # 3) 碰撞检测
        contact, track, dist, cnx, cny, tx, ty = \
            find_best_contact(nx, ny, rider_radius, tracks)

        if contact and track:
            on_ground = True
            last_material = track.material
            last_tangent = (tx, ty)

            # 计算法线：从表面最近点指向 rider
            push_x = nx - cnx
            push_y = ny - cny
            push_len = math.hypot(push_x, push_y)
            if push_len > 0.001:
                nx_norm, ny_norm = push_x / push_len, push_y / push_len
            else:
                nx_norm, ny_norm = 0.0, -1.0

            # 推出到表面
            overlap = rider_radius + SURFACE_THICKNESS - dist
            if overlap > 0:
                x = nx + nx_norm * overlap
                y = ny + ny_norm * overlap
            else:
                x, y = nx, ny

            # 4) 法向反弹 + 切向摩擦力
            vn = vx * nx_norm + vy * ny_norm  # 法向速度分量
            if vn > 0:  # 只有"撞向"表面时才反弹
                # 法向反弹
                restitution = track.material.restitution
                vx -= vn * nx_norm
                vy -= vn * ny_norm
                vx += (-vn * restitution) * nx_norm
                vy += (-vn * restitution) * ny_norm

            # 切向摩擦力（每子步施加固定比例的摩擦）
            vt = vx * tx + vy * ty          # 切向速度
            v_tx = vt * tx
            v_ty = vt * ty
            friction = (1.0 - track.material.friction)
            vx -= v_tx * friction * 8.0 * sub_dt
            vy -= v_ty * friction * 8.0 * sub_dt

            # 混沌扰动（材质相关）
            chaos = track.material.chaos_factor
            vx += (random.random() - 0.5) * chaos * 8 * sub_dt
            vy += (random.random() - 0.5) * chaos * 8 * sub_dt
        else:
            x, y = nx, ny
            on_ground = False

    # 5) 全局混沌扰动
    cx, cy = physics.chaos_perturbation(x, y)
    vx += cx
    vy += cy

    return {
        'x': x, 'y': y,
        'vx': vx, 'vy': vy,
        'on_ground': on_ground,
        'material': last_material,
        'tangent': last_tangent,
    }
