"""
PQ 种族数据：21 种族，每个种族 1-2 项属性获得 +3 起始加成。
属性映射: STR/力量, CON/体质, DEX/敏捷, INT/智力, WIS/智慧, CHA/魅力, HP=HP Max, MP=MP Max
"""

RACES: dict[str, dict[str, int]] = {
    "半兽人":        {"HP Max": 3},
    "半人":          {"CHA": 3},
    "半半身人":      {"DEX": 3},
    "双重霍比特":    {"STR": 3},
    "霍布霍比特":    {"DEX": 3, "CON": 3},
    "低等精灵":      {"CON": 3},
    "粪精灵":        {"WIS": 3},
    "会说话的小马":  {"MP Max": 3, "INT": 3},
    "陀螺地精":      {"DEX": 3},
    "次等矮人":      {"CON": 3},
    "冠羽矮人":      {"CHA": 3},
    "鳗鱼人":        {"DEX": 3},
    "熊猫人":        {"CON": 3, "STR": 3},
    "跨性别狗头人":  {"WIS": 3},
    "附魔摩托车":    {"MP Max": 3},
    "鬼火精灵":      {"WIS": 3},
    "战雀":          {"DEX": 3, "INT": 3},
    "双重伍基人":    {"STR": 3},
    "斯科瑞林人":    {"WIS": 3},
    "半加拿大人":    {"CON": 3},
    "陆行鱿鱼":      {"STR": 3, "HP Max": 3},
}

# 属性名映射到 Player 属性字段
RACE_BONUS_MAP: dict[str, str] = {
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


def random_race():
    """返回 (种族名, {bonus_key: bonus_amount})"""
    name = random.choice(list(RACES.keys()))
    return name, dict(RACES[name])


def apply_race_bonus(stats: dict, race_name: str):
    """将种族加成应用到属性字典上"""
    import copy
    result = copy.deepcopy(stats)
    bonuses = RACES.get(race_name, {})
    for key, val in bonuses.items():
        field = RACE_BONUS_MAP.get(key, key.lower())
        if field in result:
            result[field] += val
    return result
