# -*- coding: utf-8 -*-
"""世界源 —— 地牢从哪来（**内置 / 超级引擎**两种实现，接口相同）。

内置源（默认）
--------------
沿用旧版行为：``size x size`` 网格，每格随机为空地/怪物/宝藏/陷阱，
再随机放一个出口且保证不在出生点。**纯标准库、行为与旧版逐项一致**。

超级引擎源
----------
用 worldbuilder 的**真实地牢生成**（房间 + 走廊）抽出**可解关卡图**
（nodes / edges / keys / entrance / boss）。游戏不再是"随机格子"，而是
一间间有连通关系的房间：

* ``entrance`` 是出生房间，``boss`` 作为出口（最远房间）；
* 相邻的房间 = 图上的一条边 ⇒ 移动选项由**图**决定，不是网格四方向；
* ``keys`` 保留在图里（本作暂不启用锁钥，但数据已就绪 —— 见 README 边界）。
"""

from __future__ import annotations

import random
from typing import Any, Dict, List, Optional, Tuple

from . import engine as _eng

__all__ = [
    "ROOM_EMPTY", "ROOM_MONSTER", "ROOM_TREASURE", "ROOM_TRAP", "ROOM_EXIT",
    "Room", "World", "BuiltinWorldSource", "SuperEngineWorldSource",
    "make_world_source",
]

ROOM_EMPTY = "空地"
ROOM_MONSTER = "怪物"
ROOM_TREASURE = "宝藏"
ROOM_TRAP = "陷阱"
ROOM_EXIT = "出口"


class Room:
    """一间房：编号 + 类型 + 名字 + 邻居。"""

    __slots__ = ("rid", "kind", "name", "neighbors", "pos")

    def __init__(self, rid: str, kind: str, name: str = "",
                 neighbors: Optional[List[str]] = None, pos: Tuple[int, int] = (0, 0)):
        self.rid = rid
        self.kind = kind
        self.name = name or rid
        self.neighbors = list(neighbors or [])
        self.pos = pos

    def __repr__(self):
        return f"<Room {self.rid} {self.kind} →{self.neighbors}>"


class World:
    """一局的地牢：房间表 + 起点 + 出口 + 元数据（给 UI 展示用）。"""

    __slots__ = ("rooms", "start", "exit_id", "meta", "grid_mode", "size")

    def __init__(self, rooms: Dict[str, Room], start: str, exit_id: str,
                 meta: Optional[Dict[str, Any]] = None,
                 grid_mode: bool = False, size: int = 0):
        self.rooms = rooms
        self.start = start
        self.exit_id = exit_id
        self.meta = meta or {}
        self.grid_mode = grid_mode
        self.size = size

    def neighbors_of(self, rid: str) -> List[str]:
        return self.rooms[rid].neighbors

    def kind_of(self, rid: str) -> str:
        return self.rooms[rid].kind


