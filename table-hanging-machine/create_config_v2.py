"""
一键生成完整 config.xlsx v2.1
包含：角色/装备/背包/任务/怪物/章节/法术/商店装备
v2.1 更新：
- 角色新增智慧(WIS)属性，使用 klass 字段
- 装备新增肩甲，共 11 槽
- 种族使用 PQ 风格名称
"""
import os
import openpyxl

BASE = os.path.dirname(os.path.abspath(__file__))
wb = openpyxl.Workbook()

# ==================== Sheet1: 角色 ====================
ws = wb.active
ws.title = "角色"
ws.append(["属性", "值"])
player_data = [
    ["姓名", "Nebib"],
    ["种族", "Will o' the Wisp"],
    ["klass", "Runeloremaster"],
    ["等级", 1],
    ["经验", 0],
    ["升级经验", 1150],
    ["力量", 12],
    ["体质", 14],
    ["敏捷", 11],
    ["智力", 15],
    ["智慧", 13],
    ["魅力", 10],
    ["HP", 100],
    ["MP", 80],
    ["章节", "Act I"],
]
for row in player_data:
    ws.append(row)

# ==================== Sheet2: 装备（11 槽） ====================
ws2 = wb.create_sheet("装备")
ws2.append(["部位", "名称", "攻击", "防御"])
equipment = [
    ("武器", "+5 花彩的定制阔剑之混乱", 5, 0),
    ("盾牌", "+2 令人印象深刻的塔盾之忠诚", 0, 12),
    ("头盔", "花彩的神圣的钛甲之坚毅", 0, 8),
    ("胸甲", "镶刀的钻石甲之力", 3, 15),
    ("肩甲", "令人印象深刻的秘银肩甲之勇气", 1, 6),
    ("臂甲", "令人印象深刻的镶刀的秘银甲之忍耐", 2, 12),
    ("手套", "+1 钻石甲之迅捷", 1, 5),
    ("内甲", "+2 定制的镶刀的秘银甲之幸运", 2, 14),
    ("裤甲", "+3 定制的秘银甲之纪律", 3, 11),
    ("腿甲", "+1 钻石甲之平衡", 1, 9),
    ("足甲", "镶刀的钻石甲之轻灵", 2, 10),
]
for eq in equipment:
    ws2.append(list(eq))

# ==================== Sheet3: 背包 ====================
ws3 = wb.create_sheet("背包")
ws3.append(["名称", "数量"])
inventory = [
    ("莫库斯 牙齿", 1), ("伊洛胡 连枷", 2), ("瓷巨人 瓷器", 1), ("梁龙 鳞", 1),
    ("羽毛 佩鲁 表袋", 1), ("蒸气巨人 水滴", 1), ("氧气 佩鲁 血小板", 1), ("雷龙 脑", 1),
    ("魔龙 龙臂", 1), ("朱庇克斯 凝胶", 1), ("双头怪 毛皮", 1), ("啤酒 佩鲁 泡沫", 1),
    ("火巨人 香烟", 1), ("潘特 瑟瑞斯 头", 1), ("橡胶 佩鲁 球", 1), ("星芒的 紧身衣 之快度", 1),
    ("陷阱 铁丝", 1), ("巨齿龙 下颚", 1),
]
for inv in inventory:
    ws3.append(list(inv))

# ==================== Sheet4: 任务 ====================
ws4 = wb.create_sheet("任务")
ws4.append(["名称", "目标类型", "目标", "需求数量", "奖励类型", "奖励值"])

import random as _r
_r.seed(42)
reward_pool = ["装备", "属性", "法术", "金币", "特殊宝物"]
stat_boosts_pq = [
    "力量+2","体质+2","敏捷+2","智力+2","智慧+2","魅力+2","全属性+2"]
equip_rewards_pq = [
    "铁剑","皮甲","木盾","铁护腕","皮靴","铁头盔","皮手套"]
spell_rewards_pq = [
    "火球术","冰霜箭","治愈之光","闪电链","暗影弹"]

# --- PQ 数据驱动的任务 ---
# 击杀任务：用 PQ 怪物英文名（子串匹配 "giant Kobold" → "Kobold"）
pq_kill_targets = [
    "Vermine","Kobold","Giant Rat","Goblin","Slime","Zombie",
    "Skeleton","Bat","Spider","Worm","Orc","Gnoll","Hobgoblin",
    "Ghoul","Wraith","Ghost","Troll","Ogre","Bandit","Brigand",
    "Gargoyle","Manticore","Wyvern","Chimera","Basilisk",
    "Cockatrice","Griffon","Hippogriff","Minotaur","Centaur",
    "Golem","Doppelganger","Medusa","Harpy","Cyclops",
    "Hellhound","Werewolf","Vampire Bat","Giant Scorpion",
    "Mummy","Giant Snake","Lich","Death Knight","Shadow Demon",
    "Succubus","Incubus","Banshee","Wendigo","Nightmare",
    "Dragon Whelp","Gorgon","Hydra","Kraken","Behemoth",
    "Leviathan","Phoenix","Thunderbird","Roc","Juggernaut",
    "Stone Giant",
]

