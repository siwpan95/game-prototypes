"""
alloy.test.test_trpg - TRPG 规则内核测试（自 D20 测试套件移植，R2）

规则内核自 D20（G:\\local\\D20）并入 alloy.trpg 后，本套件钉住与 D20 一致的
行为契约（D&D-GURPS 变体角色构建），并补上 alloy 侧新增的内核契约：
装配幂等 / 共享总线 / fork 每角色独立作用域 / 事件退订回收 / 装配失败 loud。

移植口径：D20 的 pytest fixtures 改为普通构造助手，pytest.raises 改为显式
try/except；随机种子与 D20 原测试逐一对齐，保证战斗宏断言可重现。
"""

import random

from alloy.core.context import Context, DuplicateServiceError
from alloy.core.event_bus import EventBus
from alloy.trpg import (
    Character,
    CordisError,
    Service,
    TrpgContext,
    preset_trpg,
)
from alloy.trpg.attributes import calc_attribute_cost
from alloy.trpg.data import DIFFICULTY_COST
from alloy.trpg.dice import (
    gurps_success_chance,
    roll_3d6,
    roll_d100,
    roll_d20,
    roll_d6,
    roll_dice,
    roll_weapon_damage,
)

# 与 D20 composition.yml 一致的 14 服务清单
FOURTEEN_SERVICES = [
    "attributes", "background", "combat", "derived", "dice", "equipment", "feats",
    "perks", "race", "rest", "sheet", "skills", "slots", "techniques",
]

# D20 盗贼.txt 的稳定关键字段（与 CP 末位无关）
THIEF_FIELDS = [
    "属性: 力量:11, 敏捷:10, 体质:13",
    "优点: 昏暗视觉",
    "缺点: 荣誉准则(+10)",
    "天赋: 轻巧战法 Lv.1",
    "近战攻击: 10(+1) = 11",
    "技术: 偷袭要害打击",
    "匕首:",
    "全身板甲:",
    "铁盾:",
    "HP: 65 | AC: 20",
    "近战: +11 | 远程: +8",
    "强韧: +11 | 反射: +10 | 意志: +10",
]


# ---------------------------------------------------------------------------
#  构造助手（对应 D20 conftest fixtures）
# ---------------------------------------------------------------------------
def _char(cp=150):
    return Character(cp)


def _fighter():
    c = Character()
    c.set_attribute("力量", 16)
    c.purchase_skill("近战攻击", 12)
    c.purchase_skill("活力", 10)  # 提供 HP
    c.equip_item("匕首")
    return c


def _seeded_char():
    random.seed(42)
    c = Character()
    c.set_attribute("力量", 16)
    c.purchase_skill("近战攻击", 12)
    c.purchase_skill("活力", 10)
    c.equip_item("短剑")
    return c


def _thief():
    """复现 D20 data/sample_thief.py 的盗贼构建（仅公共 API）。"""
    c = Character(150)
    c.set_attribute("力量", 11)
    c.set_attribute("体质", 13)
    c.add_advantage("昏暗视觉", 2)
    c.add_disadvantage("荣誉准则", 10)
    c.add_talent("轻巧战法", 1)
    for sk, lvl in [("反射豁免", 10), ("强韧豁免", 10), ("意志豁免", 10),
                    ("活力", 14), ("潜行", 10), ("躲藏", 10),
                    ("近战攻击", 10)]:
        c.purchase_skill(sk, lvl)
    c.purchase_technique("偷袭要害打击")
    c.equip_item("匕首")
    c.equip_item("全身板甲")
    c.equip_item("铁盾")
    return c


# ---------------------------------------------------------------------------
#  属性系统
# ---------------------------------------------------------------------------
def test_trpg_attr_cost_base_free():
    assert calc_attribute_cost(10) == 0
    assert calc_attribute_cost(8) == 0  # 低于 10 不退款


def test_trpg_attr_cost_brackets():
    assert calc_attribute_cost(11) == 10
    assert calc_attribute_cost(12) == 20
    assert calc_attribute_cost(13) == 35


def test_trpg_attr_cost_monotonic():
    prev = 0
    for v in range(10, 21):
        cost = calc_attribute_cost(v)
        assert cost >= prev
        prev = cost


def test_trpg_set_attribute_basic():
    c = _char()
    ok, _ = c.set_attribute("力量", 14)
    assert ok
    assert c.attributes["力量"] == 14
    assert c.cp == 150 - calc_attribute_cost(14)


