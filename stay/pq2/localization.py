"""中文本地化 — 基于 D&D 背景的英译中字典"""

from .types import EQUIPMENT_LABELS

# 角色面板
CHARACTER_UI = {
    "Name": "名称",
    "Race": "种族",
    "Class": "职业",
    "Level": "等级",
    "STR": "力量",
    "CON": "体质",
    "DEX": "敏捷",
    "INT": "智力",
    "WIS": "感知",
    "CHA": "魅力",
    "HP": "生命值",
    "MP": "魔法值",
    "HP Max": "生命值",
    "MP Max": "魔法值",
    "Gold": "金币",
    "Experience": "经验值",
    "Equipment": "装备",
    "Spells": "法术",
    "Inventory": "背包",
    "Current Action": "当前行动",
    "Plot": "剧情",
    "Quests": "任务",
    "Character": "角色信息",
}

# 主菜单
MAIN_MENU_CN = {
    "New Game": "新游戏",
    "Load Game": "读取存档",
    "Exit": "退出",
    "A Zero-Player RPG Adventure": "一款零玩家 RPG 冒险",
}

# 角色创建
CHAR_CREATE_CN = {
    "Character Creation": "角色创建",
    "Random": "随机",
    "Attributes": "属性",
    "Roll": "投骰",
    "Unroll": "撤销",
    "Auto": "自动",
    "Stop": "停止",
    "Target (optional):": "目标属性（可选）：",
    "TOTAL": "合计",
    "Total": "合计",
    "SOLD! Begin Adventure": "成交！开始冒险",
}

# 杂项
MISC_CN = {
    "DNA": "基因序列",
    "Genetic Sequence": "基因序列",
    "的基因序列:": "的基因序列：",
    "Load Error": "加载错误",
    "Failed to load save file": "加载存档失败",
    "(empty)": "（空）",
    "Save Game": "保存存档",
    "Load Save Game": "读取存档文件",
    "PQ2 Save Files": "PQ2 存档文件",
    "All Files": "所有文件",
    "Error loading save": "加载存档出错",
    "Plot Progress": "剧情进度",
    "Quest Progress": "任务进度",
}

# 装备槽位
EQUIPMENT_CN = {
    "Weapon": "武器",
    "Shield": "盾牌",
    "Helm": "头盔",
    "Hauberk": "链甲",
    "Brassairts": "肩甲",
    "Vambraces": "护腕",
    "Gauntlets": "护手",
    "Gambeson": "棉甲",
    "Cuisses": "护腿",
    "Greaves": "胫甲",
    "Sollerets": "战靴",
}

# 行动文本
ACTION_TEXT = {
    "Loading": "加载中",
    "Heading to the killing fields": "前往杀戮之地",
    "Heading to market to sell loot": "前往市场出售战利品",
    "Negotiating purchase of better equipment": "讨价还价购买更好的装备",
    "Executing": "正在对战",
    "Selling": "正在出售",
}

# 序幕/剧情
PLOT_TEXT = {
    "Prologue": "序幕",
    "Act": "章节",
    "Experiencing an enigmatic and foreboding night vision": "经历一段神秘而阴森的夜间幻象",
    "Much is revealed about that wise old bastard you'd underestimated": "关于你之前低估了的那个睿智的老家伙，很多事情都暴露出来了",
    "A shocking series of events leaves you alone and bewildered, but resolute": "一连串令人震惊的事件让你孤身一人、茫然无措，但也多了份坚定",
    "Drawing upon an unrealized reserve of determination, you set out on a long and dangerous journey": "你唤醒了心中从未察觉的决心，踏上了一段漫长而危险的旅程",
    "Exhausted, you arrive at a friendly oasis in a hostile land": "疲惫不堪的你，抵达了这片险恶土地上的一处友善绿洲",
    "You greet old friends and meet new allies": "你与老友重逢，也结识了新的盟友",
    "You are privy to a council of powerful do-gooders": "你获准参与一场由强大义士组成的会议",
    "There is much to be done. You are chosen!": "前路任务艰巨，你被选中了",
    "Your quarry is in sight, but a mighty enemy bars your path!": "目标已近在眼前，却有一名强大的敌人挡在了你的路上",
    "A desperate struggle commences with": "殊死搏斗开始了",
    "Locked in grim combat with": "陷入惨烈的缠斗",
    "seems to have the upper hand!": "似乎占据了上风",
    "You seem to gain the advantage over": "你似乎在对抗中占据了优势",
    " Victory!": "胜利了！",
    " is slain! Exhausted, you lose consciousness": "已被斩杀！你精疲力竭，失去了意识",
    "You awake in a friendly place, but the road awaits": "你在一处安全的地方醒来，但前路仍需继续",
    "Oh sweet relief! You've reached the protection of the good": "终于松了口气！你抵达了善意庇护之下",
    "There is rejoicing, and an unnerving encounter with": "众人欢庆，而你与",
    " in private": "的私下会面却令人不安",
    "You forget your": "你忘了带自己的",
    " and go back to get it": "于是回去取",
    "What''s this!? You overhear something shocking!": "这是什么情况！？你无意中听到了令人震惊的消息",
    "Could": "难道",
    " be a dirty double-dealer?": "是个背信弃义的两面派",
    "Who can possibly be trusted with this news!? ... Oh yes, of course": "这样的消息能托付给谁呢！？—— 哦对，当然是",
    "Loading": "加载中",
}

