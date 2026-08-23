"""噪声生成：value / perlin / fractal，返回 0..1 的 numpy 数组。

所有函数输入 x, y（标量或同形数组），返回同形数组。
seed 控制可复现性。
"""
from __future__ import annotations

import numpy as np


def _hash2(ix, iy, seed):
    """整数格点 -> 确定性伪随机 [0,1)。支持数组输入。"""
    ix = np.asarray(ix, dtype=np.int64)
    iy = np.asarray(iy, dtype=np.int64)
    h = ix * 374761393 + iy * 668265263 + np.int64(seed) * 1013904223
    h = (h ^ (h >> 13)) * 1274126177
    h = h ^ (h >> 16)
    return (h.astype(np.int64) & 0x7FFFFFFF).astype(np.float64) / 0x7FFFFFFF


def _smooth(t):
    return t * t * (3.0 - 2.0 * t)


# 2D 梯度噪声理论最大投影幅度（√(xf²+yf²) 在角点最大 ≈ √2/2）
_PERLIN_NORM = np.sqrt(2.0) / 2.0


def _lerp(a, b, t):
    return a + t * (b - a)


def value_noise(x, y, seed: int = 0) -> np.ndarray:
    """值噪声：格点随机值 + 平滑插值，返回 0..1。"""
    x = np.asarray(x, dtype=np.float64)
    y = np.asarray(y, dtype=np.float64)
    xi = np.floor(x).astype(np.int64)
    yi = np.floor(y).astype(np.int64)
    xf = x - xi
    yf = y - yi
    v00 = _hash2(xi, yi, seed)
    v10 = _hash2(xi + 1, yi, seed)
    v01 = _hash2(xi, yi + 1, seed)
    v11 = _hash2(xi + 1, yi + 1, seed)
    u = _smooth(xf)
    v = _smooth(yf)
    return _lerp(_lerp(v00, v10, u), _lerp(v01, v11, u), v)


def perlin_noise(x, y, seed: int = 0) -> np.ndarray:
    """Perlin 梯度噪声（基于格点角度梯度），返回 0..1。"""
    x = np.asarray(x, dtype=np.float64)
    y = np.asarray(y, dtype=np.float64)
    xi = np.floor(x).astype(np.int64)
    yi = np.floor(y).astype(np.int64)
    xf = x - xi
    yf = y - yi
    ang00 = _hash2(xi, yi, seed) * 2.0 * np.pi
    ang10 = _hash2(xi + 1, yi, seed) * 2.0 * np.pi
    ang01 = _hash2(xi, yi + 1, seed) * 2.0 * np.pi
    ang11 = _hash2(xi + 1, yi + 1, seed) * 2.0 * np.pi
    gx00, gy00 = np.cos(ang00), np.sin(ang00)
    gx10, gy10 = np.cos(ang10), np.sin(ang10)
    gx01, gy01 = np.cos(ang01), np.sin(ang01)
    gx11, gy11 = np.cos(ang11), np.sin(ang11)
    d00 = gx00 * xf + gy00 * yf
    d10 = gx10 * (xf - 1) + gy10 * yf
    d01 = gx01 * xf + gy01 * (yf - 1)
    d11 = gx11 * (xf - 1) + gy11 * (yf - 1)
    u = _smooth(xf)
    v = _smooth(yf)
    n = _lerp(_lerp(d00, d10, u), _lerp(d01, d11, u), v)
    # 按理论最大幅度归一化，使输出能覆盖完整 0..1 区间（提升对比度）
    return np.clip((n / _PERLIN_NORM + 1.0) / 2.0, 0.0, 1.0)


def fbm(x, y, octaves: int = 4, lacunarity: float = 2.0, gain: float = 0.5,
        seed: int = 0) -> np.ndarray:
    """分形布朗运动（fBm）：多层 perlin 叠加，返回 0..1。

    参数：
        octaves:    叠加层数（默认 4）
        lacunarity: 每层频率倍增（默认 2.0）
        gain:       每层振幅衰减（默认 0.5）
        seed:       随机种子
    """
    x = np.asarray(x, dtype=np.float64)
    y = np.asarray(y, dtype=np.float64)
    total = np.zeros_like(x, dtype=np.float64)
    amp = 1.0
    freq = 1.0
    maxv = 0.0
    for o in range(octaves):
        total += amp * perlin_noise(x * freq, y * freq, seed=seed + o)
        maxv += amp
        amp *= gain
        freq *= lacunarity
    return np.clip(total / maxv, 0.0, 1.0)


def fractal_noise(x, y, octaves: int = 4, seed: int = 0) -> np.ndarray:
    """分形噪声：fBm 的便捷封装（默认 lacunarity=2.0 / gain=0.5）。

    示例：
        xs, ys = np.meshgrid(np.arange(64), np.arange(64))
        hm = fractal_noise(xs, ys, octaves=5, seed=1)
    """
    return fbm(x, y, octaves=octaves, lacunarity=2.0, gain=0.5, seed=seed)


# ---- Simplex 噪声（Perlin 的改进：方向伪影更少、计算更快）----
def _perm_table(seed):
    """由 seed 生成长度 512 的排列表（0..255 洗牌后复制）。"""
    rng = np.random.RandomState(seed)
    p = np.arange(256, dtype=np.int64)
    rng.shuffle(p)
    return np.concatenate([p, p])


# 12 个二维梯度方向
_GRAD2 = np.array([
    [1, 1], [-1, 1], [1, -1], [-1, -1],
    [1, 0], [-1, 0], [1, 0], [-1, 0],
    [0, 1], [0, -1], [0, 1], [0, -1],
], dtype=np.float64)


def simplex_noise(x, y, seed: int = 0) -> np.ndarray:
    """2D Simplex 噪声（Stefan Gustavson 算法），返回 0..1。

    相比 perlin 方向伪影更少、计算更快。支持标量/同形数组输入。
    """
    x = np.asarray(x, dtype=np.float64)
    y = np.asarray(y, dtype=np.float64)
    perm = _perm_table(seed)
    F2 = 0.5 * (np.sqrt(3.0) - 1.0)
    G2 = (3.0 - np.sqrt(3.0)) / 6.0
    s = (x + y) * F2
    i = np.floor(x + s).astype(np.int64)
    j = np.floor(y + s).astype(np.int64)
    t = (i + j) * G2
    x0 = x - (i - t)
    y0 = y - (j - t)
    i1 = (x0 > y0).astype(np.int64)
    j1 = 1 - i1

    def _corner(ox, oy, oi, oj):
        cx = x0 - ox
        cy = y0 - oy
        t2 = 0.5 - cx * cx - cy * cy
        t2 = np.where(t2 > 0.0, t2, 0.0)
        gi = (i + oi) & 255
        gj = (j + oj) & 255
        idx = (perm[gi] + perm[gj]) & 255
        g = _GRAD2[idx % 12]
        grad = g[..., 0] * cx + g[..., 1] * cy
        return (t2 * t2) * (t2 * t2) * grad

    z = np.zeros_like(x0, dtype=np.float64)
    n0 = _corner(z, z, 0, 0)
    n1 = _corner(i1 - G2, j1 - G2, i1, j1)
    n2 = _corner(np.full_like(x0, 1.0 - 2.0 * G2),
                 np.full_like(y0, 1.0 - 2.0 * G2), 1, 1)
    n = 70.0 * (n0 + n1 + n2)
    return np.clip((n + 1.0) / 2.0, 0.0, 1.0)