def test_trpg_set_attribute_too_low():
    ok, msg = _char().set_attribute("力量", 9)
    assert not ok and "不能低于10" in msg


def test_trpg_set_attribute_unknown():
    ok, _ = _char().set_attribute("幸运", 12)
    assert not ok


def test_trpg_set_attribute_insufficient_cp():
    ok, msg = _char().set_attribute("力量", 20)
    assert not ok and "CP不足" in msg


def test_trpg_set_attribute_lower_refunds():
    c = _char()
    c.set_attribute("力量", 14)
    cp_after = c.cp
    ok, _ = c.set_attribute("力量", 12)
    assert ok and c.cp > cp_after


def test_trpg_attr_mod():
    c = _char()
    c.set_attribute("敏捷", 16)
    assert c.attr_mod("敏捷") == 3
    assert c.attr_mod("力量") == 0


# ---------------------------------------------------------------------------
#  技能系统
# ---------------------------------------------------------------------------
def test_trpg_skill_cost_unknown():
    assert _char().calc_skill_cost("不存在的技能", 10) == (0, 0)


def test_trpg_skill_cost_to_attr_level():
    cost, delta = _char().calc_skill_cost("近战攻击", 10)
    assert delta == 10 and cost == 11


def test_trpg_skill_cost_difficulty():
    assert DIFFICULTY_COST["A"][3] > DIFFICULTY_COST["E"][3]


def test_trpg_purchase_skill_success():
    c = _char()
    ok, _ = c.purchase_skill("近战攻击", 12)
    assert ok and c.skills["近战攻击"] == 12 and c.cp < 150


def test_trpg_purchase_skill_insufficient_cp():
    ok, msg = _char().purchase_skill("近战攻击", 25)
    assert not ok and "CP不足" in msg


def test_trpg_purchase_skill_no_improvement():
    c = _char()
    c.purchase_skill("近战攻击", 10)
    ok, msg = c.purchase_skill("近战攻击", 10)
    assert not ok and "未提高" in msg


def test_trpg_foundations_all_missing():
    missing = _char().check_foundations()
    assert len(missing) == 8
    assert "近战攻击" in missing and "活力" in missing


def test_trpg_foundations_clear():
    c = _char()
    for sk in ["活力", "近战攻击", "远程攻击", "闪避防御",
               "强韧豁免", "反射豁免", "意志豁免", "施法攻击"]:
        c.purchase_skill(sk, 11)
    assert c.check_foundations() == []


def test_trpg_default_rank_zero():
    assert _char().effective_skill_rank("潜行") == 0


def test_trpg_default_rank_same_attr():
    c = _char()
    c.purchase_skill("近战攻击", 14)
    assert c.effective_skill_rank("运动") == 12   # 同目 avg(14)-2


def test_trpg_default_rank_same_category():
    c = _char()
    c.purchase_skill("近战攻击", 14)
    assert c.effective_skill_rank("躲藏") == 11   # 同纲 avg(14)-3


def test_trpg_learned_overrides_default():
    c = _char()
    c.purchase_skill("潜行", 15)
    assert c.effective_skill_rank("潜行") == 15


def test_trpg_talent_bonus_applied():
    c = _char()
    c.purchase_skill("潜行", 10)
    c.add_talent("暗杀者", 2)
    assert c.effective_skill_rank("潜行") == 12


# ---------------------------------------------------------------------------
#  骰子与检定
# ---------------------------------------------------------------------------
def test_trpg_roll_ranges():
    for _ in range(200):
        assert 1 <= roll_d20() <= 20
        assert 1 <= roll_d100() <= 100
    rolls, total = roll_3d6()
    assert len(rolls) == 3 and 3 <= total <= 18


def test_trpg_roll_d6():
    rolls, total = roll_d6(3, mod=2)
    assert len(rolls) == 3 and total == sum(rolls) + 2
    assert roll_d6(0) == ([], 0)


def test_trpg_gurps_chance():
    assert gurps_success_chance(3) == 0
    assert gurps_success_chance(18) == 100
    assert 45 <= gurps_success_chance(10) <= 55


def test_trpg_weapon_damage():
    random.seed(0)
    rolls, desc = roll_weapon_damage("长剑")
    assert desc == "1d8" and len(rolls) == 1 and 1 <= rolls[0] <= 8
    random.seed(0)
    rolls, desc = roll_weapon_damage("巨剑")
    assert desc == "2d6" and len(rolls) == 2
    random.seed(0)
    _, desc = roll_weapon_damage("不存在的武器")
    assert desc == "1d4"


