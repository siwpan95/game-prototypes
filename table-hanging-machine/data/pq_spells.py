"""
PQ 法术数据：47 法术名 + 随机分配类型/威力/MP消耗。
"""

SPELL_NAMES = [
    "史莱姆指", "兔子拳", "急躁术", "妙招",
    "悲伤术", "晕船术", "鞋带缠绕", "疫苗接种",
    "烦人锥", "磁力球", "无形之手",
    "反胃云", "体液幽默", "幽灵瘴气",
    "机智小伙", "牙关紧闭", "历史课", "恐水症",
    "大姐大", "糊状锥", "重来一局",
    "内斯特妙计", "神圣蝙蝠棍", "良性肿瘤",
    "脑门", "召唤悍妇", "困惑术", "活化床头柜",
    "穴居人之眼", "诅咒名字", "水肿术",
    "玻璃体幽默", "罗杰的华丽幻象", "贪欲术",
    "黑色爱达荷", "星界瘴气", "幽灵牡蛎",
    "辛辣之手", "血管成形术", "格罗格诺的假日",
    "恶性肿瘤", "活化束腰衣", "熊之铠甲",
    "神圣压路机", "扁桃体切除术", "诅咒家人",
    "无尽困惑",
]

SPELL_TYPES = ["伤害", "治疗", "增益", "减益"]

SPELL_TYPE_DESCRIPTIONS = {
    "伤害": ["造成 {power} 点伤害"],
    "治疗": ["恢复 {power} 点生命"],
    "增益": ["暂时提升攻击力 {power}%"],
    "减益": ["降低敌人防御 {power}%"],
}

import random


def random_spell():
    """返回一个随机的 Spell 数据字典"""
    spell_type = random.choice(SPELL_TYPES)
    # 威力根据类型不同而变化
    if spell_type == "伤害":
        power = random.randint(15, 60)
        mp_cost = random.randint(8, 30)
    elif spell_type == "治疗":
        power = random.randint(20, 80)
        mp_cost = random.randint(10, 40)
    elif spell_type == "增益":
        power = random.randint(10, 50)
        mp_cost = random.randint(5, 25)
    else:  # 减益
        power = random.randint(5, 40)
        mp_cost = random.randint(5, 25)

    desc_template = random.choice(SPELL_TYPE_DESCRIPTIONS[spell_type])
    description = desc_template.format(power=power)

    return {
        "name": random.choice(SPELL_NAMES),
        "spell_type": spell_type,
        "power": power,
        "mp_cost": mp_cost,
        "description": description,
    }
