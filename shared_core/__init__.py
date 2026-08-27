"""
shared_core — Hell Below 11款游戏统一框架

统一的文字冒险游戏引擎框架，支持三种游戏模式：
  - 标准模式（故事驱动 + 谜题）
  - 领域驱动模式（房间探索 + 物品 + 标志位）
  - 卡牌战斗模式（回合制战斗 + 卡组管理）

所有模块使用相对导入。Tkinter GUI 是唯一 UI 后端。
"""

__version__ = "1.0.0"
__author__ = "Hell Below Unified Architecture"

# Core
from shared_core.game_state import GameState, PlayerState
from shared_core.base_engine import BaseEngine

# World models
from shared_core.room import Room
from shared_core.item import Item
from shared_core.character import Character

# Systems
from shared_core.puzzle import Puzzle, PuzzleSystem
from shared_core.inventory import Inventory
from shared_core.event_bus import EventBus, EventTypes
from shared_core.command_parser import CommandParser
from shared_core.command_handler import CommandHandler

# Data
from shared_core.json_loader import JSONLoader
from shared_core.save_load import SaveLoadManager

# UI
from shared_core.renderer import Renderer
from shared_core.main_win import MainWindow
from shared_core.styles import Styles
from shared_core.text_fmt import TextFormatter
from shared_core.animation import Animation
from shared_core.logger import Logger

# Optional combat (import guard)
try:
    from shared_core.combat_engine import CombatEngine, CombatState
    from shared_core.card import Card, CardDeck
    from shared_core.enemy import Enemy, EnemyInstance
except ImportError:
    CombatEngine = CombatState = Card = CardDeck = Enemy = EnemyInstance = None

__all__ = [
    # Core
    "GameState", "PlayerState", "BaseEngine",
    # World
    "Room", "Item", "Character",
    # Systems
    "Puzzle", "PuzzleSystem", "Inventory",
    "EventBus", "EventTypes",
    "CommandParser", "CommandHandler",
    # Data
    "JSONLoader", "SaveLoadManager",
    # UI
    "Renderer", "MainWindow", "Styles",
    "TextFormatter", "Animation", "Logger",
]
