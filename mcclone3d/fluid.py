# -*- coding: utf-8 -*-
"""水流：**垂直灌注**模型（纯逻辑，零 GL）。

## 为什么不是元自动机（CA）—— 实测教训

初版按 MC 的 level 模型做了 CA（下落 / 水平扩散 / level+1 衰减 / 7 级干涸），
在真实地形上**永不收敛**：挖穿海床后连跑 **3000 tick，洞内水量卡在 6/343**，
`active` 永远非空 —— 水在洞底"冲刷 → 干涸 → 再冲刷"。根因是三件事叠加：

1. **无限水源**（海）持续补水，而干涸的格下一 tick 又被重新填上；
2. 水**下落与水平流互斥**，于是洞底的水永远在"往旁边流"与"被上面填回来"之间摆；
3. CA 里没有"水面"这个概念 ⇒ 找不到稳定态。

所以本版换成**一次性灌注**（不做迭代演化）：玩家改动方块时，从扰动点**向上
找同列最近的水**，找到就沿垂直方向灌到非空气处为止。理由：

* 本项目**没有水桶**（玩家不能主动倒水），水只能由"改地形"驱动 ⇒
  触发次数极少（一次挖 = 一次灌注），**不需要每帧演化**；
* **可预测、可测试**：一根水柱，无震荡；
* **代价写清楚**：洞里**不会积水成面**（横向铺开与干涸都没做）——
  已知边界，见 `docs/phase2c_设计.md`。

## 状态不进存档（与光照同口径）

`levels` 可由「方块 + 源」完全重算（重放一次灌注即可）⇒ 存档仍是 v3。
⚠ 所以灌注**必须**用 `world.set_generated` 写（不记增量）——
用 `world.set` 会把水写进存档增量（几万格）。

## 源 = 生成时的水

`mark_sources` 在生成后扫一遍：所有水格都是**源**（海/湖是无限水源，MC 同款）。
"洞里有没有水"因此完全由**玩家有没有把地形挖通**决定 —— 这就是"洞穴与海打通"的
实现，而且**不需要改 `caves.py` 的生成**（洞初始无水，MC 同款）。
"""
from __future__ import annotations

from .blocks import AIR, WATER

__all__ = ['FluidSystem', 'TICK_BUDGET', 'MAX_FILL', 'can_enter', 'find_source']

#: 单次灌注的最大格数（**防呆上限**：世界高 64 ⇒ 正常最多 64 格；
#: 玩家在 500 格高的世界里灌水也不会跑飞）
MAX_FILL = 256

#: 每次玩家改动最多处理多少个扰动点（挖一格只激活 1 个；挖一大片会更多）
TICK_BUDGET = 64


def can_enter(world, x: int, y: int, z: int, allow_water: bool = False) -> bool:
    """水能不能流进这一格。

    `allow_water=True`（灌注用）：空气**或水**都可以 —— 灌注是"填满这一柱"，
    遇到已有水就说明下面已经是水柱了。
    """
    if y < 0 or y >= world.height:
        return False
    b = world.get(x, y, z)
    return b == AIR or (allow_water and b == WATER)


def find_source(world, sources: set, x: int, y: int, z: int):
    """从 `(x, y, z)` 往上找最近的水格，返回其 y（没有则 None）。

    只认**这一列**：水往四面铺开是 CA 的事，本版不做（见模块 docstring）。
    """
    for yy in range(max(0, int(y)), world.height):
        if (x, yy, z) in sources or world.get(x, yy, z) == WATER:
            return yy
    return None


