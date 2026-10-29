"""
全局配置 — 所有系统共用的常量。
单一来源，避免重复定义导致不一致。
"""

CELL = 20          # 每个字符格子的像素尺寸
COLS = 40          # 地图列数
ROWS = 32          # 地图行数（mansion_map.txt 共 32 行，索引 0-31）

WINDOW_W = COLS * CELL + 160   # 960：游戏区 + 卡牌面板
WINDOW_H = ROWS * CELL         # 640：完整地图高度

FILL_CHAR = "墙"   # 补齐字符 — 不足 COLS 列的行用墙壁填充

BLOCKED_CHARS = set("墙暗门")   # 不可行走字符集

PORTAL_CHARS = set("▼▲→←↑↓")  # 传送门锚点字符 — 玩家走上这些格子可能触发地图切换
