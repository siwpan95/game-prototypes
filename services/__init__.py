"""服务层 - 纯算法，无状态，不依赖 UI。

- deck:     生成标准 144 张牌堆
- layouts:  生成棋盘槽位坐标 (乌龟 / 金字塔 / 矩形)
- matcher:  自由牌判定 / 配对 / 两折连通 / 提示与死局检测
- scorer:   计分规则
"""
from .deck import build_standard_deck, DeckSpec
from .layouts import LayoutKind, generate_layout
from .matcher import (
    is_free, tile_match, find_hint_pair, count_solvable_pairs,
    has_solution, can_link, find_all_free,
)
from .scorer import score_for_match, ScoreBreakdown

__all__ = [
    "build_standard_deck", "DeckSpec",
    "LayoutKind", "generate_layout",
    "is_free", "tile_match", "find_hint_pair", "count_solvable_pairs",
    "has_solution", "can_link", "find_all_free",
    "score_for_match", "ScoreBreakdown",
]
