# -*- coding: utf-8 -*-
"""fx_tiles — M6 程序化像素瓦片纹理工厂。

为 BlockWorld 的各 block_id 生成**带纹理**的 pygame.Surface（确定性、无外部素材依赖），
替代 tile_world_renderer 的纯色块。tile_world_renderer._tile_surface 优先调用本模块，
失败 / 无 pygame 时回退纯色块（地基零改动，旧测试签名不变）。

设计要点：
  - 确定性：同 block_id 同纹理（基于 tile 内像素坐标的 hash 噪声，与世界坐标无关）。
  - 可选 rng（random.Random(seed)）：用于整体色调微扰，支持未来「资源包」概念；不传则固定图案。
  - 延迟导入 pygame（_pygame），导入期无 pygame 依赖；headless 下 make 抛错由调用方兜底。
  - 与 tile_world_renderer._TILE_RGB 调色板保持一致，视觉无缝衔接。
"""
from __future__ import annotations

import random
from typing import Dict, Optional, Tuple

# 调色板（BlockDef.color 语义名 → RGB），与 tile_world_renderer._TILE_RGB 一致。
_TILE_RGB: Dict[str, Tuple[int, int, int]] = {
    "white": (240, 240, 240),
    "gray": (130, 130, 130),
    "brown": (134, 96, 67),
    "green": (80, 170, 70),
    "blue": (60, 120, 220),
    "yellow": (224, 200, 90),
    "black": (20, 20, 20),
    "red": (200, 60, 60),
    "magenta": (180, 80, 180),
    "cyan": (80, 200, 200),
    "lava": (220, 90, 30),
}


def _pygame():
    """延迟导入 pygame；不可用时抛出清晰错误。"""
    import pygame
    if pygame is None:
        raise RuntimeError("需要安装可选依赖 pygame 才能生成瓦片纹理")
    return pygame


def _shade(rgb: Tuple[int, int, int], factor: float) -> Tuple[int, int, int]:
    """按比例调亮/调暗颜色（钳制到 [0,255]）。"""
    return (min(255, int(rgb[0] * factor)),
            min(255, int(rgb[1] * factor)),
            min(255, int(rgb[2] * factor)))


def _hash_noise(x: int, y: int, seed: int = 0) -> float:
    """基于像素坐标的确定性伪随机，返回 [0,1)。

    不依赖世界坐标，保证同 block_id 同纹理（资源包 seed 仅微调色调）。
    """
    h = (x * 374761393 + y * 668265263 + seed * 2147483647) & 0xFFFFFFFF
    h = (h ^ (h >> 13)) * 1274126177 & 0xFFFFFFFF
    return ((h ^ (h >> 16)) & 0xFFFF) / 0xFFFF


