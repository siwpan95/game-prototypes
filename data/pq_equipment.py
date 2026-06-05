"""
PQ 装备数据：武器/盾牌/护甲基表 + 正负面词缀 + "之XX"后缀 + 命名生成函数。
"""

# 11 装备槽
EQUIPMENT_SLOTS = [
    "武器",      # Weapon
    "盾牌",      # Shield
    "头盔",      # Helm
    "胸甲",      # Hauberk
    "肩甲",      # Brassairts
    "臂甲",      # Vambraces
    "手套",      # Gauntlets
    "内甲",      # Gambeson
    "裤甲",      # Cuisses
    "腿甲",      # Greaves
    "足甲",      # Sollerets
]

# 槽位分类
WEAPON_SLOTS = {"武器"}
SHIELD_SLOTS = {"盾牌"}
ARMOR_SLOTS = {"头盔", "胸甲", "肩甲", "臂甲", "手套", "内甲", "裤甲", "腿甲", "足甲"}

# --- 武器基表 (name|base_atk) ---
WEAPON_BASE = [
    ("木棍", 0), ("破酒瓶", 1), ("匕首", 1), ("树枝", 1),
    ("赶牛棒", 1), ("鳗鱼矛", 2), ("猎刀", 2), ("羊角锤", 2),
    ("手锤", 2), ("柴架", 3), ("手斧", 3), ("战斧", 3),
    ("砍刀", 3), ("撬棍", 4), ("钉头锤", 4), ("战镐", 4),
    ("叶形锤", 5), ("短剑", 5), ("长铁剑", 5), ("猎剑", 5),
    ("巴塞拉短剑", 5), ("短弯刀", 6), ("火铳", 6), ("长剑", 6),
    ("曲弓弩", 6), ("弯刀", 7), ("阔剑", 7), ("克林弯刀", 7),
    ("战锤", 7), ("流星锤", 8), ("长柄镐", 8), ("短矛枪", 8),
    ("异种大剑", 9), ("臂甲锤", 9), ("火绳枪", 10), ("长矛", 10),
    ("长戟", 11), ("长柄斧", 12), ("班迪巨剑", 15),
]

# --- 盾牌基表 (name|base_def) ---
SHIELD_BASE = [
    ("阳伞", 0), ("馅饼盘", 1), ("垃圾桶盖", 2),
    ("小圆盾", 3), ("有机玻璃盾", 4), ("挡泥板", 4), ("圆盾", 5),
    ("甲壳盾", 5), ("罗马方盾", 6), ("防御盾", 6), ("鸢盾", 7),
    ("巨盾", 8), ("塔盾", 9), ("巴洛克花盾", 11),
    ("宙斯盾", 12), ("磁力场", 18),
]

# --- 护甲基表 (name|base_def) ---
ARMOR_BASE = [
    ("蕾丝", 1), ("流苏", 2), ("粗麻布", 3), ("帆布", 4),
    ("法兰绒", 5), ("麂皮", 6), ("仿皮", 7), ("皮革", 8),
    ("熊皮", 9), ("环甲", 10), ("鳞甲", 12), ("链甲", 14),
    ("板条甲", 15), ("板甲", 16), ("工程塑料", 17), ("凯夫拉", 18),
    ("钛合金", 19), ("秘银甲", 20), ("钻石甲", 25),
    ("等离子甲", 30),
]

# --- 攻击正面词缀 (name|bonus) ---
OFFENSE_POS = [
    ("抛光的", 1), ("锯齿的", 1), ("沉重的", 1), ("尖刺的", 2),
    ("钢铁的", 2), ("凶残的", 3), ("淬毒的", 4), ("刺骨的", 4),
    ("舞动的", 5), ("无形的", 6), ("斩首的", 7),
]

# --- 攻击负面词缀 ---
OFFENSE_NEG = [
    ("钝的", -2), ("褪色的", -1), ("生锈的", -3), ("软垫的", -5),
    ("弯曲的", -4), ("迷你的", -4), ("橡胶的", -6), ("削弱版", -7),
    ("失衡的", -2),
]

# --- 防御正面词缀 ---
DEFENSE_POS = [
    ("镶钉的", 1), ("加固的", 2), ("镀金的", 2), ("花饰的", 3),
    ("神圣的", 4), ("亚麻的", 1), ("精良的", 4), ("华丽的", 5),
    ("定制的", 3),
]

