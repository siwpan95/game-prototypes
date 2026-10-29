"""
放置英雄 — 游戏引擎包。
对外暴露 GameEngine（核心）、GameState（状态）、UpgradeDef（装备定义）。
"""

from .core import GameEngine
from .state import GameState
from .upgrade import UpgradeDef
from .fmt import fmt_gold, fmt_dps, fmt_num

__all__ = ["GameEngine", "GameState", "UpgradeDef", "fmt_gold", "fmt_dps", "fmt_num"]
