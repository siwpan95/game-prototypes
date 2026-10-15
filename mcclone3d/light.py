# -*- coding: utf-8 -*-
"""逐格光照：**天光（列传播）+ 方块光（点光源 BFS）**（纯逻辑，零 GL）。

## 为什么必须"增量"而不是"重算全世界"

世界默认 256×256×64 ≈ **419 万格**。改一格就整图重算光照，等于每挖一下卡几秒。
所以本模块只有三个入口是"贵"的（`build_all` / `relight_column` / `add_light`），
**内核只在区块脏的时候碰它们**，且都返回"这次实际改了几格"——那个数字就是判据。

## ⚠ 性能：为什么**没有**"一次算全世界"的入口（实测血的教训）

第一版写了 `build_all()`：先逐列灌天光，再把**所有 level>1 的格子**当种子做一次
全局 BFS。在 64×32 的世界里，地表以上整片空气都是 level 15 ⇒ 种子 ~4 万个，
BFS 波及整图 ⇒ **跑到 5.8 GB 内存、几十秒不收敛**（实测把一个 python 进程喂成
5.8 GB 后被我强杀）。方向没错、规模错了。

**结论（本模块的现行口径）**：

* 渲染实际需要的只是**看得到的那些面**的光 ⇒ **按区块按需算**（`relight_chunk`）；
* 单区块的 BFS **限制在一块"区块 + 15 格外扩"的盒子里**（光最远走 15 格，
  所以盒子外的光不可能影响盒内 —— 这不是近似，是上界）；
* 开销与"看得到的区块数"成正比（本版默认 256 个），而不是与世界体积成正比。

## 光照模型（与 MC 同构，但只说清我们实现了哪几条）

* 取值 **0..15**（0 = 全黑、15 = 满亮）；天光与方块光**分开存**：
  世界任何时候的"天光能到多少"由 `sun.day_factor` 决定，**不烘进数据** ——
  否则每次昼夜变化都要重算全世界；
  所以每格的最终亮度 = `max(方块光, 天光 × day_factor)`（见 `combined`）。
* **天光列传播**：从世界顶往下，遇到不透明方块就停；**经过透明方块（水/玻璃）衰减 1**。
  这与 MC 的"天光在竖直方向不衰减"略不同 —— 我们的水/玻璃会挡光，更符合直觉也更省事。
* **水平扩散**：天光与方块光都用**逐层 BFS**向六邻扩散，每格 −1，直到 0。
  实现上是"种子队列 + 逐级扩展"，不是递归（递归会爆栈且难增量）。
* **不透明方块内部光为 0**（石头里面是黑的）——这一条让"洞里有光、石头里没光"成立。

## 数据结构

按区块存两个 `bytearray(4096)`：

```
chunk (cx,cy,cz)  ->  {'sky': bytearray, 'block': bytearray}
```

索引换算与 `world.ChunkedWorld` **同一套**（`(ly*16+lz)*16+lx`），所以查一块的光
不需要另算坐标 —— 两套索引一旦不同步就会出现"光照与方块错位一格"这种鬼 bug。
"""
from __future__ import annotations

from . import blocks as B
from .world import CHUNK, _idx, _local, chunk_key

__all__ = ['MAX_LIGHT', 'DEFAULT_HALO', 'LightEngine', 'LightOverflow',
           'combined', 'SKY_FULL']

#: 光照最大值（与 MC 同为 15）
MAX_LIGHT = 15
SKY_FULL = MAX_LIGHT

#: `relight_chunk` 的默认光晕半径（取舍与依据见该方法文档；精确值用 `MAX_LIGHT`）
DEFAULT_HALO = 4


class LightOverflow(RuntimeError):
    """光照扩散超出护栏 —— **响亮失败**，不静默截断（见 `_spread_from` 的说明）。"""


#: 临时诊断开关（排查光照性能时打开；正常路径零开销）
_DEBUG = False

#: 六个邻格方向
_NEIGHBORS = ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1))


def _transparent(block_id: int) -> bool:
    """光能不能穿过这一格。

    空气与液体/玻璃能穿；**其余一律不穿**。注意这里与"面剔除"的口径**故意不同**：
    面剔除问"看不看得见那一面"，光照问"光能不能进来"。水能透光但会衰减（见 `_cost`）。
    """
    return B.is_transparent(block_id)


