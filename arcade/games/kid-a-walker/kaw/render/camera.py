# -*- coding: utf-8 -*-
"""相机与矩阵（numpy 实现，不引入 pyglm 之类的额外依赖）。

坐标约定：
    X = 地图列方向，Y = 地图行方向，Z = 向上。
    眼高 GL_EYE_Z，天花板 GL_WALL_H，一格 = 1 个世界单位。
    这与 raycast.py 的约定完全一致（眼在 0.5、墙高 1、地板 0），
    所以两个后端看到的世界尺度是一样的。

矩阵一律按**数学行主序**返回（M[row][col]）。
上传给 OpenGL 时用 `M.T.astype('f4').tobytes()` —— C 序的转置正好是列主序。
"""
import math

import numpy as np


def perspective(fov_y_deg: float, aspect: float, near: float, far: float) -> np.ndarray:
    """透视投影矩阵。fov_y 是**垂直**视角（度）。"""
    f = 1.0 / math.tan(math.radians(fov_y_deg) * 0.5)
    m = np.zeros((4, 4), np.float32)
    m[0, 0] = f / aspect
    m[1, 1] = f
    m[2, 2] = (far + near) / (near - far)
    m[2, 3] = 2.0 * far * near / (near - far)
    m[3, 2] = -1.0
    return m


def ortho(w: float, h: float) -> np.ndarray:
    """覆盖层用的正交投影：像素坐标直接当裁剪坐标用。"""
    m = np.eye(4, dtype=np.float32)
    m[0, 0] = 2.0 / w
    m[1, 1] = -2.0 / h          # Y 向下
    m[2, 2] = -1.0
    m[3, 0] = -1.0
    m[3, 1] = 1.0
    return m


def view_matrix(px: float, py: float, pz: float,
                yaw: float, pitch: float) -> np.ndarray:
    """视图矩阵。yaw 绕 Z 轴（与 raycast 的 pang 同一约定），pitch 抬头为正。"""
    cp, sp = math.cos(pitch), math.sin(pitch)
    fx, fy, fz = math.cos(yaw) * cp, math.sin(yaw) * cp, sp

    # right = normalize(cross(forward, world_up))，world_up = +Z
    rx, ry, rz = fy, -fx, 0.0
    rl = math.hypot(rx, ry)
    if rl < 1e-8:                # 正上/正下看时退化，随便取一个
        rx, ry, rz, rl = 1.0, 0.0, 0.0, 1.0
    rx, ry, rz = rx / rl, ry / rl, rz / rl

    # true_up = cross(right, forward)
    ux, uy, uz = (ry * fz - rz * fy,
                  rz * fx - rx * fz,
                  rx * fy - ry * fx)

    m = np.eye(4, dtype=np.float32)
    m[0, :3] = (rx, ry, rz)
    m[1, :3] = (ux, uy, uz)
    m[2, :3] = (-fx, -fy, -fz)
    m[0, 3] = -(rx * px + ry * py + rz * pz)
    m[1, 3] = -(ux * px + uy * py + uz * pz)
    m[2, 3] = (fx * px + fy * py + fz * pz)
    return m


def upload(m: np.ndarray) -> bytes:
    """矩阵 → 可直接喂给 moderngl uniform 的字节（列主序）。"""
    return np.ascontiguousarray(m.T, dtype=np.float32).tobytes()
