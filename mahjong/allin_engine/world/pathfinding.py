"""寻路求解器 — 补齐 MapGraph / MapData 缺的加权最短路与网格 A*。

- GraphPathFinder：在 MapGraph 的节点邻接上做 BFS（无权）/ Dijkstra（加权）/ A*（带位置启发）。
- grid_astar：在 MapData 的字符网格上做网格 A*（4 或 8 连通）。

纯新增模块，不修改 allin_engine 任何既有代码。
"""

from __future__ import annotations

import heapq
import math
from collections import deque
from typing import Callable, Dict, List, Optional, Tuple

from allin_engine.world.map_graph import MapGraph
from allin_engine.world.map_data import MapData


# ─────────────────────────── 图寻路 ───────────────────────────
class GraphPathFinder:
    """在 MapGraph 上做最短路查询。

    用法：
        pf = GraphPathFinder(graph)
        path = pf.bfs("hub", "boss_room")                 # 无权 BFS（最快）
        path = pf.shortest_path("hub", "boss_room")       # 加权 Dijkstra
        path = pf.astar("hub", "boss_room", pos_fn=...)   # 带启发 A*
    """

    def __init__(self, graph: MapGraph, ignore_locks: bool = True):
        self.graph = graph
        self.ignore_locks = ignore_locks

    def _adjacency(self, start: str, goal: str) -> Dict[str, List[Tuple[str, float]]]:
        """构建 (邻居, 权重) 邻接表，跳过锁定的中间节点。"""
        adj: Dict[str, List[Tuple[str, float]]] = {}
        for nid, node in self.graph.nodes.items():
            if not self.ignore_locks and node.is_locked and nid not in (start, goal):
                continue
            neighbors: List[Tuple[str, float]] = []
            for nb in node.connections:
                tgt = self.graph.nodes.get(nb)
                if tgt is None:
                    continue
                if not self.ignore_locks and tgt.is_locked and nb not in (start, goal):
                    continue
                neighbors.append((nb, 1.0))
            adj[nid] = neighbors
        return adj

    def bfs(self, start: str, goal: str) -> Optional[List[str]]:
        """无权最短路径（BFS）。"""
        if start not in self.graph.nodes or goal not in self.graph.nodes:
            return None
        if start == goal:
            return [start]
        adj = self._adjacency(start, goal)
        prev = {start: None}
        q: deque = deque([start])
        while q:
            cur = q.popleft()
            if cur == goal:
                break
            for nb, _ in adj.get(cur, []):
                if nb not in prev:
                    prev[nb] = cur
                    q.append(nb)
        return self._reconstruct(prev, start, goal)

    def dijkstra(self, start: str, goal: str,
                 weight_fn: Optional[Callable[[str, str], float]] = None) -> Optional[List[str]]:
        """加权最短路（Dijkstra）。weight_fn(from_id, to_id) -> 权重。"""
        if start not in self.graph.nodes or goal not in self.graph.nodes:
            return None
        if start == goal:
            return [start]
        adj = self._adjacency(start, goal)
        dist: Dict[str, float] = {start: 0.0}
        prev: Dict[str, Optional[str]] = {start: None}
        heap = [(0.0, start)]
        while heap:
            d, cur = heapq.heappop(heap)
            if cur == goal:
                break
            if d > dist.get(cur, math.inf):
                continue
            for nb, base_w in adj.get(cur, []):
                w = weight_fn(cur, nb) if weight_fn else base_w
                nd = d + w
                if nd < dist.get(nb, math.inf):
                    dist[nb] = nd
                    prev[nb] = cur
                    heapq.heappush(heap, (nd, nb))
        return self._reconstruct(prev, start, goal)

    def shortest_path(self, start: str, goal: str,
                      weight_fn: Optional[Callable[[str, str], float]] = None) -> Optional[List[str]]:
        """加权最短路（Dijkstra 别名）。"""
        return self.dijkstra(start, goal, weight_fn)

    def astar(self, start: str, goal: str,
              pos_fn: Callable[[str], Tuple[float, float]],
              weight_fn: Optional[Callable[[str, str], float]] = None) -> Optional[List[str]]:
        """A*。pos_fn(node_id) -> (x, y) 提供启发坐标。"""
        if start not in self.graph.nodes or goal not in self.graph.nodes:
            return None
        if start == goal:
            return [start]
        adj = self._adjacency(start, goal)
        gx, gy = pos_fn(goal)

        def h(nid: str) -> float:
            x, y = pos_fn(nid)
            return math.hypot(x - gx, y - gy)

        g: Dict[str, float] = {start: 0.0}
        prev: Dict[str, Optional[str]] = {start: None}
        heap = [(h(start), 0.0, start)]
        while heap:
            f, d, cur = heapq.heappop(heap)
            if cur == goal:
                break
            if d > g.get(cur, math.inf):
                continue
            for nb, base_w in adj.get(cur, []):
                w = weight_fn(cur, nb) if weight_fn else base_w
                nd = d + w
                if nd < g.get(nb, math.inf):
                    g[nb] = nd
                    prev[nb] = cur
                    heapq.heappush(heap, (nd + h(nb), nd, nb))
        return self._reconstruct(prev, start, goal)

    @staticmethod
    def _reconstruct(prev: Dict[str, Optional[str]], start: str, goal: str) -> Optional[List[str]]:
        if goal not in prev:
            return None
        path: List[str] = []
        cur: Optional[str] = goal
        while cur is not None:
            path.append(cur)
            cur = prev[cur]
        path.reverse()
        return path


