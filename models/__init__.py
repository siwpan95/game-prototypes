"""麻将连连看 - 数据模型层 (Model)

仅包含纯数据结构，不依赖任何 UI 框架。
- Tile:   单张牌的不可变描述
- Board:  三维坐标 (layer, row, col) -> Tile 的棋盘容器
- GameState: 一局游戏的完整可变状态
"""
from .tile import Tile, Suit
from .board import Board, Pos
from .game_state import GameState, GameMode

__all__ = ["Tile", "Suit", "Board", "Pos", "GameState", "GameMode"]
