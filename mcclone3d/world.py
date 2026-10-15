# -*- coding: utf-8 -*-
"""区块化体素世界：确定性生成 + 编辑增量 + 邻块感知（纯逻辑，零 GL）。

三件事
------
1. **存储**：按区块 `(cx, cy, cz)` 存成 `bytearray`（方块 id 一个字节）。
   区块尺寸 16×16×16（MC 的横向标准就是 16 列）。
2. **生成**：`generate()` 由种子**完全确定** —— 地形高度 / 矿脉 / 水 / 沙滩 / 树
   全部可由 `(seed, x, y, z)` 复算，不依赖任何随机库（见 `_hash01` 的说明）。
3. **编辑**：只记增量（`edits`）。存档 = **种子 + 增量**，不存整个世界 ——
   与引擎侧 WorldLog 的思路一致（快照 + 增量），且存档体积与"改了多少"成正比。

坐标口径
--------
* 世界坐标 `(x, y, z)`：整数格号，`y` 向上，**没有负数**（本版世界是有限的箱体）。
* 区块坐标 = 世界坐标整除 `CHUNK`；区块内局部 = 取模。
* 邻居查询 `get()` **自动跨区块**，所以网格化的面剔除在区块边界上是对的
  （这是"区块化"最容易出错的地方，单测专门钉它）。

边界约定
--------
世界外一律视为 `AIR`：好处是"世界边缘的方块面会被画出来"（看得见边界），
而不是靠一层隐形墙挡住视线。
"""
from __future__ import annotations

import math
from functools import lru_cache

from .blocks import (AIR, BEDROCK, BLOCK_IDS, COAL_ORE, DIRT, GRASS, GRAVEL,
                     IRON_ORE, LEAVES, LOG, SAND, SNOW, STONE, WATER,
                     by_id, is_solid, name_of)

__all__ = ['CHUNK', 'SEA_LEVEL', 'ChunkedWorld', 'chunk_key', 'ORE_BANDS',
           'ore_bands', 'surface_height']

#: 区块边长（三轴同长，索引换算最简单）
CHUNK = 16

#: 海平面（**默认 64 高世界**的口径；世界自己的值见 `ChunkedWorld.sea_level`）
SEA_LEVEL = 30


def chunk_key(x: int, y: int, z: int):
    """世界坐标 → 区块坐标 `(cx, cy, cz)`（整除；世界无负数，不必 floor）。"""
    return x // CHUNK, y // CHUNK, z // CHUNK


def _local(x: int, y: int, z: int):
    """世界坐标 → 区块内偏移 `(lx, ly, lz)`。"""
    return x % CHUNK, y % CHUNK, z % CHUNK


def _idx(lx: int, ly: int, lz: int) -> int:
    """区块内线性索引：`(ly * CHUNK + lz) * CHUNK + lx`。"""
    return (ly * CHUNK + lz) * CHUNK + lx


# ------------------------------------------------------------ 确定性噪声
def _hash01(*args) -> float:
    """整数元组 → [0,1) 的确定性哈希。

    **刻意不用 `random` / `hash()`**：
    * `random` 要赌跨平台逐位一致；
    * `hash()` 对 str 带随机盐（`PYTHONHASHSEED`）⇒ 同一份代码两次运行会生成不同的世界。
    自己写一行 sin 哈希，两个坑都绕开（与引擎 `logic/blocks.py` 的 `_hash01` 同源思路）。

    ⚠ **别改这个函数的算法** —— 存档只存「种子 + 编辑增量」，地形/矿脉/洞穴
    全部由它重算。改哈希 ⇒ 老存档里的玩家建筑会浮空或埋进石头。
    性能上只能做**行为等价**的优化（`import math` 提到模块级：本函数被调
    百万次，每次函数体内 import 都要查一遍 `sys.modules`）。
    """
    h = 0
    for i, a in enumerate(args):
        h = (h * 131 + int(a) * (7 + i * 13)) & 0x7FFFFFFF
    s = (h % 1000003) / 1000003.0
    # 再用一层三角函数打散低位规律（不然整数格点上会出现明显的棋盘纹）
    return (math.sin(s * 12.9898 + h * 0.0001) * 43758.5453) % 1.0


