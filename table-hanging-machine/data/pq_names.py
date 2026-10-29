"""
PQ 随机名字生成器：使用音节表组合生成随机名。
"""

SYLLABLES = [
    "阿", "贝", "苍", "达", "恩", "风", "格", "海", "荆", "卡",
    "岚", "芒", "凝", "破", "期", "刃", "石", "天", "微", "夕",
    "炎", "泽", "烈", "霜", "焰", "尘", "影", "光", "冥", "渊",
    "锋", "雷", "星", "痕", "寂", "空",
]

import random


def generate_name(seed=None) -> str:
    """生成一个 1-3 音节的随机名字"""
    if seed is not None:
        random.seed(seed)
    count = random.randint(1, 3)
    parts = [random.choice(SYLLABLES) for _ in range(count)]
    return "".join(parts)