# ---------------------------------------------------------------------------
#  通用 NdS 伤害骰与 rng 注入（R2 反向增强：moba_battle_platform 同构原语）
# ---------------------------------------------------------------------------
def test_trpg_roll_dice_ranges():
    for _ in range(100):
        assert 1 <= roll_dice(2, 6) <= 12
        assert 1 <= roll_dice(1, 4) <= 4


def test_trpg_roll_dice_edge():
    assert roll_dice(0, 6) == 0
    assert roll_dice(-3, 6) == 0
    assert roll_dice(2, 0) == 2   # size<=0 收敛为 1，两骰各 1


def test_trpg_roll_dice_seeded():
    random.seed(42)
    a = roll_dice(3, 8)
    random.seed(42)
    b = roll_dice(3, 8)
    assert a == b


def test_trpg_rng_injection():
    import random as _random
    r1, r2 = _random.Random(7), _random.Random(7)
    assert roll_d20(r1) == roll_d20(r2)
    r3, r4 = _random.Random(7), _random.Random(7)
    assert roll_dice(2, 12, r3) == roll_dice(2, 12, r4)


def test_trpg_roll_d6_rng_injection():
    from alloy.trpg.dice import roll_d6 as _d6
    import random as _random
    r1, r2 = _random.Random(5), _random.Random(5)
    assert _d6(2, mod=3, rng=r1) == _d6(2, mod=3, rng=r2)


# ---------------------------------------------------------------------------
#  装备系统
# ---------------------------------------------------------------------------
def test_trpg_equip_weapon():
    c = _char()
    ok, _ = c.equip_item("匕首")
    assert ok and "匕首" in c.equipment and c.cp == 148


def test_trpg_equip_unknown():
    ok, msg = _char().equip_item("神器")
    assert not ok and "未知装备" in msg


def test_trpg_equip_armor_proficiency():
    c = _char()
    ok, _ = c.equip_item("皮甲")           # 轻甲无需专精
    assert ok
    ok, msg = c.equip_item("鳞甲")         # 中甲需闪避防御
    assert not ok and "闪避防御" in msg
    c.purchase_skill("闪避防御", 11)
    assert c.equip_item("鳞甲")[0]
    ok, msg = c.equip_item("全身板甲")     # 重甲需近战攻击
    assert not ok and "近战攻击" in msg


def test_trpg_unequip_refunds():
    c = _char()
    c.purchase_skill("近战攻击", 11)
    c.equip_item("铁盾")
    cp_after = c.cp
    ok, _ = c.unequip_item("铁盾")
    assert ok and c.cp == cp_after + 5


def test_trpg_armor_bonus():
    c = _char()
    c.purchase_skill("近战攻击", 11)
    c.equip_item("全身板甲")   # AC+8
    c.equip_item("铁盾")       # AC+2
    assert c.armor_bonus == 10


def test_trpg_armor_max_dex():
    rich = Character(500)
    rich.set_attribute("敏捷", 16)
    rich.purchase_skill("近战攻击", 11)
    rich.equip_item("全身板甲")   # max_dex 0
    assert rich.ac == 18


def test_trpg_strictest_max_dex_wins():
    rich = Character(500)
    rich.set_attribute("敏捷", 16)
    rich.purchase_skill("近战攻击", 11)
    rich.purchase_skill("闪避防御", 11)
    rich.equip_item("锁子衫")
    rich.equip_item("铁盾")
    assert rich.ac == 22


def test_trpg_finesse_detection():
    c = _char()
    assert not c.has_finesse_weapon()
    c.equip_item("刺剑")
    assert c.has_finesse_weapon()


# ---------------------------------------------------------------------------
#  优缺点 / 天赋
# ---------------------------------------------------------------------------
def test_trpg_advantage():
    c = _char()
    assert c.add_advantage("战斗反射", 15)[0]
    assert "战斗反射" in c.advantages and c.cp == 135
    assert c.add_advantage_by_name("双手灵巧")[0]
    assert c.cp == 130   # 库内价 5
    assert not c.add_advantage_by_name("不存在的优点")[0]


def test_trpg_disadvantage():
    c = _char()
    assert c.add_disadvantage("荣誉准则", 10)[0]
    assert c.cp == 160
    assert c.add_disadvantage_by_name("过度自信")[0]
    assert c.cp == 165


