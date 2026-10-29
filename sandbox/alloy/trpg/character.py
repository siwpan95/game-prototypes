"""alloy.trpg.character - Character 公共门面（alloy 化装配）

自 D20（G:\\local\\D20，D&D-GURPS 变体角色构建器）并入（R2）。14 个子系统不再是
mixin 多重继承，而是挂到 ``TrpgContext`` 上的 ``Service``：

    Character
      ├── ctx.attributes   AttributesService   属性购买
      ├── ctx.equipment    EquipmentService    装备系统
      ├── ctx.perks        PerksService        优点/缺点/天赋
      ├── ctx.techniques   TechniquesService    技术（战技/法术）
      ├── ctx.race         RaceService         种族
      ├── ctx.background   BackgroundService   背景
      ├── ctx.feats        FeatsService        专长
      ├── ctx.skills       SkillsService       技能购买与默认值
      ├── ctx.dice         DiceService         骰子检定
      ├── ctx.derived      DerivedService      HP/AC/攻击/豁免
      ├── ctx.slots        SpellSlotsService   法术位
      ├── ctx.rest         RestService         先攻/休整
      ├── ctx.combat       CombatService       战斗宏
      └── ctx.sheet        SheetService        角色卡渲染

``Character`` 本身只是一层**兼容门面**：
- 持有 ``ctx``（TrpgContext：alloy 服务容器 + alloy EventBus 事件 + 可逆生命周期）
  与 ``state``（可变实例状态）；
- 全部老公共方法委托给对应 ``ctx.<service>.<method>``；
- 实例状态字段（``cp`` / ``attributes`` / ``skills`` / …）通过 ``__getattr__`` /
  ``__setattr__`` 透明代理到 ``ctx.state``，服务读写 ``ctx.state`` 即等于读写角色；
- 类级规则数据（``SKILL_LIBRARY`` / ``TECHNIQUES`` / …）从 ``alloy.trpg.data``
  单一事实来源复制为类属性，保证 ``char.SKILL_LIBRARY`` 等老 API 不变；
- 装配由 ``preset_trpg`` 驱动（alloy 预设风格；D20 原为 composition.yml + loader）。

多角色装配模式（fork 双作用域）：
    from alloy.core.context import Context
    from alloy.core.event_bus import EventBus
    from alloy.trpg import Character, preset_trpg

    root = Context(); root.provide("bus", EventBus())
    fork = root.fork("char1")
    preset_trpg(fork)
    char = Character(ctx=fork)      # 每角色独立服务实例与事件订阅
    fork.dispose()                  # 该角色随作用域整体回收
"""

from __future__ import annotations

from .preset import preset_trpg
from .data import (
    ATTRIBUTES, EQUIPMENT_LIBRARY, SKILL_LIBRARY, DIFFICULTY_COST,
    TECHNIQUES, TALENT_BONUS_GROUPS, SKILL_CATEGORIES, ARMOR_PROFICIENCY,
    ADVANTAGES_LIBRARY, DISADVANTAGES_LIBRARY, WEAPON_DICE, FINESSE_WEAPONS,
    DEFAULT_STARTING_CP, DEFAULT_MAX_DISADVANTAGE_CP,
)


class CharacterState:
    """角色可变状态（单一真相，被所有 Service 共享读写）。

    字段与 D20 重构前 ``Character`` 实例状态一一对应，确保行为一致。
    """

    def __init__(self, starting_cp: int, max_disadvantage_cp: int) -> None:
        # ---- 核心资源 ----
        self.cp = starting_cp
        self.base_cp = starting_cp                    # 创建期判定基准
        self.purchases: int = 0                       # 购买动作计数（>0 即锁创建期）
        self.max_disadvantage_cp = max_disadvantage_cp
        # ---- 属性 ----
        self.attributes: dict[str, int] = {attr: 10 for attr in ATTRIBUTES}
        # ---- 优缺点 / 天赋 ----
        self.advantages: list[str] = []
        self.disadvantages: list[tuple[str, int]] = []
        self.talents: list[tuple[str, int]] = []        # (天赋名, 等级)
        # ---- 技能 / 技术 ----
        self.skills: dict[str, int] = {}                # {技能名: 等级}
        self.techniques: list[str] = []                 # 已学技术名
        # ---- 装备 ----
        self.armor_bonus: int = 0
        self._armor_max_dex: int = 99
        self.equipment: list[str] = []
        # ---- 扩充子系统（种族/背景/专长/法术位/休整）----
        self.race: str = ""
        self.race_element: str = "火"
        self.background: str = ""
        self.feats: list[str] = []                      # 专长（含选择：名(选择)）
        self.proficiencies: list[str] = []              # 熟练技能（+2 有效等级）
        self.slots: dict[int, int] = {}                 # {环位: 拥有法术位数}
        self.slots_used: dict[int, int] = {}            # {环位: 已消耗数}
        self.current_hp: int | None = None              # None = 满血（随 max_hp）
        self.hit_dice_used: int = 0
        self.lucky_used: int = 0
        self.breath_used: bool = False
        self.relentless_used: bool = False


