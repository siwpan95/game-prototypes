# -*- coding: utf-8 -*-
"""程序化生成的纹理：地砖 / 天花板块 / 12 种装饰物精灵。

全部用 numpy 现算，不依赖任何美术资源 —— 打包时不用带素材文件。
纹理按 [x, y] 索引（与 pygame.surfarray 的内存布局一致）。
"""
import numpy as np
import pygame

TILE_FLOOR = "floor"
TILE_CEIL = "ceil"


def _uv(n):
    """返回 (X, Y)，形状均为 (n, n)，按 [x, y] 索引。"""
    t = (np.arange(n, dtype=np.float32) + 0.5) / n
    return np.meshgrid(t, t, indexing="ij")


def make_tile_texture(n=64, base=(18, 35, 50), shade=(8, 18, 35),
                      grid=(15, 45, 90), grid_strength=0.85,
                      line_w=0.035, panel=False, seed=7):
    """一格地砖 / 天花板块。边缘发光线 + 细噪点，暗色赛博风。"""
    rng = np.random.default_rng(seed)
    X, Y = _uv(n)

    base = np.asarray(base, np.float32)
    shade = np.asarray(shade, np.float32)
    grid = np.asarray(grid, np.float32)

    img = base[None, None, :] + (shade - base)[None, None, :] * Y[..., None]

    # 细噪点（避免大面积死板纯色）
    noise = rng.random((n, n), dtype=np.float32)
    img *= (0.955 + 0.045 * noise)[..., None]

    # 格边发光线
    edge = np.minimum(np.minimum(X, 1.0 - X), np.minimum(Y, 1.0 - Y))
    line = np.exp(-edge / line_w)
    img += grid[None, None, :] * (line * grid_strength)[..., None]

    # 中心面板：一圈内嵌矩形，让顶面不空
    if panel:
        inner = np.minimum(np.minimum(np.abs(X - 0.5), np.abs(Y - 0.5)), 0.5)
        ring = np.exp(-np.abs(inner - 0.30) / 0.02)
        img += grid[None, None, :] * (ring * 0.08)[..., None]

    return np.clip(img, 0, 255).astype(np.uint8)


