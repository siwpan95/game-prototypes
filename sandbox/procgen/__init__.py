"""procgen —— 程序化生成库。

供各游戏项目 import 复用：

    import procgen as pg
    hm = pg.generate_heightmap(64, 64, seed=1)
    d  = pg.generate_dungeon(48, 32, rooms=8, seed=2)
    names = pg.NameGenerator(style='fantasy').generate(10)
    drops = pg.LootTable([("金币",50,(1,10)),("传说剑",1,(1,1))]).roll(5)
"""
from __future__ import annotations

from .noise import (value_noise, perlin_noise, fractal_noise, fbm, simplex_noise)
from .dungeon import (generate_dungeon, generate_dungeon_bsp, generate_cave,
                      to_ascii)
from .town import generate_town
from .namegen import NameGenerator
from .loot import LootTable
from .terrain import (generate_heightmap, classify, generate_terrain,
                      generate_moisture, classify_biomes, generate_world,
                      WATER, SAND, GRASS, FOREST, MOUNTAIN, TERRAIN_NAMES,
                      BIOME_NAMES)

__all__ = [
    "value_noise", "perlin_noise", "fractal_noise", "fbm", "simplex_noise",
    "generate_dungeon", "generate_dungeon_bsp", "generate_cave", "to_ascii",
    "generate_town",
    "NameGenerator",
    "LootTable",
    "generate_heightmap", "classify", "generate_terrain",
    "generate_moisture", "classify_biomes", "generate_world",
    "WATER", "SAND", "GRASS", "FOREST", "MOUNTAIN", "TERRAIN_NAMES",
    "BIOME_NAMES",
]
