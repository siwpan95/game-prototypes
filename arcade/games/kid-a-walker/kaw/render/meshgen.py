# -*- coding: utf-8 -*-
"""把一片网格区域烘焙成 GPU 顶点数组（真 3D 用）。

和 raycast 那套“逐列画竖条”完全不同：这里直接把世界**建成几何**。

- 顶点格式：pos(3) + normal(3) + uv(2) = 8 个 float32
- 地板 / 天花板 / 墙面分成三组，各自一张纹理、一次 draw call
- 面剔除：只生成"朝向空腔"的那一面。被实心格挡住的面不生成
- uv 直接用世界坐标（纹理 REPEAT），所以不用 per-cell uv，也不需要图集
- 区域边界视为空腔 —— 于是区域外沿会自动长出封口墙，不会漏光

全 numpy 向量化，没有 Python 逐格循环。
"""
import numpy as np

WALL_H = 1.0          # 墙高 / 天花板高度（世界单位）
_F = np.float32


def _quad(A, B, C, D, uvs, n):
    """把 M 个四边形展成 6M 个顶点（两个三角形 A,B,C / A,C,D）。

    A..D 均为 (M, 3)；uvs 为 (M, 4, 2)，顺序与 A,B,C,D 对应。
    绕序由调用方决定（法线用右手定则校验过）。
    """
    m = A.shape[0]
    if m == 0:
        return np.zeros((0, 8), _F)
    pos = np.empty((m, 6, 3), _F)
    pos[:, 0] = A
    pos[:, 1] = B
    pos[:, 2] = C
    pos[:, 3] = A
    pos[:, 4] = C
    pos[:, 5] = D

    uv = np.empty((m, 6, 2), _F)
    uv[:, 0] = uvs[:, 0]
    uv[:, 1] = uvs[:, 1]
    uv[:, 2] = uvs[:, 2]
    uv[:, 3] = uvs[:, 0]
    uv[:, 4] = uvs[:, 2]
    uv[:, 5] = uvs[:, 3]

    out = np.empty((m, 6, 8), _F)
    out[..., 0:3] = pos
    out[..., 3:6] = np.asarray(n, _F)
    out[..., 6:8] = uv
    return out.reshape(-1, 8)