# ─────────────────────────── 网格 A* ───────────────────────────
def grid_astar(
    grid: MapData,
    start: Tuple[int, int],
    goal: Tuple[int, int],
    blocked: Optional[set] = None,
    walkable_fn: Optional[Callable[[int, int, str], bool]] = None,
    allow_diagonal: bool = False,
    heuristic: str = "manhattan",
) -> Optional[List[Tuple[int, int]]]:
    """在 MapData 字符网格上做 A*。

    参数：
        grid: MapData 实例
        start, goal: (col, row)
        blocked: 视为墙的字符集合（默认 {grid.fill_char}）
        walkable_fn: (col,row,char) -> bool，自定义可走判定（优先于 blocked）
        allow_diagonal: 是否允许斜向移动
        heuristic: "manhattan" | "octile" | "euclidean"
    返回：
        (col,row) 路径列表（含起终点）；无路返回 None
    """
    if not (grid.in_bounds(*start) and grid.in_bounds(*goal)):
        return None
    if blocked is None:
        blocked = {grid.fill_char}

    def is_walkable(c: int, r: int) -> bool:
        if walkable_fn is not None:
            return walkable_fn(c, r, grid.get(c, r))
        return grid.get(c, r) not in blocked

    sc, sr = start
    gc, gr = goal
    if not is_walkable(sc, sr) or not is_walkable(gc, gr):
        return None
    if start == goal:
        return [start]

    def h(c: int, r: int) -> float:
        dc, dr = abs(c - gc), abs(r - gr)
        if heuristic == "euclidean":
            return math.hypot(dc, dr)
        if heuristic == "octile":
            return max(dc, dr) + (math.sqrt(2) - 1.0) * min(dc, dr)
        return float(dc + dr)  # manhattan

    moves = [(1, 0), (-1, 0), (0, 1), (0, -1)]
    if allow_diagonal:
        moves = moves + [(1, 1), (1, -1), (-1, 1), (-1, -1)]

    g: Dict[Tuple[int, int], float] = {start: 0.0}
    prev: Dict[Tuple[int, int], Optional[Tuple[int, int]]] = {start: None}
    heap = [(h(sc, sr), 0.0, start)]
    while heap:
        f, d, (c, r) = heapq.heappop(heap)
        if (c, r) == goal:
            break
        if d > g.get((c, r), math.inf):
            continue
        for dc, dr in moves:
            nc, nr = c + dc, r + dr
            if not grid.in_bounds(nc, nr):
                continue
            if not is_walkable(nc, nr):
                continue
            # 对角防穿墙：相邻两正交格不能都是墙
            if dc != 0 and dr != 0:
                if not is_walkable(c + dc, r) or not is_walkable(c, r + dr):
                    continue
            step_cost = math.hypot(dc, dr)
            nd = d + step_cost
            if nd < g.get((nc, nr), math.inf):
                g[(nc, nr)] = nd
                prev[(nc, nr)] = (c, r)
                heapq.heappush(heap, (nd + h(nc, nr), nd, (nc, nr)))
    if goal not in prev:
        return None
    path: List[Tuple[int, int]] = []
    cur: Optional[Tuple[int, int]] = goal
    while cur is not None:
        path.append(cur)
        cur = prev[cur]
    path.reverse()
    return path