def build_mip_chain(tex, count=3):
    """box 降采样出 mip 链：64 → 32 → 16 …

    远处地面每行横跨的世界长度可达近处百倍，只按原尺寸采样会出现
    严重的摩尔纹（整行拉成横条）。按行距选 mip 是标准解法。
    """
    out = [tex]
    cur = tex
    for _ in range(count - 1):
        n = cur.shape[0]
        if n < 2:
            break
        cur = (cur.reshape(n // 2, 2, n // 2, 2, 3)
                  .mean(axis=(1, 3)).round().astype(np.uint8))
        out.append(cur)
    return out


def _sdf_circle(X, Y, cx, cy, r):
    return np.sqrt((X - cx) ** 2 + (Y - cy) ** 2) - r


def _soft(a, softness=1.6):
    """把一个有符号距离场转成 0..1 的软边覆盖度。"""
    return np.clip(0.5 - a * softness * 8.0, 0.0, 1.0)


def make_sprite(kind, color, n=64, seed=0):
    """生成一张 (n, n, 4) 的 RGBA 精灵图，底边贴地。"""
    rng = np.random.default_rng(seed)
    X, Y = _uv(n)
    col = np.asarray(color, np.float32)
    bright = np.clip(col * 1.45 + 40.0, 0, 255)

    alpha = np.zeros((n, n), np.float32)
    rgb = np.zeros((n, n, 3), np.float32)

    if kind == "pillar":
        d = np.maximum(np.abs(X - 0.5) - 0.16, np.abs(Y - 0.5) - 0.46)
        cover = _soft(d, 1.2)
        glow = np.exp(-np.maximum(d, 0.0) / 0.20)
        alpha = np.clip(cover + glow * 0.55, 0, 1)
        rgb = col[None, None, :] * (0.55 + 0.45 * (1.0 - Y))[..., None]
        rgb += bright[None, None, :] * (glow * 0.35)[..., None]

    elif kind == "orb":
        d = _sdf_circle(X, Y, 0.5, 0.62, 0.26)
        cover = _soft(d, 1.4)
        glow = np.exp(-np.maximum(d, 0.0) / 0.16)
        alpha = np.clip(cover + glow * 0.45, 0, 1)
        hi = np.exp(-_sdf_circle(X, Y, 0.42, 0.52, 0.10) / 0.08)
        rgb = col[None, None, :] * (0.5 + 0.5 * (1.0 - Y))[..., None]
        rgb += bright[None, None, :] * (glow * 0.3 + hi * 0.5)[..., None]

    elif kind == "crystal":
        d = np.abs(X - 0.5) / 0.30 + np.abs(Y - 0.55) / 0.42 - 1.0
        cover = _soft(d, 1.1)
        glow = np.exp(-np.maximum(d, 0.0) / 0.22)
        alpha = np.clip(cover + glow * 0.4, 0, 1)
        facet = np.where(X < 0.5, 0.62, 1.0)
        rgb = col[None, None, :] * facet[..., None] * (0.6 + 0.4 * (1.0 - Y))[..., None]
        rgb += bright[None, None, :] * (glow * 0.32)[..., None]

    elif kind == "debris":
        for _ in range(7):
            cx, cy = rng.uniform(0.32, 0.68), rng.uniform(0.62, 0.90)
            r = rng.uniform(0.07, 0.15)
            d = _sdf_circle(X, Y, cx, cy, r)
            alpha = np.maximum(alpha, _soft(d, 1.3))
        rgb = col[None, None, :] * (0.55 + 0.45 * (1.0 - Y))[..., None]

    elif kind == "portal":
        r = np.sqrt((X - 0.5) ** 2 + (Y - 0.5) ** 2)
        ring = np.exp(-np.abs(r - 0.36) / 0.055)
        core = np.exp(-r / 0.20)
        alpha = np.clip(ring * 1.1 + core * 0.85, 0, 1)
        ang = np.arctan2(Y - 0.5, X - 0.5)
        swirl = 0.5 + 0.5 * np.sin(ang * 3.0 + r * 22.0)
        rgb = col[None, None, :] * (0.35 + 0.65 * swirl)[..., None]
        rgb += bright[None, None, :] * (ring * 0.5 + core * 0.35)[..., None]

    elif kind == "bush":
        for _ in range(5):
            cx, cy = rng.uniform(0.30, 0.70), rng.uniform(0.55, 0.85)
            r = rng.uniform(0.12, 0.20)
            d = _sdf_circle(X, Y, cx, cy, r)
            alpha = np.maximum(alpha, _soft(d, 1.2))
        rgb = col[None, None, :] * (0.45 + 0.55 * (1.0 - Y))[..., None]

    elif kind == "sign":
        d = np.maximum(np.abs(X - 0.5) * 1.9 + (Y - 0.35) - 0.42,
                       np.abs(X - 0.5) - 0.34)
        cover = _soft(d, 1.2)
        stem = _soft(np.maximum(np.abs(X - 0.5) - 0.05, np.abs(Y - 0.82) - 0.16), 1.3)
        alpha = np.clip(cover + stem, 0, 1)
        glow = np.exp(-np.maximum(d, 0.0) / 0.18)
        rgb = col[None, None, :] * (0.6 + 0.4 * (1.0 - Y))[..., None]
        rgb += bright[None, None, :] * (glow * 0.4)[..., None]

    else:  # 兜底：方块
        d = np.maximum(np.abs(X - 0.5) - 0.28, np.abs(Y - 0.5) - 0.40)
        alpha = _soft(d, 1.2)
        rgb = col[None, None, :] * (0.6 + 0.4 * (1.0 - Y))[..., None]

    out = np.empty((n, n, 4), np.uint8)
    out[..., :3] = np.clip(rgb, 0, 255).astype(np.uint8)
    out[..., 3] = np.clip(alpha * 255.0, 0, 255).astype(np.uint8)
    return out


# ── 装饰物类型 → (形状, 颜色, 世界宽, 世界高) ──
# 宽高以「世界单位」计：1.0 = 一个格子宽 / 一面墙高
SPRITE_SPECS = {
    2:  ("pillar", (0, 255, 200), 0.42, 1.00),   # AETHER GLOW  发光柱
    3:  ("sign",   (220, 60, 60), 0.60, 0.80),   # RED ALERT    警示牌
    4:  ("orb",    (230, 200, 100), 0.55, 0.55),  # TREASURY     宝珠
    5:  ("bush",   (60, 200, 100), 0.80, 0.55),  # VERDANT      植被
    6:  ("orb",    (180, 80, 240), 0.60, 0.60),  # ENERGY CORE  能量核
    7:  ("orb",    (255, 150, 60), 0.50, 0.50),  # FIRE EXIT    火光
    8:  ("debris", (140, 140, 150), 0.85, 0.35),  # RUINS        碎石
    9:  ("pillar", (80, 220, 255), 0.34, 0.90),  # TECH NOOK    科技柱
    10: ("crystal", (100, 180, 255), 0.55, 0.95),  # CRYSTAL CAVE 蓝水晶
    11: ("crystal", (160, 80, 220), 0.55, 0.95),  # MYSTIC ALTAR 紫水晶
    12: ("portal", (255, 255, 100), 1.00, 1.00),  # PORTAL GATE  传送门
}


def build_sprite_surfaces(n=64):
    """返回 {deco_type: (pygame.Surface, world_w, world_h)}"""
    out = {}
    for t, (kind, col, ww, wh) in SPRITE_SPECS.items():
        arr = make_sprite(kind, col, n=n, seed=t)
        # 32 位面不能用 surfarray.blit_array，走 frombuffer + convert_alpha
        surf = pygame.image.frombuffer(arr.tobytes(), (n, n), "RGBA").convert_alpha()
        out[t] = (surf, ww, wh)
    return out