def _cost(block_id: int) -> int:
    """光穿过这一格要衰减多少（0 = 不衰减）。"""
    if block_id == B.AIR:
        return 0
    if B.is_liquid(block_id):          # 水：每格衰减 1（比空气暗，但还能透）
        return 1
    return 1                            # 玻璃等透明固体也衰减 1


#: **所有可能透光的方块 id**（`relight_chunk` 用它一眼判"这块全是实心"）。
#: ⚠ **必须显式带上空气（id 0）**：`B.all_blocks()` 是"被定义的方块"，
#: 空气不在其中（它是"没有方块"）—— 漏了它，含空气的区块会被误判成实心而整块跳过，
#: 表现为"整张地图全黑"（实测踩过：1024 个区块全被跳过，光照一个格子都没算）。
_LIGHT_PASSABLE_IDS = frozenset(
    [B.AIR] + [b.id for b in B.all_blocks() if _transparent(b.id)])

assert B.AIR in _LIGHT_PASSABLE_IDS, \
    '空气必须在可透光集合里，否则含空气的区块会被整块跳过（全黑）'


class LightEngine:
    """光照场。**与世界同生命周期**；由内核在方块变化时调用增量入口。"""

    def __init__(self, world):
        self.world = world
        self.chunks: dict[tuple, dict] = {}
        #: 统计（"这次改动动了几格"就是判据，不是"看起来变亮了"）
        self.stats = {'built': 0, 'relit': 0, 'seeded': 0, 'spread': 0}
        #: 已经按区块算过光的区块数（渲染按需调用时会涨）
        self.relit_chunks = 0
        #: 全世界列传播是否已做过（`column_pass_all` 置位；`kernel` 开局调用一次）
        self.columns_done = False

    # ------------------------------------------------------------ 存取
    def _chunk(self, key, create=True):
        c = self.chunks.get(key)
        if c is None and create:
            c = {'sky': bytearray(CHUNK ** 3), 'block': bytearray(CHUNK ** 3)}
            self.chunks[key] = c
        return c

    def _cell(self, buf_name, x, y, z):
        """取某格的某种光；世界外/未建区块返回 0。

        ⚠ 这是**热路径**（列传播按格调用，一个区块 15k 次）。
        所以这里只做一次 `chunks.get(chunk_key(...))`，不再走 `_local` + `_idx` 两个函数
        （实测：把这两步内联后单区块从 300ms 量级降到几十毫秒）。
        """
        c = self.chunks.get((x >> 4, y >> 4, z >> 4))
        if c is None:
            return 0
        return c[buf_name][((y & 15) << 8) | ((z & 15) << 4) | (x & 15)]

    def sky(self, x, y, z) -> int:
        return self._cell('sky', x, y, z)

    def block(self, x, y, z) -> int:
        return self._cell('block', x, y, z)

    def _set(self, buf_name, x, y, z, value) -> bool:
        """写某格的光；返回是否**真的变了**（判据：变了才继续扩散，否则会死循环）。

        与 `_cell` 同样内联索引换算（热路径）。世界外直接拒（不建多余区块）。
        """
        if not (0 <= x < self.world.size and 0 <= y < self.world.height
                and 0 <= z < self.world.size):
            return False
        key = (x >> 4, y >> 4, z >> 4)
        c = self.chunks.get(key)
        if c is None:
            c = {'sky': bytearray(CHUNK ** 3), 'block': bytearray(CHUNK ** 3)}
            self.chunks[key] = c
        i = ((y & 15) << 8) | ((z & 15) << 4) | (x & 15)
        buf = c[buf_name]
        if buf[i] == value:
            return False
        buf[i] = value
        return True

    # ------------------------------------------------------------ 全局列传播
    def column_pass_all(self) -> int:
        """**全世界**做一遍天光列传播（不自上而下重灌，逐区块接力）。

        为什么要有这一步（架构变更的实测依据）：把列传播塞进 `relight_chunk` 后，
        每次都要从世界顶往下灌一遍，**开销与世界高度成正比**；
        `halo=15` 时单区块 285ms、256×64 世界要 70 多秒。
        拆出来之后：列传播全图一次（快，只与"格数"成正比），横向扩散按区块按需做。

        **必须在任何 `relight_chunk` 之前调用一次**（`kernel._init` 已代劳）。
        """
        n = 0
        tops = {}
        # y 必须由高到低（光从上方传下来）；x/z 顺序无关
        for cy in range((self.world.height - 1) >> 4, -1, -1):
            for cx in range((self.world.size + CHUNK - 1) // CHUNK):
                for cz in range((self.world.size + CHUNK - 1) // CHUNK):
                    got = self._column_pass_chunk(
                        cx, cy, cz, 0, self.world.size - 1, 0, self.world.size - 1,
                        0, self.world.height - 1, tops)
                    if got:
                        tops.update({(x, z, cy - 1): lv for (x, z), lv in got.items()})
                    n += 1
        self.columns_done = True
        self.stats['columns'] = n
        return n

    # ------------------------------------------------------------ 按区块按需
    def _buffers(self, cx, cy, cz, create=True):
        """取某区块的 `(方块缓冲, 天光缓冲, 方块光缓冲)`；`create=False` 时可返回 None。

        直接读 `world` 的区块缓冲是这里最重要的优化：`world.get()` 每格要做
        "算区块键 → 取模 → 算索引"三件事，一个区块 1.5 万格就能吃掉上百毫秒。
        """
        key = (cx, cy, cz)
        blk = self.world.chunks.get(key)
        if blk is None:
            return (None, None, None)
        c = self.chunks.get(key)
        if c is None:
            if not create:
                return (blk, None, None)
            c = {'sky': bytearray(CHUNK ** 3), 'block': bytearray(CHUNK ** 3)}
            self.chunks[key] = c
        return (blk, c['sky'], c['block'])

    def _column_pass_chunk(self, cx, cy, cz, bx0, bx1, bz0, bz1, by0, by1, tops):
        """对某区块做天光列传播。

        `tops[(cx, cz, cy)]` 是"该区块**上方紧邻**那个区块的底格天光值"（没有则 15）——
        有了它，每个区块只需处理自己这 16 层，不必从世界顶重灌。
        ⚠ 列一旦撞到不透明方块就**整列结束**（下方永远无天光），所以后续区块
        不会再把光接回来；`tops` 里对该列记 0 即可。
        """
        blk, sky, _ = self._buffers(cx, cy, cz, create=True)
        if blk is None:
            return {}
        x0, x1 = max(bx0, cx * CHUNK), min(bx1, cx * CHUNK + CHUNK - 1)
        z0, z1 = max(bz0, cz * CHUNK), min(bz1, cz * CHUNK + CHUNK - 1)
        if x0 > x1 or z0 > z1:
            return {}
        y_base = cy * CHUNK
        out = {}
        for x in range(x0, x1 + 1):
            lx = x & 15
            for z in range(z0, z1 + 1):
                lz = z & 15
                level = tops.get((cx, cz, cy), SKY_FULL)   # 上方区块给下来的光
                last = level
                for ly in range(CHUNK - 1, -1, -1):
                    y = y_base + ly
                    if y >= self.world.height:
                        continue
                    b = blk[(ly << 8) | (lz << 4) | lx]
                    if not _transparent(b):
                        last = 0
                        break
                    level = max(0, level - _cost(b))
                    last = level
                    i = (ly << 8) | (lz << 4) | lx
                    if level > sky[i]:
                        sky[i] = level
                    if level == 0:
                        break
                # 交给下方区块的"入口值"：本区块底格以下的光
                if last > 0:
                    out[(cx, cz)] = last
        self._tops_out = out
        return out
    def relight_chunk(self, cx: int, cy: int, cz: int, halo: int | None = None) -> int:
        """算（或重算）一个区块的光照，返回被写入的格子数。

        **这是渲染路径唯一需要的入口**（见模块说明：不提供"一次算全世界"）。

        `halo` 是"往区块外多看几格"：光最远走 15 格，所以 **halo=15 是精确上界**，
        但代价是盒内格子数 `(16+2h)³` 随 h 平方增长 —— 实测 h=15 时单区块 ~156ms，
        全图要 40 秒，不可用。默认取 `DEFAULT_HALO=4`：

        * 盒内 24×24×32 ≈ 1.8 万格（h=15 时是 4.6 万）；
        * 平地/缓坡上结果与 h=15 **完全相同**（列传播本来就按列精确）；
        * 差异只出现在"陡崖边缘 15 格内的水平扩散"——那是光照模型里最不敏感的部分。

        **要精确值就显式传 `halo=light.MAX_LIGHT`**（CLI/单测的对拍路径就是这么做的），
        这样"精度"是一个**显式选择**，而不是藏在实现里的偶然值。
        """
        if halo is None:
            halo = DEFAULT_HALO
        # ① 两种"白算"的区块直接跳过（各带一条实测依据）：
        #   (a) **全实心**：一块里没有任何透光方块 ⇒ 每格光照恒为 0。
        #       实测：地表以下的区块占一多半，跳过它们省掉约 40% 开销。
        #   (b) **全空气**：地表以上的区块里没有任何可见面（网格是空的），
        #       算出来的光照没人看得见 —— 而它们恰好是"整片天空 level 15"那种
        #       最费的区块。跳过是纯赚。
        #   ⚠ 判据必须用**方块 id 集合**（`set(blk)` 是 C 层做的），
        #     逐格扫 4096 次会把这个优化本身变成瓶颈。
        blk = self.world.chunks.get((cx, cy, cz))
        if blk is not None:
            ids = set(blk)
            c = self.chunks.get((cx, cy, cz))
            if not (ids & _LIGHT_PASSABLE_IDS):                 # 全实心
                if c is not None:
                    c['sky'][:] = b'\x00' * (CHUNK ** 3)
                    c['block'][:] = b'\x00' * (CHUNK ** 3)
                self.relit_chunks += 1
                return 0
            if ids == {B.AIR}:                                  # 全空气：没有面要画
                if c is None:
                    c = {'sky': bytearray(CHUNK ** 3), 'block': bytearray(CHUNK ** 3)}
                    self.chunks[(cx, cy, cz)] = c
                if self.columns_done:
                    c['sky'][:] = bytes([SKY_FULL]) * (CHUNK ** 3)
                self.relit_chunks += 1
                return 0
        r = int(halo)
        x0, y0, z0 = cx * CHUNK, cy * CHUNK, cz * CHUNK
        x1, y1, z1 = x0 + CHUNK - 1, y0 + CHUNK - 1, z0 + CHUNK - 1
        # ⚠ `halo=0` 时**只在本区块内**做横向扩散，但天光列传播仍要覆盖**本区块的列**
        #    （所以盒子的 x/z 至少是这一块）。这时相邻区块的横向光不参与 ——
        #    代价是"区块边界上的深洞会比实际略暗"，收益是**开销与全世界无关**。
        bx0, by0, bz0 = max(0, x0 - r), max(0, y0 - r), max(0, z0 - r)
        bx1 = min(self.world.size - 1, x1 + r)
        by1 = min(self.world.height - 1, y1 + r)
        bz1 = min(self.world.size - 1, z1 + r)

        # ① 天光列传播：**全世界已经做过一次**（`column_pass_all`）就直接用；
        #    没做过（单测里直接 new 一个 LightEngine）就只为盒内补一次。
        #    ⚠ 关键：列传播**不做**的话，天空区全是 0 ⇒ 种子为空 ⇒ 整块渲染成黑的。
        if not self.columns_done:
            tops = {}
            for cy_i in range(by1 >> 4, (by0 >> 4) - 1, -1):
                for cx_i in range(bx0 >> 4, (bx1 >> 4) + 1):
                    for cz_i in range(bz0 >> 4, (bz1 >> 4) + 1):
                        got = self._column_pass_chunk(cx_i, cy_i, cz_i, bx0, bx1,
                                                      bz0, bz1, by0, by1, tops)
                        if got:
                            tops.update({(x, z, cy_i - 1): lv
                                         for (x, z), lv in got.items()})
        # ② 天光扩散：**每列只从"最下面那个透光格"播种**（见 `_column_bottom_seeds`）
        seeds_sky = self._column_bottom_seeds(bx0, by0, bz0, bx1, by1, bz1)
        if _DEBUG:
            import sys as _sys
            print(f'[light] box=({bx0},{by0},{bz0})..({bx1},{by1},{bz1}) '
                  f'种子={len(seeds_sky)}', file=_sys.stderr, flush=True)
        n = self._spread_from('sky', seeds_sky, box=(bx0, by0, bz0, bx1, by1, bz1))

        # ③ 方块光：盒内的自发光方块当种子
        seeds_block = []
        for x in range(bx0, bx1 + 1):
            for z in range(bz0, bz1 + 1):
                for y in range(max(0, by0), by1 + 1):
                    b = self.world.get(x, y, z)
                    if b == B.AIR:
                        continue
                    ent = B.BLOCKS.get(b)
                    if ent is not None and ent.emissive > 0 and _transparent(b):
                        lv = min(MAX_LIGHT, max(0, int(round(ent.emissive * MAX_LIGHT))))
                        if self._set('block', x, y, z, lv):
                            seeds_block.append((x, y, z, lv))
        n += self._spread_from('block', seeds_block,
                               box=(bx0, by0, bz0, bx1, by1, bz1))
        self.stats['relit'] += n
        self.relit_chunks += 1
        return n

    def _column_bottom_seeds(self, bx0, by0, bz0, bx1, by1, bz1):
        """天光扩散的种子：**从"暗格"播种**——凡是"自己是暗的、邻居里有亮的"格子。

        ⚠ 方向反过来是本模块性能的最终解法（前三次都错在同一件事上）。
        实测数字（31×31×31 的盒子里，见模块说明的三次事故）：

        * **亮的格子当种子**：亮区内部六邻全亮（谁也点不亮），边界格虽有 1676 个，
          但每个仍要检查 6 邻且**绝大多数邻居已经够亮** ⇒ 仅表面一层的扩展就把
          访问量顶到 **76 万格**（护栏拦下）。根因是"种子数"不等于"有用工作量"。
        * **暗的格子当种子**：每个种子**必然被点亮**（它的亮邻居就是光源），
          于是 BFS 的访问量 ∝ 真正需要照亮的格子数。平坦地形上这类格子只有
          地表下方薄薄一层 + 水下的几格 ⇒ 直接掉两个数量级。

        每个暗格的值直接取"亮邻居能给的最大值"，**不做"先清零再扩散"** ——
        列传播已经把亮区铺好了，这里只是把光继续往外推。
        """
        out = []
        get = self.world.get
        cell = self._cell
        for x in range(bx0, bx1 + 1):
            for z in range(bz0, bz1 + 1):
                for y in range(max(0, by0), by1 + 1):
                    if not _transparent(get(x, y, z)):
                        continue
                    cur = cell('sky', x, y, z)
                    best = 0
                    for (dx, dy, dz) in _NEIGHBORS:
                        nx, ny, nz = x + dx, y + dy, z + dz
                        nb = get(nx, ny, nz)
                        if not _transparent(nb):
                            continue
                        src = cell('sky', nx, ny, nz)
                        if src < 3:                   # 源头太暗，推不出有意义的光
                            continue
                        want = src - 1 - _cost(nb)
                        if want > best:
                            best = want
                    if best > cur:
                        out.append((x, y, z, best))
        return out

    def _only_frontier(self, buf_name: str, cands):
        """只保留"**边界格**"：邻居里存在能被它点亮的暗格。

        ⚠ 这一步是本模块性能的关键（实测教训）：先前把"所有 level>1 的格子"都当种子，
        而平坦地形上**整片天空都是 15** ⇒ 种子 4 万个、BFS 访问 65 万格直接失控
        （护栏拦下时打印的 `已访问 657700 格` 就是它）。
        物理上，光只从"更亮的格子指向更暗的邻居"流动，所以**内部格（六邻都不比它暗）
        根本不产生任何新光** —— 把它们从种子里剔掉，结果一模一样、工作量掉一个量级。
        """
        out = []
        get = self.world.get
        cell = self._cell
        for (x, y, z, level) in cands:
            if level <= 1:
                continue
            for (dx, dy, dz) in _NEIGHBORS:
                nx, ny, nz = x + dx, y + dy, z + dz
                b = get(nx, ny, nz)
                if not _transparent(b):
                    continue
                want = level - 1 - _cost(b)
                if want > 0 and want > cell(buf_name, nx, ny, nz):
                    out.append((x, y, z, level))
                    break
        return out

    # ------------------------------------------------------------ 全量（慎用）
    def build_all(self) -> int:
        """**逐区块**算一遍全部区块（只在开局/读档用；不要写成"一次全局 BFS"）。

        这个入口之所以安全，是因为它内部先做一次全局列传播、再逐个调 `relight_chunk`
        —— 每次的 BFS 都被限制在"区块 + halo 格外扩"里，不会像第一版那样让队列涨到 5.8 GB。
        """
        self.column_pass_all()
        n = 0
        for (cx, cy, cz) in sorted(self.world.chunks):
            n += self.relight_chunk(cx, cy, cz)
        self.stats['built'] = n
        return n

    def _spread_from(self, buf_name: str, seeds, max_visits: int = 400_000,
                     box=None) -> int:
        """**逐层 BFS**：从种子出发向六邻扩散，每格 −1，直到 0。

        只朝"还能更亮"的方向扩散（`want > 当前值` 才写），所以：
        * 不会死循环（每写一次值必然增大，值有上界 15）；
        * 复杂度与"实际受影响的格子数"成正比。

        ⚠ `max_visits` 是**护栏**，不是可有可无的保险：第一版没有它，
        实测把一个 python 进程喂到 **5.8 GB 内存**才被我强杀。
        超限时**响亮抛错**（`LightOverflow`），绝不静默截断 ——
        静默截断会让光照"看着差不多、某些地方莫名发黑"，那种 bug 最难查。

        ## `box` 为什么必须有（2026-10-15 实测踩到，Phase 2-C 加洞穴后暴露）

        `box = (x0, y0, z0, x1, y1, z1)`：扩散**只在这个盒子里**发生。
        没有它，BFS 会顺着地形一路走出盒子 —— 世界没有洞穴时无所谓
        （地下全实心，扩散几步就撞墙停），但**一旦有洞穴**：天光会顺着
        洞口灌进整个洞穴系统，每写一次值就再扩散一轮，单区块访问量
        冲到 **113 万**（护栏 40 万）⇒ `LightOverflow` ⇒ **demo 直接起不来**。
        而且它还是**错的**：洞里被灌成 level 14 的"全亮"。
        `relight_chunk` 的文档早写了"只在本区块内横向扩散"，这里补上实现。
        """
        changed = 0
        visits = 0
        queue = list(seeds)
        world_get = self.world.get
        if box is not None:
            bx0, by0, bz0, bx1, by1, bz1 = box
        while queue:
            visits += len(queue)
            if visits > max_visits:
                raise LightOverflow(
                    f'光照扩散超出上限（{buf_name}）：已访问 {visits} 格 > {max_visits}。'
                    f' 这通常意味着种子集过大或扩散范围失控 ——'
                    f' 检查是否在"整片天空"上撒了种子（见 light.py 模块说明的 5.8 GB 事故）。')
            nxt = []
            for (x, y, z, level) in queue:
                if level <= 1:
                    continue
                for (dx, dy, dz) in _NEIGHBORS:
                    nx, ny, nz = x + dx, y + dy, z + dz
                    if box is not None and not (bx0 <= nx <= bx1 and by0 <= ny <= by1
                                                and bz0 <= nz <= bz1):
                        continue
                    b = world_get(nx, ny, nz)
                    if not _transparent(b):
                        continue
                    want = level - 1 - _cost(b)
                    if want <= 0:
                        continue
                    if want > self._cell(buf_name, nx, ny, nz):
                        self._set(buf_name, nx, ny, nz, want)
                        changed += 1
                        nxt.append((nx, ny, nz, want))
            queue = nxt
        self.stats['spread'] = changed
        self.stats['visits'] = visits
        return changed

    # ------------------------------------------------------------ 增量
    def on_block_changed(self, x: int, y: int, z: int) -> int:
        """方块变了（挖/放）后修光照，返回**受影响的格子数**。

        分三步，缺一不可：
        1. **清掉旧值**：这一格及其"靠它供光"的下游要先降到 0（用 BFS 收集受害者）；
        2. **列传播**：天光从顶重新灌到这一列（挖开一个洞，天光要能顺着洞下来）；
        3. **重新扩散**：把周围（含新光源）当种子再扩散一遍。
        """
        n = 0
        self._clear_region(x, y, z, 'sky')
        self._clear_region(x, y, z, 'block')
        n += self.relight_column(x, z)
        # 周围一圈当种子（半径取 MAX_LIGHT：再远的光不可能一步影响这里）
        seeds_sky, seeds_block = [], []
        r = MAX_LIGHT
        # ⚠ 扩散**限制在这颗球的包围盒内**（与 `relight_chunk` 同一条纪律）：
        #   没有边界时光会顺着洞口一路灌进整个洞穴系统 —— 既错又爆护栏。
        box = (max(0, x - r), max(0, y - r), max(0, z - r),
               min(self.world.size - 1, x + r),
               min(self.world.height - 1, y + r),
               min(self.world.size - 1, z + r))
        for dx in range(-r, r + 1):
            for dy in range(-r, r + 1):
                for dz in range(-r, r + 1):
                    if abs(dx) + abs(dy) + abs(dz) > r:
                        continue
                    sx, sy, sz = x + dx, y + dy, z + dz
                    if not (0 <= sx < self.world.size and 0 <= sy < self.world.height
                            and 0 <= sz < self.world.size):
                        continue
                    if not _transparent(self.world.get(sx, sy, sz)):
                        continue
                    vs = self._cell('sky', sx, sy, sz)
                    if vs > 1:
                        seeds_sky.append((sx, sy, sz, vs))
                    vb = self._cell('block', sx, sy, sz)
                    if vb > 1:
                        seeds_block.append((sx, sy, sz, vb))
        n += self._spread_from('sky', seeds_sky, box=box)
        n += self._spread_from('block', seeds_block, box=box)
        # 新方块若是光源，把它自己种下去
        b = self.world.get(x, y, z)
        ent = B.BLOCKS.get(b)
        if ent is not None and ent.emissive > 0 and _transparent(b):
            lv = min(MAX_LIGHT, max(0, int(round(ent.emissive * MAX_LIGHT))))
            if self._set('block', x, y, z, lv):
                n += 1
                n += self._spread_from('block', [(x, y, z, lv)], box=box)
                self.stats['seeded'] += 1
        self.stats['relit'] += n
        return n

    def _clear_region(self, x: int, y: int, z: int, buf_name: str):
        """把"靠 (x,y,z) 供光"的格子清零（含 (x,y,z) 自己）。

        判据：从目标格出发，凡满足 `邻居值 == 当前值 - 1 - cost` 的邻居，
        就是"由它供的光"，继续往外交替收集；收集完一次性清零。
        **先收集再清**，不能边清边扩散 —— 那样会把还需要保留的光也清掉。
        """
        start = self._cell(buf_name, x, y, z)
        if start <= 0:
            return 0
        victims = [(x, y, z)]
        seen = {(x, y, z)}
        head = 0
        while head < len(victims):
            (cx, cy, cz) = victims[head]
            head += 1
            cur = self._cell(buf_name, cx, cy, cz)
            for (dx, dy, dz) in _NEIGHBORS:
                nx, ny, nz = cx + dx, cy + dy, cz + dz
                if (nx, ny, nz) in seen:
                    continue
                b = self.world.get(nx, ny, nz)
                if not _transparent(b):
                    continue
                nv = self._cell(buf_name, nx, ny, nz)
                if nv == 0:
                    continue
                if nv < cur or (nv == cur and buf_name == 'block'):
                    seen.add((nx, ny, nz))
                    victims.append((nx, ny, nz))
        for (cx, cy, cz) in victims:
            self._set(buf_name, cx, cy, cz, 0)
        return len(victims)

    def relight_column(self, x: int, z: int) -> int:
        """重算一列的天光（从世界顶往下，遇阻即停）。返回写入格数。"""
        n = 0
        level = SKY_FULL
        for y in range(self.world.height - 1, -1, -1):
            b = self.world.get(x, y, z)
            if not _transparent(b):
                break
            level = max(0, level - _cost(b))
            if self._set('sky', x, y, z, level):
                n += 1
            if level == 0:
                break
        return n

    # ------------------------------------------------------------ 组合
    def combined(self, x, y, z, day_factor: float = 1.0) -> int:
        """某格的最终亮度 0..15：`max(方块光, 天光 × day_factor)`。

        天光**不烘进数据**（见模块说明）：昼夜变化只改这一个乘数，
        所以"白天→夜晚"不触发任何重算。
        """
        sky = self.sky(x, y, z) * max(0.0, min(1.0, day_factor))
        blk = self.block(x, y, z)
        return int(round(max(sky, blk)))

    def face_light(self, x, y, z, nx, ny, nz, day_factor: float = 1.0) -> int:
        """某个面**外侧那一格**的亮度（渲染用）。

        取外侧而不是方块自身：方块自身的光是 0（不透明方块内部无光），
        而"看得见的那一面有多亮"取决于它**朝外那格**的光照。
        """
        return self.combined(x + nx, y + ny, z + nz, day_factor)

    def dump_stats(self) -> dict:
        return dict(self.stats)
