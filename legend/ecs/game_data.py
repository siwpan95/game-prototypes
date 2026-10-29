"""
游戏数据加载模块 — 从 data/game_data.xlsx 读取所有配置表
如果 Excel 不存在，自动从硬编码数据生成模板。

Sheet 结构：
  monsters  : prefix, suffix, base_hp, base_exp（旧格式，向后兼容）
  prefixes  : prefix（独立前缀池，与后缀随机组合）
  suffixes  : suffix（独立后缀池）
  affixes   : id, label, icon, weight, hp_mult, exp_mult, dodge_bonus, dr, on_attack, on_death
  equipment : id, name, desc, icon, weight, bonus_atk, bonus_crit, bonus_dodge, bonus_hp, bonus_lifesteal, bonus_exp, bonus_cd
  skills    : id, name, desc, cooldown, cost_exp_pool, effect_fn
  events    : id, name, weight, effect_fn
  tasks     : id, name, desc, target_value, reward_exp, event_type, monster_name, skill_id
"""

import os
import typing as _t

try:
    from openpyxl import load_workbook, Workbook
    _HAS_OPENPYXL = True
except Exception:
    _HAS_OPENPYXL = False

# ── 默认数据（Excel 不存在时用于生成模板） ───────────────────────

_DEFAULT_MONSTERS = [
    ("暗影", "刺客", 35, 12),
    ("亡灵", "骑士", 50, 18),
    ("火焰", "恶魔", 45, 20),
    ("冰霜", "巫师", 30, 15),
    ("剧毒", "蜘蛛", 25, 10),
    ("岩石", "巨人", 70, 25),
    ("风暴", "领主", 55, 22),
    ("幻影", "刺客", 28, 14),
    ("腐朽", "亡灵", 40, 16),
    ("熔岩", "暴君", 60, 28),
    ("暗影", "猎豹", 22, 9),
    ("亡灵", "弓箭手", 32, 13),
]

_DEFAULT_PREFIXES = [
    "暗影", "亡灵", "火焰", "冰霜", "剧毒",
    "岩石", "风暴", "幻影", "腐朽", "熔岩",
    "雷霆", "深渊", "血色", "虚空", "狂野",
]

_DEFAULT_SUFFIXES = [
    "刺客", "骑士", "恶魔", "巫师", "蜘蛛",
    "巨人", "领主", "猎豹", "弓箭手", "暴君",
    "战士", "法师", "游侠", "祭司", "狂战士",
]

_DEFAULT_AFFIXES = [
    ("elite", "精英", "⭐", 15, 2.0, 1.5, 0.0, 0, "", ""),
    ("swift", "迅捷", "💨", 10, 1.0, 1.1, 0.15, 0, "", ""),
    ("hardened", "硬化", "🛡", 12, 1.0, 1.0, 0.0, 3, "", ""),
    ("cursed", "诅咒", "💀", 8, 0.7, 2.0, 0.0, 0, "", ""),
    ("burning", "燃烧", "🔥", 10, 1.0, 1.2, 0.0, 0, "burning_on_attack", ""),
    ("phantom", "幻影", "👻", 5, 1.0, 1.3, 0.0, 0, "", ""),
]

_DEFAULT_EQUIPMENT = [
    ("iron_sword", "铁剑", "ATK+3", "⚔", 30, 3, 0, 0, 0, 0, 0, 0),
    ("spiked_club", "狼牙棒", "ATK+6, 暴击+3%", "🔨", 18, 6, 0.03, 0, 0, 0, 0, 0),
    ("mage_robe", "魔导师长袍", "闪避+5%", "👘", 15, 0, 0, 0.05, 0, 0, 0, 0),
    ("vampire_fang", "吸血鬼之牙", "攻击偷取 8% 伤害为 HP", "🦷", 10, 0, 0, 0, 0, 0.08, 0, 0),
    ("dragon_scale", "龙鳞甲", "HP上限+30", "🛡", 12, 0, 0, 0, 30, 0, 0, 0),
    ("lucky_coin", "幸运硬币", "暴击+5%, EXP获得+10%", "🪙", 8, 0, 0.05, 0, 0, 0, 0.10, 0),
    ("time_hourglass", "时空沙漏", "技能冷却-1s", "⏳", 7, 0, 0, 0, 0, 0, 0, -1),
]

