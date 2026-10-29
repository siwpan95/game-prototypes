# -*- coding: utf-8 -*-
"""洞穴生成：3D 噪声挖 cheese 空腔 + 确定性 worm 隧道打通地表（纯逻辑，零 GL）。

## 为什么不是"逐格 3D fBm"（实测数据）

预算：默认世界 256×256×64，海平面 30。**地下候选带实测 1.83M 格**
（平均 28 格/列，约束是"表土下 3 格""水面下""陆地列"）。

* 逐格一次三线性插值的 3D 值噪声 = 8 次哈希 ⇒ 1.83M × 8 × 0.11µs ≈ **1.6s**；
  再乘 fBm 的 2~3 个八度就是 3~5s —— 而 `generate()` 现在只要 **4.82s**，
  等于翻倍。
* 所以走**粗格场 + 逐格细噪声**：
  - 粗格（8×4×8）值噪声**一次性预计算**成扁平 `array('f')`（16K 格 ≈ 0.02s），
    逐格只做插值算术（不碰哈希）；
  - 每格额外 1 次细哈希（0.11µs）做块状细节。

  实测总开销 **≈ +0.8s**（+16%），换取生成耗时仍在 5~6s 量级。

粗格偏低频 ⇒ 洞穴是"大空腔 + 块状边界"，这与方块世界的气质一致
（MC 的洞穴本来也是块状的，不是光滑的溶洞）。

## worm 隧道为什么单独一套

"允许自然洞口"不能靠噪声碰运气 —— 噪声挖穿地表是随机的，玩家找不到入口。
worm 是**从地下向上游走的管状隧道**：起点按 `(seed, 粗格)` 确定性选出，
必有洞口，且洞口位置可复现（回放/测试都对得上）。

隧道**不逐格查询**：一次算完，按**区块分组**存进 `TunnelIndex`
（`_generate_chunk` 只查自己那一份 ⇒ O(1)），因此与"惰性分块生成"自洽
—— `ensure_chunk` 单块生成的结果与全量 `generate()` 一致（单测钉这条）。

## 三条护栏（写在判据里，不靠调用顺序）

1. **基岩不动**（`y == 0`）；
2. **表土保底 3 格**（`y >= 地表 - 3` 不挖）⇒ 洞顶有岩层，不会"一挖就塌到天"；
3. **水下地形整个列不挖**（`地表 <= 海平面 + 1`）⇒ **洞里不会有水**。
   本项目没有流体系统（Phase 2-C 之后才谈），否则水会"悬空"或灌满洞穴。

worm 是唯一的例外，也是**唯一允许打穿表土的东西** —— 它就是"自然洞口"的实现。
但它只挖穿**最后 1~2 格表土**（不是竖井）：玩家从地表走下去是**水平走进洞穴**，
不会掉进一口几十格深的井里（那会触发摔落伤害，`Phase 1` 已实现）。
"""
from __future__ import annotations

import array
import math
from functools import lru_cache

from .world import _hash01

__all__ = ['CaveField', 'cave_field', 'density', 'is_cave', 'cave_threshold',
           'TunnelIndex', 'tunnels', 'COARSE', 'CAVE_THRESHOLD', 'SOIL_KEEP',
           'WORM_CELL', 'WORM_STEPS', 'WORM_RADIUS', 'WORMS_PER_CELL',
           'W_COARSE', 'W_MID', 'W_FINE']

#: 粗格尺度 `(x, y, z)`。x/z 大、y 小 ⇒ 洞穴在竖直方向更碎（横向连片、纵向分层）
COARSE = (8, 4, 8)

#: 挖空阈值（浅层基准）。探针实测：64 高世界候选带里挖空 **10.02%**。
#: 初版按"均匀分布"猜 0.585，实测挖了 **49.7%** —— 值噪声分布不是均匀的，
#: 猜测不成立，阈值必须实测标定（现分布：中位 0.5023、标准差 0.186）。
CAVE_THRESHOLD = 0.75

