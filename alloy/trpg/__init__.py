"""alloy.trpg - TRPG 规则内核（自 D20 并入，R2）

D&D-GURPS 变体角色构建器（D20，G:\\local\\D20）的规则内核：属性/装备/优缺点/
天赋/技术/种族/背景/专长/技能/骰子/衍生/法术位/休整/战斗宏/角色卡 14 个子系统
+ 数据中枢，运行在 alloy 的可逆装配内核（Context + EventBus）之上。

数据中枢：alloy.trpg.data（融合 D&D 三宝书与 GURPS Basic Set，单一事实来源）。

快速开始：
    from alloy.trpg import Character, preset_trpg

    # 独立用法（自备 alloy Context）
    c = Character()
    c.set_attribute("力量", 16)
    c.purchase_skill("近战攻击", 12)
    print(c.show_sheet())

    # 挂入引擎（preset 风格，可与其它 alloy 预设共存）
    from alloy.core.context import Context
    ctx = Context()
    preset_trpg(ctx)
    c2 = Character(ctx=ctx)
"""
from .character import Character
from .context import CordisError, Service, TrpgContext
from .data import (
    ATTRIBUTES, EQUIPMENT_LIBRARY, SKILL_LIBRARY, DIFFICULTY_COST,
    TECHNIQUES, TALENT_BONUS_GROUPS, SKILL_CATEGORIES, ARMOR_PROFICIENCY,
    ADVANTAGES_LIBRARY, DISADVANTAGES_LIBRARY, WEAPON_DICE, FINESSE_WEAPONS,
    DEFAULT_STARTING_CP, DEFAULT_MAX_DISADVANTAGE_CP, ability_mod,
)
from .dice import (
    gurps_success_chance, roll_3d6, roll_d6, roll_d20, roll_d100, roll_dice,
)
from .preset import MOUNT_ORDER, mount_trpg_services, preset_trpg

__all__ = [
    "Character",
    "CordisError",
    "Service",
    "TrpgContext",
    "preset_trpg",
    "mount_trpg_services",
    "MOUNT_ORDER",
    "ATTRIBUTES", "EQUIPMENT_LIBRARY", "SKILL_LIBRARY", "DIFFICULTY_COST",
    "TECHNIQUES", "TALENT_BONUS_GROUPS", "SKILL_CATEGORIES", "ARMOR_PROFICIENCY",
    "ADVANTAGES_LIBRARY", "DISADVANTAGES_LIBRARY", "WEAPON_DICE", "FINESSE_WEAPONS",
    "DEFAULT_STARTING_CP", "DEFAULT_MAX_DISADVANTAGE_CP", "ability_mod",
    "roll_d20", "roll_d100", "roll_d6", "roll_3d6", "roll_dice",
    "gurps_success_chance",
]

# 继承 D20 的版本线（2.0.0 → 并入 alloy 记为 2.1.0）
__version__ = "2.1.0"