class TileTextureFactory:
    """确定性像素瓦片纹理工厂（按 (block_id, seed) 缓存）。"""

    _CACHE: Dict[Tuple[int, Optional[int]], object] = {}

    @classmethod
    def make(cls, block_id: int, registry, tile_size: int = 32,
             rng: Optional[random.Random] = None):
        """返回 block_id 对应的纹理 Surface；失败（无 pygame）抛 RuntimeError。"""
        seed = rng.randint(0, 2 ** 31 - 1) if rng is not None else 0
        key = (block_id, seed)
        if key in cls._CACHE:
            return cls._CACHE[key]

        pg = _pygame()
        try:
            block = registry.get(block_id) if registry is not None else None
        except (KeyError, IndexError):
            block = None
        color_name = block.color if block is not None else "white"
        rgb = _TILE_RGB.get(color_name, _TILE_RGB["white"])
        ts = tile_size
        surf = pg.Surface((ts, ts))
        name = block.name if block is not None else ""

        # 分派纹理（未知方块 → 纯色块）
        if name == "grass":
            cls._grass(surf, ts, rgb, seed)
        elif name == "stone" or name == "stone_brick":
            cls._stone(surf, ts, rgb, seed, brick=(name == "stone_brick"))
        elif name == "dirt":
            cls._dirt(surf, ts, rgb, seed)
        elif name == "sand":
            cls._sand(surf, ts, rgb, seed)
        elif name == "water":
            cls._water(surf, ts, rgb, seed)
        elif name == "lava":
            cls._lava(surf, ts, rgb, seed)
        elif name == "glass":
            cls._glass(surf, ts, rgb)
        else:
            cls._flat(surf, ts, rgb)

        # 透明方块（water/glass）整体半透明
        if block is not None and block.transparent:
            surf.set_alpha(170)

        cls._CACHE[key] = surf
        return surf

    # ── 纹理绘制（均基于 tile 内像素坐标，确定性）──
    @staticmethod
    def _flat(surf, ts: int, rgb) -> None:
        pg = _pygame()
        surf.fill(rgb)
        lighter = _shade(rgb, 1.25)
        darker = _shade(rgb, 0.7)
        pg.draw.rect(surf, lighter, (0, 0, ts, 1))
        pg.draw.rect(surf, lighter, (0, 0, 1, ts))
        pg.draw.rect(surf, darker, (0, ts - 1, ts, 1))
        pg.draw.rect(surf, darker, (ts - 1, 0, 1, ts))

    @staticmethod
    def _grass(surf, ts: int, rgb, seed: int) -> None:
        pg = _pygame()
        dirt = _TILE_RGB["brown"]
        surf.fill(dirt)
        grass_h = max(5, ts // 3)
        surf.fill(rgb, (0, 0, ts, grass_h))          # 草层
        # 草尖下垂
        for x in range(0, ts, 2):
            n = _hash_noise(x, 7, seed)
            if n > 0.45:
                dy = int(n * 4)
                surf.set_at((x, grass_h + dy), _shade(rgb, 1.12))
        # 泥土颗粒
        for i in range(ts * ts // 10):
            x = int(_hash_noise(i, 11, seed) * ts)
            y = int(_hash_noise(i, 23, seed) * ts)
            if y > grass_h:
                surf.set_at((x, y),
                            _shade(dirt, 0.82 if _hash_noise(i, 31, seed) > 0.5
                                   else 1.12))

    @staticmethod
    def _stone(surf, ts: int, rgb, seed: int, brick: bool = False) -> None:
        pg = _pygame()
        surf.fill(rgb)
        # 噪点
        for i in range(ts * ts // 6):
            x = int(_hash_noise(i, 41, seed) * ts)
            y = int(_hash_noise(i, 53, seed) * ts)
            surf.set_at((x, y),
                        _shade(rgb, 0.8 if _hash_noise(i, 61, seed) > 0.5
                               else 1.18))
        if brick:
            # 砖纹：横线 + 错列竖线
            line = _shade(rgb, 0.65)
            bh = max(4, ts // 4)
            for y in range(0, ts, bh):
                pg.draw.rect(surf, line, (0, y, ts, 1))
                off = (y // bh) % 2 * (ts // 2)
                for x in range(off, ts, ts // 2):
                    pg.draw.rect(surf, line, (x, y, 1, bh))

    @staticmethod
    def _dirt(surf, ts: int, rgb, seed: int) -> None:
        pg = _pygame()
        surf.fill(rgb)
        for i in range(ts * ts // 8):
            x = int(_hash_noise(i, 71, seed) * ts)
            y = int(_hash_noise(i, 83, seed) * ts)
            surf.set_at((x, y),
                        _shade(rgb, 0.85 if _hash_noise(i, 91, seed) > 0.5
                               else 1.1))

    @staticmethod
    def _sand(surf, ts: int, rgb, seed: int) -> None:
        pg = _pygame()
        surf.fill(rgb)
        for i in range(ts * ts // 5):
            x = int(_hash_noise(i, 101, seed) * ts)
            y = int(_hash_noise(i, 113, seed) * ts)
            surf.set_at((x, y),
                        _shade(rgb, 0.92 if _hash_noise(i, 121, seed) > 0.5
                               else 1.08))

    @staticmethod
    def _water(surf, ts: int, rgb, seed: int) -> None:
        pg = _pygame()
        surf.fill(rgb)
        # 波纹（横向浅亮线）
        light = _shade(rgb, 1.25)
        for y in range(3, ts, 6):
            off = int(_hash_noise(0, y, seed) * 4)
            for x in range(off, ts, 8):
                surf.set_at((x, y), light)
                if x + 2 < ts:
                    surf.set_at((x + 1, y), light)

    @staticmethod
    def _lava(surf, ts: int, rgb, seed: int) -> None:
        pg = _pygame()
        surf.fill(rgb)
        bright = (255, 200, 90)
        for i in range(ts * ts // 7):
            x = int(_hash_noise(i, 131, seed) * ts)
            y = int(_hash_noise(i, 143, seed) * ts)
            if _hash_noise(i, 151, seed) > 0.6:
                surf.set_at((x, y), bright)

    @staticmethod
    def _glass(surf, ts: int, rgb) -> None:
        pg = _pygame()
        surf.fill(_shade(rgb, 1.4))
        # 高光边框 + 斜向反光
        edge = (220, 240, 245)
        pg.draw.rect(surf, edge, (0, 0, ts, 1))
        pg.draw.rect(surf, edge, (0, 0, 1, ts))
        pg.draw.rect(surf, _shade(rgb, 0.7), (0, ts - 1, ts, 1))
        pg.draw.rect(surf, _shade(rgb, 0.7), (ts - 1, 0, 1, ts))
        for i in range(2, ts - 1):
            surf.set_at((i, i), edge)