class BuiltinWorldSource:
    """内置世界源（默认）：网格随机，行为与旧版一致。"""

    name = "builtin"

    def __init__(self, size: int = 4):
        self.size = size

    def build(self, seed: Optional[int] = None, **kw) -> World:
        rng = random.Random(seed) if seed is not None else random
        size = self.size
        types = [ROOM_EMPTY, ROOM_MONSTER, ROOM_TREASURE, ROOM_TRAP]
        # **逐字复刻旧版 create_map 的取数顺序**，保证同种子下网格逐格一致：
        #   ① 铺满随机 → ② 掷出口并落 EXIT → ③ 出生点置 EMPTY
        #   → ④ 若出口撞上出生点，循环重掷并再落 EXIT
        # （若把"重掷"挪到赋值之前，随机数消耗顺序就变了，同种子会分叉）
        grid = [[rng.choice(types) for _ in range(size)] for _ in range(size)]
        exit_pos = (rng.randint(0, size - 1), rng.randint(0, size - 1))
        start = (0, 0)
        # 重掷到不撞出生点为止，**只落一次** EXIT。
        # 旧版是在循环里反复 ``grid[exit] = EXIT``：一旦某次重掷又落回 (0,0)，
        # 就会把出生点覆写成出口，并且留下**两个出口**（与它自己那句
        # "出生点设为空地，保证安全"的注释相悖）。这里按注释意图修正。
        while exit_pos == start:
            exit_pos = (rng.randint(0, size - 1), rng.randint(0, size - 1))
        grid[exit_pos[0]][exit_pos[1]] = ROOM_EXIT
        grid[start[0]][start[1]] = ROOM_EMPTY

        rooms: Dict[str, Room] = {}
        for r in range(size):
            for c in range(size):
                rid = f"{r},{c}"
                nb = []
                if r > 0:
                    nb.append(f"{r-1},{c}")
                if r < size - 1:
                    nb.append(f"{r+1},{c}")
                if c > 0:
                    nb.append(f"{r},{c-1}")
                if c < size - 1:
                    nb.append(f"{r},{c+1}")
                rooms[rid] = Room(rid, grid[r][c], pos=(r, c), neighbors=nb)
        return World(rooms, start="0,0", exit_id=f"{exit_pos[0]},{exit_pos[1]}",
                     meta={"source": "builtin", "grid": grid}, grid_mode=True,
                     size=size)


class SuperEngineWorldSource:
    """超级引擎世界源：worldbuilder 的真实地牢 + 可解关卡图。"""

    name = "superengine"

    def __init__(self, engine, width: int = 32, height: int = 24, rooms: int = 6):
        self.engine = engine
        self.width = width
        self.height = height
        self.rooms = rooms

    def build(self, seed: Optional[int] = None, **kw) -> World:
        wb = self.engine.worldbuilder()
        s = int(seed) if seed is not None else 0
        d = wb.generate_dungeon(self.width, self.height, rooms=self.rooms, seed=s)
        graph = wb.dungeon_graph(d["grid"], locks=0, loops=2, seed=s)

        nodes = graph["nodes"]
        edges = graph["edges"]
        entrance = graph.get("entrance") or (nodes[0]["id"] if nodes else "room-00")
        boss = graph.get("boss") or (nodes[-1]["id"] if nodes else entrance)

        # 邻接表
        adj: Dict[str, List[str]] = {n["id"]: [] for n in nodes}
        for e in edges:
            a, b = e.get("a"), e.get("b")
            if a in adj and b in adj:
                if b not in adj[a]:
                    adj[a].append(b)
                if a not in adj[b]:
                    adj[b].append(a)

        # 房间类型：入口恒空地，boss 房做出口，其余按权重随机（不含出口）
        rng = random.Random(s)
        pool = [ROOM_EMPTY, ROOM_MONSTER, ROOM_MONSTER, ROOM_TREASURE, ROOM_TRAP]
        rooms: Dict[str, Room] = {}
        for n in nodes:
            rid = n["id"]
            if rid == boss:
                kind = ROOM_EXIT
            elif rid == entrance:
                kind = ROOM_EMPTY
            else:
                kind = rng.choice(pool)
            rooms[rid] = Room(rid, kind, name=n.get("name") or rid,
                              neighbors=adj.get(rid, []))
        return World(rooms, start=entrance, exit_id=boss,
                     meta={"source": "superengine",
                           "graph": {"nodes": len(nodes), "edges": len(edges),
                                     "keys": len(graph.get("keys", []))}},
                     grid_mode=False)


def make_world_source(kind: str, engine=None, size: int = 4, rooms: int = 6,
                      width: int = 32, height: int = 24):
    """工厂：按名字造世界源；``kind='super'`` 但引擎不可用时**回退**内置。

    参数按名称分流（``size`` 归内置、``rooms/width/height`` 归引擎），
    这样回退时不会把引擎专属参数误传给内置源。
    """
    if kind == "super" and engine is not None and _eng.ready(engine):
        return SuperEngineWorldSource(engine, width=width, height=height, rooms=rooms)
    return BuiltinWorldSource(size=size)