_DEFAULT_SKILLS = [
    ("flame_slash", "火焰斩", "造成 1.5×ATK 火焰伤害，无视闪避", 3, 8, "skill_flame_slash"),
    ("heal", "治疗术", "恢复自身 30~50 HP", 5, 5, "skill_heal"),
    ("lightning_chain", "闪电链", "造成伤害并溅射其他存活怪物 50% 伤害", 6, 12, "skill_lightning_chain"),
    ("ice_shard", "冰锥术", "伤害 + 目标复活时间+2s", 4, 7, "skill_ice_shard"),
    ("poison_strike", "剧毒打击", "伤害 + 持续掉血 3 回合", 5, 10, "skill_poison_strike"),
    ("thunder_clap", "雷霆震击", "对全体怪物造成 30% ATK 伤害", 8, 15, "skill_thunder_clap"),
    ("shadow_step", "暗影步", "获得 100% 闪避 1 回合", 6, 6, "skill_shadow_step"),
    ("blood_rage", "血怒", "损失 20% HP，ATK+50% 3 回合", 10, 0, "skill_blood_rage"),
]

_DEFAULT_EVENTS = [
    ("merchant", "神秘商人", 20, "event_merchant"),
    ("exp_rain", "经验雨", 25, "event_exp_rain"),
    ("blessing", "祝福之光", 20, "event_blessing"),
    ("monster_riot", "怪物暴动", 15, "event_monster_riot"),
]

_DEFAULT_TASKS = [
    ("t1", "击杀任意怪物 x8", "击杀任意怪物", 8, 20, "kill", "*", ""),
    ("t2", "升到 Lv.3", "角色等级达到 3", 3, 25, "level_up", "", ""),
    ("t3", "使用火焰斩击杀 x3", "使用火焰斩击杀怪物", 3, 15, "skill_kill", "", "flame_slash"),
]


# ── 公开接口 ─────────────────────────────────────────────────

_cached_data: _t.Optional[dict] = None
_EXCEL_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "game_data.xlsx")
_EXCEL_PATH = os.path.normpath(_EXCEL_PATH)


def get_data(reload: bool = False) -> dict:
    """
    获取所有游戏数据，返回 dict：
      {
        "monsters": [("前缀","后缀",base_hp,base_exp), ...],  # 旧格式
        "prefixes": ["暗影","亡灵",...],
        "suffixes": ["刺客","骑士",...],
        "affixes":  {id: {label,icon,weight,...}},
        "equipment": {id: {name,desc,icon,weight,bonuses:{...}}},
        "skills":   {id: {name,desc,cooldown,cost,effect_fn}},
        "events":   {id: {name,weight,effect_fn}},
        "tasks":    [(id,name,desc,target_value,reward_exp,event_type,monster_name,skill_id), ...],
      }
    """
    global _cached_data
    if _cached_data is not None and not reload:
        return _cached_data

    if not _HAS_OPENPYXL:
        print("[game_data] openpyxl 未安装，使用默认数据")
        _cached_data = _default_all()
        return _cached_data

    if not os.path.exists(_EXCEL_PATH):
        print(f"[game_data] {_EXCEL_PATH} 不存在，生成模板...")
        _generate_template()

    _cached_data = _load_from_excel()
    return _cached_data


def reload_data() -> dict:
    """强制重新从 Excel 加载"""
    return get_data(reload=True)


# ── 内部：默认数据 ─────────────────────────────────────────

