"""entities.py — ECS 组件、物品目录、怪物模板库。

整合 alloy 的：
  - core.ecs.Component            → 自定义组件基类
  - world.item                    → Item / create_weapon / create_armor / create_consumable
  - systems.simple_combat         → MobTemplate / MobLibrary
"""
from __future__ import annotations

import copy
from dataclasses import dataclass, field

from alloy.core.ecs import Component
from alloy.world.item import (
    Item, create_weapon, create_armor, create_consumable,
)
from alloy.systems.simple_combat import MobTemplate, MobLibrary


# ═══════════════════════════════════════════════════════════
#  ECS 组件（挂在 alloy.core.ecs.Entity 上）
# ═══════════════════════════════════════════════════════════

@dataclass
class Position(Component):
    """网格坐标（x=列, y=行）。"""
    x: int = 0
    y: int = 0


@dataclass
class Health(Component):
    """生命值组件（怪物用）。"""
    value: int = 100
    max: int = 100


@dataclass
class MobBrain(Component):
    """怪物大脑：模板 + 程序化名字 + 状态机/行为树实例 + 特殊能力。"""
    template: MobTemplate
    name: str
    fsm: object = None          # alloy.ai.decision.GenericStateMachine
    bt: object = None           # alloy.ai.decision.BehaviorTree (Boss 用)
    blackboard: object = None   # alloy.ai.decision.Blackboard (Boss 用)
    alive: bool = True
    ability: str | None = None  # 特殊能力：poison / drain / regen（来自模板 metadata）
    # —— 新增：运行时战斗状态与行为参数 ——
    status_effects: list = None # 怪物身上的状态异常（中毒/灼烧/麻痹），同玩家结构
    attack_range: int = 1       # >1 表示远程怪（视线+射程内可发射）
    ranged_kind: str | None = None  # "arrow" / "bolt"
    onhit: str | None = None    # 远程命中附加效果：burn / poison
    enraged: bool = False       # Boss 狂暴阶段标记

    def __post_init__(self):
        if self.status_effects is None:
            self.status_effects = []


# ═══════════════════════════════════════════════════════════
#  物品目录（全部用引擎 Item 构建，携带 stats/effects）
# ═══════════════════════════════════════════════════════════

def build_catalog() -> dict[str, Item]:
    """构造可用物品目录：武器 / 护甲 / 药水。

    设计原则（参考 roguelike 装备曲线）：少量核心数值 + 清晰反馈，
    高阶物品随层数分档进入掉落池，形成可预期的成长节奏。
    """
    items: dict[str, Item] = {}

    weapons = [
        ("dagger", "匕首", 3),
        ("rusty_sword", "生锈铁剑", 4),
        ("iron_sword", "铁剑", 7),
        ("steel_blade", "钢刃", 10),
        ("rune_blade", "符文之刃", 13),
        ("legend_sword", "传说之剑", 18),
        ("void_edge", "虚空之锋", 23),
    ]
    for iid, name, atk in weapons:
        items[iid] = create_weapon(
            iid, name, {"attack": atk}, description=f"攻击力 +{atk}"
        )

    armors = [
        ("leather", "皮甲", 2),
        ("chain", "锁子甲", 4),
        ("plate", "板甲", 7),
        ("mythril", "秘银甲", 10),
        ("dragon_scale", "龙鳞甲", 14),
        ("titan_plate", "泰坦板甲", 19),
    ]
    for iid, name, dfn in armors:
        items[iid] = create_armor(
            iid, name, {"defense": dfn}, description=f"防御力 +{dfn}"
        )

    items["minor_potion"] = create_consumable(
        "minor_potion", "治疗药水", {"hp": 15}, description="恢复 15 点生命"
    )
    items["major_potion"] = create_consumable(
        "major_potion", "强效药水", {"hp": 40}, description="恢复 40 点生命"
    )
    items["greater_potion"] = create_consumable(
        "greater_potion", "极效药水", {"hp": 70}, description="恢复 70 点生命"
    )
    return items


# 按层数分档的掉落池（索引 = min(层-1, 4)）
WEAPON_TIERS = [
    ["dagger", "rusty_sword"],
    ["iron_sword", "rusty_sword"],
    ["steel_blade", "iron_sword"],
    ["rune_blade", "steel_blade"],
    ["legend_sword", "rune_blade", "void_edge"],
]
ARMOR_TIERS = [
    ["leather"],
    ["chain", "leather"],
    ["plate", "chain"],
    ["mythril", "plate"],
    ["dragon_scale", "mythril", "titan_plate"],
]
POTIONS = ["minor_potion", "major_potion", "greater_potion"]


