"""procgen 冒烟测试：import procgen 并断言各生成函数返回形状/类型正确。

运行：
    cd <仓库根>/procgen
    python test_smoke.py
"""

import os
import sys

# G:\game 中 procgen 被扁平化，本文件位于 G:\game\procgen\test_smoke.py，
# 需把「包的上一级目录」(G:\game) 加入 sys.path 才能 import procgen。
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import procgen
from procgen import (
    value_noise, perlin_noise, fractal_noise,
    generate_dungeon, NameGenerator, LootTable,
    generate_heightmap, classify,
)


def check(cond, msg):
    if not cond:
        raise AssertionError("FAIL: " + msg)
    print("OK  : " + msg)


# --- noise ---
xs = np.linspace(0, 10, 32)
ys = np.linspace(0, 10, 24)
X, Y = np.meshgrid(xs, ys)
vn = value_noise(X, Y, seed=1)
check(vn.shape == (24, 32), "value_noise 返回同形数组 (24,32)")
check(vn.dtype.kind == "f" and vn.min() >= 0 and vn.max() <= 1, "value_noise 浮点且范围 0..1")

pn = perlin_noise(X, Y, seed=2)
check(pn.shape == (24, 32), "perlin_noise 返回同形数组 (24,32)")
check(pn.dtype.kind == "f" and 0 <= float(pn.min()) and float(pn.max()) <= 1, "perlin_noise 浮点且范围 0..1")

fn = fractal_noise(X, Y, octaves=4, seed=3)
check(fn.shape == (24, 32), "fractal_noise 返回同形数组 (24,32)")
check(0 <= float(fn.min()) and float(fn.max()) <= 1, "fractal_noise 范围 0..1")

# 标量输入
sv = value_noise(1.5, 2.5, seed=1)
check(np.isscalar(sv) or sv.shape == (), "value_noise 标量输入返回标量")

# --- dungeon ---
d = generate_dungeon(width=50, height=30, rooms=10, seed=3)
check(d["grid"].shape == (30, 50), "dungeon grid 形状 (30,50)")
check(set(np.unique(d["grid"]).tolist()) <= {0, 1}, "dungeon grid 仅含 0/1")
check(len(d["rooms"]) >= 1, "dungeon 至少 1 个房间")
check(isinstance(d["connections"], list), "dungeon connections 为列表")

# --- namegen ---
ng = NameGenerator(syllables=2, style="fantasy")
names = ng.generate(12)
check(len(names) == 12, "namegen 返回 12 个名称")
check(all(isinstance(n, str) and n.istitle() for n in names), "namegen 返回字符串且首字母大写")
ng2 = NameGenerator(style="sci")
check(len(ng2.generate(5)) == 5, "namegen(sci) 返回 5 个名称")

# --- loot ---
lt = LootTable([("金币", 50, (1, 20)), ("宝石", 5, (1, 2)), ("剑", 1, (1, 1))])
drops = lt.roll(20)
check(isinstance(drops, list) and len(drops) >= 20, "loot roll 返回列表且数量>=20")
check(all(isinstance(x, str) for x in drops), "loot 元素均为字符串")

# --- terrain ---
hm = generate_heightmap(w=96, h=64, seed=7, scale=8.0)
check(hm.shape == (64, 96), "heightmap 形状 (64,96)")
check(hm.dtype == np.float32, "heightmap 为 float32")
check(0 <= float(hm.min()) and float(hm.max()) <= 1, "heightmap 范围 0..1")

cls = classify(hm)
check(cls.shape == hm.shape, "classify 与 heightmap 同形")
check(set(np.unique(cls).tolist()) <= {0, 1, 2, 3}, "classify 类别在 0..3")

print("\n全部冒烟测试通过 [OK]")
