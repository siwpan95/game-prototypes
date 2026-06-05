"""
PQ 职业数据：18 职业，每个职业 1-2 项属性获得 +2 起始加成。
"""

CLASSES: dict[str, dict[str, int]] = {
    "原初圣武士":       {"WIS": 2, "CON": 2},
    "巫毒公主":         {"INT": 2, "CHA": 2},
    "机械僧侣":         {"STR": 2},
    "木浮僧":           {"DEX": 2},
    "幻术法师":         {"INT": 2, "MP Max": 2},
    "匕首骑士":         {"DEX": 2},
    "内修石匠":         {"CON": 2},
    "战士／风琴师":     {"CHA": 2, "STR": 2},
    "猎豹盗贼":         {"DEX": 2},
    "符文博学者":       {"WIS": 2},
    "绞杀猎人":         {"DEX": 2, "INT": 2},
    "重罪犯":           {"STR": 2},
    "挠痒模仿者":       {"WIS": 2, "INT": 2},
    "慢性投毒者":       {"CON": 2},
    "疯狂私生子":       {"CON": 2},
    "低吟者":           {"WIS": 2},
    "驭鸟者":           {"WIS": 2},
    "害虫驯师":         {"INT": 2},
}

CLASS_BONUS_MAP: dict[str, str] = {
    "STR": "strength",
    "CON": "constitution",
    "DEX": "dexterity",
    "INT": "intelligence",
    "WIS": "wisdom",
    "CHA": "charisma",
    "HP Max": "constitution",
    "MP Max": "intelligence",
}

import random


def random_class():
    """返回 (职业名, {bonus_key: bonus_amount})"""
    name = random.choice(list(CLASSES.keys()))
    return name, dict(CLASSES[name])


def apply_class_bonus(stats: dict, class_name: str):
    """将职业加成应用到属性字典上"""
    import copy
    result = copy.deepcopy(stats)
    bonuses = CLASSES.get(class_name, {})
    for key, val in bonuses.items():
        field = CLASS_BONUS_MAP.get(key, key.lower())
        if field in result:
            result[field] += val
    return result