def test_trpg_disadvantage_cap():
    c = _char()
    for name, cp in [("守密", 10), ("责任感", 10), ("贪婪", 15), ("正义感", 10),
                     ("丑陋", 10), ("文盲", 5), ("嗜酒", 5)]:
        assert c.add_disadvantage(name, cp)[0]
    ok, msg = c.add_disadvantage("坏视力", 25)
    assert not ok and "不能超过" in msg


def test_trpg_talent():
    c = _char()
    assert c.add_talent("暗杀者", 2)[0]
    assert ("暗杀者", 2) in c.talents and c.cp == 140
    assert not c.add_talent("不存在的天赋", 1)[0]
    assert not c.add_talent("暗杀者", 0)[0]
    assert not c.add_talent("暗杀者", 4)[0]


def test_trpg_talent_bonus_stack():
    c = _char()
    c.add_talent("暗杀者", 1)
    c.add_talent("机敏斥候", 2)
    assert c.get_talent_bonus("潜行") == 3
    assert c.get_talent_bonus("近战攻击") == 0


# ---------------------------------------------------------------------------
#  技术
# ---------------------------------------------------------------------------
def test_trpg_technique_prereq():
    c = _char()
    ok, msg = c.purchase_technique("偷袭要害打击")
    assert not ok and "近战攻击" in msg and "5" in msg
    c.purchase_skill("近战攻击", 12)
    assert c.purchase_technique("偷袭要害打击")[0]
    assert "偷袭要害打击" in c.techniques


def test_trpg_technique_attr_prereq():
    c = _char()
    c.purchase_skill("近战攻击", 11)
    ok, msg = c.purchase_technique("猛力攻击")
    assert not ok and "力量" in msg and "13" in msg
    c.set_attribute("力量", 13)
    assert c.purchase_technique("猛力攻击")[0]


def test_trpg_technique_spell_prereq():
    c = _char()
    ok, msg = c.purchase_technique("火球术")
    assert not ok and "奥术施法" in msg
    c.purchase_skill("奥术施法", 11)
    assert c.purchase_technique("火球术")[0]
    assert c.has_technique("火球术")


# ---------------------------------------------------------------------------
#  衍生数值
# ---------------------------------------------------------------------------
def test_trpg_hp_zero_without_vitality():
    assert _char().hp() == 0


def test_trpg_hp_with_vitality():
    c = _char()
    c.set_attribute("体质", 14)
    c.purchase_skill("活力", 5)
    assert c.hp() == 30


def test_trpg_ac_calc():
    c = _char()
    assert c.ac == 10
    c.set_attribute("敏捷", 16)
    c.purchase_skill("闪避防御", 11)
    c.equip_item("皮甲")
    assert c.ac == 19


def test_trpg_attack_and_save_bonus():
    c = _char()
    c.purchase_skill("近战攻击", 12)
    assert c.attack_bonus(True) == 12
    c.purchase_skill("远程攻击", 10)
    assert c.attack_bonus(False) == 10
    c.set_attribute("体质", 14)
    c.purchase_skill("强韧豁免", 10)
    assert c.save_bonus("fort") == 12
    try:
        c.save_bonus("luck")
        raise AssertionError("未知豁免类型应抛 ValueError")
    except ValueError:
        pass


# ---------------------------------------------------------------------------
#  战斗宏
# ---------------------------------------------------------------------------
def test_trpg_combat_unknown_macro():
    assert "未知战斗宏" in _seeded_char().combat_macro("not_a_macro")


def test_trpg_combat_melee_hit_miss():
    assert "近战攻击" in _seeded_char().combat_macro("melee_attack", target_ac=5)
    assert "未命中" in _seeded_char().combat_macro("melee_attack", target_ac=50)


def test_trpg_combat_sneak_attack():
    f = _fighter()
    f.purchase_technique("偷袭要害打击")
    assert f._sneak_attack_dice() == 5   # (12-4)//2+1
    random.seed(1)
    result = f.combat_macro("sneak_attack", target_ac=2, flat_footed=True)
    assert "精准伤害" in result or "未命中" in result
    # 无灵巧武器无精准伤害
    c = Character(500)
    c.set_attribute("力量", 16)
    c.purchase_skill("近战攻击", 12)
    c.purchase_technique("偷袭要害打击")
    c.equip_item("长剑")
    random.seed(1)
    assert "精准伤害" not in c.combat_macro("sneak_attack", target_ac=2, flat_footed=True)