#: 深度增益：越深阈值越低 ⇒ **越深洞穴越密**（浅层零星、深层成腔）。
#: ⚠ 方向别搞反：`y` 越小越深，所以要减 `(1 - y/sea)` 而不是 `(sea - y)/sea`
#:   —— 初版写成加，于是**深处阈值 0.679 > 浅处 0.660**，实际成了"越浅越密"
#:   （单测 `t_threshold_deeper_denser` 抓到的）。
DEPTH_GAIN = 0.03

#: 表土保底层数：`y >= 地表 - SOIL_KEEP` 不挖（洞顶岩层厚度）
SOIL_KEEP = 3

#: worm 起点间距（格）：每 `WORM_CELL × WORM_CELL` 的水平粗格最多一条隧道
WORM_CELL = 32
#: 每条 worm 走多少步（每步挖一个球）
WORM_STEPS = 74
#: worm 的球半径（格）：1.9 ⇒ 通道约 3 格宽 × 3 格高（玩家 0.6×1.8，绰绰有余）
WORM_RADIUS = 1.9
#: 每个粗格里**长出 worm 的概率**（太密就成"地下全是隧道"，太空则很少见洞口）
WORMS_PER_CELL = 0.70

#: 三级场的权重（和为 1）：粗格（大空腔）/ 块级（中频边界）/ 逐格（细节）
W_COARSE = 0.50
W_MID = 0.38
W_FINE = 0.12