def build_mob_library() -> MobLibrary:
    """怪物模板库：普通怪 + 守关 Boss（含特殊能力）。

    特殊能力（写在 metadata["ability"]，由 MobBrain.ability 读取）：
      - poison：攻击使玩家中毒（每回合掉血）
      - drain ：攻击吸血，自身回血
      - regen ：每回合自我恢复（适合高血量肉盾）
    """
    lib = MobLibrary()
    lib.register_batch([
        MobTemplate("goblin", "哥布林", icon="g", hp=12, damage=3,
                    drops=[("gold", 3, 8)]),
        MobTemplate("skeleton", "骷髅", icon="s", hp=18, damage=5,
                    drops=[("gold", 4, 10)]),
        MobTemplate("slime", "史莱姆", icon="S", hp=10, damage=2,
                    drops=[("gold", 2, 5)]),
        MobTemplate("orc", "兽人", icon="o", hp=28, damage=7,
                    drops=[("gold", 6, 14)]),
        # —— 新增怪物 ——
        MobTemplate("bat", "吸血蝠", icon="b", hp=9, damage=3,
                    drops=[("gold", 2, 6)],
                    metadata={"ability": "drain"}),
        MobTemplate("wraith", "幽魂", icon="w", hp=16, damage=6,
                    drops=[("gold", 5, 12)],
                    metadata={"ability": "poison"}),
        MobTemplate("troll", "巨魔", icon="T", hp=42, damage=9,
                    drops=[("gold", 10, 20), ("major_potion", 1, 1)],
                    metadata={"ability": "regen"}),
        MobTemplate("golem", "石巨人", icon="G", hp=55, damage=8,
                    drops=[("gold", 12, 25), ("rune_blade", 1, 1)],
                    metadata={"ability": "regen"}),
        # —— 远程 / 新行为怪物（打通「远程攻击 + 群聚」AI）——
        MobTemplate("archer", "骷髅弓手", icon="a", hp=14, damage=5,
                    drops=[("gold", 4, 10)],
                    metadata={"range": 6, "ranged": "arrow"}),
        MobTemplate("mage", "暗影法师", icon="m", hp=12, damage=6,
                    drops=[("gold", 6, 14), ("major_potion", 1, 1)],
                    metadata={"range": 5, "ranged": "bolt", "onhit": "burn"}),
        MobTemplate("spider", "毒蛛", icon="x", hp=8, damage=3,
                    drops=[("gold", 2, 6)],
                    metadata={"ability": "poison"}),
        MobTemplate("gargoyle", "石魔像", icon="V", hp=38, damage=7,
                    drops=[("gold", 9, 18), ("plate", 1, 1)],
                    metadata={"ability": "regen"}),
        # —— 守关 Boss ——
        MobTemplate("dragon", "巨龙", icon="D", mob_type="boss",
                    hp=90, damage=14,
                    drops=[("legend_sword", 1, 1), ("dragon_scale", 1, 1),
                           ("gold", 30, 60)]),
    ])
    return lib


# ───────────────────────────────────────────────────────────
#  Boss ASCII 立绘（沉浸感增强；遭遇 Boss 时渲染）
# ───────────────────────────────────────────────────────────
BOSS_ART: dict[str, list[str]] = {
    "dragon": [
        "        \\||/",
        "        ( oo )",
        "    ___|____\\__",
        "  ==|  _ dragon_  |",
        "    | （传说巨龙）|",
        "    ~~~UU~~~~UU~~~",
    ],
}



def scale_template(tmpl: MobTemplate, factor: float) -> MobTemplate:
    """复制模板并按层数难度系数缩放 HP / 伤害，得到本层实际怪物。

    factor = 1 + (floor-1) * 难度增量。Boss 也走同一曲线，
    保证越深越危险、越靠后越有压迫感（roguelike 难度爬升共识）。
    """
    t = copy.copy(tmpl)
    t.hp = max(1, round(tmpl.hp * factor))
    t.damage = max(1, round(tmpl.damage * factor))
    return t

