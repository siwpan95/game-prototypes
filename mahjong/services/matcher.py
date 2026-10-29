"""配对与连通判定 - 核心规则算法。

包含:
  is_free            自由牌判定 (交叉堆叠遮挡 + 左右露边)
  tile_match         两张牌是否可配对
  find_all_free      列出全部自由牌
  find_hint_pair     找一对可消除 (提示用)
  count_solvable_pairs 可消对数
  has_solution       是否还有可消对 (死局判定)
  can_link           link 模式两折连通判定 (修复原版 bug)
"""
from typing import List, Optional, Tuple

from models.board import Board, Pos
from models.tile import Tile, Suit


# ============================================================
#  自由牌判定 (上海麻将 / 交叉堆叠)
# ============================================================
def _is_blocked_above(board: Board, l: int, r: int, c: int) -> bool:
    """检查 (l,r,c) 是否被 layer l+1 的牌遮挡。
    上层 (l+1, r', c') 压住下层 (l, r',c')/(l, r',c'+1)/(l, r'+1,c')/(l, r'+1,c'+1)。
    故压住 (l,r,c) 的上层位置为 (l+1, r-1,c-1)/(l+1, r-1,c)/(l+1, r,c-1)/(l+1, r,c)。
    """
    if l + 1 > board.max_layer:
        return False
    for dr in (0, -1):
        for dc in (0, -1):
            t = board.get((l + 1, r + dr, c + dc))
            if t is not None:
                return True
    return False


def is_free(board: Board, pos: Pos) -> bool:
    """标准上海麻将自由牌：上方无压 + 左右至少一侧同层无邻接牌。"""
    if board.get(pos) is None:
        return False
    l, r, c = pos
    if _is_blocked_above(board, l, r, c):
        return False
    left = board.get((l, r, c - 1))
    right = board.get((l, r, c + 1))
    return left is None or right is None


def find_all_free(board: Board) -> List[Tuple[Pos, Tile]]:
    """返回 [(pos, tile)]，所有当前自由牌。"""
    out = []
    for pos in board.occupied_positions():
        if is_free(board, pos):
            out.append((pos, board.get(pos)))
    return out


# ============================================================
#  配对判定
# ============================================================
def tile_match(a: Tile, b: Tile) -> bool:
    return a.matches(b)


# ============================================================
#  提示 / 死局检测
# ============================================================
def _candidate_pairs(board: Board, mode: str):
    """生成所有候选配对 (自由牌两两组合 / link 模式全部牌两两组合)。"""
    if mode == "mahjong":
        frees = find_all_free(board)
        for i in range(len(frees)):
            for j in range(i + 1, len(frees)):
                yield frees[i], frees[j]
    else:  # link
        all_t = [(p, board.get(p)) for p in board.occupied_positions()]
        for i in range(len(all_t)):
            for j in range(i + 1, len(all_t)):
                yield all_t[i], all_t[j]


def find_hint_pair(board: Board, mode: str) -> Optional[Tuple[Pos, Pos]]:
    """找到任意一对可消除的牌，返回 (pos_a, pos_b) 或 None。"""
    for (pa, ta), (pb, tb) in _candidate_pairs(board, mode):
        if not tile_match(ta, tb):
            continue
        if mode == "link" and not can_link(board, pa, pb):
            continue
        return pa, pb
    return None


def count_solvable_pairs(board: Board, mode: str) -> int:
    """统计当前可消除对数。"""
    n = 0
    for (pa, ta), (pb, tb) in _candidate_pairs(board, mode):
        if not tile_match(ta, tb):
            continue
        if mode == "link" and not can_link(board, pa, pb):
            continue
        n += 1
    return n


def has_solution(board: Board, mode: str) -> bool:
    return find_hint_pair(board, mode) is not None


