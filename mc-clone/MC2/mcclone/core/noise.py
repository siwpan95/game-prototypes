"""
noise — 确定性 Perlin 梯度噪声（无硬依赖）。

提供：
  - PerlinNoise: 基于置换表的 2D 梯度噪声，支持 fbm 分形叠加。

确定性保证：所有随机性仅来自 random.Random(seed)，
禁止全局 random / 时间 / os.urandom，保证同 seed 同输出。
"""

from __future__ import annotations

import math
import random


def _fade(t: float) -> float:
    """Perlin 五次平滑插值因子：6t^5 - 15t^4 + 10t^3。"""
    return t * t * t * (t * (t * 6 - 15) + 10)


def _grad(hash_val: int, x: float, y: float) -> float:
    """根据哈希低 3 位选择 8 个梯度方向之一，与偏移量做点乘。"""
    grad_map = [
        (1, 1), (1, -1), (-1, 1), (-1, -1),
        (1, 0), (-1, 0), (0, 1), (0, -1),
    ]
    gx, gy = grad_map[hash_val & 7]
    return gx * x + gy * y


class PerlinNoise:
    """确定性 2D Perlin 梯度噪声。

    构造时用 random.Random(seed) 构建置换表并复制成长度 2*perm_size。
    noise() 返回约 [-1, 1]；fbm() 叠加多个 octave，归一化后也约 [-1, 1]。
    """

    def __init__(self, seed: int = 0, perm_size: int = 256) -> None:
        """初始化置换表。

        参数：
            seed: 随机种子（决定地形形态，确定性来源）
            perm_size: 置换表基础长度（默认 256，须为 2 的幂）
        """
        self.seed = seed
        self.perm_size = perm_size
        rng = random.Random(seed)
        base = list(range(perm_size))
        rng.shuffle(base)
        # 复制成 2 倍长度，避免取模越界（perm_size=256 时用 &255 索引）
        self.perm: list[int] = base + base

    def noise(self, x: float, y: float) -> float:
        """计算单点 2D Perlin 噪声，返回约 [-1, 1]。

        参数：
            x: 世界 x 坐标（浮点）
            y: 世界 y 坐标（浮点）

        返回：
            噪声值，约 [-1, 1]
        """
        perm = self.perm
        x0 = math.floor(x)
        y0 = math.floor(y)
        x1 = x0 + 1
        y1 = y0 + 1
        sx = _fade(x - x0)
        sy = _fade(y - y0)

        # 四个格点的梯度点乘
        n00 = _grad(perm[perm[x0 & 255] + (y0 & 255)], x - x0, y - y0)
        n10 = _grad(perm[perm[x1 & 255] + (y0 & 255)], x - x1, y - y0)
        n01 = _grad(perm[perm[x0 & 255] + (y1 & 255)], x - x0, y - y1)
        n11 = _grad(perm[perm[x1 & 255] + (y1 & 255)], x - x1, y - y1)

        ix0 = n00 + (n10 - n00) * sx
        ix1 = n01 + (n11 - n01) * sx
        return ix0 + (ix1 - ix0) * sy

    def fbm(self, x: float, y: float, octaves: int = 4,
            lacunarity: float = 2.0, persistence: float = 0.5) -> float:
        """分形布朗运动（叠加多个倍频 octave）。

        参数：
            x, y: 基础采样坐标
            octaves: 叠加层数（默认 4）
            lacunarity: 每层频率倍增系数（默认 2.0）
            persistence: 每层振幅衰减系数（默认 0.5）

        返回：
            归一化叠加值，约 [-1, 1]
        """
        total = 0.0
        amplitude = 1.0
        frequency = 1.0
        max_value = 0.0
        for _ in range(octaves):
            total += self.noise(x * frequency, y * frequency) * amplitude
            max_value += amplitude
            amplitude *= persistence
            frequency *= lacunarity
        if max_value == 0.0:
            return 0.0
        return total / max_value
