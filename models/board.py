"""Board - 三维坐标棋盘容器，底层由引擎 ECS World 承载。

坐标 Pos = (layer, row, col)，layer 0 为最底层。
交叉堆叠模型（标准上海麻将）：
  上层牌 (l+1, r, c) 压在 4 张下层牌 (l, r,c)/(l, r,c+1)/(l, r+1,c)/(l, r+1,c+1) 之上。
  故牌 (l, r, c) 被遮挡，当且仅当 layer l+1 存在 (l+1, r-1,c-1)/(l+1, r-1,c)/(l+1, r,c-1)/(l+1, r,c)。

深度 ECS 化：每张牌是引擎 World 中的一个 Entity，携带 `Tile`（本身即 Component）
与 `PositionComponent`（坐标）。Board 是 World 的适配器，对外 API 与旧版完全一致，
因此 services / views 无需改动即可运行在 ECS 之上。
"""
from dataclasses import dataclass, field
from typing import Dict, Iterator, List, Optional, Tuple

from alloy.core import Entity, World

from .components import Pos, PositionComponent
from .tile import Tile


class Board:
    """棋盘数据：坐标 -> 引擎 Entity（Entity 上挂 Tile + PositionComponent）。

    None 表示该槽位曾被占、现已消除（保留槽位以维持坐标稳定）。
    """

    def __init__(self) -> None:
        self.world: World = World()
        # 坐标 -> Entity 索引（O(1) 按坐标查询/删除）
        self._slots: Dict[Pos, Optional[Entity]] = {}
        self.max_layer: int = 0
        self.rows: int = 0
        self.cols: int = 0

    # ---- 槽位管理 ------------------------------------------------
    def place(self, pos: Pos, tile: Tile) -> Entity:
        l, r, c = pos
        ent = self.world.create_entity()
        ent.add(tile)                        # Tile 本身即 Component
        ent.add(PositionComponent(l, r, c))
        self._slots[pos] = ent
        self.max_layer = max(self.max_layer, l)
        self.rows = max(self.rows, r + 1)
        self.cols = max(self.cols, c + 1)
        return ent

    def reserve(self, pos: Pos) -> None:
        """预留空槽位（布局生成时占位用）。"""
        l, r, c = pos
        if pos not in self._slots:
            self._slots[pos] = None
        self.max_layer = max(self.max_layer, l)
        self.rows = max(self.rows, r + 1)
        self.cols = max(self.cols, c + 1)

    def get(self, pos: Pos) -> Optional[Tile]:
        ent = self._slots.get(pos)
        return ent.get(Tile) if ent is not None else None

    def remove(self, pos: Pos) -> Optional[Tile]:
        ent = self._slots.get(pos)
        if ent is None:
            return None
        tile = ent.get(Tile)
        self.world.remove_entity(ent.id)
        self._slots[pos] = None
        return tile

    def restore(self, pos: Pos, tile: Tile) -> Entity:
        return self.place(pos, tile)

    # ---- 查询 ----------------------------------------------------
    def occupied_positions(self) -> List[Pos]:
        """当前仍有牌的坐标（按 layer 降序、row、col 排序，便于自上而下绘制）。"""
        out = [p for p, e in self._slots.items() if e is not None]
        out.sort(key=lambda p: (-p[0], p[1], p[2]))
        return out

    def remaining(self) -> int:
        return sum(1 for e in self._slots.values() if e is not None)

    def all_slots(self) -> List[Pos]:
        return list(self._slots.keys())

    def is_empty(self) -> bool:
        return self.remaining() == 0

    def copy_structure(self) -> "Board":
        """复制空结构（同槽位、无牌），用于洗牌保留布局。"""
        b = Board()
        b.max_layer = self.max_layer
        b.rows = self.rows
        b.cols = self.cols
        b._slots = {p: None for p in self._slots}
        return b