# 怪物修饰词
MONSTER_MODS_CN = {
    "dead": "死",
    "comatose": "昏迷",
    "crippled": "伤残",
    "sick": "患病",
    "undernourished": "营养不良",
    "foetal": "胚胎",
    "baby": "幼体",
    "preadolescent": "未成年",
    "teenage": "青少年",
    "underage": "未成熟",
    "greater": "高等",
    "massive": "巨型",
    "enormous": "庞大",
    "giant": "巨",
    "titanic": "泰坦",
    "veteran": "老兵",
    "cursed": "被诅咒",
    "warrior": "战士",
    "undead": "亡灵",
    "demon": "恶魔",
    "imaginary": "幻想",
    "messianic": "救世",
    "Battle-": "战斗",
    "Were-": "狼人",
}

# 法术
SPELLS_CN = {
    "Slime Finger": "黏液手指",
    "Rabbit Punch": "兔子拳",
    "Hastiness": "迅捷术",
    "Good Move": "精妙步法",
    "Gyp": "诈骗术",
    "Sadness": "悲伤术",
    "Seasick": "晕船术",
    "Shoelaces": "鞋带术",
    "Inoculate": "免疫接种",
    "Cone of Annoyance": "烦扰之锥",
    "Magnetic Orb": "磁性法球",
    "Invisible Hands": "无形之手",
    "Revolting Cloud": "令人作呕的云雾",
    "Aqueous Humor": "水样幽默",
    "Spectral Miasma": "幽灵瘴气",
    "Clever Fellow": "机灵鬼",
    "Lockjaw": "牙关紧闭术",
    "History Lesson": "历史教训",
    "Hydrophobia": "恐水症",
    "Big Sister": "大姐姐",
    "Cone of Paste": "浆糊之锥",
    "Mulligan": "重掷术",
    "Nestor's Bright Idea": "内斯特的妙计",
    "Holy Batpole": "神圣蝙蝠杆",
    "Tumor (Benign)": "肿瘤（良性）",
    "Braingate": "脑域之门",
    "Nonplus": "困惑术",
    "Animate Nightstand": "活化床头柜",
    "Eye of the Troglodyte": "穴居人之眼",
    "Curse Name": "恶咒之名",
    "Dropsy": "水肿术",
    "Vitreous Humor": "玻璃体术",
    "Roger's Grand Illusion": "罗杰的盛大幻象",
    "Covet": "觊觎术",
    "Astral Miasma": "星界瘴气",
    "Spectral Oyster": "幽灵牡蛎",
    "Acrid Hands": "辛辣之手",
    "Angioplasty": "血管成形术",
    "Grognor's Big Day Off": "格罗格诺的休息日",
    "Tumor (Malignant)": "肿瘤（恶性）",
    "Animate Tunic": "活化束腰衣",
    "Ursine Armor": "熊形铠甲",
    "Holy Roller": "神圣翻滚者",
    "Tonsillectomy": "扁桃体切除术",
    "Curse Family": "家族诅咒",
    "Infinite Confusion": "无尽混乱",
}