# ============================================================
#  两折连通判定 (link 模式)
#  修复原版 bug: 2 折逻辑"对称略"导致漏判；此处完整实现 0/1/2 折。
# ============================================================
def can_link(board: Board, pos1: Pos, pos2: Pos) -> bool:
    """link 模式下两点是否可在 ≤2 拐点内连通。
    投影到 (row, col) 平面 (忽略 layer)；允许绕到棋盘边界外一格。
    """
    _, r1, c1 = pos1
    _, r2, c2 = pos2
    if (r1, c1) == (r2, c2):
        return False

    occ = set()
    for (l, r, c) in board.occupied_positions():
        occ.add((r, c))
    # 起点 / 终点视为可通行
    occ.discard((r1, c1))
    occ.discard((r2, c2))

    R = board.rows
    C = board.cols

    def row_clear(r: int, ca: int, cb: int) -> bool:
        """行 r 上 (ca, cb) 开区间内无牌；r 越界视为空。"""
        if r < 0 or r >= R:
            return True
        lo, hi = sorted((ca, cb))
        for c in range(lo + 1, hi):
            if (r, c) in occ:
                return False
        return True

    def col_clear(c: int, ra: int, rb: int) -> bool:
        if c < 0 or c >= C:
            return True
        lo, hi = sorted((ra, rb))
        for r in range(lo + 1, hi):
            if (r, c) in occ:
                return False
        return True

    # 0 折
    if r1 == r2 and row_clear(r1, c1, c2):
        return True
    if c1 == c2 and col_clear(c1, r1, r2):
        return True

    # 1 折: 拐点 (r1,c2) 或 (r2,c1)
    if (r1, c2) not in occ and row_clear(r1, c1, c2) and col_clear(c2, r1, r2):
        return True
    if (r2, c1) not in occ and col_clear(c1, r1, r2) and row_clear(r2, c1, c2):
        return True

    # 2 折: 中继行 rm (p1 竖→(rm,c1), 横→(rm,c2), 竖→p2)
    for rm in range(-1, R + 1):
        if rm == r1 or rm == r2:
            continue
        if (rm, c1) in occ or (rm, c2) in occ:
            continue
        if col_clear(c1, r1, rm) and row_clear(rm, c1, c2) and col_clear(c2, rm, r2):
            return True
    # 2 折: 中继列 cm
    for cm in range(-1, C + 1):
        if cm == c1 or cm == c2:
            continue
        if (r1, cm) in occ or (r2, cm) in occ:
            continue
        if row_clear(r1, c1, cm) and col_clear(cm, r1, r2) and row_clear(r2, cm, c2):
            return True
    return False


def link_path(board: Board, pos1: Pos, pos2: Pos) -> Optional[List[Tuple[int, int]]]:
    """返回 pos1 -> pos2 的连通折线路径 (grid 坐标列表, 含绕外点)。

    与 can_link 判定完全一致 (0/1/2 折 + 可绕到边界外一格)。返回 None 表示不可连。
    路径点用于绘制连连看连线动画, 让 ≤2 拐弯规则可见。
    """
    _, r1, c1 = pos1
    _, r2, c2 = pos2
    if (r1, c1) == (r2, c2):
        return None

    occ = set()
    for (l, r, c) in board.occupied_positions():
        occ.add((r, c))
    occ.discard((r1, c1))
    occ.discard((r2, c2))

    R = board.rows
    C = board.cols

    def row_clear(r: int, ca: int, cb: int) -> bool:
        if r < 0 or r >= R:
            return True
        lo, hi = sorted((ca, cb))
        return not any((r, c) in occ for c in range(lo + 1, hi))

    def col_clear(c: int, ra: int, rb: int) -> bool:
        if c < 0 or c >= C:
            return True
        lo, hi = sorted((ra, rb))
        return not any((r, c) in occ for r in range(lo + 1, hi))

    # 0 折
    if r1 == r2 and row_clear(r1, c1, c2):
        return [(r1, c1), (r1, c2)]
    if c1 == c2 and col_clear(c1, r1, r2):
        return [(r1, c1), (r2, c1)]
    # 1 折 (拐点 (r1,c2))
    if (r1, c2) not in occ and row_clear(r1, c1, c2) and col_clear(c2, r1, r2):
        return [(r1, c1), (r1, c2), (r2, c2)]
    # 1 折 (拐点 (r2,c1))
    if (r2, c1) not in occ and col_clear(c1, r1, r2) and row_clear(r2, c1, c2):
        return [(r1, c1), (r2, c1), (r2, c2)]
    # 2 折: 中继行 rm
    for rm in range(-1, R + 1):
        if rm == r1 or rm == r2:
            continue
        if (rm, c1) in occ or (rm, c2) in occ:
            continue
        if col_clear(c1, r1, rm) and row_clear(rm, c1, c2) and col_clear(c2, rm, r2):
            return [(r1, c1), (rm, c1), (rm, c2), (r2, c2)]
    # 2 折: 中继列 cm
    for cm in range(-1, C + 1):
        if cm == c1 or cm == c2:
            continue
        if (r1, cm) in occ or (r2, cm) in occ:
            continue
        if row_clear(r1, c1, cm) and col_clear(cm, r1, r2) and row_clear(r2, cm, c2):
            return [(r1, c1), (r1, cm), (r2, cm), (r2, c2)]
    return None