class FluidSystem:
    """水的元状态（源 + 已灌注的流动水）。**不存方块**，只记"哪格是我们灌的"。"""

    __slots__ = ('sources', 'levels', 'active', 'ticks', 'poured')

    def __init__(self):
        #: 源水格 `(x,y,z)`：生成时标记，**永不改变**
        self.sources: set = set()
        #: 已灌注的流动水（level 恒为 1；这张表是为了"哪格是流动水"可查）
        self.levels: dict = {}
        #: 待处理的扰动点（玩家每次改动加一个）
        self.active: set = set()
        self.ticks = 0
        self.poured = 0

    # ------------------------------------------------------------ 标记/扰动
    def mark_sources(self, world) -> int:
        """生成后调用：把世界里的水格全部标成源。返回源格数。

        ⚠ **必须用 C 层的 `bytes.find`**：默认世界 419 万格、水约 8 万 ——
        逐格 `enumerate` 扫一遍要好几秒；`find` 扫 4KB 是微秒级，
        还能先用 `count` 为 0 整块跳过（绝大多数区块根本没水）。
        """
        n = 0
        pat = bytes([WATER])
        for (cx, cy, cz), buf in world.chunks.items():
            if buf.count(pat) == 0:
                continue
            wx0, wy0, wz0 = cx * 16, cy * 16, cz * 16
            i = buf.find(pat)
            while i >= 0:
                ly, lz, lx = (i // 256) % 16, (i // 16) % 16, i % 16
                self.sources.add((wx0 + lx, wy0 + ly, wz0 + lz))
                n += 1
                i = buf.find(pat, i + 1)
        return n

    def disturb(self, world, x: int, y: int, z: int):
        """玩家改了 `(x,y,z)` ⇒ 记一个扰动点（灌注在 `step` 里做）。

        **只记这一格**：玩家挖一格触发一柱灌注，挖一整条隧道会逐格触发
        ⇒ 水跟着玩家的挖通路径一路灌进去（不需要"从源头逐级激活"那套逻辑，
        也就不会有"漏激活 ⇒ 水灌一半"的 bug）。
        """
        self.active.add((x, y, z))

    # ------------------------------------------------------------ 灌注
    def _pour(self, world, x: int, y: int, z: int) -> int:
        """向上找水源，灌满它与扰动点之间的空隙。返回灌注格数。"""
        sy = find_source(world, self.sources, x, y, z)
        if sy is None:
            return 0
        lo = max(y, sy - 1 - MAX_FILL)
        n = 0
        for yy in range(sy - 1, lo - 1, -1):
            if (x, yy, z) in self.sources:
                break
            if not can_enter(world, x, yy, z, allow_water=True):
                break
            world.set_generated(x, yy, z, WATER)     # 不记增量（可由源重算）
            self.levels[(x, yy, z)] = 1
            n += 1
        return n

    def step(self, world, budget: int = TICK_BUDGET) -> int:
        """处理扰动点（灌注）。返回这一 tick 灌注的格数。"""
        if not self.active:
            return 0
        cur = sorted(self.active)                    # 排序 ⇒ 与插入顺序无关
        self.active = set()
        n = 0
        for (x, y, z) in cur[:max(1, int(budget))]:
            n += self._pour(world, x, y, z)
        if len(cur) > max(1, int(budget)):
            self.active.update(cur[max(1, int(budget)):])
        self.ticks += 1
        self.poured += n
        return n

    def repour_all(self, world) -> int:
        """读档后**重放**灌注（返回灌注格数）。

        为什么需要：灌注只在"玩家改动"时触发，而水本身不进存档 ⇒ 不重灌的话
        读档回来洞是干的（实测：读档后水量 0）。

        口径：**只重放玩家的改动点**（`world.edits` 里的那些格）。
        那些点已经在存档里（洞必然是玩家挖的），从它们向上找源 ⇒
        水域下的洞会被灌上，陆地上的洞找不到源自然不灌。
        比"扫全图找水源"便宜两个数量级（实测 1 万条 edits ≈ 0.3s），
        而且**精确**：不会把"玩家没碰过的自然洞穴"也灌满。

        ⚠ 初版扫"源的正下方是空气"——错在源在**水面**，正下方是海底地形，
        永远不是空气（实测只灌到 1 格）。
        """
        n = 0
        for (x, y, z) in list(world.edits):
            n += self._pour(world, x, y, z)
        self.poured += n
        return n

    # ------------------------------------------------------------ 查询
    def flowing_count(self) -> int:
        return len(self.levels)

    def stats(self) -> dict:
        return {'sources': len(self.sources), 'flowing': len(self.levels),
                'active': len(self.active), 'ticks': self.ticks,
                'poured': self.poured}