class CaveField:
    """**预计算**的三级洞穴场：逐格查询是"3 次整除 + 2 次数组索引（多数时候到此为止）"。

    ## 为什么必须预计算 + 分级剪枝（实测数据，别再靠猜）

    cProfile（128×128×64）：`_hash01` 被调 **155 万次**、占 tottime **1.6s**，
    `is_cave` 单位成本 **2.65µs** ⇒ 全图 183 万格就是 **+4.85s**
    （生成耗时 4.82s → 8.10s，**+68%**）。两次错误猜测都记在这里：

    1. 先猜"是 `from . import caves` 每格导入的开销" ⇒ 改成预建 `CaveField` 实例，
       **一点没省**（8.11s → 8.10s）。教训：先 profile 再改。
    2. 真正的开销是**每格一次哈希 + 每次八点插值**。于是改成三级场
       （粗格 8×4×8 / 块级中频 / 逐格细噪）并做**块级剪枝**：
       若 `粗格×W_COARSE + 块级×W_MID + W_FINE` 都够不到阈值，
       则**整块 256 格直接跳过**，连细哈希都不算。

    三级场的另一个好处：洞穴形态分层（大空腔 + 中频腔室 + 逐格碎边），
    比单层噪声更像"洞穴"，比纯块状噪声更有细节。
    """

    __slots__ = ('seed', 'size', 'height', 'sea', '_f', '_m', '_gn', '_thr_lo')

    def __init__(self, seed: int, size: int, height: int, sea: int):
        self.seed = int(seed)
        self.size = int(size)
        self.height = int(height)
        self.sea = int(sea)
        cx, cy, cz = COARSE
        self._gn = ((size + cx - 1) // cx, (height + cy - 1) // cy,
                    (size + cz - 1) // cz)
        gx_n, gy_n, gz_n = self._gn
        n = gx_n * gy_n * gz_n
        coarse = array.array('f', bytes(4 * n))
        mid = array.array('f', bytes(4 * n))
        i = 0
        for iy in range(gy_n):
            for iz in range(gz_n):
                for ix in range(gx_n):
                    # ⚠ 这里存**纯节点值**：不插值、不把 `COARSE` 的尺度当权重。
                    #   曾写成 `c + (c1 - c) * 8` ⇒ 值域 ±316，阈值怎么调都没用
                    #   （探针实测 0.585 与 0.75 的挖空比例都是 49.5%）。
                    coarse[i] = _hash01(ix, iy, iz, seed ^ 0x0CA7E)
                    mid[i] = _hash01(ix, iy, iz, seed ^ 0xB10C)
                    i += 1
        self._f = coarse
        self._m = mid
        #: 剪枝用的**保守下界阈值**（全场最小 ⇒ 任何一块都不会被误剪）
        self._thr_lo = CAVE_THRESHOLD - DEPTH_GAIN

    # ------------------------------------------------------------ 查询
    def _idx(self, x: int, y: int, z: int) -> int:
        """粗格索引；**场外返回 -1**（调用方按"不挖"处理）。"""
        cx, cy, cz = COARSE
        gx, gy, gz = x // cx, y // cy, z // cz
        gx_n, gy_n, gz_n = self._gn
        if gx < 0 or gy < 0 or gz < 0 or gx >= gx_n or gy >= gy_n or gz >= gz_n:
            return -1
        return (gy * gz_n + gz) * gx_n + gx

    def density(self, x: int, y: int, z: int) -> float:
        """洞穴密度场 0..1（**不含护栏**；单测用它量化形态）。"""
        i = self._idx(x, y, z)
        if i < 0:
            return 0.0
        base = (W_COARSE * self._f[i] + W_MID * self._m[i])
        return base + W_FINE * _hash01(x, y, z, self.seed ^ 0xCA7E)

    def is_cave(self, x: int, y: int, z: int, surface: int) -> bool:
        """这一格是不是洞穴空腔（含全部护栏）。

        `surface` 是该列地表高度。护栏见模块 docstring §三。
        """
        if surface <= self.sea + 1:
            return False                                # 水下/岸边地形：洞里不能进水
        if y <= 1 or y >= surface - SOIL_KEEP:
            return False                                # 基岩上 / 表土保底
        if y > self.sea:
            return False                                # 海平面以上（海底地形上部）
        i = self._idx(x, y, z)
        if i < 0:
            return False
        # 块级剪枝：细噪声的最大贡献是 W_FINE，够不到阈值就**整块跳过**
        # （这一条把 70% 的块挡在"连哈希都不用算"之外 —— 见类 docstring 的实测）
        if (W_COARSE * self._f[i] + W_MID * self._m[i] + W_FINE) <= self._thr_lo:
            return False
        return self.density(x, y, z) > cave_threshold(y, self.sea)


@lru_cache(maxsize=8)
def cave_field(seed: int, size: int, height: int, sea: int) -> CaveField:
    """按 `(seed, size, height, sea)` 记忆的洞场（测试与一次性脚本用）。

    ⚠ **生成热路径不要用它**：`ChunkedWorld` 自己持有实例，
    别每次都过一遍 `lru_cache`（那正是初版慢 4.4s 的原因）。
    """
    return CaveField(seed, size, height, sea)


def cave_threshold(y: int, sea: int) -> float:
    """该深度的挖空阈值：**越深越低** ⇒ 越深越容易挖。

    `sea` 是海平面（地下带在 `y < sea`）。`y=sea` 返回基准 `CAVE_THRESHOLD`，
    `y=0` 返回基准 − `DEPTH_GAIN`。
    """
    y = max(0, min(int(sea), int(y)))
    return CAVE_THRESHOLD - DEPTH_GAIN * (1.0 - y / max(1, sea))


def density(x: int, y: int, z: int, seed: int, size: int, height: int) -> float:
    """模块级便捷口径（默认海平面口径）—— 探针与单测用，热路径别用。"""
    return cave_field(seed, size, height, int(round(height * 0.47))).density(x, y, z)


def is_cave(x: int, y: int, z: int, surface: int, seed: int, sea: int,
            size: int, height: int) -> bool:
    """模块级便捷口径（见 `density` 的 ⚠）。"""
    return cave_field(seed, size, height, sea).is_cave(x, y, z, surface)


# ------------------------------------------------------------ worm 隧道
class TunnelIndex:
    """worm 隧道按**区块**分组的索引（生成某块时 O(1) 取自己那一份）。

    ⚠ 一次性算完是必须的：每格去问"我在任一球心里吗"要扫几千个球心，
    1.83M 格 × 几千 = 十亿级比较（不可行）。
    """

    __slots__ = ('by_chunk', 'holes')

    def __init__(self, by_chunk: dict, holes: dict):
        #: `(cx, cy, cz)` → 该区块内被 worm 挖掉的**局部** `(lx, ly, lz)` 集合
        self.by_chunk = by_chunk
        #: `(x, z)` → 地表洞口格（给测试/截图用；不参与生成判定）
        self.holes = holes

    def cells_in(self, cx: int, cy: int, cz: int):
        return self.by_chunk.get((cx, cy, cz), frozenset())


def _worm_spheres(seed: int, size: int, height: int, sea: int, surface_fn):
    """逐条 worm 游走，产出 `(球心 x, y, z)` 序列。"""
    n = (size + WORM_CELL - 1) // WORM_CELL
    for gx in range(n):
        for gz in range(n):
            if _hash01(gx, gz, seed ^ 0x77) > WORMS_PER_CELL:
                continue
            base_x = gx * WORM_CELL + _hash01(gx, gz, seed ^ 0x71) * WORM_CELL
            base_z = gz * WORM_CELL + _hash01(gx, gz, seed ^ 0x72) * WORM_CELL
            x = float(base_x)
            z = float(base_z)
            y = 4.0 + _hash01(gx, gz, seed ^ 0x73) * (height * 0.30)
            cap = height - 2
            for step in range(WORM_STEPS):
                h = surface_fn(int(x), int(z))
                # ⚠ **水下/岸边地形整条 worm 都不挖**（洞里进水是没法修的：
                #   本项目没有流体系统，水会"悬空"）。探针实测：岸边地形
                #   （h <= sea+1）的列确实会长出 worm，于是洞口开在水里。
                if h <= sea + 1:
                    break
                # 到达洞顶层 ⇒ 最后补一个"地表窗口"球，把表土打穿（见下）
                if y >= h - SOIL_KEEP + 1.0:
                    yield x, float(h - 1.0), z
                    break
                ang = _hash01(gx, gz, step, seed ^ 0x74) * math.tau
                up = 0.34 + _hash01(gx, gz, step, seed ^ 0x75) * 0.42
                side = 1.0 - up * 0.55
                x = min(size - 2.0, max(1.0, x + math.cos(ang) * side))
                z = min(size - 2.0, max(1.0, z + math.sin(ang) * side))
                y = min(cap, max(2.0, y + up))
                yield x, y, z


@lru_cache(maxsize=4)
def _tunnels_cached(seed: int, size: int, height: int, sea: int):
    """算 worm 索引。`surface_fn` 用**公式**重建（见 `tunnels()`），保证可缓存。"""
    from .world import surface_height          # 局部导入：避开与 world 的导入环
    surface_fn = lambda x, z: surface_height(x, z, seed, height)

    r2 = WORM_RADIUS * WORM_RADIUS
    reach = int(math.ceil(WORM_RADIUS))
    by_chunk: dict = {}
    holes: dict = {}
    chunk = 16
    for (x, y, z) in _worm_spheres(seed, size, height, sea, surface_fn):
        ix, iy, iz = int(round(x)), int(round(y)), int(round(z))
        h = surface_fn(ix, iz)
        for dy in range(-reach, reach + 1):
            for dz in range(-reach, reach + 1):
                for dx in range(-reach, reach + 1):
                    if dx * dx + dy * dy + dz * dz > r2:
                        continue
                    px, py, pz = ix + dx, iy + dy, iz + dz
                    if not (0 <= px < size and 1 < py < height and 0 <= pz < size):
                        continue
                    key = (px // chunk, py // chunk, pz // chunk)
                    by_chunk.setdefault(key, set()).add((px % chunk, py % chunk, pz % chunk))
                    if py >= h - SOIL_KEEP:
                        holes[(px, pz)] = h
    return TunnelIndex(by_chunk, holes)


def tunnels(seed: int, size: int, height: int, sea: int) -> TunnelIndex:
    """本世界（按 `seed/size/height/sea`）的 worm 隧道索引。

    与调用顺序无关 ⇒ 惰性分块生成与全量生成结果一致。
    """
    return _tunnels_cached(int(seed), int(size), int(height), int(sea))
