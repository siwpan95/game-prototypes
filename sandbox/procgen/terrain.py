"""地形生成：用分形噪声生成高度图，并按阈值分类为地形类别。"""
from __future__ import annotations

import numpy as np

from .noise import fractal_noise

# 地形类别编码
WATER, SAND, GRASS, FOREST, MOUNTAIN = 0, 1, 2, 3, 4
TERRAIN_NAMES = {WATER: "水", SAND: "沙", GRASS: "草", FOREST: "林", MOUNTAIN: "山"}


def generate_heightmap(w: int = 64, h: int = 64, seed: int = 0,
                        scale: float = 0.08, octaves: int = 5,
                        falloff: float = 0.0) -> np.ndarray:
    """生成 w x h 高度图（0..1，float32），由分形噪声采样。

    falloff > 0 时叠加径向衰减，使地图边缘更低，形成岛屿形状（典型 0.2~0.5）。
    """
    xs, ys = np.meshgrid(np.arange(w), np.arange(h))
    hm = fractal_noise(xs * scale, ys * scale, octaves=octaves, seed=seed)
    if falloff:
        cx, cy = (w - 1) / 2.0, (h - 1) / 2.0
        d = np.sqrt((xs - cx) ** 2 + (ys - cy) ** 2) / (max(w, h) / 2.0)
        hm = hm * (1.0 - falloff * np.clip(d, 0.0, 1.0))
    return hm.astype(np.float32)


def classify(hm: np.ndarray) -> np.ndarray:
    """高度图 -> 地形类别编码数组（同形）。"""
    cls = np.zeros_like(hm, dtype=np.int8)
    cls[hm >= 0.75] = MOUNTAIN
    cls[(hm >= 0.55) & (hm < 0.75)] = FOREST
    cls[(hm >= 0.35) & (hm < 0.55)] = GRASS
    cls[(hm >= 0.30) & (hm < 0.35)] = SAND
    cls[hm < 0.30] = WATER
    return cls


def generate_terrain(w: int = 64, h: int = 64, seed: int = 0,
                     scale: float = 0.08, octaves: int = 5) -> dict:
    """一步生成高度图 + 地形分类。"""
    hm = generate_heightmap(w, h, seed, scale, octaves)
    return {"heightmap": hm, "classes": classify(hm)}


# ---- 生物群系（基于 高度 + 湿度 的 Whittaker 式分类）----
WATER, BEACH, GRASS, FOREST, DESERT, TUNDRA, MOUNTAIN, SNOW = range(8)
BIOME_NAMES = {
    WATER: "水", BEACH: "滩", GRASS: "草", FOREST: "林",
    DESERT: "漠", TUNDRA: "苔", MOUNTAIN: "山", SNOW: "雪",
}


def generate_moisture(w: int = 64, h: int = 64, seed: int = 0,
                      scale: float = 0.12, octaves: int = 4) -> np.ndarray:
    """生成 0..1 的湿度图（float32），用于生物群系分类。"""
    xs, ys = np.meshgrid(np.arange(w), np.arange(h))
    return fractal_noise(xs * scale, ys * scale, octaves=octaves,
                         seed=seed + 99991).astype(np.float32)


def classify_biomes(hm: np.ndarray, moisture: np.ndarray,
                    temperature: np.ndarray = None) -> np.ndarray:
    """由高度、湿度（可选温度）分类生物群系，返回同形 int8 编码。

    temperature 缺省时取 1 - 高度（海拔越低越热）。

    海拔带划分（自下而上）：
        水 <0.28 | 滩 0.28~0.32 | 低地 0.32~0.55（按湿度分 漠/草/林）
        | 山地 0.55~0.75 | 苔原 0.75~0.85 | 雪 >=0.85
    苔原/雪线由“海拔”决定，temperature 仅用于微调雪线（足够高且足够冷才积雪）。
    """
    hm = np.asarray(hm, dtype=np.float64)
    moisture = np.asarray(moisture, dtype=np.float64)
    if temperature is None:
        temperature = 1.0 - hm
    else:
        temperature = np.asarray(temperature, dtype=np.float64)
    cls = np.zeros(hm.shape, dtype=np.int8)
    cls[hm < 0.28] = WATER
    cls[(hm >= 0.28) & (hm < 0.32)] = BEACH
    land = (hm >= 0.32)
    # 低地：按湿度划分温带植被
    low = land & (hm < 0.55)
    cls[low & (moisture < 0.30)] = DESERT
    cls[low & (moisture >= 0.30) & (moisture < 0.60)] = GRASS
    cls[low & (moisture >= 0.60)] = FOREST
    # 中高海拔：山地 -> 苔原 -> 雪，温度仅决定最高带的雪线
    cls[land & (hm >= 0.55) & (hm < 0.75)] = MOUNTAIN
    cls[land & (hm >= 0.75) & (hm < 0.85)] = TUNDRA
    high = (hm >= 0.85)
    cls[high & (temperature < 0.40)] = SNOW          # 高且冷 -> 雪
    cls[high & (temperature >= 0.40)] = TUNDRA        # 高但偏暖 -> 仍按苔原
    return cls


def generate_world(w: int = 64, h: int = 64, seed: int = 0,
                   scale: float = 0.08, octaves: int = 5,
                   falloff: float = 0.0) -> dict:
    """一步生成完整世界：高度图 + 湿度图 + 温度图 + 生物群系。"""
    hm = generate_heightmap(w, h, seed, scale, octaves, falloff=falloff)
    moist = generate_moisture(w, h, seed, scale=scale * 1.5, octaves=max(2, octaves - 1))
    temp = (1.0 - hm.astype(np.float64)).astype(np.float32)
    biomes = classify_biomes(hm, moist, temp)
    return {"heightmap": hm, "moisture": moist,
            "temperature": temp, "biomes": biomes}
