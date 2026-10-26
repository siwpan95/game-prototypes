"""table-hanging-machine 无头自检 —— 不启动 tkinter 托盘/窗口。

只 import 纯逻辑模块 game_engine（以及它依赖的 data 包），
不 import main.pyw（会创建 pystray 托盘图标 + Tk 界面），
也不 import excel_writer / config_loader（需要 openpyxl 且属于工具栏）。

验证点：
1. 角色创建：roll_stats 的 3d6 值域与 seed 可复现性，auto_create 的 HP/MP 与初始装备；
2. 衍生属性公式：xp_to_next / 负重量 / 闪避 / 法术防御 / 装备与背包汇总；
3. 存档往返：to_save_dict -> JSON -> from_save_dict 字段一致；
4. 状态推进：gain_xp 升级（含 WIS 加成与等级上限）、combat_tick 击杀掉落经验。

运行：python selfcheck.py
"""

import json
import os
import random
import sys
import traceback

ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from game_engine import (
    EquipmentItem, Item, Monster, Player, Spell, roll_stats,
)

SEED = 20261026


def check_character_creation():
    """功能点 1：属性 Roll 与自动建角的确定性、HP/MP、初始装备。"""
    random.seed(SEED)
    stats_a = roll_stats()
    random.seed(SEED)
    stats_b = roll_stats()
    if stats_a != stats_b:
        return "同一随机种子下 roll_stats 结果不可复现"
    if set(stats_a) != {"strength", "constitution", "dexterity",
                        "intelligence", "wisdom", "charisma"}:
        return "roll_stats 返回的属性字段不符：%r" % (sorted(stats_a),)

    seen = set()
    for _ in range(200):
        stats = roll_stats()
        for name, value in stats.items():
            if not (3 <= value <= 18):
                return "%s 属性 %r 越出 3d6 上限 [3, 18]" % (name, value)
            seen.add(value)
    if len(seen) < 5:
        return "200 次 roll 只出现 %d 种点数，随机性可疑" % len(seen)

    p1 = Player.auto_create(seed=4242)
    p2 = Player.auto_create(seed=4242)
    if (p1.name, p1.race, p1.klass, p1.strength, p1.constitution,
            sorted(p1.equipment)) != (p2.name, p2.race, p2.klass,
                                      p2.strength, p2.constitution,
                                      sorted(p2.equipment)):
        return "同一 seed 的 auto_create 结果不可复现"

    if p1.level != 1 or p1.xp != 0:
        return "新角色等级/经验应为 1/0，实际 %r/%r" % (p1.level, p1.xp)
    if p1.max_hp != int(p1.constitution * 4.5 + 10 + 50):
        return "初始 max_hp=%d 与体质公式不符" % p1.max_hp
    if p1.max_mp != int(p1.intelligence * 4 + 10 + 30):
        return "初始 max_mp=%d 与智力公式不符" % p1.max_mp
    if p1.hp != p1.max_hp or p1.mp != p1.max_mp:
        return "新角色 HP/MP 未充满"
    if "武器" not in p1.equipment:
        return "auto_create 未给出初始武器，装备槽：%r" % (sorted(p1.equipment),)
    weapon = p1.equipment["武器"]
    if not weapon.name or weapon.atk < 0:
        return "初始武器数据异常：%r" % (weapon,)
    if not p1.combat_log:
        return "auto_create 未写入诞生日志"
    return ""


def check_derived_properties():
    """功能点 2：衍生属性与汇总公式。"""
    p = Player(
        name="测试者", level=7, xp=100,
        strength=12, constitution=14, dexterity=20, intelligence=9,
        wisdom=10, charisma=11,
        equipment={
            "武器": EquipmentItem("测试剑", atk=11, def_=0),
            "护甲": EquipmentItem("测试甲", atk=0, def_=6),
        },
        inventory={"药水": Item("药水", 3), "面包": Item("面包", 2)},
    )

    if p.xp_to_next != max(10, int(1000 * (1.15 ** p.level))):
        return "xp_to_next 与 PQ 公式不符：%r" % (p.xp_to_next,)
    if Player(level=1).xp_to_next >= Player(level=2).xp_to_next:
        return "xp_to_next 未随等级递增"
    if p.equip_atk != 11 or p.equip_def != 6:
        return "装备汇总错误：atk=%r def=%r" % (p.equip_atk, p.equip_def)
    if p.inv_count != 5:
        return "背包数量汇总错误：%r" % (p.inv_count,)
    if p.max_encumbrance != p.strength * 2 + 5:
        return "负重量公式错误：%r" % (p.max_encumbrance,)
    if abs(p.dodge_chance - min(0.30, p.dexterity * 0.01)) > 1e-12:
        return "闪避率公式错误：%r" % (p.dodge_chance,)
    if Player(dexterity=100).dodge_chance != 0.30:
        return "闪避率上限 30%% 未生效"
    if p.spell_defense != p.wisdom // 3:
        return "法术防御公式错误：%r" % (p.spell_defense,)

    p.learn_spell(Spell("火球术", "伤害", 20, 10))
    if len(p.spells) != 1:
        return "learn_spell 未加入新法术"
    p.learn_spell(Spell("火球术", "伤害", 20, 10))
    if len(p.spells) != 1 or p.spells[0].power <= 20:
        return "重复学习同一法术应当强化而非重复添加"

    monster = Monster.spawn(7)
    if monster.hp != monster.max_hp or monster.max_hp <= 0:
        return "Monster.spawn 生成的怪物 HP 异常：%r/%r" % (
            monster.hp, monster.max_hp)
    if not monster.name or monster.level < 1:
        return "Monster.spawn 生成的怪物数据异常：%r" % (monster,)
    return ""


