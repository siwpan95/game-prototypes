# -*- coding: utf-8 -*-
"""无限区块网格管理器：按需生成、远处卸载、世界坐标查询。"""
import math
import random

from ..config import (
    CHUNK_CLEAN_RANGE,
    CHUNK_PRELOAD_RANGE,
    CHUNK_SIZE,
    DARK_ROOM_TEMPLATES,
)
from .pool import _ALL_TEMPLATES, _DIR_DELTA, _OPPOSITE
from .templates import make_room_cross

# 模板字符 → 格值 查找表（'.':0 空  '#':1 墙  'C':12 传送门）
_CELL_CODES = {
    '.': 0, '#': 1,
    '2': 2, '3': 3, '4': 4, '5': 5, '6': 6,
    '7': 7, '8': 8, '9': 9, 'A': 10, 'B': 11, 'C': 12,
}

class WorldMap:
    """
    管理无限延伸的区块网格。
    区块坐标 (cx, cy)，世界坐标 = (cx*CHUNK_SIZE + local_x, cy*CHUNK_SIZE + local_y)。
    
    策略：玩家在哪，预加载周围区块；走远了的区块卸载。
    未加载区块cell()返回1（墙），防止空气墙。
    """
    def __init__(self, seed=None):
        self._rng = random.Random(seed or random.randint(0, 2**32))
        self._chunks: dict[tuple[int,int], list[str]] = {}   # (cx,cy) -> 21行字符串
        self._exits:  dict[tuple[int,int], set[str]]  = {}   # (cx,cy) -> {'N','S','E','W'}子集
        self._template_names: dict[tuple[int,int], str] = {} # (cx,cy) -> 模板函数名（暗室判定用）
        # 生成起始区块（四向出口）
        self._generate_chunk((0, 0), required_exits={'N','S','E','W'})

    def find_safe_spawn(self, cx, cy):
        """寻找安全出生点：空地、远离墙壁、周围无危险"""
        # 优先检查当前区块，找不到则检查周围区块
        for check_cx, check_cy in [(cx, cy)] + [(cx + dx, cy + dy) for dx in (-1, 0, 1) for dy in (-1, 0, 1) if (dx, dy) != (0, 0)]:
            spawn = self._find_spawn_in_chunk(check_cx, check_cy)
            if spawn is not None:
                return spawn
        # 最终回退：区块中心
        return (cx * CHUNK_SIZE + 10.5, cy * CHUNK_SIZE + 10.5)
    
    def _find_spawn_in_chunk(self, cx, cy):
        """在指定区块内寻找安全出生点"""
        chunk = self._chunks.get((cx, cy))
        if chunk is None:
            self._generate_chunk((cx, cy))
            chunk = self._chunks.get((cx, cy))
        if chunk is None:
            return None
        center = CHUNK_SIZE // 2
        
        def _check_cell(lx, ly):
            """检查格子是否适合作为出生点"""
            if not (0 <= lx < CHUNK_SIZE and 0 <= ly < CHUNK_SIZE):
                return False
            ch = chunk[ly][lx]
            if ch != '.':  # 必须为空地
                return False
            # 检查周围 5x5 范围内的危险和墙壁
            for dy2 in range(-2, 3):
                for dx2 in range(-2, 3):
                    nx, ny = lx + dx2, ly + dy2
                    if 0 <= nx < CHUNK_SIZE and 0 <= ny < CHUNK_SIZE:
                        neighbor = chunk[ny][nx]
                        # 危险类型：墙壁(1)、红色警示区(3)、酸液池(5)、传送门(C)
                        if neighbor in ('#', '3', '5', 'C'):
                            return False
            return True
        
        # 螺旋向外搜索，优先中心附近
        for radius in range(6):
            for dy in range(-radius, radius + 1):
                for dx in range(-radius, radius + 1):
                    if abs(dx) != radius and abs(dy) != radius:
                        continue
                    lx, ly = center + dx, center + dy
                    if _check_cell(lx, ly):
                        return (cx * CHUNK_SIZE + lx + 0.5, cy * CHUNK_SIZE + ly + 0.5)
        
        # 回退：找任意空地（不检查周围）
        for ly in range(CHUNK_SIZE):
            for lx in range(CHUNK_SIZE):
                if chunk[ly][lx] == '.':
                    return (cx * CHUNK_SIZE + lx + 0.5, cy * CHUNK_SIZE + ly + 0.5)
        return None

    # ── 出口查询 ──
    def _has_exit(self, cx, cy, direction) -> bool:
        return direction in self._exits.get((cx, cy), set())

    # ── 区块生成 ──
    def _generate_chunk(self, coord, required_exits=None):
        if coord in self._chunks:
            return
        cx, cy = coord

        # 由相邻区块推断必需出口
        forced = set(required_exits or [])
        for d, (dx, dy) in _DIR_DELTA.items():
            nb = (cx + dx, cy + dy)
            if nb in self._exits and _OPPOSITE[d] in self._exits[nb]:
                forced.add(d)

        # 从模板库中筛选并随机选择
        exits = self._pick_exits(forced, coord)
        template_fn = self._pick_template(exits)
        grid = template_fn()
        self._chunks[coord] = grid
        self._exits[coord]  = set(exits)
        # 记录模板函数名（用于暗室判定）
        self._template_names[coord] = template_fn.__name__

    def _pick_exits(self, forced, coord):
        """在 forced 基础上随机扩充出口（确保至少有一条路回来）。

        随机扩充必须额外检查：**若某方向的邻居已生成且没有声明反向出口，
        则该方向不能开** —— 否则会产生"单边出口"（玩家走出去撞墙）。
        forced 来自已生成邻居的反向声明，天然互连，无需检查。
        """
        exits = set(forced)
        cx, cy = coord

        def _ok(d):
            nb = (cx + _DIR_DELTA[d][0], cy + _DIR_DELTA[d][1])
            return nb not in self._exits or _OPPOSITE[d] in self._exits[nb]

        # 随机添加额外出口
        for d in ['N', 'S', 'E', 'W']:
            if d not in exits and _ok(d) and self._rng.random() < 0.45:
                exits.add(d)
        # 保证至少2个出口（只从"不会造死路"的方向里补）
        pool = [d for d in ['N', 'S', 'E', 'W'] if d not in exits and _ok(d)]
        while len(exits) < 2 and pool:
            d = self._rng.choice(pool)
            pool.remove(d)
            exits.add(d)
        return frozenset(exits)

    def _pick_template(self, exits):
        """从模板库中找最匹配的模板，优先精确匹配"""
        if exits in _ALL_TEMPLATES:
            return self._rng.choice(_ALL_TEMPLATES[exits])
        # 找超集（模板出口包含所有必需出口的）
        candidates = []
        for tmpl_exits, fns in _ALL_TEMPLATES.items():
            if exits.issubset(tmpl_exits):
                candidates.extend(fns)
        if candidates:
            return self._rng.choice(candidates)
        # 兜底：十字走廊
        return make_room_cross

    # ── 区块按需生成 + 远处卸载 ──
    def ensure_neighbors(self, cx: int, cy: int):
        """确保 (cx,cy) 及其预加载范围区块已生成，并卸载远处区块"""
        for dcy in range(-CHUNK_PRELOAD_RANGE, CHUNK_PRELOAD_RANGE + 1):
            for dcx in range(-CHUNK_PRELOAD_RANGE, CHUNK_PRELOAD_RANGE + 1):
                nb = (cx + dcx, cy + dcy)
                if nb not in self._chunks:
                    self._generate_chunk(nb)
        self._cleanup_distant_chunks(cx, cy)
    
    def _cleanup_distant_chunks(self, cx: int, cy: int):
        """卸载距离玩家超过 CHUNK_CLEAN_RANGE 的区块"""
        to_remove = []
        for chunk_coord in self._chunks.keys():
            dx = abs(chunk_coord[0] - cx)
            dy = abs(chunk_coord[1] - cy)
            if dx > CHUNK_CLEAN_RANGE or dy > CHUNK_CLEAN_RANGE:
                to_remove.append(chunk_coord)
        for coord in to_remove:
            del self._chunks[coord]
            if coord in self._exits:
                del self._exits[coord]
            if coord in self._template_names:
                del self._template_names[coord]

    # ── 世界坐标→格值 ──
    def cell(self, wx: float, wy: float) -> int:
        """返回世界坐标 (wx,wy) 处的格值：
        0=空  1=墙  2=发光柱  3=红色装饰  4=金色装饰
        5=绿色植被  6=紫色能量  7=橙色光源  8=灰色碎石  9=科技装饰
        A=蓝色水晶  B=紫水晶
        
        注意：未生成的区块返回1（墙壁），阻止玩家和射线进入虚空。
        """
        cx = int(math.floor(wx / CHUNK_SIZE))
        cy = int(math.floor(wy / CHUNK_SIZE))
        # 修复：使用相对坐标计算，避免 int() 对负数截断导致的错误
        lx = int(wx - cx * CHUNK_SIZE)
        ly = int(wy - cy * CHUNK_SIZE)
        # 边界夹紧
        lx = max(0, min(CHUNK_SIZE - 1, lx))
        ly = max(0, min(CHUNK_SIZE - 1, ly))
        chunk = self._chunks.get((cx, cy))
        if chunk is None:
            return 1   # 未生成区块视为墙壁，防止空气墙
        ch = chunk[ly][lx]
        return _CELL_CODES.get(ch, 1)

    # ── 当前区块坐标 ──
    @staticmethod
    def world_to_chunk(wx: float, wy: float) -> tuple[int, int]:
        return (int(math.floor(wx / CHUNK_SIZE)),
                int(math.floor(wy / CHUNK_SIZE)))

    # ── 已生成区块列表 ──
    def generated_chunks(self):
        return list(self._chunks.keys())

    # ── 暗室判定 ──
    def is_dark_room(self, cx: int, cy: int) -> bool:
        """判断指定区块是否为暗室（基于生成时使用的模板函数名）"""
        # 首先检查模板名标记
        template_name = self._template_names.get((cx, cy))
        if template_name and template_name in DARK_ROOM_TEMPLATES:
            return True
        # 备用方案：如果区块中有少量发光柱且无大面积空地，视为暗室
        chunk = self._chunks.get((cx, cy))
        if chunk is None:
            return False
        glow_count = 0
        open_count = 0
        for row in chunk:
            for ch in row:
                if ch == '2':
                    glow_count += 1
                elif ch == '.':
                    open_count += 1
        # 暗室特征：发光柱少且空地比例较低
        if glow_count <= 4 and open_count < 80:
            return True
        return False
