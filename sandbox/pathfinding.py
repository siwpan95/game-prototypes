"""pathfinding.py — Dijkstra 地图（距离场）寻路，用于怪物导航。

算法来源：roguelike 社区「Dijkstra Map」范式
（gamecodeschool《Roguelike Tutorial》Part 7 / bracket-lib 的 DijkstraMap）。

核心思想（来自社区共识，胜于逐怪 A*）：
  - 每回合从「玩家位置」对整张地图做一次 BFS 洪水填充，
    得到每格到玩家的步数（距离场）。
  - 怪物只需看四邻格中数字最小者「下坡」，即沿最短路径走向玩家
    （绕墙、穿门、过走廊，像水填满洞穴一样绕过障碍）。
  - 同一张距离场「上坡」读即为逃跑路线：受伤怪物走数字最大者远离玩家。
  - 一次洪水，全怪共用，复杂度 O(W*H)，远优于每只怪各跑一次 A*。

因为每步代价均为 1，这里用 BFS（加权版本才是真正的 Dijkstra），
但社区仍沿用「Dijkstra Map」这一名称。
"""
from __future__ import annotations

from collections import deque
from typing import Callable, List, Tuple

# 不可达标记（被墙封闭或玩家无法到达的区域）
UNREACHABLE = 10 ** 9

# 四邻方向（与游戏其它模块保持一致：右/左/下/上）
_DIRS = ((1, 0), (-1, 0), (0, 1), (0, -1))


def compute_dijkstra(goal_x: int, goal_y: int,
                     walkable: Callable[[int, int], bool],
                     width: int, height: int) -> List[List[int]]:
    """从 (goal_x,goal_y) 洪水填充，返回 dist[y][x]（到目标的步数）。

    walkable(x,y) 返回 True 表示该格可通行（非墙）。
    被墙封闭或与目标不连通的格记为 UNREACHABLE。
    """
    dist: List[List[int]] = [[UNREACHABLE] * width for _ in range(height)]
    if not (0 <= goal_x < width and 0 <= goal_y < height):
        return dist
    if not walkable(goal_x, goal_y):
        return dist
    dist[goal_y][goal_x] = 0
    q: deque = deque([(goal_x, goal_y)])
    while q:
        x, y = q.popleft()
        d = dist[y][x]
        for dx, dy in _DIRS:
            nx, ny = x + dx, y + dy
            if (0 <= nx < width and 0 <= ny < height
                    and dist[ny][nx] == UNREACHABLE and walkable(nx, ny)):
                dist[ny][nx] = d + 1
                q.append((nx, ny))
    return dist


def step_downhill(x: int, y: int, dist: List[List[int]],
                  width: int, height: int,
                  forbidden: set) -> Tuple[int, int] | None:
    """返回从 (x,y) 朝玩家（距离更小）的下一步方向 (dx,dy)，无路返回 None。

    forbidden: 不可踏入的格集合（如其它怪物占据的格、玩家当前格）。
    仅在「存在更近邻居」时移动；否则视为已贴脸/卡住，返回 None。
    """
    best = dist[y][x]
    best_dir: Tuple[int, int] | None = None
    for dx, dy in _DIRS:
        nx, ny = x + dx, y + dy
        if not (0 <= nx < width and 0 <= ny < height):
            continue
        if (nx, ny) in forbidden:
            continue
        d = dist[ny][nx]
        if d < best:
            best = d
            best_dir = (dx, dy)
    return best_dir


def step_uphill(x: int, y: int, dist: List[List[int]],
                width: int, height: int,
                forbidden: set) -> Tuple[int, int] | None:
    """返回从 (x,y) 远离玩家（距离更大）的下一步方向 (dx,dy)，用于逃跑。

    forbidden: 不可踏入的格集合。若所有邻居都更近/不可走则原地不动。
    """
    cur = dist[y][x]
    best = cur
    best_dir: Tuple[int, int] | None = None
    for dx, dy in _DIRS:
        nx, ny = x + dx, y + dy
        if not (0 <= nx < width and 0 <= ny < height):
            continue
        if (nx, ny) in forbidden:
            continue
        d = dist[ny][nx]
        if d > best:
            best = d
            best_dir = (dx, dy)
    return best_dir


def clear_los(x0: int, y0: int, x1: int, y1: int,
              blocked: Callable[[int, int], bool]) -> bool:
    """Bresenham 视线判定：(x0,y0)→(x1,y1) 之间是否被墙/障碍遮挡。

    用于远程怪物「有墙挡着就打不到」的判定。端点自身不计入遮挡。
    """
    dx = abs(x1 - x0)
    dy = abs(y1 - y0)
    sx = 1 if x0 < x1 else -1
    sy = 1 if y0 < y1 else -1
    err = dx - dy
    cx, cy = x0, y0
    while True:
        if (cx, cy) == (x1, y1):
            return True
        if (cx, cy) != (x0, y0) and blocked(cx, cy):
            return False
        e2 = 2 * err
        if e2 > -dy:
            err -= dy
            cx += sx
        if e2 < dx:
            err += dx
            cy += sy
