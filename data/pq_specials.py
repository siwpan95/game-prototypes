"""
PQ 特殊宝物数据：37 基名 + 33 形容词 + 52 后缀 = 任务奖励用。
"""

SPECIAL_BASE = [
    "王冠", "花环", "宝石", "药瓶", "头饰", "剑鞘",
    "弓箭", "透镜", "神灯", "圣歌集", "金羊毛", "桂冠", "胸针",
    "手钻", "卵石", "信天翁", "火盆", "弹链", "古书",
    "石榴石", "紫水晶", "烛台", "束腰", "宝珠", "权杖",
    "安卡符", "护身符", "法球", "旧物", "装饰品", "锦缎",
    "丝带", "珠宝", "亮片", "小玩意", "兜帽", "狐镜",
]

SPECIAL_ADJ = [
    "黄金的", "镀金的", "幽灵的", "星界的", "花饰的", "珍贵的",
    "精雕的", "二重的", "金丝的", "十字形的", "奥术的", "受福的",
    "崇敬的", "幸运的", "附魔的", "闪耀的", "宏伟的",
    "神圣的", "传说的", "神话的", "水晶的", "朴素的",
    "炫富的", "唯一的", "谚语的", "可怕的", "致命的",
    "仁慈的", "超凡的", "华丽的", "钢铁的", "镀金铜的",
    "威猛的",
]

# 复用装备模块的 ITEM_OF
from .pq_equipment import ITEM_OF, random_item_of

import random


def generate_special():
    """生成一件特殊宝物，返回 (完整名, base_name, adj, of_name, value)"""
    base = random.choice(SPECIAL_BASE)
    adj = random.choice(SPECIAL_ADJ)
    of_name = random_item_of()
    full_name = f"{adj}{base} 之 {of_name}"
    value = random.randint(50, 2000)
    return full_name, base, adj, of_name, value
