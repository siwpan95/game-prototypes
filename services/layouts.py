"""棋盘布局生成器。

所有布局返回 List[Pos] = List[(layer, row, col)]，长度应 == 144。
交叉堆叠约定 (见 models/board.py)：
  上层牌 (l+1, r, c) 压在 4 张下层 (l, r,c)/(l, r,c+1)/(l, r+1,c)/(l, r+1,c+1) 之上。
  故上层范围应严格内缩于下层范围 (每边至少小 1)。
"""
from enum import Enum
from typing import List, Tuple

from models.board import Pos


class LayoutKind(str, Enum):
    TURTLE = "turtle"       # 经典乌龟 (上海麻将标准) - 4层 86+40+14+4
    PYRAMID = "pyramid"     # 对称金字塔 (4层)
    RECTANGLE = "rectangle" # 简化矩形堆叠 (兼容旧版)
    LINK_FLAT = "link_flat" # 连连看平面布局 (单层 12×18, 每3列空1列 = 144)


# --------------------------------------------------------------------
# 经典乌龟布局 (上海麻将标准形态)
#   layer 0 (86): 主体 6×12 + 头/尾突 + 4腿
#   layer 1 (40): 4×10 居中
#   layer 2 (14): 2×7 居中
#   layer 3 (4) : 2×2 顶尖
# --------------------------------------------------------------------
def _turtle_layout() -> List[Pos]:
    slots: List[Pos] = []

    # --- Layer 0 : 86 张 ---
    # 主体矩形: rows 1..6, cols 1..12  -> 6×12 = 72
    for r in range(1, 7):
        for c in range(1, 13):
            slots.append((0, r, c))
    # 尾部突出 (左): rows 3..4, col 0  -> 2
    for r in (3, 4):
        slots.append((0, r, 0))
    # 头部突出 (右): rows 3..4, cols 13..14  -> 4
    for r in (3, 4):
        for c in (13, 14):
            slots.append((0, r, c))
    # 上腿 (row 0): cols 3,4,9,10  -> 4
    for c in (3, 4, 9, 10):
        slots.append((0, 0, c))
    # 下腿 (row 7): cols 3,4,9,10  -> 4
    for c in (3, 4, 9, 10):
        slots.append((0, 7, c))
    assert len(slots) == 86, f"L0 数量错误: {len(slots)}"

    # --- Layer 1 : 40 张 (rows 2..5, cols 2..11) ---
    l1 = [(1, r, c) for r in range(2, 6) for c in range(2, 12)]
    assert len(l1) == 40
    slots.extend(l1)

    # --- Layer 2 : 14 张 (rows 3..4, cols 3..9) ---
    l2 = [(2, r, c) for r in range(3, 5) for c in range(3, 10)]
    assert len(l2) == 14
    slots.extend(l2)

    # --- Layer 3 : 4 张 (顶尖单行: row 3, cols 4..7) ---
    # 支撑合法：每张 (3,3,c) 下方需 (2,3,c)/(2,3,c+1)/(2,4,c)/(2,4,c+1)，
    # 均落在 L2 (rows3-4, cols3-9) 内。
    l3 = [(3, 3, c) for c in range(4, 8)]
    assert len(l3) == 4
    slots.extend(l3)

    assert len(slots) == 144, f"乌龟布局总数错误: {len(slots)}"
    return slots


# --------------------------------------------------------------------
# 对称金字塔 (4层): 96 + 32 + 12 + 4 = 144
# --------------------------------------------------------------------
def _pyramid_layout() -> List[Pos]:
    slots: List[Pos] = []
    # L0: rows 0..7, cols 2..13  -> 8×12 = 96
    for r in range(8):
        for c in range(2, 14):
            slots.append((0, r, c))
    # L1: rows 1..6, cols 3..10  -> 6×8 = 48? 取前32会破坏对称，改用 4×8
    # 重新: L1 rows 2..5, cols 3..10 -> 4×8 = 32
    for r in range(2, 6):
        for c in range(3, 11):
            slots.append((1, r, c))
    # L2: rows 3..4, cols 4..9  -> 2×6 = 12
    for r in range(3, 5):
        for c in range(4, 10):
            slots.append((2, r, c))
    # L3: 顶尖单行 row 3, cols 5..8 -> 1×4 = 4
    # 支撑合法：每张 (3,3,c) 下方 (2,3,c)/(2,3,c+1)/(2,4,c)/(2,4,c+1) 均在 L2 (rows3-4, cols4-9) 内。
    for c in range(5, 9):
        slots.append((3, 3, c))
    assert len(slots) == 96 + 32 + 12 + 4 == 144
    return slots


# --------------------------------------------------------------------
# 简化矩形堆叠 (兼容旧版 gen_simple_layers): 80+36+20+8 = 144
# 注意: 此布局为柱状堆叠兼容用，不严格保证交叉堆叠支撑。
# --------------------------------------------------------------------
def _rectangle_layout() -> List[Pos]:
    slots: List[Pos] = []
    # L0: rows 0..7, cols 2..11 -> 8×10 = 80
    for r in range(8):
        for c in range(2, 12):
            slots.append((0, r, c))
    # L1: rows 1..6, cols 3..10 -> 6×8 = 48, 取居中36 (rows 2..5, cols 3..8 -> 4×6=24? 不够)
    # 为保持对称取 rows 2..5 cols 3..10 的前 4 行 6 列 = 24，不够 36
    # 直接用 rows 1..6 cols 3..8 = 6×6 = 36
    for r in range(1, 7):
        for c in range(3, 9):
            slots.append((1, r, c))
    # L2: rows 2..5, cols 4..8 -> 4×5 = 20
    for r in range(2, 6):
        for c in range(4, 9):
            slots.append((2, r, c))
    # L3: rows 3..4, cols 5..8 -> 2×4 = 8
    for r in range(3, 5):
        for c in range(5, 9):
            slots.append((3, r, c))
    assert len(slots) == 80 + 36 + 20 + 8 == 144
    return slots


# --------------------------------------------------------------------
# 连连看平面布局 (单层, 带气道)
#   连连看本就是二维游戏: 任意两格用 ≤2 拐弯折线连通即可消除 (可绕到棋盘外)。
#   关键: 满铺棋盘会把内部牌夹死, 看着像"同行同列都消不了"。
#   故本布局在 12 行 × 18 列中, 每 3 列留 1 列气道 -> 144 张牌 + 72 气道。
#   气道让 ≤2 拐弯 + 绕外 规则下大量"同行/同列"牌可连通, 游戏更顺手。
# --------------------------------------------------------------------
def _link_flat_layout() -> List[Pos]:
    """连连看平面布局: 单层 12×18, 每 3 列空 1 列, 共 144 张牌。"""
    slots: List[Pos] = []
    ROWS, COLS, GAP = 12, 18, 3
    for r in range(ROWS):
        for c in range(COLS):
            if c % GAP == GAP - 1:   # 每第 3 列作气道
                continue
            slots.append((0, r, c))
    assert len(slots) == 144, f"连连看布局应为 144 张, 实际 {len(slots)}"
    return slots


_LAYOUTS = {
    LayoutKind.TURTLE: _turtle_layout,
    LayoutKind.PYRAMID: _pyramid_layout,
    LayoutKind.RECTANGLE: _rectangle_layout,
    LayoutKind.LINK_FLAT: _link_flat_layout,
}


def generate_layout(kind: LayoutKind = LayoutKind.TURTLE) -> List[Pos]:
    """生成指定类型的布局，返回 144 个槽位坐标。"""
    return list(_LAYOUTS[kind]())
