"""
AllinEngine 系统层 — 统一游戏系统模块。

提供输入处理、命令解析、谜题系统、背包管理、
存档管理、Mod加载、战斗引擎等核心系统。

使用指南（避免误用两套并行系统）：
    - 战斗有两套，互相独立、可共存：
        * CombatEngine + Card/CardDeck/CardLibrary/Enemy（卡牌驱动，适合 Roguelike）
        * SimpleCombat + MobTemplate/MobLibrary（三选一回合制，适合生存/RPG）
      选型看玩法，不要在同一局游戏里混用两套状态机。
    - 背包有两套，互相独立：
        * Inventory（基础键值背包，init 层使用）
        * StackableInventory + EquipmentSlots + ItemRegistry（来自 Minecraft 实战，支持堆叠/装备）
      同样按项目需要二选一；StackableInventory 与 SimpleCombat 已对齐接口可无缝配合。
"""

from __future__ import annotations

# 输入系统
from .input import InputManager, InputSource, CLIInputSource, PygameInputSource, TkinterInputSource

# 命令系统
from .command import CommandParser, CommandHandler, CommandResult

# 谜题系统
from .puzzle import Puzzle, PuzzleSystem

# 背包系统
from .inventory import Inventory, InventoryItem

# 可堆叠背包（来自 Minecraft 实战沉淀）
from .stackable_inventory import (
    StackableInventory, EquipmentSlots, ItemRegistry,
)

# 存档系统
from .save_load import SaveLoadManager, SaveSlotInfo

# Mod 加载系统
from .mod_loader import (
    ModManager, MapManager,
    ModManifest, MapDef, PortalDef, MechanismDef, MechanismAction,
)

# 战斗系统
from .combat import (
    CombatState, CombatEngine,
    Card, CardDeck, CardLibrary,
    Enemy, EnemyInstance, Intent, IntentType, EnemyLibrary,
)

# 轻量回合制战斗（来自 Minecraft 实战沉淀）
from .simple_combat import (
    SimpleCombat, MobTemplate, CombatResult, MobLibrary,
)

# 合成系统（来自 Minecraft 实战沉淀）
from .crafting import CraftingSystem, Recipe

__all__ = [
    # 输入
    "InputManager", "InputSource", "CLIInputSource", "PygameInputSource", "TkinterInputSource",
    # 命令
    "CommandParser", "CommandHandler", "CommandResult",
    # 谜题
    "Puzzle", "PuzzleSystem",
    # 背包
    "Inventory", "InventoryItem",
    "StackableInventory", "EquipmentSlots", "ItemRegistry",
    # 存档
    "SaveLoadManager", "SaveSlotInfo",
    # Mod
    "ModManager", "MapManager",
    "ModManifest", "MapDef", "PortalDef", "MechanismDef", "MechanismAction",
    # 战斗（卡牌）
    "CombatState", "CombatEngine",
    "Card", "CardDeck", "CardLibrary",
    "Enemy", "EnemyInstance", "Intent", "IntentType", "EnemyLibrary",
    # 战斗（轻量回合制）
    "SimpleCombat", "MobTemplate", "CombatResult", "MobLibrary",
    # 合成
    "CraftingSystem", "Recipe",
]
