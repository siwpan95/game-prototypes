# -*- coding: utf-8 -*-
"""bloom / 网格观感调参探针（无窗口，dummy SDL）。

扫描若干种子找装饰物最密的出生区，渲染 bloom 关 / 开对比样张，
另存一张抬头看天花板的天花板网格检查图。调 GL_BLOOM_* 或网格 shader
后跑一遍即可肉眼对比。

    python tools/bloom_probe.py            # 默认扫 40 个种子

输出目录：build_test/gl_out/（已 gitignore）。
"""
import argparse
import os
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import numpy as np
import pygame

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)

import kaw.render.gl as glmod
from kaw.config import H, W, MAX_DEPTH, NUM_RAYS
from kaw.render.meshgen import region_cells
from kaw.world.worldmap import WorldMap
from kaw.render.gl import GLRenderer

OUT = os.path.join(_ROOT, "build_test", "gl_out")


def deco_count(world, cx, cy):
    """统计 (cx,cy) 3x3 区域内的装饰物格数"""
    cells, _, _ = region_cells(world, cx, cy, 1, 21)
    return int(((cells >= 2) & (cells <= 12)).sum())


def scan_seeds(n):
    best = None
    for seed in range(1, n + 1):
        w = WorldMap(seed=seed * 7919)
        w.ensure_neighbors(0, 0)
        spawn = w.find_safe_spawn(0, 0)
        cx, cy = w.world_to_chunk(*spawn)
        cnt = deco_count(w, cx, cy)
        if best is None or cnt > best[1]:
            best = (seed, cnt, spawn)
    return best


def render(world, spawn, angle_deg, pitch_pix, name, strength=None):
    if strength is not None:
        glmod.GL_BLOOM_STRENGTH = strength      # 0=关  默认=开
    surf = pygame.Surface((W, H))
    canvas = pygame.Surface((W, H), pygame.SRCALPHA, 32)
    r = GLRenderer(surf, world, mode="offscreen")
    zbuf = [0.0] * NUM_RAYS
    px, py = spawn
    r.draw_world(px, py, np.radians(angle_deg), pitch_pix, zbuf, world, MAX_DEPTH)
    r.present(canvas)
    path = os.path.join(OUT, name)
    pygame.image.save(surf, path)
    print("  saved", name)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, default=40)
    args = ap.parse_args()

    os.makedirs(OUT, exist_ok=True)
    seed, cnt, spawn = scan_seeds(args.seeds)
    print(f"最密种子 seed={seed * 7919} 出生3x3装饰物={cnt} spawn={spawn}")
    world = WorldMap(seed=seed * 7919)
    world.ensure_neighbors(0, 0)
    world.ensure_neighbors(*world.world_to_chunk(*spawn))

    for ang in (0, 90, 200):
        render(world, spawn, ang, 0, f"bloom_off_a{ang}.png", 0.0)
        render(world, spawn, ang, 0, f"bloom_on_a{ang}.png", 0.75)
    render(world, spawn, 0, 200, "ceil_check.png")   # 抬头看天花板（网格/切面检查）
    print("完成:", OUT)


if __name__ == "__main__":
    main()