# 收集任务：用 PQ 怪物掉落物（精确匹配）
pq_collect_targets = [
    "鼠尾巴","破布","蜡烛头","小刀","鼠皮","生肉","短剑","麻袋",
    "黏液","玻璃碎片","腐肉","骨片","生锈头盔","蝙蝠翅膀","尖牙",
    "蛛丝","毒液","蠕虫黏液","泥土","战斧","兽皮","长矛","鬣狗皮",
    "链甲碎片","战锤","灵魂碎片","暗影布","灵质","旧金币","巨魔皮",
    "大棒","食人魔牙","巨棒","匕首","钱袋","短弓","皮革甲","石肤",
    "暗水晶","蝎尾","狮鬃","飞龙鳞","奇美拉角","混合之血","石化眼",
    "蛇鳞","石化羽毛","鸡冠","狮鹫羽毛","狮鹫爪","马鹫鬃","巨鸟喙",
    "牛角","巨斧","马蹄铁","长弓","黏土块","符文石","变形皮",
    "记忆丝","蛇发","石化碎片","鸟妖羽毛","利爪","独眼巨人眼",
    "巨锤","地狱犬牙","地狱火","狼人毛皮","银子弹","吸血蝙蝠牙",
    "蝙蝠翼","巨蝎螯","蝎毒","裹尸布","圣甲虫","巨蛇皮","蛇毒",
    "命匣","暗法术书","符文剑","黑铁甲","暗影精华","恶魔角",
    "魅魔之翼","魅惑香水","梦魔之角","暗影斗篷","女妖之纱",
    "哀嚎碎片","温迪灵魂","冰晶","噩梦鬃毛","暗黑马蹄","幼龙鳞",
    "火焰碎片","石牛气息","青铜蹄","九头蛇毒","多头鳞","海妖触手",
    "深海珍珠","巨兽牙","巨兽骨","海龙鳞","深渊之水","凤凰羽毛",
    "重生灰烬","雷鸟羽","闪电晶","巨鸟羽","金刚石","攻城锤",
    "铁铸甲","巨石","巨人骨",
]

all_quests = []
# 击杀任务（60个）
for target in _r.sample(pq_kill_targets, min(60, len(pq_kill_targets))):
    name = f"消灭 {target}"
    rt = _r.choice(reward_pool)
    if rt == "装备":
        rv = _r.choice(equip_rewards_pq)
    elif rt == "属性":
        rv = _r.choice(stat_boosts_pq)
    elif rt == "法术":
        rv = _r.choice(spell_rewards_pq)
    elif rt == "特殊宝物":
        rv = "特殊宝物"
    else:
        rv = str(_r.choice([80, 100, 120, 150, 200, 250, 300]))
    all_quests.append((name, "击杀", target,
                       _r.choice([1, 2, 3, 4, 5]), rt, rv))

# 收集任务（40个）
for target in _r.sample(pq_collect_targets, min(40, len(pq_collect_targets))):
    name = f"收集 {target}"
    rt = _r.choice(reward_pool)
    if rt == "装备":
        rv = _r.choice(equip_rewards_pq)
    elif rt == "属性":
        rv = _r.choice(stat_boosts_pq)
    elif rt == "法术":
        rv = _r.choice(spell_rewards_pq)
    elif rt == "特殊宝物":
        rv = "特殊宝物"
    else:
        rv = str(_r.choice([50, 80, 100, 120, 150, 200]))
    all_quests.append((name, "收集", target,
                       _r.choice([1, 2, 3, 4, 5]), rt, rv))

for q in all_quests:
    ws4.append(list(q))