def test_trpg_combat_sneak_dice_capped():
    god = Character(5000)
    god.set_attribute("力量", 20)
    god.purchase_skill("近战攻击", 30)
    god.equip_item("匕首")
    assert god._sneak_attack_dice() == 10


def test_trpg_combat_power_attack():
    f = _fighter()
    f.set_attribute("力量", 13)
    f.purchase_technique("猛力攻击")
    random.seed(1)
    assert "猛力攻击" in f.combat_macro("power_attack", target_ac=5)
    assert "未学会" in _seeded_char().combat_macro("power_attack", target_ac=10)


def test_trpg_combat_whirlwind():
    f = _fighter()
    f.set_attribute("力量", 15)
    f.purchase_skill("近战攻击", 10)
    f.purchase_technique("旋风切割")
    random.seed(1)
    result = f.combat_macro("whirlwind", num_targets=3, target_ac=30)
    assert "目标1" in result and "目标3" in result


def test_trpg_combat_fireball():
    mage = Character(500)
    mage.set_attribute("智力", 18)
    mage.purchase_skill("奥术施法", 15)
    assert mage.purchase_technique("火球术")[0]
    assert mage.buy_slot(3)[0]
    random.seed(1)
    result = mage.combat_macro("fireball", dc=1, num_targets=1)
    assert "8d6" in result and "火焰" in result
    assert "未学会" in _char().combat_macro("fireball")


def test_trpg_combat_magic_missile():
    c = _char()
    c.set_attribute("智力", 14)
    c.purchase_skill("奥术施法", 10)
    c.purchase_technique("魔法飞弹")
    c.buy_slot(1)
    random.seed(1)
    result = c.combat_macro("magic_missile", num_targets=1)
    assert "自动命中" in result and "力场伤害" in result


def test_trpg_combat_healing_word():
    c = _char()
    c.set_attribute("智力", 14)
    c.purchase_skill("奥术施法", 10)
    c.purchase_technique("治疗言灵")
    c.buy_slot(1)
    result = c.combat_macro("healing_word")
    assert "治疗言灵" in result and "生命恢复" in result


def test_trpg_combat_gurps_techniques():
    f = _fighter()
    f.purchase_technique("欺诈攻击")
    random.seed(1)
    assert "欺诈攻击" in f.combat_macro("deceptive_attack", target_ac=8)
    f.purchase_technique("连环打击")
    random.seed(1)
    result = f.combat_macro("rapid_strike", target_ac=20)
    assert "第1击" in result and "第2击" in result
    f.purchase_technique("全力强击")
    random.seed(1)
    result = f.combat_macro("allout_strong", target_ac=2)
    assert "全力强击" in result and "无法防御" in result
    f.purchase_technique("精准突击")
    random.seed(1)
    result = f.combat_macro("allout_determined", target_ac=2)
    assert "精准突击" in result and "+4" in result


# ---------------------------------------------------------------------------
#  扩充子系统：法术位 / 专长 / 种族 / 背景 / 休整
# ---------------------------------------------------------------------------
def test_trpg_slots_buy_spend_cap():
    c = _char()
    ok, msg = c.buy_slot(1)
    assert not ok and "奥术施法" in msg
    c.purchase_skill("奥术施法", 1)
    for _ in range(4):
        assert c.buy_slot(1)[0]
    ok, msg = c.buy_slot(1)
    assert not ok and "上限" in msg
    assert c.cp == 150 - 1 - 4
    assert c.ctx.slots.spend_slot(1)[0]
    assert c.ctx.slots.available(1) == 3


def test_trpg_slots_high_ring_prereq():
    c = _char()
    c.purchase_skill("奥术施法", 5)
    assert c.buy_slot(3)[0]
    assert c.cp == 150 - 5 - 3
    ok, msg = c.buy_slot(9)
    assert not ok and "17" in msg
    assert c.ctx.slots.spend_slot(0)[0]   # 戏法无需位


def test_trpg_slots_long_rest_recovers():
    c = _char()
    c.purchase_skill("奥术施法", 1)
    c.buy_slot(1)
    c.ctx.slots.spend_slot(1)
    assert c.ctx.slots.available(1) == 0
    c.long_rest()
    assert c.ctx.slots.available(1) == 1


def test_trpg_feat_alert():
    c = _char()
    assert c.add_feat("警觉")[0]
    assert c.cp == 138   # 12 CP
    assert c.ctx.rest.initiative_bonus() == 5


