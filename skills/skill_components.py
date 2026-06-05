"""
技能系统 — ECS 组件（混合架构之 ECS 部分）
技能作为 Component 挂在玩家实体上。
"""

from typing import List, Optional


class SkillSlotComponent:
    """
    技能槽组件：挂在玩家实体上。
    持有已解锁技能 ID 列表和冷却状态。
    """
    def __init__(self, max_slots: int = 4) -> None:
        self.max_slots: int = max_slots
        # 已解锁技能 ID 列表（对应 skill_defs.py 的 skill_id）
        self.skill_ids: List[str] = []
        # 冷却计时：{skill_id: remaining_cooldown}
        self.cooldowns: dict[str, int] = {}


class CooldownComponent:
    """通用冷却组件（可挂在任意实体上）"""
    def __init__(self, cooldown: int = 0) -> None:
        self.remaining: int = cooldown


class SkillEffectComponent:
    """
    技能效果组件：临时挂在目标实体上，下一帧由系统结算。
    """
    def __init__(self,
                 damage_bonus: int = 0,
                 heal_amount: int = 0,
                 dodge_bonus: float = 0.0,
                 turns_remaining: int = 1) -> None:
        self.damage_bonus: int = damage_bonus
        self.heal_amount: int = heal_amount
        self.dodge_bonus: float = dodge_bonus
        self.turns_remaining: int = turns_remaining