# ==================== Sheet5: 怪物 ====================
ws5 = wb.create_sheet("怪物")
ws5.append(["名称", "等级", "HP", "攻击", "防御", "经验", "掉落物品(分号分隔)"])
monsters = [
    # 序言·暗影森林
    ("树精", 18, 120, 25, 12, 85, "木材;树精汁液"),
    ("地魔", 22, 180, 35, 18, 120, "地魔之核;泥土结晶"),
    ("沼泽泥怪", 12, 90, 18, 8, 55, "沼泽苔藓;泥怪黏液"),
    ("暗影幼狼", 15, 100, 22, 10, 70, "暗影毛皮;狼牙"),
    ("毒蘑菇精", 20, 140, 28, 14, 95, "毒蘑菇孢子;致幻菇"),
    # 荒野征途
    ("石巨人", 28, 350, 55, 30, 200, "巨石碎片;花岗岩"),
    ("蛇鸣兽", 24, 210, 42, 22, 150, "蛇鸣鳞片;毒牙"),
    ("龙龟", 32, 500, 70, 45, 320, "龙龟甲;长寿水"),
    ("魅棺", 30, 420, 65, 35, 250, "魅影纱布;色情元素"),
    ("游荡骑士", 35, 300, 50, 30, 220, "生锈的骑士剑;骑士徽章"),
    ("沙暴元素", 38, 280, 55, 25, 240, "沙暴核心;元素结晶"),
    ("食人花", 42, 320, 58, 28, 260, "食人花种子;麻痹花粉"),
    # 深渊裂隙
    ("深渊触手", 58, 450, 72, 38, 350, "触手黏液;深渊珍珠"),
    ("熔岩魔像", 62, 520, 80, 50, 400, "熔岩核心;黑曜石碎片"),
    ("虚空行者", 68, 480, 85, 40, 420, "虚空精华;空间碎片"),
    ("时间蠕虫", 72, 550, 78, 45, 450, "时光之沙;虫壳碎片"),
    # 龙焰山脉
    ("火龙幼崽", 78, 600, 90, 52, 500, "龙鳞片;龙息余烬"),
    ("黑曜石像鬼", 82, 580, 95, 55, 520, "黑曜石核心;石像鬼之翼"),
    ("噬魂女妖", 85, 520, 100, 42, 540, "女妖之泪;魂之丝线"),
    ("雷霆巨鹰", 88, 620, 105, 58, 560, "雷鸟之羽;暴风之眼"),
    ("冰霜骨龙", 92, 700, 110, 65, 600, "冰龙骨;霜冻精华"),
    # 诸神黄昏
    ("堕落天使", 95, 650, 120, 60, 650, "天使之翼;堕落圣光"),
    ("泰坦残骸", 97, 800, 115, 75, 700, "泰坦之心;神铁碎片"),
    ("混沌巨兽", 99, 900, 130, 70, 750, "混沌核心;虚空之眼"),
    ("星辰吞噬者", 102, 850, 140, 68, 800, "星核碎片;暗物质"),
    ("末日巨龙", 105, 1000, 150, 80, 900, "末日之心;龙神鳞片"),
]
for m in monsters:
    ws5.append(list(m))

# ==================== Sheet6: 章节 ====================
ws6 = wb.create_sheet("章节")
ws6.append(["章节名", "最低等级", "怪物列表", "任务列表"])
acts = [
    ("序言·暗影森林", 1,
     "Vermine;Kobold;Giant Rat;Goblin;Slime;Zombie;Skeleton;Bat;Spider;Worm",
     "Vermine;Kobold;Giant Rat;Goblin;Slime;Zombie;Skeleton;Bat;Spider;Worm;鼠尾巴;破布;蜡烛头;小刀;鼠皮;生肉;短剑;麻袋;黏液;玻璃碎片"),
    ("荒野征途", 30,
     "Orc;Gnoll;Hobgoblin;Ghoul;Wraith;Ghost;Troll;Ogre;Bandit;Brigand",
     "Orc;Gnoll;Hobgoblin;Ghoul;Wraith;Ghost;Troll;Ogre;Bandit;Brigand;战斧;兽皮;长矛;鬣狗皮;链甲碎片;战锤;灵魂碎片;暗影布;灵质;旧金币"),
    ("深渊裂隙", 55,
     "Gargoyle;Manticore;Wyvern;Chimera;Basilisk;Cockatrice;Griffon;Minotaur;Golem;Doppelganger",
     "Gargoyle;Manticore;Wyvern;Chimera;Basilisk;Cockatrice;Griffon;Minotaur;Golem;Doppelganger;石肤;暗水晶;蝎尾;狮鬃;飞龙鳞;奇美拉角"),
    ("龙焰山脉", 75,
     "Medusa;Harpy;Cyclops;Hellhound;Werewolf;Vampire Bat;Giant Scorpion;Mummy;Giant Snake;Lich",
     "Medusa;Harpy;Cyclops;Hellhound;Werewolf;Vampire Bat;Giant Scorpion;Mummy;Giant Snake;Lich;蛇发;鸟妖羽毛;独眼巨人眼;地狱犬牙;狼人毛皮"),
    ("诸神黄昏", 92,
     "Death Knight;Shadow Demon;Banshee;Wendigo;Dragon Whelp;Hydra;Kraken;Phoenix;Leviathan;Stone Giant",
     "Death Knight;Shadow Demon;Banshee;Wendigo;Dragon Whelp;Hydra;Kraken;Phoenix;Leviathan;Stone Giant;符文剑;暗影精华;女妖之纱;温迪灵魂;幼龙鳞"),
]
for a in acts:
    ws6.append(list(a))