def check_save_roundtrip():
    """功能点 3：存档字典 -> JSON -> 对象 的往返。"""
    p = Player.auto_create(seed=99)
    p.gold = 1234
    p.chapter = "第三章 — 试炼"
    p.current_act = "第一幕"
    p.add_item("铁矿石", 4)
    p.learn_spell(Spell("冰锥", "伤害", 30, 12, "造成冰霜伤害"))
    p.quests = []

    saved = p.to_save_dict()
    raw = json.dumps(saved, ensure_ascii=False)   # 存档必须可 JSON 序列化
    restored = Player.from_save_dict(json.loads(raw))

    scalar_fields = (
        "name", "race", "klass", "title", "level", "xp",
        "strength", "constitution", "dexterity", "intelligence", "wisdom",
        "charisma", "hp", "max_hp", "mp", "max_mp",
        "chapter", "gold", "current_act",
    )
    for field in scalar_fields:
        if getattr(restored, field) != getattr(p, field):
            return "存档往返字段 %s 不一致：%r != %r" % (
                field, getattr(restored, field), getattr(p, field))

    if {k: (v.name, v.atk, v.def_) for k, v in restored.equipment.items()} != \
            {k: (v.name, v.atk, v.def_) for k, v in p.equipment.items()}:
        return "存档往返装备不一致"
    if restored.inventory != p.inventory:
        return "存档往返背包不一致"
    if [(s.name, s.power, s.mp_cost) for s in restored.spells] != \
            [(s.name, s.power, s.mp_cost) for s in p.spells]:
        return "存档往返法术不一致"
    if restored.combat_log != p.combat_log[-50:]:
        return "存档往返战斗日志不一致"
    if saved.get("version") != 3:
        return "存档未写入 version=3"

    # 旧存档兼容：job 代替 klass，无 wisdom / mp
    legacy = json.loads(raw)
    legacy["job"] = legacy.pop("klass")
    legacy.pop("wisdom")
    legacy.pop("mp")
    legacy.pop("max_mp")
    legacy["version"] = 1
    old = Player.from_save_dict(legacy)
    if old.klass != p.klass:
        return "旧存档 job->klass 兼容失败：%r" % (old.klass,)
    if old.wisdom != 10 or old.mp != 50:
        return "旧存档缺省字段兼容失败：wisdom=%r mp=%r" % (old.wisdom, old.mp)
    return ""


def check_progression_and_combat():
    """功能点 4：经验推进（升级）与战斗回合击杀。"""
    p = Player.auto_create(seed=2026)
    p.level, p.xp = 1, 0
    threshold = p.xp_to_next

    small = max(1, threshold // 10)
    expect = int(small * (1.0 + p.wisdom * 0.02))
    p.gain_xp(small)
    if p.level != 1:
        return "少量经验不应升级（level=%r）" % (p.level,)
    if p.xp != expect:
        return "WIS 经验加成不符：xp=%r，期望 %r" % (p.xp, expect)

    p.gain_xp(threshold)
    if p.level != 2:
        return "经验超过阈值后等级为 %r，期望 2" % (p.level,)
    if not (p.xp < p.xp_to_next):
        return "升级后 xp=%r 未低于新阈值 %r" % (p.xp, p.xp_to_next)
    if p.hp != p.max_hp or p.mp != p.max_mp:
        return "升级后 HP/MP 未按新上限重置"
    if not any("升至" in line for line in p.combat_log):
        return "升级未写入战斗日志"

    # 头衔：20 级触发
    q = Player.auto_create(seed=7)
    q.level, q.xp = 19, 0
    q.gain_xp(q.xp_to_next)
    if q.level != 20 or not q.title:
        return "20 级未获得头衔：level=%r title=%r" % (q.level, q.title)

    # 战斗：高属性角色砍木桩，验证回合推进与经验结算
    fighter = Player.auto_create(seed=11)
    fighter.strength = 60
    fighter.xp = 0
    dummy = Monster(name="训练木桩", level=1, max_hp=12, hp=12,
                    attack=1, defense=1, xp=50, loot_table=[])
    xp_before = fighter.xp
    killed = False
    for _ in range(100):
        if fighter.combat_tick(dummy):
            killed = True
            break
    if not killed:
        return "战斗 100 回合仍未击杀木桩（hp=%r）" % (dummy.hp,)
    if dummy.hp > 0:
        return "击杀后木桩 hp=%r 仍为正" % (dummy.hp,)
    if fighter.xp <= xp_before:
        return "击杀怪物后经验未增加：%r -> %r" % (xp_before, fighter.xp)
    if not any("击败" in line for line in fighter.combat_log):
        return "战斗日志未记录击杀"
    if fighter.hp <= 0 or fighter.hp > fighter.max_hp:
        return "战斗后 HP 异常：%r/%r" % (fighter.hp, fighter.max_hp)
    return ""


def main():
    checks = [
        ("roll_stats + auto_create character", check_character_creation),
        ("derived stat formulas + Monster.spawn", check_derived_properties),
        ("save dict round-trip (incl. legacy save)", check_save_roundtrip),
        ("xp progression + combat_tick kill", check_progression_and_combat),
    ]
    for label, func in checks:
        try:
            err = func()
        except Exception:
            print("FAIL: %s raised" % label)
            traceback.print_exc()
            return 1
        if err:
            print("FAIL: %s: %s" % (label, err))
            return 1

    print("selfcheck ok: validated %d things -- %s" % (
        len(checks), "; ".join(label for label, _ in checks)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
