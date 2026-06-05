"""
PQ 章节数据：纯进度标记，用等级区间标记而非限制怪物/任务池。
"""

ACTS = [
    {"name": "第一章 — 序章",       "min_level": 1,  "max_level": 8},
    {"name": "第二章 — 荒野",      "min_level": 9,  "max_level": 20},
    {"name": "第三章 — 深渊",     "min_level": 21, "max_level": 35},
    {"name": "第四章 — 龙焰",      "min_level": 36, "max_level": 55},
    {"name": "第五章 — 诸神黄昏",   "min_level": 56, "max_level": 999},
]

import random


def get_current_act(level: int) -> dict:
    """根据玩家等级获取当前章节"""
    current = ACTS[0]
    for act in ACTS:
        if level >= act["min_level"]:
            current = act
    return current


def get_quest_count_for_level(level: int) -> int:
    """根据等级返回推荐任务数量"""
    if level <= 10:
        return 5
    elif level <= 30:
        return 6
    elif level <= 50:
        return 7
    else:
        return 8
