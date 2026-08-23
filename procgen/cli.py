"""procgen 演示入口（命令行）。

用法：
    python cli.py terrain  --size 64 --seed 1 --out terrain.png
    python cli.py dungeon --w 48 --h 32 --rooms 8 --seed 2
    python cli.py name    --style fantasy --n 10
    python cli.py loot    --n 5
    python cli.py noise   --size 64 --seed 1 --out noise.png
"""
from __future__ import annotations

import argparse
import os
import sys

import numpy as np

# 允许从包内直接运行：确保 procgen 包可导入
# 说明：在 G:\game 中 procgen 被扁平化，本文件位于 G:\game\procgen\cli.py，
# 因此需把「包的上一级目录」(G:\game) 加入 sys.path，import procgen 才能命中
# G:\game\procgen 这个包；若直接放在 G:\tools\procgen\cli.py（包外）则应去掉一层 dirname。
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import procgen as pg
from procgen.dungeon import to_ascii


def _save_png(arr, path):
    from PIL import Image
    a = np.clip(arr, 0, 1)
    Image.fromarray((a * 255).astype(np.uint8), mode="L").save(path)
    print(f"已保存 {path}")


def cmd_terrain(a):
    t = pg.generate_terrain(a.size, a.size, seed=a.seed)
    print("地形类别分布:", {pg.TERRAIN_NAMES[k]: int((t['classes'] == k).sum())
                            for k in range(5)})
    if a.out:
        _save_png(t["heightmap"], a.out)


def cmd_dungeon(a):
    d = pg.generate_dungeon(a.w, a.h, rooms=a.rooms, seed=a.seed)
    print(f"房间数: {len(d['rooms'])}  连接数: {len(d['connections'])}")
    print(to_ascii(d["grid"]))


def cmd_name(a):
    names = pg.NameGenerator(style=a.style, seed=a.seed).generate(a.n)
    print("\n".join(names))


def cmd_loot(a):
    table = pg.LootTable([
        ("金币", 50, (1, 10)),
        ("药水", 10, (1, 3)),
        ("宝石", 5, (1, 2)),
        ("传说剑", 1, (1, 1)),
    ], seed=a.seed)
    print("\n".join(table.roll(a.n)))


def cmd_noise(a):
    xs, ys = np.meshgrid(np.arange(a.size), np.arange(a.size))
    arr = pg.fractal_noise(xs, ys, octaves=5, seed=a.seed)
    if a.out:
        _save_png(arr, a.out)
    else:
        print(arr)


def main():
    p = argparse.ArgumentParser(description="procgen 程序化生成演示")
    sub = p.add_subparsers(dest="cmd", required=True)

    pt = sub.add_parser("terrain"); pt.add_argument("--size", type=int, default=64)
    pt.add_argument("--seed", type=int, default=0); pt.add_argument("--out", default="")
    pt.set_defaults(func=cmd_terrain)

    pd = sub.add_parser("dungeon"); pd.add_argument("--w", type=int, default=48)
    pd.add_argument("--h", type=int, default=32); pd.add_argument("--rooms", type=int, default=8)
    pd.add_argument("--seed", type=int, default=0); pd.set_defaults(func=cmd_dungeon)

    pn = sub.add_parser("name"); pn.add_argument("--style", default="fantasy")
    pn.add_argument("--n", type=int, default=10); pn.add_argument("--seed", type=int, default=0)
    pn.set_defaults(func=cmd_name)

    pl = sub.add_parser("loot"); pl.add_argument("--n", type=int, default=5)
    pl.add_argument("--seed", type=int, default=0); pl.set_defaults(func=cmd_loot)

    pz = sub.add_parser("noise"); pz.add_argument("--size", type=int, default=64)
    pz.add_argument("--seed", type=int, default=0); pz.add_argument("--out", default="")
    pz.set_defaults(func=cmd_noise)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