# 武器
WEAPONS_CN = {
    "Sharp Rock": "尖锐的石头",
    "Stick": "木棍",
    "Broken Bottle": "破瓶",
    "Shiv": "自制短刀",
    "Sprig": "细枝",
    "Oxgoad": "牛刺棒",
    "Eelspear": "捕鳗矛",
    "Bowie Knife": "鲍伊刀",
    "Claw Hammer": "羊角锤",
    "Handpeen": "手锻锤",
    "Andiron": "柴架铁",
    "Hatchet": "短柄斧",
    "Tomahawk": "战斧",
    "Hackbarm": "劈砍杆",
    "Crowbar": "撬棍",
    "Mace": "钉头锤",
    "Battleadze": "战斗斧",
    "Leafmace": "叶锤",
    "Shortsword": "短剑",
    "Longiron": "长铁剑",
    "Poachard": "偷猎者剑",
    "Baselard": "巴塞拉尔剑",
    "Whinyard": "弯柄剑",
    "Blunderbuss": "滑膛枪",
    "Longsword": "长剑",
    "Crankbow": "曲柄弓",
    "Blibo": "布利博剑",
    "Broadsword": "宽剑",
    "Kreen": "克林刃",
    "Warhammer": "战锤",
    "Morning Star": "晨星锤",
    "Pole-adze": "长柄斧",
    "Spontoon": "短矛",
    "Bastard Sword": "杂种剑",
    "Peen-arm": "锻头臂",
    "Culverin": "老式火炮",
    "Lance": "长枪",
    "Halberd": "戟",
    "Poleax": "长柄战斧",
    "Bandyclef": "班迪克莱夫刃",
}

# 盾牌
SHIELDS_CN = {
    "Parasol": "阳伞盾", "Pie Plate": "馅饼盘盾", "Garbage Can Lid": "垃圾桶盖盾",
    "Buckler": "小圆盾", "Plexiglass": "有机玻璃盾", "Fender": "挡泥板盾",
    "Round Shield": "圆形盾牌", "Carapace": "甲壳盾", "Scutum": "矩形大盾",
    "Propugner": "防御者盾", "Kite Shield": "鸢形盾", "Pavise": "巨盾",
    "Tower Shield": "塔盾", "Baroque Shield": "巴洛克盾牌", "Aegis": "埃癸斯盾",
    "Magnetic Field": "磁场盾",
}

# 盔甲
ARMORS_CN = {
    "Lace": "蕾丝甲", "Macrame": "编结甲", "Burlap": "粗麻甲", "Canvas": "帆布甲",
    "Flannel": "法兰绒甲", "Chamois": "麂皮甲", "Pleathers": "仿皮甲",
    "Leathers": "皮甲", "Bearskin": "熊皮甲", "Ringmail": "环甲",
    "Scale Mail": "鳞甲", "Chainmail": "锁子甲", "Splint Mail": "板条甲",
    "Platemail": "板甲", "ABS": "塑料甲", "Kevlar": "凯夫拉甲",
    "Titanium": "钛甲", "Mithril Mail": "秘银甲", "Diamond Mail": "钻石甲",
    "Plasma": "等离子甲",
}

# 物品属性
ITEM_ATTRIB_CN = {
    "Polished": "抛光", "Serrated": "锯齿", "Heavy": "重型", "Pronged": "多叉",
    "Steely": "钢铁", "Vicious": "恶毒", "Venomed": "涂毒", "Stabbity": "锋利",
    "Dancing": "舞动", "Invisible": "隐形", "Vorpal": "巨刃",
    "Studded": "铆钉", "Banded": "带状", "Gilded": "镀金", "Festooned": "饰花",
    "Holy": "神圣", "Cambric": "细麻", "Fine": "精制", "Impressive": "非凡",
    "Custom": "定制",
}

# 特殊物品
SPECIALS_CN = {
    "Diadem": "王冠", "Festoon": "花彩", "Gemstone": "宝石", "Phial": "小药瓶",
    "Tiara": "头饰", "Scabbard": "剑鞘", "Arrow": "箭", "Lens": "透镜",
    "Lamp": "灯", "Hymnal": "赞美诗", "Fleece": "羊毛", "Laurel": "月桂",
    "Brooch": "胸针", "Gimlet": "手钻", "Cobble": "鹅卵石", "Albatross": "信天翁",
    "Brazier": "火盆", "Bandolier": "子弹带", "Tome": "巨著", "Garnet": "石榴石",
    "Amethyst": "紫水晶", "Candelabra": "枝形烛台", "Corset": "紧身衣",
    "Sphere": "球体", "Sceptre": "权杖", "Ankh": "安卡十字章",
    "Talisman": "护身符", "Orb": "法球", "Gammel": "伽梅尔", "Ornament": "装饰品",
    "Brocade": "织锦",
}

