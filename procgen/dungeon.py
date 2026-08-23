"""地牢生成：随机房间 + L 形走廊，返回网格与房间信息。"""
from __future__ import annotations

import warnings

import numpy as np


def generate_dungeon(width: int = 48, height: int = 32, rooms: int = 8,
                     seed: int = 0) -> dict:
    """生成简单地牢。

    返回：
        {
          'grid': 二维 int8 数组 (height, width)，0=墙 1=地,
          'rooms': [{'x','y','w','h','cx','cy'}, ...],
          'connections': [(room_i, room_j), ...],
        }
    """
    if width < 8 or height < 8:
        raise ValueError(f"地牢尺寸过小，至少需要 8x8，收到 {width}x{height}")
    if rooms < 1:
        raise ValueError("rooms 必须 >= 1")

    rng = np.random.RandomState(seed)
    grid = np.zeros((height, width), dtype=np.int8)

    # 房间尺寸上限受网格约束，避免出现 randint(low>=high) 的 ValueError
    w_max = min(10, width - 2)
    h_max = min(8, height - 2)

    placed = []
    attempts = 0
    while len(placed) < rooms and attempts < rooms * 20:
        attempts += 1
        w = rng.randint(4, w_max)
        h = rng.randint(4, h_max)
        x = rng.randint(1, width - w - 1)
        y = rng.randint(1, height - h - 1)
        # 简单重叠检测（允许轻微相邻）
        overlap = any(not (x + w < r['x'] - 1 or x > r['x'] + r['w'] + 1 or
                           y + h < r['y'] - 1 or y > r['y'] + r['h'] + 1)
                      for r in placed)
        if overlap:
            continue
        room = {'x': x, 'y': y, 'w': w, 'h': h,
                'cx': x + w // 2, 'cy': y + h // 2}
        placed.append(room)
        grid[y:y + h, x:x + w] = 1

    if len(placed) < rooms:
        warnings.warn(
            f"仅放置 {len(placed)}/{rooms} 个房间（空间不足或重试次数耗尽）",
            stacklevel=2,
        )

    connections = []
    for i in range(1, len(placed)):
        a, b = placed[i - 1], placed[i]
        _carve_corridor(grid, a['cx'], a['cy'], b['cx'], b['cy'])
        connections.append((i - 1, i))

    return {'grid': grid, 'rooms': placed, 'connections': connections}


def _carve_corridor(grid, x1, y1, x2, y2):
    """L 形走廊：先水平后垂直（也可先垂后水，简单交替）。"""
    h_dir = 1 if x2 >= x1 else -1
    for x in range(x1, x2 + h_dir, h_dir):
        grid[y1, x] = 1
    v_dir = 1 if y2 >= y1 else -1
    for y in range(y1, y2 + v_dir, v_dir):
        grid[y, x2] = 1


def to_ascii(grid, wall: str = "#", floor: str = ".") -> str:
    """把网格转成 ASCII 地图字符串（便于打印/调试）。"""
    lines = []
    for row in grid:
        lines.append("".join(floor if c else wall for c in row))
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# BSP 地牢（二叉空间分割）：递归分割 -> 叶子内房间 -> 自底向上连通
# ---------------------------------------------------------------------------
def generate_dungeon_bsp(width: int = 48, height: int = 32, seed: int = 0,
                         min_leaf: int = 10, max_leaf: int = 22,
                         room_min: int = 4, room_max: int = 11) -> dict:
    """基于二叉空间分割（BSP）的地牢生成。

    1. 递归把地图二分，直到子区足够小；
    2. 每个叶子区内放一间不重叠的随机房间；
    3. 自底向上连接姐妹子树，保证整图连通。

    返回与 generate_dungeon 相同结构：{'grid','rooms','connections'}。
    """
    if width < 8 or height < 8:
        raise ValueError(f"地牢尺寸过小，至少需要 8x8，收到 {width}x{height}")
    rng = np.random.RandomState(seed)
    grid = np.zeros((height, width), dtype=np.int8)

    def split(x, y, w, h, depth):
        if depth > 12 or (w <= max_leaf and h <= max_leaf and rng.rand() < 0.25) \
           or (w < min_leaf * 2 and h < min_leaf * 2):
            return {"x": x, "y": y, "w": w, "h": h,
                    "left": None, "right": None, "room": None}
        if w > h and w >= min_leaf * 2:
            horizontal = False
        elif h > w and h >= min_leaf * 2:
            horizontal = True
        else:
            horizontal = rng.rand() < 0.5
        if horizontal:
            cut = rng.randint(min_leaf, h - min_leaf + 1)
            a = split(x, y, w, cut, depth + 1)
            b = split(x, y + cut, w, h - cut, depth + 1)
        else:
            cut = rng.randint(min_leaf, w - min_leaf + 1)
            a = split(x, y, cut, h, depth + 1)
            b = split(x + cut, y, w - cut, h, depth + 1)
        return {"x": x, "y": y, "w": w, "h": h,
                "left": a, "right": b, "room": None}

    root = split(0, 0, width, height, 0)
    leaves = []

    def collect(node):
        if node["left"] is None:
            leaves.append(node)
        else:
            collect(node["left"])
            collect(node["right"])

    collect(root)

    rooms = []
    for lf in leaves:
        maxw = min(room_max, lf["w"] - 2)
        maxh = min(room_max, lf["h"] - 2)
        if maxw < room_min or maxh < room_min:
            continue
        rw = rng.randint(room_min, maxw + 1)
        rh = rng.randint(room_min, maxh + 1)
        rx = lf["x"] + rng.randint(1, lf["w"] - rw)
        ry = lf["y"] + rng.randint(1, lf["h"] - rh)
        room = {"x": rx, "y": ry, "w": rw, "h": rh,
                "cx": rx + rw // 2, "cy": ry + rh // 2}
        lf["room"] = room
        rooms.append(room)
        grid[ry:ry + rh, rx:rx + rw] = 1

    connections = []

    def connect(node):
        if node["left"] is None:
            return node["room"]
        lr = connect(node["left"])
        rr = connect(node["right"])
        if lr is not None and rr is not None:
            _carve_corridor(grid, lr["cx"], lr["cy"], rr["cx"], rr["cy"])
            connections.append((rooms.index(lr), rooms.index(rr)))
            return lr
        return lr if lr is not None else rr

    connect(root)

    if not rooms:
        warnings.warn("BSP 未生成任何房间（空间过小）", stacklevel=2)
    return {"grid": grid, "rooms": rooms, "connections": connections}


# ---------------------------------------------------------------------------
# 元胞自动机洞穴（RogueBasin 4-5 规则 + 洪水填充连通）
# ---------------------------------------------------------------------------
def _wall_neighbors(grid):
    """统计每个格 3x3（含自身）内的墙数；用 roll 求和，仅内部格有效。"""
    counts = np.zeros(grid.shape, dtype=np.int64)
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            counts += np.roll(np.roll(grid, dy, 0), dx, 1)
    return counts


def _label_regions(mask):
    """4-连通标记（洪水填充），返回 (labeled, n_regions)。0 为背景。"""
    h, w = mask.shape
    labeled = np.zeros((h, w), dtype=np.int32)
    k = 0
    for y in range(h):
        for x in range(w):
            if mask[y, x] and labeled[y, x] == 0:
                k += 1
                labeled[y, x] = k
                stack = [(y, x)]
                while stack:
                    cy, cx = stack.pop()
                    for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                        ny, nx = cy + dy, cx + dx
                        if 0 <= ny < h and 0 <= nx < w \
                                and mask[ny, nx] and labeled[ny, nx] == 0:
                            labeled[ny, nx] = k
                            stack.append((ny, nx))
    return labeled, k


def generate_cave(width: int = 48, height: int = 32, seed: int = 0,
                  fill_prob: float = 0.45, iterations: int = 5,
                  border_wall: bool = True) -> dict:
    """元胞自动机洞穴生成（RogueBasin 4-5 规则）。

    - 初始随机填充（墙概率 fill_prob）；
    - 迭代平滑：3x3 墙数 >= 5 则该格变墙；
    - 洪水填充保留最大的可走连通块，其余回填为墙。

    返回：{'grid': 1=地/0=墙, 'regions': 连通块数, 'floor_count': 地板格数}。
    """
    if width < 8 or height < 8:
        raise ValueError(f"洞穴尺寸过小，至少需要 8x8，收到 {width}x{height}")
    rng = np.random.RandomState(seed)
    grid = (rng.rand(height, width) < fill_prob).astype(np.int8)  # 1=墙

    def _frame(g):
        if border_wall:
            g[0, :] = 1
            g[-1, :] = 1
            g[:, 0] = 1
            g[:, -1] = 1
        return g

    grid = _frame(grid)
    for _ in range(iterations):
        grid = _frame((_wall_neighbors(grid) >= 5).astype(np.int8))

    floor = (grid == 0)                       # 内部约定：0=地板
    labeled, n_regions = _label_regions(floor)
    if n_regions == 0:
        warnings.warn("未生成任何可走区域", stacklevel=2)
        out = np.zeros((height, width), dtype=np.int8)  # 全墙
        if border_wall:
            pass  # 已是全墙
        return {"grid": out, "regions": 0, "floor_count": 0}

    sizes = np.bincount(labeled.ravel())
    biggest = int(np.argmax(sizes[1:]) + 1)
    kept = (labeled == biggest)
    # 输出约定与 dungeon 一致：1=地(可走) 0=墙
    out = np.where(kept, 1, 0).astype(np.int8)
    if border_wall:
        out[0, :] = 0
        out[-1, :] = 0
        out[:, 0] = 0
        out[:, -1] = 0
    return {"grid": out, "regions": n_regions, "floor_count": int(kept.sum())}
