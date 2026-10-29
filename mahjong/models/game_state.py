"""GameState - 一局游戏的完整可变状态。

由 ViewModel 持有与修改，View 只读。
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Tuple

from .board import Board, Pos
from .tile import Tile


class GameMode(str, Enum):
    MAHJONG = "mahjong"   # 上海麻将：自由牌配对 (正宗)
    LINK = "link"         # 连连看：两折连通配对 (变体)


@dataclass
class MoveRecord:
    """单步操作记录，供撤销使用。

    elapsed_before / combo_before / last_match_at_before 保存消除前的
    计时与连击状态，使 undo() 成为真正的逆操作（而非只把 combo 清 0）。
    """
    pos_a: Pos
    tile_a: Tile
    pos_b: Pos
    tile_b: Tile
    score_delta: int = 0
    elapsed_before: float = 0.0
    combo_before: int = 0
    last_match_at_before: float = 0.0
    win_bonus: int = 0


@dataclass
class GameState:
    board: Board = field(default_factory=Board)
    score: int = 0
    elapsed: float = 0.0
    time_limit: int = 300          # 秒；0 表示不限时
    selected: Optional[Pos] = None
    mode: GameMode = GameMode.MAHJONG
    history: List[MoveRecord] = field(default_factory=list)
    hints_left: int = 3
    shuffles_left: int = 3
    running: bool = False
    paused: bool = False
    won: bool = False
    lost: bool = False
    moves: int = 0
    combo: int = 0                 # 连续快速配对的连击
    last_match_at: float = -1.0    # -1 表示"尚无上一次配对"，避免开局首配误判连击

    # ---- 派生属性 ------------------------------------------------
    @property
    def time_left(self) -> float:
        if self.time_limit <= 0:
            return float("inf")
        return max(0.0, self.time_limit - self.elapsed)

    @property
    def remaining_tiles(self) -> int:
        return self.board.remaining()

    @property
    def can_undo(self) -> bool:
        return bool(self.history) and self.running and not self.won