# 任务关键词
QUEST_CN = {
    "Exterminate": "消灭",
    "Seek": "寻找",
    "Deliver this": "交付",
    "Fetch me": "获取",
    "Placate": "安抚",
}

# 种族
RACES_CN = {
    "Half Orc": "半兽人",
    "Half Man": "半身人",
    "Half Halfling": "半半身人",
    "Double Hobbit": "双霍比特人",
    "Hob-Hobbit": "霍比特人",
    "Low Elf": "低等精灵",
    "Dung Elf": "粪精灵",
    "Talking Pony": "会说话的小马",
    "Gyrognome": "旋翼侏儒",
    "Lesser Dwarf": "小矮人",
    "Crested Dwarf": "冠矮人",
    "Eel Man": "鳗人",
    "Panda Man": "熊猫人",
    "Trans-Kobold": "跨狗头人",
    "Enchanted Motorcycle": "被施法的摩托车",
    "Will o' the Wisp": "鬼火",
    "Battle-Finch": "战斗雀",
    "Double Wookiee": "双伍基人",
    "Skraeling": "斯克莱林人",
    "Demicanadian": "半加拿大人",
    "Land Squid": "陆鱿",
}

# 职业
CLASSES_CN = {
    "Ur-Paladin": "远古圣武士",
    "Voodoo Princess": "巫毒公主",
    "Puma Burgular": "美洲豹窃贼",
    "Robot Monk": "机器武僧",
    "Mu-Fu Monk": "穆夫武僧",
    "Mage Illusioner": "幻术师",
    "Shiv-Knight": "短刀骑士",
    "Birdrider": "鸟骑士",
    "Bastard Lunatic": "杂种狂徒",
    "Hunter Strangler": "猎杀勒喉者",
    "Fighter/Organist": "战士/风琴手",
    "Slow Poisoner": "慢性毒药师",
    "Tickle-Mimic": "挠痒拟态者",
    "Inner Mason": "内殿共济会士",
    "Battle-Felon": "战斗重犯",
    "Runeloremaster": "符文博学士",
    "Jungle Clown": "丛林小丑",
    "Vermineer": "除害师",
}

# ========== 组合翻译函数 ==========

# 构建完整翻译表
TRANSLATION_TABLE = {}
TRANSLATION_TABLE.update(CHARACTER_UI)
TRANSLATION_TABLE.update(MAIN_MENU_CN)
TRANSLATION_TABLE.update(CHAR_CREATE_CN)
TRANSLATION_TABLE.update(MISC_CN)
TRANSLATION_TABLE.update(EQUIPMENT_CN)
TRANSLATION_TABLE.update(ACTION_TEXT)
TRANSLATION_TABLE.update(PLOT_TEXT)
TRANSLATION_TABLE.update(MONSTER_MODS_CN)
TRANSLATION_TABLE.update(SPELLS_CN)
TRANSLATION_TABLE.update(WEAPONS_CN)
TRANSLATION_TABLE.update(SHIELDS_CN)
TRANSLATION_TABLE.update(ARMORS_CN)
TRANSLATION_TABLE.update(ITEM_ATTRIB_CN)
TRANSLATION_TABLE.update(SPECIALS_CN)
TRANSLATION_TABLE.update(QUEST_CN)
TRANSLATION_TABLE.update(RACES_CN)
TRANSLATION_TABLE.update(CLASSES_CN)

# #9：模块加载时缓存按长度降序的键列表，避免 translate() 每帧（每 100ms）重建，
# 消除 O(条目数 × 词典大小) 的重复排序开销。
_SORTED_KEYS = sorted(TRANSLATION_TABLE.keys(), key=len, reverse=True)


