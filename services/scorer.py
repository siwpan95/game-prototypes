"""计分规则。

基础分 10 / 对；季花额外 +5；
连续快速配对触发连击加成；通关有时间剩余奖励。
"""
from dataclasses import dataclass

from models.tile import Tile, Suit

BASE_SCORE = 10
BONUS_SEASON_FLOWER = 5
COMBO_WINDOW = 3.0     # 秒：距上次配对 < 此值则连击 +1
COMBO_PER_STEP = 2     # 每级连击额外分


@dataclass
class ScoreBreakdown:
    base: int = 0
    bonus: int = 0          # 季花加成
    combo: int = 0          # 连击加成
    total: int = 0

    def __str__(self) -> str:
        parts = [f"基础 {self.base}"]
        if self.bonus:
            parts.append(f"季花 +{self.bonus}")
        if self.combo:
            parts.append(f"连击 +{self.combo}")
        parts.append(f"= {self.total}")
        return "  ".join(parts)


def score_for_match(
    tile_a: Tile,
    tile_b: Tile,
    combo: int = 0,
    time_since_last: float = 999.0,
) -> ScoreBreakdown:
    """计算单次配对的得分增量。

    combo: 当前已连击数 (本次配对前的值)
    time_since_last: 距上一次配对的秒数
    """
    base = BASE_SCORE
    bonus = BONUS_SEASON_FLOWER if (
        tile_a.suit in (Suit.SEASON, Suit.FLOWER)
        or tile_b.suit in (Suit.SEASON, Suit.FLOWER)
    ) else 0

    combo_lvl = combo
    if time_since_last >= COMBO_WINDOW:
        combo_lvl = 0  # 超时则连击中断
    combo_score = combo_lvl * COMBO_PER_STEP

    return ScoreBreakdown(
        base=base,
        bonus=bonus,
        combo=combo_score,
        total=base + bonus + combo_score,
    )


def time_bonus(time_left: float) -> int:
    """通关时按剩余时间给奖励分。"""
    return int(time_left) * 2