# ==================== Sheet7: 法术 ====================
ws7 = wb.create_sheet("法术")
ws7.append(["名称", "类型", "威力", "MP消耗", "描述"])
spells = [
    ("火球术", "伤害", 35, 15, "投掷一枚灼热的火球"),
    ("冰霜箭", "伤害", 30, 12, "发射一支极寒的冰箭"),
    ("闪电链", "伤害", 40, 18, "释放一道连锁闪电"),
    ("暗影弹", "伤害", 32, 14, "凝聚暗影能量轰击敌人"),
    ("神圣惩击", "伤害", 45, 20, "召唤圣光惩罚邪恶"),
    ("陨石术", "伤害", 55, 25, "从天空召唤一颗陨石"),
    ("毒雾术", "伤害", 25, 10, "释放一片剧毒雾气"),
    ("灵魂燃烧", "伤害", 50, 22, "点燃敌人的灵魂"),
    ("治愈之光", "治疗", 40, 20, "温暖的圣光恢复生命"),
    ("生命之泉", "治疗", 60, 28, "生命能量涌入全身"),
    ("再生术", "治疗", 25, 12, "缓慢持续恢复生命"),
    ("神圣护盾", "治疗", 35, 16, "召唤圣盾吸收伤害"),
    ("力量祝福", "增益", 10, 15, "临时提升攻击力"),
    ("敏捷光环", "增益", 8, 12, "临时提升闪避"),
    ("铁壁术", "增益", 12, 18, "皮肤变得如钢铁坚硬"),
    ("狂暴术", "增益", 15, 20, "激发狂暴，大幅提升攻击"),
    ("虚弱诅咒", "减益", 10, 10, "削弱敌人的力量"),
    ("腐蚀术", "减益", 8, 8, "腐蚀敌人的护甲"),
    ("减速术", "减益", 5, 6, "减缓敌人的行动"),
    ("沉默术", "减益", 12, 14, "封印敌人的魔法能力"),
]
for s in spells:
    ws7.append(list(s))

# ==================== Sheet8: 商店装备 ====================
ws8 = wb.create_sheet("商店装备")
ws8.append(["名称", "部位", "攻击", "防御", "价格"])
shop = [
    ("铁剑", "武器", 5, 0, 120), ("钢剑", "武器", 8, 0, 250),
    ("秘银长剑", "武器", 12, 0, 500), ("符文之刃", "武器", 16, 0, 900),
    ("暗影之牙", "武器", 20, 0, 1500), ("龙焰巨剑", "武器", 25, 0, 2500),
    ("诸神裁决", "武器", 30, 0, 4000),
    ("木盾", "盾牌", 0, 3, 80), ("铁盾", "盾牌", 0, 6, 180),
    ("塔盾", "盾牌", 0, 10, 380), ("龙鳞盾", "盾牌", 0, 15, 700),
    ("圣光壁垒", "盾牌", 0, 20, 1200),
    ("皮帽", "头盔", 0, 2, 60), ("铁头盔", "头盔", 0, 4, 150),
    ("秘银冠", "头盔", 0, 7, 300), ("龙骨头盔", "头盔", 1, 9, 500),
    ("皮甲", "胸甲", 0, 4, 150), ("链甲", "胸甲", 0, 8, 350),
    ("板甲", "胸甲", 1, 12, 600), ("龙鳞胸甲", "胸甲", 2, 16, 1000),
    ("皮护腕", "臂甲", 0, 2, 50), ("铁护腕", "臂甲", 1, 3, 120),
    ("布手套", "手套", 0, 1, 40), ("皮手套", "手套", 1, 2, 100),
    ("布裤", "裤甲", 0, 2, 60), ("皮裤", "裤甲", 0, 4, 140),
    ("布鞋", "足甲", 0, 1, 40), ("皮靴", "足甲", 1, 2, 100),
    ("铁靴", "足甲", 0, 4, 180),
]
for s in shop:
    ws8.append(list(s))

wb.save(os.path.join(BASE, "config.xlsx"))
print(f"✅ config.xlsx v2 已生成")
print(f"   角色:1 | 装备:10件 | 背包:18种 | 任务:{len(all_quests)}个")
print(f"   怪物:{len(monsters)}种 | 章节:{len(acts)}个")
print(f"   法术:{len(spells)}个 | 商店装备:{len(shop)}件")