def translate(text: str) -> str:
    """翻译文本。先精确匹配，再按最长子串匹配。"""
    if not text:
        return text

    # 精确匹配
    if text in TRANSLATION_TABLE:
        return TRANSLATION_TABLE[text]

    # 按长度降序匹配子串（使用缓存的 _SORTED_KEYS）
    result = text
    for key in _SORTED_KEYS:
        if len(key) > 1 and key in result:
            result = result.replace(key, TRANSLATION_TABLE[key])
    return result


def translate_action_label(label: str) -> str:
    """翻译行动标签（#7：替换前缀后继续翻译剩余文本，避免中英混杂）"""
    if not label:
        return label
    for eng, cn in ACTION_TEXT.items():
        if label.startswith(eng):
            rest = label[len(eng):]
            return cn + (translate(rest) if rest else "")
    return translate(label)


def translate_quest_label(label: str) -> str:
    """翻译任务标签（#7：替换前缀后继续翻译剩余文本，避免中英混杂）"""
    if not label:
        return label
    for eng, cn in QUEST_CN.items():
        if label.startswith(eng):
            rest = label[len(eng):]
            return cn + (translate(rest) if rest else "")
    return translate(label)


# ========== A11 本地化缺键监控 ==========
# 显式字典查找（get_cn）缺失时记录到 registry，供 CI/遥测消费，
# 而非仅静默回退英文（呼应 postmortem A10/A11）。
# 注意：仅监控「显式键查找」边界；自由文本翻译（translate 的子串扫描、
# 装备/物品复合名展示）不监控，避免噪声。
import time as _time

MISSING_KEYS = {}  # key -> {"count": int, "first_seen": float}


def record_missing_key(key: str) -> None:
    """记录一个缺失的翻译键（去重，按 key 累计计数）。"""
    if not key:
        return
    entry = MISSING_KEYS.get(key)
    if entry is None:
        MISSING_KEYS[key] = {"count": 1, "first_seen": _time.time()}
    else:
        entry["count"] += 1


def get_missing_keys():
    """返回 [(key, count, first_seen), ...]，供测试/遥测消费。"""
    return [(k, v["count"], v["first_seen"]) for k, v in MISSING_KEYS.items()]


def clear_missing_keys() -> None:
    """清空缺键登记（测试隔离用）。"""
    MISSING_KEYS.clear()


def audit_translation_coverage() -> list:
    """A11：核验数据文件名是否都有中文翻译，缺失记入 MISSING_KEYS 并返回缺失列表。
    覆盖（有完整中文字典的类别，避免噪声）：种族/职业/法术/武器/盾牌/盔甲/
    装备槽/怪物修饰词/行动文本/剧情文本/任务关键词。
    刻意排除怪物名/特殊物品/物品属性等专有名词（按游戏设计以英文展示，
    否则会淹没监控）。供启动审计与 CI 使用。
    """
    missing = []
    try:
        from .data.races import RACES
        from .data.classes import CLASSES
        from .data.spells import SPELLS
        from .data.weapons import WEAPONS
        from .data.shields import SHIELDS
        from .data.armors import ARMORS

        names = []
        names += [r.name for r in RACES]
        names += [c.name for c in CLASSES]
        names += list(SPELLS)
        names += [w.label for w in WEAPONS]
        names += [s.label for s in SHIELDS]
        names += [a.label for a in ARMORS]
        names += list(EQUIPMENT_LABELS)
        names += list(MONSTER_MODS_CN.keys())
        names += list(ACTION_TEXT.keys())
        names += list(PLOT_TEXT.keys())
        names += list(QUEST_CN.keys())

        for n in names:
            if n and n not in TRANSLATION_TABLE:
                record_missing_key(n)
                if n not in missing:
                    missing.append(n)
    except Exception as e:
        # 审计失败不应影响启动；记录异常键便于排查
        record_missing_key(f"<audit-error: {type(e).__name__}>")
    return missing


def get_cn(text: str, default: str = "", monitor: bool = True) -> str:
    """获取中文翻译，找不到则返回默认值。

    monitor=True 时，若 key 缺失则记入缺键监控（A11）；装备/物品复合名等
    自由文本展示应传 monitor=False 以避免噪声。
    """
    cn = TRANSLATION_TABLE.get(text)
    if cn is None:
        if monitor:
            record_missing_key(text)
        return default if default else text
    return cn
