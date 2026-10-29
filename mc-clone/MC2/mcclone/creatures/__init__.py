# -*- coding: utf-8 -*-
"""creatures — M4 生物与世界模块包（生物/物理/AI/掉落/系统/刷怪/渲染）。

导出（供 main_gui / 测试直接使用）：
  Creature / CreatureKind / AIState / CreatureConfig（entity）
  move_with_collision（physics）
  AIController / AIContext / Pathing（ai）
  DROP_TABLE / roll_drops / TAMING（drops）
  CreatureSystem（system）
  SpawnSystem / SpawnConfig（spawn）
  CreatureRenderer（render）

本包仅依赖地基（geometry / block_registry / block_world / event_bus）与
本地 creatures 子模块；不依赖 pygame（渲染器延迟导入）；可 headless 断言。
"""

from __future__ import annotations

from mcclone.creatures.entity import (
    Creature,
    CreatureKind,
    AIState,
    CreatureConfig,
)
from mcclone.creatures.physics import move_with_collision
from mcclone.creatures.ai import AIController, AIContext, Pathing
from mcclone.creatures.drops import DROP_TABLE, roll_drops, TAMING
from mcclone.creatures.system import CreatureSystem
from mcclone.creatures.spawn import SpawnSystem, SpawnConfig
from mcclone.creatures.render import CreatureRenderer

__all__ = [
    "Creature",
    "CreatureKind",
    "AIState",
    "CreatureConfig",
    "move_with_collision",
    "AIController",
    "AIContext",
    "Pathing",
    "DROP_TABLE",
    "roll_drops",
    "TAMING",
    "CreatureSystem",
    "SpawnSystem",
    "SpawnConfig",
    "CreatureRenderer",
]