def test_trpg_feat_tough_hp_hook():
    c = _char()
    c.purchase_skill("活力", 2)
    hp_before = c.hp()
    assert c.add_feat("强壮")[0]
    assert c.hp() == hp_before + 4


def test_trpg_feat_athlete_choice():
    c = _char()
    assert c.add_feat("运动员", "力量")[0]
    assert c.attributes["力量"] == 11
    assert c.has_feat("运动员")


def test_trpg_feat_prereqs():
    c = _char()
    ok, msg = c.add_feat("防御决斗者")   # 需敏捷 13
    assert not ok and "敏捷" in msg
    ok, _ = c.add_feat("元素亲和", "火")   # 需会施法
    assert not ok
    c.purchase_skill("奥术施法", 1)
    assert c.add_feat("元素亲和", "火")[0]


def test_trpg_feat_observant():
    c = _char()
    c.purchase_skill("侦察", 4)
    c.add_feat("观察力")
    assert c.effective_skill_rank("侦察") == 6


def test_trpg_feat_no_duplicate():
    c = _char()
    assert c.add_feat("警觉")[0]
    ok, msg = c.add_feat("警觉")
    assert not ok and "已拥有" in msg


def test_trpg_race_human():
    c = _char()
    assert c.set_race("人类")[0]
    assert c.cp == 90   # 60 CP
    assert all(v == 11 for v in c.attributes.values())


def test_trpg_race_elf():
    c = _char()
    assert c.set_race("精灵")[0]
    assert c.cp == 150 - 28
    assert c.attributes["敏捷"] == 12
    assert "黑暗视觉" in c.advantages
    assert "侦察" in c.proficiencies


def test_trpg_race_tiefling_fire_resist():
    c = _char()
    c.set_race("提夫林")
    c.purchase_skill("活力", 2)
    assert "5 点" in c.take_damage(10, "火")


def test_trpg_race_half_orc_relentless():
    c = _char()
    c.set_race("半兽人")
    c.purchase_skill("活力", 2)
    c.take_damage(999)
    assert c.ctx.rest.current_hp() == 1


def test_trpg_race_dragonborn_breath():
    c = _char()
    c.set_race("龙裔", {"元素": "电"})
    assert "电" in c.combat_macro("dragon_breath")
    assert "充能" in c.combat_macro("dragon_breath")


def test_trpg_race_creation_only():
    c = _char()
    c.purchase_skill("活力", 1)
    ok, msg = c.set_race("人类")
    assert not ok and "创建期" in msg


def test_trpg_race_half_elf_choose():
    c = _char()
    assert c.set_race("半精灵", {"任选+1": ["智力", "感知"]})[0]
    assert c.attributes["智力"] == 11 and c.attributes["感知"] == 11
    assert c.cp == 150 - 48


def test_trpg_background_soldier():
    c = _char()
    assert c.set_background("士兵")[0]
    c.purchase_skill("运动", 4)
    assert c.effective_skill_rank("运动") == 6   # 4 + 熟练+2
    assert c.effective_skill_rank("恐吓") == 2   # 默认 0 + 熟练+2


def test_trpg_background_feature():
    c = _char()
    c.set_background("学者")
    assert c.background_feature() == "研究者"


def test_trpg_background_creation_only():
    c = _char()
    c.purchase_skill("活力", 1)
    ok, msg = c.set_background("士兵")
    assert not ok and "创建期" in msg


def test_trpg_rest_current_hp():
    c = _char()
    c.purchase_skill("活力", 2)
    assert c.ctx.rest.current_hp() == c.hp()
    c.take_damage(3)
    assert c.ctx.rest.current_hp() == c.hp() - 3
    c.heal(1)
    assert c.ctx.rest.current_hp() == c.hp() - 2


def test_trpg_rest_short_rest_hit_dice():
    c = _char()
    c.purchase_skill("活力", 3)
    c.take_damage(999)
    out = c.short_rest()
    assert "短休" in out
    assert c.ctx.state.hit_dice_used == 1
    assert c.ctx.rest.current_hp() > 0
    assert "无可用生命骰" in _char().short_rest()


def test_trpg_rest_long_rest_full():
    c = _char()
    c.purchase_skill("活力", 2)
    c.purchase_skill("奥术施法", 1)
    c.buy_slot(1)
    c.ctx.slots.spend_slot(1)
    c.take_damage(5)
    c.ctx.state.lucky_used = 2
    out = c.long_rest()
    assert "长休" in out
    assert c.ctx.rest.current_hp() == c.hp()
    assert c.ctx.slots.available(1) == 1
    assert c.ctx.state.lucky_used == 0


