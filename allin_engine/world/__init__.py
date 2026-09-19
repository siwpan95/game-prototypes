"""
allin_engine.world — 游戏世界模块。

提供游戏世界核心数据模型：
  - 游戏状态管理 (GameState, PlayerState, ImageryNetwork)
  - 字符网格地图 (MapData)
  - 房间与关卡 (Room, Portal, Mechanism)
  - 物品系统 (Item)
  - 角色系统 (Character)
  - 地图导航图 (MapGraph, MapNode)
"""

from .game_state import (
    Chapter,
    GameState,
    ImageryNetwork,
    ImageryNode,
    PlayerState,
)
from .map_data import MapData
from .room import (
    Mechanism,
    MechanismAction,
    Portal,
    Room,
)
from .item import (
    Item,
    create_armor,
    create_consumable,
    create_key,
    create_weapon,
)
from .character import Character
from .map_graph import (
    MapGraph,
    MapNode,
)
from .pathfinding import (
    GraphPathFinder,
    grid_astar,
)

__all__ = [
    # game_state
    "Chapter",
    "GameState",
    "ImageryNetwork",
    "ImageryNode",
    "PlayerState",
    # map_data
    "MapData",
    # room
    "Mechanism",
    "MechanismAction",
    "Portal",
    "Room",
    # item
    "Item",
    "create_armor",
    "create_consumable",
    "create_key",
    "create_weapon",
    # character
    "Character",
    # map_graph
    "MapGraph",
    "MapNode",
    # pathfinding
    "GraphPathFinder",
    "grid_astar",
]