def build_region_mesh(cells: np.ndarray, ox: float, oy: float,
                      wall_h: float = WALL_H):
    """cells: (N, N) 的格值数组（1 = 实心墙）。ox/oy 是 cell(0,0) 的世界坐标。

    返回 dict：{'floor': (M,8), 'wall': (M,8), 'ceil': (M,8)}
    """
    n = cells.shape[0]
    solid = (cells == 1)
    # 区域外看成空腔 —— 让外沿长出封口墙
    s = np.pad(solid, 1, constant_values=False)

    # ---- 地板（非实心格）----
    ii, jj = np.nonzero(~solid)
    x0 = (ox + ii).astype(_F)
    y0 = (oy + jj).astype(_F)
    z0 = np.zeros_like(x0)
    A = np.stack([x0, y0, z0], 1)
    B = np.stack([x0 + 1, y0, z0], 1)
    C = np.stack([x0 + 1, y0 + 1, z0], 1)
    D = np.stack([x0, y0 + 1, z0], 1)
    uvs = np.stack([np.stack([x0, y0], 1), np.stack([x0 + 1, y0], 1),
                    np.stack([x0 + 1, y0 + 1], 1), np.stack([x0, y0 + 1], 1)], 1)
    floor = _quad(A, B, C, D, uvs, (0.0, 0.0, 1.0))

    # ---- 天花板（非实心格）----
    # 注：_quad(A,B,C,D) 以 A-C 为对角线切两个三角形，覆盖完整 quad。
    # 不能写 _quad(A,C,B,D) 那种换序 —— 那会变成蝴蝶结，顶上留一个三角形洞
    # （渲染不开 culling，绕序无关紧要，覆盖完整才是唯一要求）。
    zt = np.full_like(x0, wall_h)
    A = np.stack([x0, y0, zt], 1)
    B = np.stack([x0 + 1, y0, zt], 1)
    C = np.stack([x0 + 1, y0 + 1, zt], 1)
    D = np.stack([x0, y0 + 1, zt], 1)
    ceil = _quad(A, B, C, D, uvs, (0.0, 0.0, -1.0))

    # ---- 墙面 ----
    # s 的 (i+1, j+1) 对应 cells 的 (i, j)
    inner = s[1:-1, 1:-1]
    si, sj = np.nonzero(inner)
    sx = (ox + si).astype(_F)
    sy = (oy + sj).astype(_F)

    parts = []
    # 四个方向：邻居非实心才生面
    for di, dj, axis in ((-1, 0, 'x'), (1, 0, 'x'), (0, -1, 'y'), (0, 1, 'y')):
        nb = s[1 + si + di, 1 + sj + dj]
        m = np.nonzero(~nb)[0]
        if m.size == 0:
            continue
        wx, wy = sx[m], sy[m]
        zl = np.zeros_like(wx)
        zh = np.full_like(wx, wall_h)

        if axis == 'x':
            px = wx if di < 0 else wx + 1.0
            A = np.stack([px, wy, zl], 1)
            B = np.stack([px, wy + 1, zl], 1)
            C = np.stack([px, wy + 1, zh], 1)
            D = np.stack([px, wy, zh], 1)
            # uv: 沿墙 = y，竖直 = z
            uvs_w = np.stack([np.stack([wy, zl], 1), np.stack([wy + 1, zl], 1),
                              np.stack([wy + 1, zh], 1), np.stack([wy, zh], 1)], 1)
            nrm = (-1.0, 0.0, 0.0) if di < 0 else (1.0, 0.0, 0.0)
            parts.append(_quad(A, B, C, D, uvs_w, nrm))
        else:
            py = wy if dj < 0 else wy + 1.0
            A = np.stack([wx, py, zl], 1)
            B = np.stack([wx + 1, py, zl], 1)
            C = np.stack([wx + 1, py, zh], 1)
            D = np.stack([wx, py, zh], 1)
            # uv: 沿墙 = x，竖直 = z
            uvs_w = np.stack([np.stack([wx, zl], 1), np.stack([wx + 1, zl], 1),
                              np.stack([wx + 1, zh], 1), np.stack([wx, zh], 1)], 1)
            nrm = (0.0, -1.0, 0.0) if dj < 0 else (0.0, 1.0, 0.0)
            parts.append(_quad(A, B, C, D, uvs_w, nrm))

    # ---- 墙顶（实心格在 z=wall_h 处封口，抬头看不会漏）----
    ti, tj = np.nonzero(solid)
    tx = (ox + ti).astype(_F)
    ty = (oy + tj).astype(_F)
    zt2 = np.full_like(tx, wall_h)
    A = np.stack([tx, ty, zt2], 1)
    B = np.stack([tx + 1, ty, zt2], 1)
    C = np.stack([tx + 1, ty + 1, zt2], 1)
    D = np.stack([tx, ty + 1, zt2], 1)
    uvs_t = np.stack([np.stack([tx, ty], 1), np.stack([tx + 1, ty], 1),
                      np.stack([tx + 1, ty + 1], 1), np.stack([tx, ty + 1], 1)], 1)
    parts.append(_quad(A, B, C, D, uvs_t, (0.0, 0.0, 1.0)))

    wall = np.concatenate(parts) if parts else np.zeros((0, 8), _F)
    return {'floor': floor, 'wall': wall, 'ceil': ceil}


def region_cells(world, cx: int, cy: int, radius: int, chunk: int):
    """取以玩家所在区块为中心的 (2r+1)×(2r+1) 区块区域，拼成一张格值表。

    整块一起建网格，区块接缝自然就消掉了 —— 不需要处理"邻居区块加载后要重建"的问题。
    """
    n = (2 * radius + 1) * chunk
    cells = np.ones((n, n), np.int8)      # 未生成/未覆盖的格子按墙处理
    base_x = (cx - radius) * chunk
    base_y = (cy - radius) * chunk
    for j in range(n):
        for i in range(n):
            cells[j, i] = world.cell(base_x + i + 0.5, base_y + j + 0.5)
    return cells, base_x, base_y