class Character:
    """D&D-GURPS 变体角色（alloy 化门面）。

    老 API（``char.set_attribute`` / ``char.SKILL_LIBRARY`` / ``char.cp`` /
    ``char.skills`` / ``char.show_sheet()`` …）全部保留，内部委托给 ``ctx`` 上的 Service。
    """

    # ---- 类级规则数据（单一事实来源：alloy.trpg.data），保持老 API 可用 ----
    ATTRIBUTES = ATTRIBUTES
    EQUIPMENT_LIBRARY = EQUIPMENT_LIBRARY
    SKILL_LIBRARY = SKILL_LIBRARY
    DIFFICULTY_COST = DIFFICULTY_COST
    TECHNIQUES = TECHNIQUES
    TALENT_BONUS_GROUPS = TALENT_BONUS_GROUPS
    SKILL_CATEGORIES = SKILL_CATEGORIES
    ARMOR_PROFICIENCY = ARMOR_PROFICIENCY
    ADVANTAGES_LIBRARY = ADVANTAGES_LIBRARY
    DISADVANTAGES_LIBRARY = DISADVANTAGES_LIBRARY
    WEAPON_DICE = WEAPON_DICE
    FINESSE_WEAPONS = FINESSE_WEAPONS
    DEFAULT_STARTING_CP = DEFAULT_STARTING_CP
    DEFAULT_MAX_DISADVANTAGE_CP = DEFAULT_MAX_DISADVANTAGE_CP

    # 需要透明代理到 ctx.state 的实例状态字段
    _STATE_ATTRS = (
        "cp", "max_disadvantage_cp", "attributes", "advantages",
        "disadvantages", "talents", "skills", "techniques",
        "equipment", "armor_bonus", "_armor_max_dex",
        "race", "race_element", "background", "feats", "proficiencies",
        "slots", "slots_used", "current_hp", "hit_dice_used",
        "lucky_used", "breath_used", "relentless_used",
    )

    def __init__(self, starting_cp: int = DEFAULT_STARTING_CP,
                 max_disadvantage_cp: int = DEFAULT_MAX_DISADVANTAGE_CP,
                 *, ctx=None):
        # ctx / state 为普通实例属性，不走状态代理
        self.state = CharacterState(starting_cp, max_disadvantage_cp)
        if ctx is None:
            from alloy.core.context import Context
            ctx = Context()
        # alloy 预设装配（幂等）：宿主已有存活的 trpg 内核则直接复用
        preset_trpg(ctx)
        self.ctx = ctx.get("trpg")
        self.ctx.state = self.state

    def dispose(self) -> None:
        """回收本角色内核：逆序运行全部 disposer（含事件退订）并清空服务。

        只回收 TRPG 作用域，不动宿主其它服务；多角色共享宿主时建议用 fork 模式
        （fork.dispose() 随作用域整体回收）。
        """
        self.ctx.dispose()

    # ------------------------------------------------------------------
    #  状态字段透明代理：char.cp / char.attributes / ... 读写都落到 ctx.state
    # ------------------------------------------------------------------
    def __getattr__(self, name: str):
        if name in self._STATE_ATTRS:
            return getattr(self.state, name)
        raise AttributeError(name)

    def __setattr__(self, name: str, value) -> None:
        if name in self._STATE_ATTRS:
            object.__setattr__(self.state, name, value)
        else:
            object.__setattr__(self, name, value)

    # ==================================================================
    #  公共 API：全部委托给 ctx.<service>
    # ==================================================================
    # ---- 属性 ----
    def set_attribute(self, attr: str, value: int) -> tuple[bool, str]:
        return self.ctx.attributes.set_attribute(attr, value)

    def attr_mod(self, attr: str) -> int:
        return self.ctx.attributes.attr_mod(attr)

    # ---- 优缺点 / 天赋 ----
    def add_advantage(self, name: str, cost: int) -> tuple[bool, str]:
        return self.ctx.perks.add_advantage(name, cost)

    def add_advantage_by_name(self, name: str) -> tuple[bool, str]:
        return self.ctx.perks.add_advantage_by_name(name)

    def add_disadvantage(self, name: str, cp_return: int) -> tuple[bool, str]:
        return self.ctx.perks.add_disadvantage(name, cp_return)

    def add_disadvantage_by_name(self, name: str) -> tuple[bool, str]:
        return self.ctx.perks.add_disadvantage_by_name(name)

    def add_talent(self, talent_name: str, level: int = 1) -> tuple[bool, str]:
        return self.ctx.perks.add_talent(talent_name, level)

    def get_talent_bonus(self, skill_name: str) -> int:
        return self.ctx.perks.get_talent_bonus(skill_name)

    # ---- 技能 ----
    def calc_skill_cost(self, skill_name: str, target_rank: int) -> tuple[int, int]:
        return self.ctx.skills.calc_skill_cost(skill_name, target_rank)

    def purchase_skill(self, skill_name: str, target_rank: int) -> tuple[bool, str]:
        return self.ctx.skills.purchase_skill(skill_name, target_rank)

    def check_foundations(self) -> list[str]:
        return self.ctx.skills.check_foundations()

    def effective_skill_rank(self, skill_name: str) -> int:
        return self.ctx.skills.effective_skill_rank(skill_name)

    # ---- 技术 ----
    def purchase_technique(self, tech_name: str) -> tuple[bool, str]:
        return self.ctx.techniques.purchase_technique(tech_name)

    def has_technique(self, tech_name: str) -> bool:
        return self.ctx.techniques.has_technique(tech_name)

    # ---- 装备 ----
    def equip_item(self, item_name: str) -> tuple[bool, str]:
        return self.ctx.equipment.equip_item(item_name)

    def unequip_item(self, item_name: str) -> tuple[bool, str]:
        return self.ctx.equipment.unequip_item(item_name)

    def has_finesse_weapon(self) -> bool:
        return self.ctx.equipment.has_finesse_weapon()

    def _get_equipped_weapon(self) -> str:
        return self.ctx.equipment._get_equipped_weapon()

    def _recalc_armor_bonus(self) -> None:
        self.ctx.equipment._recalc_armor_bonus()

    # ---- 扩充：种族 / 背景 / 专长 / 法术位 / 休整 ----
    def set_race(self, name: str, choices: dict | None = None) -> tuple[bool, str]:
        return self.ctx.race.set_race(name, choices)

    def set_background(self, name: str) -> tuple[bool, str]:
        return self.ctx.background.set_background(name)

    def background_feature(self) -> str:
        return self.ctx.background.feature()

    def add_feat(self, name: str, choice: str = "") -> tuple[bool, str]:
        return self.ctx.feats.add_feat(name, choice)

    def has_feat(self, name: str) -> bool:
        return self.ctx.feats.has_feat(name)

    def buy_slot(self, ring: int) -> tuple[bool, str]:
        return self.ctx.slots.buy_slot(ring)

    def slot_table(self) -> list[tuple[int, int, int]]:
        return self.ctx.slots.slot_table()

    def roll_initiative(self) -> str:
        return self.ctx.rest.roll_initiative()

    def short_rest(self) -> str:
        return self.ctx.rest.short_rest()

    def long_rest(self) -> str:
        return self.ctx.rest.long_rest()

    def take_damage(self, amount: int, damage_type: str = "") -> str:
        return self.ctx.rest.take_damage(amount, damage_type)

    def heal(self, amount: int) -> str:
        return self.ctx.rest.heal(amount)

    # ---- 衍生数值 ----
    def hp(self) -> int:
        return self.ctx.derived.hp()

    def attack_bonus(self, melee: bool = True) -> int:
        return self.ctx.derived.attack_bonus(melee)

    def save_bonus(self, save_type: str) -> int:
        return self.ctx.derived.save_bonus(save_type)

    @property
    def ac(self) -> int:
        return self.ctx.derived.ac

    @property
    def max_hp(self) -> float:
        return self.ctx.derived.max_hp

    # ---- 战斗宏 ----
    def combat_macro(self, macro_name: str, **kwargs) -> str:
        return self.ctx.combat.combat_macro(macro_name, **kwargs)

    def _sneak_attack_dice(self) -> int:
        return self.ctx.combat._sneak_attack_dice()

    # ---- 骰子 ----
    def d20_check(self, skill_name: str, dc: int) -> str:
        return self.ctx.dice.d20_check(skill_name, dc)

    def d100_check(self, skill_name: str) -> str:
        return self.ctx.dice.d100_check(skill_name)

    def gurps_check(self, skill_name: str, modifier: int = 0) -> str:
        return self.ctx.dice.gurps_check(skill_name, modifier)

    def roll_d6(self, num_dice: int, mod: int = 0) -> str:
        return self.ctx.dice.roll_d6(num_dice, mod)

    def _roll_weapon_damage(self, weapon_name: str) -> tuple[list[int], str]:
        return self.ctx.dice._roll_weapon_damage(weapon_name)

    # ---- 角色卡 ----
    def show_sheet(self) -> str:
        return self.ctx.sheet.show_sheet()

    def to_dict(self) -> dict:
        return self.ctx.sheet.to_dict()

    # ------------------------------------------------------------------
    def __repr__(self) -> str:
        return (f"<Character CP={self.cp} HP={self.hp()} AC={self.ac} "
                f"skills={len(self.skills)} techs={len(self.techniques)}>")