# --- 防御负面词缀 ---
DEFENSE_NEG = [
    ("有洞的", -1), ("打补丁的", -1), ("磨损的", -2), ("褪色的", -1),
    ("生锈的", -3), ("虫蛀的", -3), ("发霉的", -2), ("撕裂的", -3),
    ("凹陷的", -3), ("被诅咒的", -5), ("塑料的", -4), ("龟裂的", -4),
    ("变形的", -3), ("腐蚀的", -3),
]

# --- "之XX" 后缀 (52个) ---
ITEM_OF = [
    "预兆", "征兆", "紧张", "快乐",
    "麻木", "危险", "工艺", "沉默", "隐形", "急速",
    "愉悦", "实用", "伤痛", "喜悦", "暴躁", "入侵",
    "混沌", "苦难", "外向", "狂乱", "坚韧", "孤独",
    "守时", "效率", "舒适", "忍耐", "拘禁",
    "囚禁", "误解", "忠诚", "嫉妒", "尖刻",
    "忧虑", "恐惧", "敬畏", "狡诈", "淫欲", "幸运",
    "洞察", "支配", "屈服", "效忠", "饥饿",
    "绝望", "残忍", "格罗布", "迪格纳", "拉", "白骨",
    "钻石仿品", "琥珀金", "水银",
]

import random


def random_item_of() -> str:
    return random.choice(ITEM_OF)


def random_offense_attrib() -> str:
    # 正面概率 > 负面
    if random.random() < 0.75:
        return random.choice(OFFENSE_POS)[0]
    else:
        return random.choice(OFFENSE_NEG)[0]


def random_defense_attrib() -> str:
    if random.random() < 0.75:
        return random.choice(DEFENSE_POS)[0]
    else:
        return random.choice(DEFENSE_NEG)[0]


def _get_attrib_bonus(attrib: str, pos_list: list, neg_list: list) -> int:
    for name, bonus in pos_list:
        if name == attrib:
            return bonus
    for name, bonus in neg_list:
        if name == attrib:
            return bonus
    return 0


def generate_weapon(atk_base: int = None) -> tuple:
    """返回 (name, atk)"""
    base_name, base_atk = random.choice(WEAPON_BASE)
    if atk_base is not None:
        base_atk = atk_base
    attrib = random_offense_attrib()
    attrib_bonus = _get_attrib_bonus(attrib, OFFENSE_POS, OFFENSE_NEG)
    of_name = random_item_of()
    name = f"{attrib}{base_name} 之 {of_name}"
    total_atk = max(0, base_atk + attrib_bonus + random.randint(-2, 2))
    return name, total_atk


def generate_shield(def_base: int = None) -> tuple:
    """返回 (name, def_)"""
    base_name, base_def = random.choice(SHIELD_BASE)
    if def_base is not None:
        base_def = def_base
    attrib = random_defense_attrib()
    attrib_bonus = _get_attrib_bonus(attrib, DEFENSE_POS, DEFENSE_NEG)
    of_name = random_item_of()
    name = f"{attrib}{base_name} 之 {of_name}"
    total_def = max(0, base_def + attrib_bonus + random.randint(-2, 2))
    return name, total_def


def generate_armor(def_base: int = None) -> tuple:
    """返回 (name, def_)"""
    base_name, base_def = random.choice(ARMOR_BASE)
    if def_base is not None:
        base_def = def_base
    attrib = random_defense_attrib()
    attrib_bonus = _get_attrib_bonus(attrib, DEFENSE_POS, DEFENSE_NEG)
    of_name = random_item_of()
    name = f"{attrib}{base_name} 之 {of_name}"
    total_def = max(0, base_def + attrib_bonus + random.randint(-2, 2))
    return name, total_def


def generate_shop_equipment():
    """为商店生成一件随机装备作为商品"""
    import random
    slot = random.choice(EQUIPMENT_SLOTS)
    if slot in WEAPON_SLOTS:
        name, atk = generate_weapon()
        def_ = 0
    elif slot in SHIELD_SLOTS:
        name, def_ = generate_shield()
        atk = 0
    else:
        name, def_ = generate_armor()
        atk = 0

    # 价格基于属性
    total = atk + def_
    price = max(10, total * random.randint(8, 20))

    return {
        "name": name,
        "slot": slot,
        "atk": atk,
        "def": def_,
        "price": price,
    }