def test_trpg_rest_combat_reflexes():
    c = _char()
    assert c.ctx.rest.initiative_bonus() == 0
    c.add_advantage("战斗反射", 15)
    assert c.ctx.rest.initiative_bonus() == 1


def test_trpg_lucky_feat_cap():
    c = _char()
    c.add_feat("幸运")
    c.purchase_skill("活力", 1)
    c.d20_check("活力", 30)
    assert c.ctx.state.lucky_used == 1
    for _ in range(3):
        c.d20_check("活力", 30)
    assert c.ctx.state.lucky_used == 3


def test_trpg_spell_macro_consumes_slot():
    c = _char()
    c.purchase_skill("奥术施法", 5)
    c.purchase_technique("火球术")
    c.buy_slot(3)
    out = c.combat_macro("fireball")
    assert "火球术(3环)" in out
    assert c.ctx.slots.available(3) == 0
    assert "施法失败" in c.combat_macro("fireball")


def test_trpg_upcast_fireball():
    c = _char()
    c.purchase_skill("奥术施法", 7)
    c.purchase_technique("火球术")
    c.buy_slot(4)
    out = c.combat_macro("fireball", upcast=4, dc=1)
    assert "火球术(4环)" in out and "9d6" in out


# ---------------------------------------------------------------------------
#  角色卡
# ---------------------------------------------------------------------------
def test_trpg_sheet_empty():
    sheet = _char().show_sheet()
    assert "角色卡" in sheet
    assert "剩余 CP: 150" in sheet
    assert "优点: 无" in sheet
    assert "装备: 无" in sheet


def test_trpg_sheet_with_content():
    f = _fighter()
    sheet = f.show_sheet()
    assert "力量:16" in sheet
    assert "匕首" in sheet
    assert f"HP: {f.hp()}" in sheet
    assert f"AC: {f.ac}" in sheet


def test_trpg_sheet_talent_line():
    c = _char()
    c.purchase_skill("潜行", 10)
    c.add_talent("暗杀者", 2)
    assert "潜行: 10(+2) = 12" in c.show_sheet()


def test_trpg_sheet_defaults_and_saves():
    c = _char()
    c.purchase_skill("近战攻击", 14)
    sheet = c.show_sheet()
    assert "未学技能" in sheet and "推算" in sheet
    assert all(s in sheet for s in ("强韧", "反射", "意志"))


def test_trpg_sheet_new_sections():
    c = _char()
    c.set_race("精灵")
    c.set_background("学者")
    c.add_feat("警觉")
    c.purchase_skill("奥术施法", 3)
    c.buy_slot(1)
    sheet = c.show_sheet()
    assert "种族: 精灵" in sheet
    assert "背景: 学者（研究者）" in sheet
    assert "专长: 警觉" in sheet
    assert "熟练(+2): 侦察, 奥术知识, 历史" in sheet
    assert "1环 0/1" in sheet
    assert "先攻:" in sheet


# ---------------------------------------------------------------------------
#  端到端：盗贼构建（复现 D20 盗贼.txt，仅公共 API）
# ---------------------------------------------------------------------------
def test_trpg_thief_sheet_key_fields():
    thief = _thief()
    sheet = thief.show_sheet()
    for field in THIEF_FIELDS:
        assert field in sheet, f"角色卡缺少字段: {field}"


def test_trpg_thief_to_dict():
    d = _thief().to_dict()
    assert d["attributes"]["力量"] == 11
    assert d["attributes"]["体质"] == 13
    assert "偷袭要害打击" in d["techniques"]
    for item in ("匕首", "全身板甲", "铁盾"):
        assert item in d["equipment"]
    assert d["advantages"] == ["昏暗视觉"]
    assert ("轻巧战法", 1) in d["talents"]
    assert d["disadvantages"] == [("荣誉准则", 10)]


# ---------------------------------------------------------------------------
#  内核契约（alloy 侧新增）：装配 / 总线 / fork / 回收
# ---------------------------------------------------------------------------
def test_trpg_services_mounted():
    c = _char()
    assert sorted(c.ctx.keys()) == sorted(FOURTEEN_SERVICES)


def test_trpg_state_shared_with_ctx():
    c = _char()
    assert c.state is c.ctx.state
    assert c.cp is c.ctx.state.cp
    ok, _ = c.set_attribute("魅力", 12)   # 20 CP
    assert ok
    assert c.ctx.state.attributes["魅力"] == 12
    assert c.ctx.state.cp == 130


