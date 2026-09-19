"""
全局配置 — 通用游戏配置常量
==============================

所有系统共用的配置常量，单一来源避免重复定义导致不一致。
模块级变量可被外部 import 覆盖，方便运行时调整。

用法：
    from allin_engine.core.config import CELL, COLS, ROWS, WINDOW_W, WINDOW_H

    # 运行时覆盖（可选）
    import allin_engine.core.config as cfg
    cfg.CELL = 32
    cfg.COLS = 60
"""

from __future__ import annotations

from typing import Set

# ── 网格 / 地图基础尺寸 ───────────────────────────────

CELL: int = 20
"""每个字符格子的像素尺寸。"""

COLS: int = 40
"""地图列数（宽度）。"""

ROWS: int = 32
"""地图行数（高度）。"""

# ── 窗口尺寸 ──────────────────────────────────────────

WINDOW_W: int = COLS * CELL + 160  # 960
"""窗口宽度 = 地图区 + 侧边面板（160px）。"""

WINDOW_H: int = ROWS * CELL  # 640
"""窗口高度 = 完整地图高度。"""

# ── 地图 / 瓦片字符集 ──────────────────────────────────

FILL_CHAR: str = "墙"
"""补齐字符 — 不足 COLS 列的行用此字符填充。"""

BLOCKED_CHARS: Set[str] = {"墙", "暗", "门"}
"""不可行走的字符集 — 碰撞检测时参考。"""

PORTAL_CHARS: Set[str] = {"▼", "▲", "→", "←", "↑", "↓"}
"""
传送门锚点字符集 — 玩家走上这些格子可能触发地图切换。
每个字符对应不同传送方向。
"""

# ── 游戏帧率 ──────────────────────────────────────────

FPS: int = 60
"""目标帧率。"""

FRAME_TIME: float = 1.0 / FPS
"""每帧时间间隔（秒）。"""

# ── 调试开关 ──────────────────────────────────────────

DEBUG: bool = False
"""全局调试开关。"""

# ── 辅助函数 ──────────────────────────────────────────

def get_window_size() -> tuple[int, int]:
    """返回当前窗口尺寸 (width, height)。"""
    return WINDOW_W, WINDOW_H


def get_grid_size() -> tuple[int, int]:
    """返回当前网格尺寸 (cols, rows)。"""
    return COLS, ROWS