def _default_all() -> dict:
    monsters = _DEFAULT_MONSTERS[:]
    affixes = {}
    for (aid, label, icon, w, hpm, em, db, dr, oa, od) in _DEFAULT_AFFIXES:
        affixes[aid] = dict(id=aid, label=label, icon=icon, weight=w,
                            hp_mult=hpm, exp_mult=em,
                            dodge_bonus=db, damage_reduction=dr,
                            on_attack=oa, on_death=od)
    equipment = {}
    for (eid, name, desc, icon, w, batk, bcrit, bdodge, bhp, bls, bexp, bcd) in _DEFAULT_EQUIPMENT:
        bonuses = {}
        if batk: bonuses["atk_base"] = batk
        if bcrit: bonuses["crit_chance"] = bcrit
        if bdodge: bonuses["dodge_chance"] = bdodge
        if bhp: bonuses["max_hp"] = bhp
        if bls: bonuses["lifesteal"] = bls
        if bexp: bonuses["exp_bonus"] = bexp
        if bcd: bonuses["cd_reduction"] = bcd
        equipment[eid] = dict(id=eid, name=name, desc=desc, icon=icon,
                              weight=w, bonuses=bonuses)
    skills = {}
    for (sid, name, desc, cd, cost, efn) in _DEFAULT_SKILLS:
        skills[sid] = dict(id=sid, name=name, desc=desc,
                           cooldown=cd, cost_exp_pool=cost, effect_fn=efn)
    events = {}
    for (eid, name, w, efn) in _DEFAULT_EVENTS:
        events[eid] = dict(id=eid, name=name, weight=w, effect_fn=efn)
    tasks = list(_DEFAULT_TASKS)
    prefixes = list(_DEFAULT_PREFIXES)
    suffixes = list(_DEFAULT_SUFFIXES)
    return dict(monsters=monsters, affixes=affixes,
                equipment=equipment, skills=skills, events=events,
                tasks=tasks, prefixes=prefixes, suffixes=suffixes)


# ── 内部：生成 Excel 模板 ──────────────────────────────────

def _generate_template() -> None:
    wb = Workbook()
    wb.remove(wb.active)  # 删除默认 sheet

    # Sheet: monsters（旧格式，向后兼容）
    ws = wb.create_sheet("monsters")
    ws.append(["prefix", "suffix", "base_hp", "base_exp"])
    for (p, s, hp, exp) in _DEFAULT_MONSTERS:
        ws.append([p, s, hp, exp])

    # Sheet: prefixes（独立前缀池）
    ws = wb.create_sheet("prefixes")
    ws.append(["prefix"])
    for p in _DEFAULT_PREFIXES:
        ws.append([p])

    # Sheet: suffixes（独立后缀池）
    ws = wb.create_sheet("suffixes")
    ws.append(["suffix"])
    for s in _DEFAULT_SUFFIXES:
        ws.append([s])

    # Sheet: affixes
    ws = wb.create_sheet("affixes")
    ws.append(["id", "label", "icon", "weight", "hp_mult", "exp_mult",
               "dodge_bonus", "damage_reduction", "on_attack", "on_death"])
    for row in _DEFAULT_AFFIXES:
        ws.append(list(row))

    # Sheet: equipment
    ws = wb.create_sheet("equipment")
    ws.append(["id", "name", "desc", "icon", "weight",
               "bonus_atk_base", "bonus_crit_chance", "bonus_dodge_chance",
               "bonus_max_hp", "bonus_lifesteal", "bonus_exp_bonus", "bonus_cd_reduction"])
    for row in _DEFAULT_EQUIPMENT:
        ws.append(list(row))

    # Sheet: skills
    ws = wb.create_sheet("skills")
    ws.append(["id", "name", "desc", "cooldown", "cost_exp_pool", "effect_fn"])
    for row in _DEFAULT_SKILLS:
        ws.append(list(row))

    # Sheet: events
    ws = wb.create_sheet("events")
    ws.append(["id", "name", "weight", "effect_fn"])
    for row in _DEFAULT_EVENTS:
        ws.append(list(row))

    # Sheet: tasks
    ws = wb.create_sheet("tasks")
    ws.append(["id", "name", "desc", "target_value", "reward_exp",
               "event_type", "monster_name", "skill_id"])
    for row in _DEFAULT_TASKS:
        ws.append(list(row))

    os.makedirs(os.path.dirname(_EXCEL_PATH), exist_ok=True)
    wb.save(_EXCEL_PATH)
    print(f"[game_data] 模板已生成：{_EXCEL_PATH}")


# ── 内部：从 Excel 加载 ──────────────────────────────────