def test_trpg_not_mixin_inheritance():
    assert Character.__bases__ == (object,)
    names = {b.__name__ for b in Character.__mro__}
    assert not any(n.endswith("Mixin") or n.endswith("Service") for n in names)


def test_trpg_preset_idempotent():
    ctx = Context()
    preset_trpg(ctx)
    adapter = ctx.get("trpg")
    preset_trpg(ctx)
    assert ctx.get("trpg") is adapter
    assert ctx.get("trpg").live


def test_trpg_preset_shares_bus():
    ctx = Context()
    bus = EventBus()
    ctx.provide("bus", bus)
    preset_trpg(ctx)
    assert ctx.get("trpg")._bus is bus


def test_trpg_preset_auto_bus():
    ctx = Context()
    preset_trpg(ctx)
    assert ctx.has("bus")


def test_trpg_character_reuses_preset():
    ctx = Context()
    preset_trpg(ctx)
    c1 = Character(ctx=ctx)
    c2 = Character(ctx=ctx)
    # 同一宿主共享一个 trpg 内核适配器；state 是每角色独立的，
    # 适配器 ctx.state 指向最近创建的角色（与 D20 单状态语义一致）。
    assert c1.ctx is c2.ctx is ctx.get("trpg")
    assert c1.state is not c2.state
    assert c2.state is c1.ctx.state


def test_trpg_fork_per_character():
    root = Context()
    root.provide("bus", EventBus())
    f1 = root.fork("char1")
    preset_trpg(f1)
    a = Character(ctx=f1)
    f2 = root.fork("char2")
    preset_trpg(f2)
    b = Character(ctx=f2)
    a.set_attribute("力量", 14)
    assert b.attributes["力量"] == 10          # 作用域隔离
    assert a.ctx is not b.ctx
    f1.dispose()
    assert not a.ctx.live
    assert b.ctx.live                          # 兄弟作用域不受影响
    assert root.get("bus").total_listeners() == 5   # 只剩 f2 的钩子


def test_trpg_dispose_unsubscribes():
    ctx = Context()
    ctx.provide("bus", EventBus())
    c = Character(ctx=ctx)
    assert ctx.get("bus").total_listeners() == 5
    c.dispose()
    assert ctx.get("bus").total_listeners() == 0
    assert not c.ctx.live
    # 复用：预设检测到已销毁适配器后重建
    c2 = Character(ctx=ctx)
    assert c2.ctx is not c.ctx and c2.ctx.live


def test_trpg_waterfall_hook():
    c = _char()
    c.purchase_skill("活力", 2)
    hp_before = c.hp()
    c.ctx.on("derived/max_hp", lambda value, nxt: nxt(value + 10))
    assert c.hp() == hp_before + 10


def test_trpg_waterfall_short_circuit():
    c = _char()
    c.purchase_skill("活力", 2)
    c.ctx.on("derived/max_hp", lambda value, nxt: 1)   # 短路，不调用 next
    assert c.hp() == 1


def test_trpg_effect_d20_semantics():
    c = _char()
    calls = []
    disp = c.ctx.effect(lambda: c.ctx.on("trpg/test", lambda *a: calls.append(1)))
    c.ctx.emit("trpg/test", 1)
    assert len(calls) == 1
    disp()
    c.ctx.emit("trpg/test", 1)
    assert len(calls) == 1


def test_trpg_serial_order():
    c = _char()
    order = []
    c.ctx.on("trpg/seq", lambda *a: order.append("a"))
    c.ctx.on("trpg/seq", lambda *a: order.append("b"))
    c.ctx.serial("trpg/seq")
    assert order == ["a", "b"]


def test_trpg_duplicate_service_fails_loud():
    from alloy.trpg.attributes import AttributesService

    c = _char()
    try:
        c.ctx.mount(AttributesService, {}, name="attributes")
        raise AssertionError("重复挂载应抛 DuplicateServiceError")
    except DuplicateServiceError:
        pass


def test_trpg_mount_missing_inject_fails():
    class Broken(Service):
        inject = ["nope"]

        def __init__(self, ctx, config=None):
            super().__init__(ctx, config)

    try:
        _char().ctx.mount(Broken)
        raise AssertionError("缺失依赖应抛 CordisError")
    except CordisError:
        pass


def test_trpg_context_repr():
    r = repr(_char().ctx)
    assert "TrpgContext" in r and "attributes" in r
