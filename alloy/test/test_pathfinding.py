"""
寻路求解器测试 — grid_astar（网格 A*）与 GraphPathFinder（图最短路）。

使用自包含的最小 Fake 网格 / 图，避免依赖完整 MapData / MapGraph 实例化。
"""

from alloy.world.pathfinding import grid_astar, GraphPathFinder


# ============================================================
# 最小 Fake 网格
# ============================================================

class _FakeGrid:
    """极简字符网格，满足 grid_astar 所需的接口：in_bounds / get / fill_char。"""

    def __init__(self, cells: list[list[str]], fill_char: str = "#"):
        # cells[row][col]
        self._cells = cells
        self.rows = len(cells)
        self.cols = max((len(r) for r in cells), default=0)
        self.fill_char = fill_char

    def in_bounds(self, col: int, row: int) -> bool:
        return 0 <= row < self.rows and 0 <= col < len(self._cells[row])

    def get(self, col: int, row: int) -> str:
        return self._cells[row][col]


# ============================================================
# 最小 Fake 图
# ============================================================

class _FakeNode:
    def __init__(self, nid: str, connections: list[str], is_locked: bool = False):
        self.nid = nid
        self.connections = connections
        self.is_locked = is_locked


class _FakeGraph:
    def __init__(self, nodes: dict[str, _FakeNode]):
        self.nodes = nodes


# ============================================================
# grid_astar 测试
# ============================================================

def test_grid_astar_basic():
    # 顶部一行畅通，起点(0,0) 终点(3,0)
    cells = [
        [".", ".", ".", "."],
        [".", "#", "#", "."],
        [".", ".", ".", "."],
    ]
    grid = _FakeGrid(cells, fill_char="#")
    path = grid_astar(grid, (0, 0), (3, 0))
    assert path is not None
    assert path[0] == (0, 0)
    assert path[-1] == (3, 0)
    # 路径必须依次相邻且全部可走
    for (c, r) in path:
        assert grid.get(c, r) != "#"
    for i in range(1, len(path)):
        dc = abs(path[i][0] - path[i - 1][0])
        dr = abs(path[i][1] - path[i - 1][1])
        assert dc + dr == 1  # 正交相邻


def test_grid_astar_goal_in_wall_returns_none():
    # 终点本身是墙 → 无路
    cells = [
        [".", ".", "."],
        [".", "#", "."],
        [".", ".", "."],
    ]
    grid = _FakeGrid(cells, fill_char="#")
    assert grid_astar(grid, (0, 0), (1, 1)) is None


def test_grid_astar_enclosed_returns_none():
    # 终点被四面墙包围 → 无路
    cells = [
        ["#", "#", "#"],
        ["#", ".", "#"],
        ["#", "#", "#"],
    ]
    grid = _FakeGrid(cells, fill_char="#")
    assert grid_astar(grid, (1, 1), (0, 0)) is None


def test_grid_astar_out_of_bounds_returns_none():
    cells = [
        [".", ".", "."],
        [".", ".", "."],
    ]
    grid = _FakeGrid(cells, fill_char="#")
    assert grid_astar(grid, (0, 0), (99, 99)) is None


def test_grid_astar_diagonal():
    # 完全开阔 3x3
    cells = [
        [".", ".", "."],
        [".", ".", "."],
        [".", ".", "."],
    ]
    grid = _FakeGrid(cells, fill_char="#")
    path = grid_astar(grid, (0, 0), (2, 2), allow_diagonal=True)
    assert path is not None
    assert path[0] == (0, 0)
    assert path[-1] == (2, 2)
    # 对角移动：路径长度应为 3（两步对角 + 含起终点共 3 个格）
    assert len(path) == 3


def test_grid_astar_no_diagonal_longer():
    cells = [
        [".", ".", "."],
        [".", ".", "."],
        [".", ".", "."],
    ]
    grid = _FakeGrid(cells, fill_char="#")
    path = grid_astar(grid, (0, 0), (2, 2), allow_diagonal=False)
    assert path is not None
    # 正交移动：曼哈顿距离 4，路径长度 5
    assert len(path) == 5


# ============================================================
# GraphPathFinder 测试
# ============================================================

def _build_linear_graph() -> _FakeGraph:
    nodes = {
        "hub": _FakeNode("hub", ["a"]),
        "a": _FakeNode("a", ["b"]),
        "b": _FakeNode("b", ["boss"]),
        "boss": _FakeNode("boss", []),
    }
    return _FakeGraph(nodes)


def test_graph_bfs():
    g = _build_linear_graph()
    pf = GraphPathFinder(g)
    path = pf.bfs("hub", "boss")
    assert path == ["hub", "a", "b", "boss"]


def test_graph_dijkstra_weighted():
    g = _build_linear_graph()
    pf = GraphPathFinder(g)

    def wf(_f, t):
        # a→b 权重特别大，迫使绕行（这里没有绕行，仅验证权重生效）
        return 10.0 if t == "b" else 1.0

    path = pf.dijkstra("hub", "boss", weight_fn=wf)
    assert path == ["hub", "a", "b", "boss"]


def test_graph_astar():
    g = _build_linear_graph()
    pf = GraphPathFinder(g)
    pos = {"hub": (0, 0), "a": (1, 0), "b": (2, 0), "boss": (3, 0)}
    path = pf.astar("hub", "boss", pos_fn=lambda nid: pos[nid])
    assert path == ["hub", "a", "b", "boss"]


def test_graph_unreachable_returns_none():
    g = _build_linear_graph()
    pf = GraphPathFinder(g)
    # 目标不在图中
    assert pf.bfs("hub", "nowhere") is None
    # 起点不在图中
    assert pf.dijkstra("nowhere", "boss") is None


def test_graph_same_node():
    g = _build_linear_graph()
    pf = GraphPathFinder(g)
    assert pf.bfs("hub", "hub") == ["hub"]
    assert pf.shortest_path("boss", "boss") == ["boss"]


def test_graph_locked_skipped_when_not_ignored():
    # 中间节点 b 被锁，ignore_locks=False 时应绕不开 → None
    nodes = {
        "hub": _FakeNode("hub", ["a", "direct"]),
        "a": _FakeNode("a", ["b"]),
        "b": _FakeNode("b", ["boss"], is_locked=True),
        "direct": _FakeNode("direct", ["boss"]),
        "boss": _FakeNode("boss", []),
    }
    g = _FakeGraph(nodes)
    pf = GraphPathFinder(g, ignore_locks=False)
    # hub -> a -> b(locked) 被拒；hub -> direct -> boss 仍可达
    path = pf.bfs("hub", "boss")
    assert path is not None
    assert "b" not in path