def _noise2(x: int, z: int, seed: int) -> float:
    """值噪声（双线性插值），周期 32 格。"""
    def g(ix, iz):
        return _hash01(ix, iz, seed)

    x0, z0 = (x // 32) * 32, (z // 32) * 32
    fx, fz = (x - x0) / 32.0, (z - z0) / 32.0
    a, b = g(x0, z0), g(x0 + 32, z0)
    c, d = g(x0, z0 + 32), g(x0 + 32, z0 + 32)
    top = a + (b - a) * fx
    bot = c + (d - c) * fx
    return top + (bot - top) * fz


def surface_height(x: int, z: int, seed: int, height: int = 64) -> int:
    """地表高度（该列最高的固体方块 y）。

    ⚠ **必须随世界高度缩放**（2026-10-14 实测踩到）：先前把基准写死在 34，
    于是 `height=32` 的测试世界**整片地表都在世界顶端之上** ⇒ 生成出来是"悬空柱子"
    （只有 y<32 的那截在，看着像凭空浮着）。现在基准 = `height × 0.53`、
    起伏 = `height × 0.19` ⇒ 任何高度下地表都落在世界**中上部**。
    """
    base = max(6.0, height * 0.53)
    amp = max(2.0, height * 0.19)
    total, a, cells = 0.0, 1.0, 32
    norm = 0.0
    for octave in range(3):
        total += a * _noise2(x * (32 // cells), z * (32 // cells), seed + octave * 977)
        norm += a
        a *= 0.5
        cells //= 2
    v = total / norm
    return int(base + (v - 0.5) * amp * 2.0)


# ------------------------------------------------------------ 矿脉分层（Phase 2-C）
#: 矿带：`(方块名, 深度上限, 簇尺度, 概率)`。深度只决定"能不能出现"，
#: 同深度内各矿种按概率**分段**（见 `_ore_at`）。
#:
#: 深度上限**随世界高度等比缩放**（基准 64 高）：默认世界正好是
#: 煤 40 / 铁 28 / 金 16 / 钻石 8。写死绝对值会让 32 高的测试世界里
#: "钻石层"挤成 3 格甚至空掉 —— 与 `surface_height`/`sea_level` 同一套缩放纪律。
#: 簇尺度统一 2：一次哈希就能定矿种（见 `_ore_at` 的性能说明），
#: 而且 2×2 的簇正是 MC 矿脉的观感。
ORE_BANDS = (
    ('coal_ore', 40, 2, 0.055),
    ('iron_ore', 28, 2, 0.040),
    ('gold_ore', 16, 2, 0.020),
    ('diamond_ore', 8, 2, 0.008),
)


@lru_cache(maxsize=512)
def ore_bands(y: int, height: int):
    """这一深度**允许**的矿带列表 `(方块名, 簇尺度, 概率)`，按浅→深排列。

    ⚠ **不是"第一个命中的带"，而是全部候选**（2026-10-15 实测踩到）：
    初版写成"从上往下第一个满足深度上限的带胜出"，于是 y=27 永远只能是煤
    （27 < 40 命中煤带，铁带根本没机会）—— 铁实际只出现在 y<16，
    "煤 40 / 铁 28" 变成了"煤 40 / 铁 16"，分层名存实亡。
    正确口径与 MC 一致：**深度只决定"能不能出现"，各矿种各自按概率撒点**。

    ⚠ **必须 `lru_cache`**：生成热路径上它被调 **183 万次**（每格一次），
    而参数只有两个小整数、返回值恒定。不缓存的话每次都要新建一个 4 元素
    列表 + 元组 —— 实测 `generate()` 从 5.8s 涨到 **8.8s（+3s）**，
    而这 3s 里没有一点是"洞穴"的锅（又一次：先 profile 再改）。
    """
    scale = height / 64.0
    out = []
    for (name, top, cell, prob) in ORE_BANDS:
        if y < int(top * scale):
            out.append((name, cell, prob))
    return tuple(out)


# ------------------------------------------------------------------ 世界
class ChunkedWorld:
    """有限箱体世界。`size` 是水平边长（格），`height` 是竖直格数。"""

    def __init__(self, seed: int = 20261014, size: int = 256, height: int = 64):
        if size % CHUNK or height % CHUNK:
            raise ValueError(f'size/height 必须是 {CHUNK} 的整数倍：size={size} height={height}')
        self.seed = int(seed)
        self.size = int(size)
        self.height = int(height)
        #: 海平面 / 雪线**随世界高度缩放**（同 `surface_height` 的理由：
        #: 写死 30 会让矮世界里"海平面在地表之上"，整片地形泡在水里）
        self.sea_level = int(round(self.height * 0.47))
        self.snow_line = int(round(self.height * 0.69))
        # Phase 2-C：**洞场预计算一次**，生成热路径只查数组。
        # ⚠ 局部导入（不是循环依赖）：`caves` 顶层 `from .world import _hash01`，
        #   而这里已经是**运行时**（world 模块早已加载完毕），所以安全；
        #   反过来在 world 顶层 import caves 会成环。
        from . import caves as _caves
        self.cave_field = _caves.CaveField(self.seed, self.size, self.height,
                                           self.sea_level)
        self.chunks: dict[tuple, bytearray] = {}
        #: 相对生成结果的**增量**：`(x,y,z) -> block_id`（存档只存这个）
        self.edits: dict[tuple, int] = {}
        #: 本世界被生成过（`generate()` 调过）的区块集合，供网格缓存判断
        self.generated: set[tuple] = set()

    # -------------------------------------------------------------- 生成
    def generate(self) -> 'ChunkedWorld':
        """按种子生成整个世界（幂等：重复调用结果相同，因为一切由种子决定）。

        ⚠ 三个轴的区块数**各不相同**（x/z 是 `size`，y 是 `height`）——
        2026-10-14 实测踩到：这里曾把三层循环全按 `size` 迭代，于是
        y 方向多算了 `size/height` 倍的区块，而**真正需要的那些反而没生成**，
        世界看上去"只有一小块有地形、其余全是空气"。现在逐轴各取各的界。
        """
        for cx in range(self.size // CHUNK):
            for cz in range(self.size // CHUNK):
                for cy in range(self.height // CHUNK):
                    self.chunks[(cx, cy, cz)] = self._generate_chunk(cx, cy, cz)
                    self.generated.add((cx, cy, cz))
        return self

    def surface_at(self, x: int, z: int) -> int:
        """该列的地表高度（= `surface_height`，**带上本世界的 height**）。

        单独立一个方法是因为"地表在哪"这件事有**三方**要用：生成、种树、玩家出生。
        先前只在生成里带 height、另外两处各写各的口径，矮世界里就会出现
        「地形在 y=17，树却按 44 的雪线判断」「玩家出生点在水面之上」这类不一致。
        """
        return surface_height(x, z, self.seed, self.height)

    def ensure_chunk(self, cx: int, cy: int, cz: int) -> bytearray:
        """按需生成一个区块（渐进式加载用；`generate()` 就是全量调它）。"""
        key = (cx, cy, cz)
        buf = self.chunks.get(key)
        if buf is None:
            buf = self._generate_chunk(cx, cy, cz)
            self.chunks[key] = buf
            self.generated.add(key)
        return buf

    def _generate_chunk(self, cx: int, cy: int, cz: int) -> bytearray:
        buf = bytearray(CHUNK * CHUNK * CHUNK)
        seed = self.seed
        for lx in range(CHUNK):
            wx = cx * CHUNK + lx
            if wx >= self.size:
                continue
            for lz in range(CHUNK):
                wz = cz * CHUNK + lz
                if wz >= self.size:
                    continue
                h = surface_height(wx, wz, seed, self.height)
                sea = self.sea_level
                beach = h <= sea + 1
                for ly in range(CHUNK):
                    wy = cy * CHUNK + ly
                    if wy >= self.height:
                        continue
                    b = self._column_block(wx, wy, wz, h, beach, seed, sea)
                    if b:
                        buf[_idx(lx, ly, lz)] = b
        # Phase 2-C：**worm 隧道**在这一步之后刷（它是"后处理"）。
        # 为什么不逐格问"我在不在某个球心里"：球心有几千个，
        # 逐格问就是十亿级比较。按区块分组索引 ⇒ O(1)，且与调用顺序无关
        # （`tunnels()` 只由 seed/size/height 决定 ⇒ 惰性分块生成结果一致）。
        from . import caves as _caves
        cells = _caves.tunnels(seed, self.size, self.height,
                               self.sea_level).cells_in(cx, cy, cz)
        for (lx, ly, lz) in cells:
            buf[_idx(lx, ly, lz)] = AIR
        return buf

    def _column_block(self, x: int, y: int, z: int, h: int, beach: bool, seed: int,
                      sea: int | None = None) -> int:
        """一格的方块 id（生成规则全在这里，便于逐条单测）。

        ⚠ **顺序就是语义**（两个条件会同时命中，谁在前谁赢）：
        `y == h`（地表那一格）必须排在 `y >= h - 3`（土层）**之前**。
        2026-10-14 实测踩过：写反之后地表那一格永远返回 DIRT
        （因为 `h >= h - 3` 恒真）⇒ 满地图没有草方块、没有沙、没有雪，
        "地表应长草"的断言全线告红 —— 而地形高度、树、水看上去都"正常"，
        这种"看起来没事的生成 bug"最难一眼看出来。
        矿脉判定则必须排在这两条之后（否则地表会冒出矿石）。
        """
        sea = self.sea_level if sea is None else int(sea)
        if y == 0:
            return BEDROCK
        if y > h:
            # 海平面以下填水；以上是空气
            return WATER if y <= sea else AIR
        if y == h:
            if h <= sea:
                return SAND if beach else GRAVEL      # 水下 / 岸边：沙或砾
            if h >= self.snow_line:
                return SNOW                           # 高处积雪
            return SAND if beach else GRASS
        if y >= h - 3:
            return SAND if beach else DIRT            # 地表下 1~3 格：土层
        # Phase 2-C：**洞穴**（挖空 ⇒ 空气）。护栏都在 `CaveField.is_cave` 里
        # （基岩 / 表土保底 3 格 / 海平面以上；水下地形整列不挖），
        # 所以这里直接问就行。
        # ⚠ 必须在矿脉**之前**：洞是空气、矿脉是石头，两者互斥；
        #   而"矿会长在洞穴壁上"正是想要的（MC 同款）。
        if self.cave_field.is_cave(x, y, z, h):
            return AIR
        # 深处：矿脉（**按深度分层**：浅层煤、深层铁/金/钻石，见 `ORE_BANDS`）
        ore = self._ore_at(x, y, z, seed, self.height)
        if ore is not None:
            return ore
        return STONE

    @staticmethod
    def _ore_at(x: int, y: int, z: int, seed: int, height: int = 64):
        """这一格是什么矿（不在任何矿带里返回 None）。

        ⚠ **深度上界由 `ore_bands` 自己兜住**，调用方不必也不能用调用顺序去保证
        "矿石不出现在地表" —— 那种保证一旦有人调换两行就没了（实测踩过，
        地表偶尔冒出矿石、把"高地表应长草"的断言随机打红）。
        **约束写在判据里，不写在调用者的顺序里。**

        ## 为什么是"一次哈希 + 概率分段"

        初版对**每个候选带各算一次哈希**。深层格平均有 **2.64 个候选带**
        ⇒ 全图 118 万次哈希（`_hash01` 是本仓最热的函数，cProfile 里
        187 万次调用占 tottime 1.9s）。改成：一次哈希把 `[0,1)` 切进
        各带的概率区间（浅→深累加）⇒ 每格恰好 1 次，簇尺度统一为 2
        （2×2 的簇也正是 MC 矿脉的观感）。
        """
        bands = ore_bands(y, height)
        if not bands:
            return None
        # 钻石允许贴基岩（y=1），其余矿留一层底
        floor = 1 if bands[-1][0] == 'diamond_ore' else 4
        if y < floor:
            return None
        cell = bands[0][2]
        v = _hash01(x // cell, y // cell, z // cell, seed ^ 0x5EED)
        acc = 0.0
        for (name, _c, prob) in bands:
            acc += prob
            if v < acc:
                return BLOCK_IDS[name]
        return None

    def plant_trees(self, count: int = 0) -> int:
        """按确定性散布种树，返回实际种下的棵数。

        树的**位置与形状都由 (x, z, seed) 决定**，所以"再生成一次"不会长出不同的树。
        树干不会种在已占用的格子上（避免把房子/水面顶穿）。
        """
        planted = 0
        step = max(6, self.size // 24)
        for x in range(4, self.size - 4, step):
            for z in range(4, self.size - 4, step):
                if _hash01(x, z, self.seed ^ 0x7EEE) > 0.22:
                    continue
                h = self.surface_at(x, z)
                if h <= self.sea_level + 1 or h >= self.snow_line:
                    continue                          # 水边与雪线不长树
                if self.get(x, h, z) not in (GRASS, DIRT, SAND):
                    continue
                self._tree(x, h + 1, z)
                planted += 1
                if count and planted >= count:
                    return planted
        return planted

    def _tree(self, x: int, y0: int, z: int):
        """一棵树：4~5 格树干 + 两层树冠。

        走的是 `put`（= `set_generated`，**不记增量**）—— 树是**地形的一部分**，
        不是玩家改动。先前用 `set()` 的话，一个新世界的 `edits` 里会凭空多出
        上百条树的记录，存档也就把整片森林当"增量"存下来了。
        """
        def put(px, py, pz, bid):
            if self.get(px, py, pz) == AIR:
                self.set_generated(px, py, pz, bid)
            return None

        trunk = 4 + int(_hash01(x, z, self.seed ^ 0xABCD) * 2)
        for i in range(trunk):
            put(x, y0 + i, z, LOG)
        top = y0 + trunk
        for dy in (-1, 0):
            r = 2 if dy == -1 else 1
            for dx in range(-r, r + 1):
                for dz in range(-r, r + 1):
                    if r == 2 and abs(dx) == r and abs(dz) == r:
                        continue                      # 四角留空，冠形更像树
                    put(x + dx, top + dy, z + dz, LEAVES)
        self.set_generated(x, top, z, LOG)

    # -------------------------------------------------------------- 读写
    def get(self, x: int, y: int, z: int) -> int:
        """取方块 id（越界一律 AIR —— 世界边界因此"看得见"）。"""
        if not (0 <= x < self.size and 0 <= y < self.height and 0 <= z < self.size):
            return AIR
        cx, cy, cz = chunk_key(x, y, z)
        buf = self.chunks.get((cx, cy, cz))
        if buf is None:
            return AIR
        lx, ly, lz = _local(x, y, z)
        return buf[_idx(lx, ly, lz)]

    def set(self, x: int, y: int, z: int, block_id: int) -> bool:
        """写一个方块；**同时记进增量**。返回是否真的改变了。

        越界或未生成的区块 → 返回 False 且**不记增量**（口径：不能改的东西就不留痕）。
        """
        if not (0 <= x < self.size and 0 <= y < self.height and 0 <= z < self.size):
            return False
        key = chunk_key(x, y, z)
        buf = self.chunks.get(key)
        if buf is None:
            return False
        lx, ly, lz = _local(x, y, z)
        i = _idx(lx, ly, lz)
        old = buf[i]
        new = int(block_id)
        if old == new:
            return False
        buf[i] = new
        self.edits[(x, y, z)] = new
        return True

    def set_generated(self, x: int, y: int, z: int, block_id: int) -> bool:
        """同 `set`，但**不记增量**（生成阶段内部用：树、原生地形）。"""
        if not (0 <= x < self.size and 0 <= y < self.height and 0 <= z < self.size):
            return False
        buf = self.chunks.get(chunk_key(x, y, z))
        if buf is None:
            return False
        lx, ly, lz = _local(x, y, z)
        buf[_idx(lx, ly, lz)] = int(block_id)
        return True

    def is_solid_at(self, x: int, y: int, z: int) -> bool:
        return is_solid(self.get(x, y, z))

    # -------------------------------------------------------------- 遍历
    def columns(self):
        """逐列产出 `(x, z, height)`（网格化 / 统计用）。"""
        for x in range(self.size):
            for z in range(self.size):
                yield x, z, self.surface_at(x, z)

    def block_count(self, block_id: int | None = None) -> int:
        """方块总数（可只数某一种）—— 单测与体检用。"""
        n = 0
        for buf in self.chunks.values():
            if block_id is None:
                n += sum(1 for b in buf if b)
            else:
                want = int(block_id)
                n += sum(1 for b in buf if b == want)
        return n

    def stats(self) -> dict:
        """一句话体检：区块数 / 非空方块数 / 编辑数 / 种下了几棵树。"""
        return {
            'seed': self.seed,
            'size': self.size,
            'height': self.height,
            'chunks': len(self.chunks),
            'blocks': self.block_count(),
            'edits': len(self.edits),
            'water': self.block_count(WATER),
            'trees': self.block_count(LOG),
        }

    # -------------------------------------------------------------- 存档
    def dump(self) -> dict:
        """存档：**种子 + 尺寸 + 增量**（不存整个世界）。

        编辑用「坐标 → 方块**名**」而不是 id：名字是给人看也给人改的，
        而 id 是内部契约 —— 存档里出现名字，将来重排 id 也不会读坏旧档
        （读档时按名字查回 id，未知名字**响亮报错**）。
        """
        return {
            'version': 1,
            'seed': self.seed,
            'size': self.size,
            'height': self.height,
            'edits': [
                [int(x), int(y), int(z), name_of(b)]
                for (x, y, z), b in sorted(self.edits.items())
            ],
        }

    def load(self, data: dict, replant: bool = True) -> 'ChunkedWorld':
        """读档：重新生成地形，再重放增量。

        `replant=True` 时先种树再重放增量 —— 顺序很重要：**玩家的编辑必须最后落**，
        否则读档后玩家的改动会被重新生成的树覆盖掉。
        """
        if int(data.get('version', 0)) != 1:
            raise ValueError(f'不支持的存档版本：{data.get("version")!r}')
        # ⚠ 尺寸校验必须在**重建世界之前**完成，否则自己刚建出来的世界永远"匹配"
        # （实测踩过：load 里先 `self.size = wd['size']` 再比对，这条校验等于没写）
        if int(data['seed']) != self.seed or int(data['size']) != self.size \
                or int(data['height']) != self.height:
            raise ValueError(
                f'存档与当前世界不一致（种子/尺寸不符）：'
                f'存档 seed={data["seed"]} size={data["size"]} height={data["height"]}，'
                f'当前 seed={self.seed} size={self.size} height={self.height}。'
                f'  ⇒ 要用这个存档，请按存档参数新建世界再读。')
        self.generate()
        if replant:
            self.plant_trees()
        self.edits.clear()
        unknown = []
        for x, y, z, name in data.get('edits', []):
            bid = BLOCK_IDS.get(name)
            if bid is None:
                unknown.append(name)
                continue
            self.set(int(x), int(y), int(z), bid)
        if unknown:
            raise ValueError(f'存档里有未知方块名：{sorted(set(unknown))}')
        return self
