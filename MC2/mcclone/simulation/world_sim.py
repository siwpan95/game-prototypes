# -*- coding: utf-8 -*-
"""simulation.world_sim — 温度扩散 / 水/岩浆流动 元胞自动机（chunk 脏标记，≤20Hz）。

WorldSim：
  - 温度场：岩浆格恒为 lava_temp（热源），其余向 4 邻均值靠拢 diffusion。
  - 水流动：每 sim tick 每水格至多移动 1 步（下 → 下斜 → 同层两侧），
           固定优先级、无 RNG，保证确定性。
  - 岩浆流动：同水规则，但仅当 tick_count % lava_move_interval == 0 时移动（更慢）。
  - 脏 chunk：仅重算含流体/热源/受热邻格的 chunk，满足 ≤20Hz 预算。
  - 节流：tick(dt) 内部累加器，仅当累计 >= 1/sim_hz 才跑一步（≤20Hz）。

确定性：仅 world.set/get + 固定优先级遍历，不引入 RNG。可 headless 断言。
"""

from __future__ import annotations

from typing import Dict, List, Set, Tuple

from mcclone.core.geometry import clamp
from mcclone.core.block_registry import AIR
from .cell import CellState, diffuse_step
from . import SimConfig
from .overlays import LayerOverlay, build_layer_overlay