def _load_from_excel() -> dict:
    wb = load_workbook(_EXCEL_PATH, data_only=True)
    monsters = []
    if "monsters" in wb.sheetnames:
        ws = wb["monsters"]
        for row in ws.iter_rows(min_row=2, values_only=True):
            if row[0] is None:
                continue
            monsters.append((str(row[0]), str(row[1]), int(row[2] or 0), int(row[3] or 0)))

    affixes = {}
    if "affixes" in wb.sheetnames:
        ws = wb["affixes"]
        for row in ws.iter_rows(min_row=2, values_only=True):
            if row[0] is None:
                continue
            aid = str(row[0])
            affixes[aid] = dict(
                id=aid,
                label=str(row[1] or ""),
                icon=str(row[2] or ""),
                weight=int(row[3] or 0),
                hp_mult=float(row[4] or 1.0),
                exp_mult=float(row[5] or 1.0),
                dodge_bonus=float(row[6] or 0.0),
                damage_reduction=int(row[7] or 0),
                on_attack=str(row[8] or "") if row[8] else "",
                on_death=str(row[9] or "") if row[9] else "",
            )

    equipment = {}
    if "equipment" in wb.sheetnames:
        ws = wb["equipment"]
        headers = [c.value for c in next(ws.iter_rows(min_row=1, max_row=1))]
        for row in ws.iter_rows(min_row=2, values_only=True):
            if row[0] is None:
                continue
            eid = str(row[0])
            bonuses = {}
            # bonus 列索引（按 headers 位置）
            for key, idx in [("atk_base", 5), ("crit_chance", 6), ("dodge_chance", 7),
                             ("max_hp", 8), ("lifesteal", 9), ("exp_bonus", 10), ("cd_reduction", 11)]:
                val = row[idx] if idx < len(row) else None
                if val:
                    bonuses[key] = float(val)
            equipment[eid] = dict(
                id=eid,
                name=str(row[1] or ""),
                desc=str(row[2] or ""),
                icon=str(row[3] or ""),
                weight=int(row[4] or 10),
                bonuses=bonuses,
            )

    skills = {}
    if "skills" in wb.sheetnames:
        ws = wb["skills"]
        for row in ws.iter_rows(min_row=2, values_only=True):
            if row[0] is None:
                continue
            sid = str(row[0])
            skills[sid] = dict(
                id=sid,
                name=str(row[1] or ""),
                desc=str(row[2] or ""),
                cooldown=int(row[3] or 0),
                cost_exp_pool=int(row[4] or 0),
                effect_fn=str(row[5] or "") if row[5] else "",
            )

    events = {}
    if "events" in wb.sheetnames:
        ws = wb["events"]
        for row in ws.iter_rows(min_row=2, values_only=True):
            if row[0] is None:
                continue
            eid = str(row[0])
            events[eid] = dict(
                id=eid,
                name=str(row[1] or ""),
                weight=int(row[2] or 0),
                effect_fn=str(row[3] or "") if row[3] else "",
            )

    tasks = []
    if "tasks" in wb.sheetnames:
        ws = wb["tasks"]
        for row in ws.iter_rows(min_row=2, values_only=True):
            if row[0] is None:
                continue
            tasks.append((
                str(row[0]),                             # id
                str(row[1] or ""),                       # name
                str(row[2] or ""),                       # desc
                int(row[3] or 0),                        # target_value
                int(row[4] or 0),                        # reward_exp
                str(row[5] or "kill"),                   # event_type
                str(row[6] or "") if row[6] else "",     # monster_name
                str(row[7] or "") if row[7] else "",     # skill_id
            ))

    prefixes = []
    if "prefixes" in wb.sheetnames:
        ws = wb["prefixes"]
        for row in ws.iter_rows(min_row=2, values_only=True):
            if row[0] is not None and str(row[0]).strip():
                prefixes.append(str(row[0]).strip())

    suffixes = []
    if "suffixes" in wb.sheetnames:
        ws = wb["suffixes"]
        for row in ws.iter_rows(min_row=2, values_only=True):
            if row[0] is not None and str(row[0]).strip():
                suffixes.append(str(row[0]).strip())

    wb.close()
    n_combo = len(prefixes) * len(suffixes)
    print(f"[game_data] 已从 Excel 加载数据："
          f"怪物{len(monsters)}种（旧），前缀{len(prefixes)}×后缀{len(suffixes)}={n_combo}组合，"
          f"词缀{len(affixes)}种，装备{len(equipment)}种，技能{len(skills)}种，事件{len(events)}种，"
          f"任务{len(tasks)}个")
    return dict(monsters=monsters, affixes=affixes,
                equipment=equipment, skills=skills, events=events,
                tasks=tasks, prefixes=prefixes, suffixes=suffixes)
