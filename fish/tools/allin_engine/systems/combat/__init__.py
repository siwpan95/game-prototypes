"""
战斗系统 — 回合制卡牌战斗引擎。

包含:
- CombatState: 单场战斗完整状态（HP/神经/AP/格挡/牌堆/Buff/Debuff）
- CombatEngine: 战斗生命周期管理（开始/出牌/回合结束/胜负判定）
- Card / CardDeck / CardLibrary: 卡牌定义、组牌与管理
- Enemy / EnemyInstance / Intent / EnemyLibrary: 敌人定义与实例
"""

from __future__ import annotations

from .combat_engine import CombatState, CombatEngine
from .card import Card, CardDeck, CardLibrary
from .enemy import Enemy, EnemyInstance, Intent, IntentType, EnemyLibrary

# 轻量回合制战斗（来自 systems/simple_combat，作为 combat 公共 API 的一部分）
from ..simple_combat import SimpleCombat, MobTemplate, CombatResult, MobLibrary

__all__ = [
    "CombatState",
    "CombatEngine",
    "Card",
    "CardDeck",
    "CardLibrary",
    "Enemy",
    "EnemyInstance",
    "Intent",
    "IntentType",
    "EnemyLibrary",
    "SimpleCombat",
    "MobTemplate",
    "CombatResult",
    "MobLibrary",
]