class WorldSim:
    """温度/流体模拟核心。"""

    def __init__(self, world, registry, cfg: "SimConfig | None" = None) -> None:
        self.world = world
        self.registry = registry
        self.cfg = cfg if cfg is not None else SimConfig()
        # 温度场：仅存非环境温度（稀疏），缺失视为 ambient_temp。
        self._temp: Dict[Tuple[int, int, int], float] = {}
        # 脏 chunk 集合（仅这些被重算）。
        self._dirty_chunks: Set[Tuple[int, int, int]] = set()
        self._tick_count: int = 0
        self._acc: float = 0.0
        self._init_state()

    # ── 初始化 ──
    def _init_state(self) -> None:
        """扫描世界：岩浆格温度钉死 + 标记含流体/热源的 chunk 为脏。"""
        for (x, y, z), bid in self.world._blocks.items():
            if bid == self.cfg.lava_id:
                self._temp[(x, y, z)] = self.cfg.lava_temp
                self._mark_chunk_dirty(x, y, z)
            elif bid == self.cfg.water_id:
                self._mark_chunk_dirty(x, y, z)

    # ── 脏标记 ──
    def _mark_chunk_dirty(self, x: int, y: int, z: int) -> None:
        """标 (x,y,z) 所在 chunk + 其 3×3×3 邻 chunk 为脏。"""
        cs = self.cfg.chunk_size
        cx, cy, cz = x // cs, y // cs, z // cs
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for dz in (-1, 0, 1):
                    self._dirty_chunks.add((cx + dx, cy + dy, cz + dz))

    def mark_dirty_around(self, x: int, y: int, z: int) -> None:
        """标记 (x,y,z) 所在 chunk 及其邻 chunk 为脏（供流体/温度重算）。"""
        self._mark_chunk_dirty(x, y, z)

    @property
    def dirty_chunks(self) -> Set[Tuple[int, int, int]]:
        """当前脏 chunk 集合（只读视图）。"""
        return self._dirty_chunks

    # ── 温度扩散 ──
    def _neighbors4(self, x: int, y: int, z: int) -> List[Tuple[int, int, int]]:
        """返回同层 4 邻坐标列表。"""
        return [
            (x - 1, y, z), (x + 1, y, z),
            (x, y - 1, z), (x, y + 1, z),
        ]

    def _diffuse_cell(self, x: int, y: int, z: int, bid: int) -> None:
        """处理单格温度：岩浆恒热源；其余向 4 邻均值靠拢（钳制）。"""
        if bid == self.cfg.lava_id:
            self._temp[(x, y, z)] = self.cfg.lava_temp
            self._mark_chunk_dirty(x, y, z)
            return
        old = self._temp.get((x, y, z), self.cfg.ambient_temp)
        ns = [self._temp.get(n, self.cfg.ambient_temp)
              for n in self._neighbors4(x, y, z)]
        new = diffuse_step(old, ns, self.cfg.diffusion,
                           0.0, self.cfg.lava_temp)
        if abs(new - old) > 1e-6:
            self._temp[(x, y, z)] = new
            self._mark_chunk_dirty(x, y, z)
        elif old != self.cfg.ambient_temp:
            self._temp[(x, y, z)] = new

    # ── 流体移动 ──
    def _flow_target(self, x: int, y: int, z: int,
                     moved_dst: Set[Tuple[int, int, int]]
                     ) -> "Tuple[int, int, int] | None":
        """按固定优先级返回流体可流入的空格（下 → 下斜 → 同层两侧）。

        疑点 B 校正（水的同层侧流约束）：
          水向同层两侧流动时，除既有的 in_bounds / moved_dst / AIR 检查外，
          额外要求「侧下方 (x±1, y-1, z) 有支撑」——即该侧下方越界（宫外视为
          有支撑）或不是 AIR（实体方块）。这样水不会向无支撑的悬空侧（侧下方为
          AIR 的悬崖边）扩一格形成瞬态过梁（overhang）；而对有支撑的平地/盆地
          仍正常横向铺平。

          注意：架构文档 docs/architecture_m3.md §7.3 第 3 条字面写「该侧下方
          亦为 AIR」，与此校正自相矛盾。本实现以「侧下方须有支撑（非 AIR）」为准，
          这是消除过梁 bug 的唯一正确方向。
        """
        # 正下：保持原逻辑完全不变
        d_below = (x, y - 1, z)
        if self.world.in_bounds(*d_below) and d_below not in moved_dst \
                and self.world.get(*d_below) == AIR:
            return d_below
        # 下斜（两侧斜下）：保持原逻辑完全不变
        for nx in (x - 1, x + 1):
            d_diag = (nx, y - 1, z)
            if not self.world.in_bounds(*d_diag):
                continue
            if d_diag in moved_dst:
                continue
            if self.world.get(*d_diag) == AIR:
                return d_diag
        # 同层两侧：疑点 B 校正——额外要求侧下方有支撑（越界视为有支撑）
        for nx in (x - 1, x + 1):
            side = (nx, y, z)
            if not self.world.in_bounds(*side):
                continue
            if side in moved_dst:
                continue
            if self.world.get(*side) != AIR:
                continue
            # 侧下方 (nx, y-1, z) 有支撑才允许横向扩：越界或 NOT AIR 均算有支撑
            below = (nx, y - 1, z)
            below_supported = (
                not self.world.in_bounds(*below)
                or self.world.get(*below) != AIR
            )
            if below_supported:
                return side
        return None

    # ── 单步 ──
    def _step(self) -> None:
        """执行一个 sim tick（仅遍历脏 chunk）。"""
        self._tick_count += 1
        chunks = list(self._dirty_chunks)
        self._dirty_chunks.clear()
        cs = self.cfg.chunk_size
        lava_move = (self._tick_count % self.cfg.lava_move_interval == 0)
        moves: List[Tuple[Tuple[int, int, int], Tuple[int, int, int], int]] = []
        moved_dst: Set[Tuple[int, int, int]] = set()
        for (cx, cy, cz) in chunks:
            x0, x1 = cx * cs, min((cx + 1) * cs, self.world.width)
            y0, y1 = cy * cs, min((cy + 1) * cs, self.world.height)
            z0, z1 = cz * cs, min((cz + 1) * cs, self.world.depth)
            for z in range(z0, z1):
                for y in range(y0, y1):
                    for x in range(x0, x1):
                        bid = self.world.get(x, y, z)
                        self._diffuse_cell(x, y, z, bid)
                        if bid == self.cfg.water_id:
                            d = self._flow_target(x, y, z, moved_dst)
                            if d is not None:
                                moves.append(((x, y, z), d, self.cfg.water_id))
                                # Bug A 修复：标记目标已占，防同 tick 内两流体抢同格丢质量
                                moved_dst.add(d)
                        elif bid == self.cfg.lava_id:
                            if lava_move:
                                d = self._flow_target(x, y, z, moved_dst)
                                if d is not None:
                                    moves.append(((x, y, z), d,
                                                  self.cfg.lava_id))
                                    # Bug A 修复：标记目标已占，防同 tick 内两流体抢同格丢质量
                                    moved_dst.add(d)
        # 应用移动（先收集后应用，避免同步干扰）
        for (s, d, fid) in moves:
            self.world.set(s[0], s[1], s[2], AIR)
            self.world.set(d[0], d[1], d[2], fid)
            self._mark_chunk_dirty(s[0], s[1], s[2])
            self._mark_chunk_dirty(d[0], d[1], d[2])

    # ── 节流入口 ──
    def tick(self, dt: float) -> None:
        """累加器节流：仅当累计 >= 1/sim_hz 才跑一步（≤20Hz）。"""
        self._acc += dt
        step = 1.0 / self.cfg.sim_hz
        while self._acc >= step:
            self._acc -= step
            self._step()

    # ── 读取接口 ──
    def get_temperature(self, x: int, y: int, z: int) -> float:
        """读取 (x,y,z) 温度（缺失返回 ambient_temp）。"""
        return self._temp.get((x, y, z), self.cfg.ambient_temp)

    def get_water(self, x: int, y: int, z: int) -> bool:
        """读取 (x,y,z) 是否为水。"""
        return self.world.get(x, y, z) == self.cfg.water_id

    def get_lava(self, x: int, y: int, z: int) -> bool:
        """读取 (x,y,z) 是否为岩浆。"""
        return self.world.get(x, y, z) == self.cfg.lava_id

    # ── 覆盖层快照 ──
    def snapshot_overlays(self, z: int) -> LayerOverlay:
        """生成第 z 层的覆盖层快照（温度/水/岩浆）。"""
        return build_layer_overlay(self.world, self, z, self.cfg)
