# -*- coding: utf-8 -*-
"""
《我的世界》文字冒险 — 游戏数据定义
====================================
物品、合成配方、生物、生物群系、维度等游戏内容数据。
"""

from __future__ import annotations

# ═══════════════════════════════════════════════════════════
#  物品定义
# ═══════════════════════════════════════════════════════════

ITEMS = {
    # === 基础资源 ===
    "wood_log":       {"name": "原木",       "icon": "🪵", "type": "resource", "tier": 0, "stack": 64},
    "wood_planks":    {"name": "木板",       "icon": "🟫", "type": "resource", "tier": 0, "stack": 64},
    "stick":          {"name": "木棍",       "icon": "🥢", "type": "resource", "tier": 0, "stack": 64},
    "cobblestone":    {"name": "圆石",       "icon": "🪨", "type": "resource", "tier": 0, "stack": 64},
    "coal":           {"name": "煤炭",       "icon": "⬛", "type": "resource", "tier": 0, "stack": 64},
    "iron_ore":       {"name": "铁矿石",     "icon": "🪨", "type": "resource", "tier": 1, "stack": 64},
    "iron_ingot":     {"name": "铁锭",       "icon": "🪙", "type": "resource", "tier": 1, "stack": 64},
    "gold_ore":       {"name": "金矿石",     "icon": "🟡", "type": "resource", "tier": 2, "stack": 64},
    "gold_ingot":     {"name": "金锭",       "icon": "🪙", "type": "resource", "tier": 2, "stack": 64},
    "diamond":        {"name": "钻石",       "icon": "💎", "type": "resource", "tier": 3, "stack": 64},
    "obsidian":       {"name": "黑曜石",     "icon": "🖤", "type": "resource", "tier": 4, "stack": 64},
    "flint":          {"name": "燧石",       "icon": "⬜", "type": "resource", "tier": 0, "stack": 64},
    "string":         {"name": "线",         "icon": "🧵", "type": "resource", "tier": 0, "stack": 64},
    "leather":        {"name": "皮革",       "icon": "🟤", "type": "resource", "tier": 0, "stack": 64},
    "wool":           {"name": "羊毛",       "icon": "🐑", "type": "resource", "tier": 0, "stack": 64},
    "feather":        {"name": "羽毛",       "icon": "🪶", "type": "resource", "tier": 0, "stack": 64},
    "wheat":          {"name": "小麦",       "icon": "🌾", "type": "resource", "tier": 0, "stack": 64},
    "blaze_rod":      {"name": "烈焰棒",     "icon": "🔥", "type": "resource", "tier": 3, "stack": 64},
    "ender_pearl":    {"name": "末影珍珠",   "icon": "🟢", "type": "resource", "tier": 4, "stack": 16},
    "ender_eye":      {"name": "末影之眼",   "icon": "🔮", "type": "resource", "tier": 4, "stack": 16},

    # === 工具 ===
    "wooden_pickaxe": {"name": "木镐",     "icon": "⛏️",  "type": "tool",   "tier": 0, "damage": 3,  "durability": 60},
    "wooden_sword":   {"name": "木剑",     "icon": "🗡️",  "type": "weapon", "tier": 0, "damage": 5,  "durability": 60},
    "wooden_axe":     {"name": "木斧",     "icon": "🪓",  "type": "tool",   "tier": 0, "damage": 4,  "durability": 60},
    "stone_pickaxe":  {"name": "石镐",     "icon": "⛏️",  "type": "tool",   "tier": 1, "damage": 5,  "durability": 132},
    "stone_sword":    {"name": "石剑",     "icon": "🗡️",  "type": "weapon", "tier": 1, "damage": 7,  "durability": 132},
    "stone_axe":      {"name": "石斧",     "icon": "🪓",  "type": "tool",   "tier": 1, "damage": 6,  "durability": 132},
    "iron_pickaxe":   {"name": "铁镐",     "icon": "⛏️",  "type": "tool",   "tier": 2, "damage": 7,  "durability": 251},
    "iron_sword":     {"name": "铁剑",     "icon": "🗡️",  "type": "weapon", "tier": 2, "damage": 9,  "durability": 251},
    "iron_axe":       {"name": "铁斧",     "icon": "🪓",  "type": "tool",   "tier": 2, "damage": 8,  "durability": 251},
    "diamond_pickaxe":{"name": "钻石镐",   "icon": "⛏️",  "type": "tool",   "tier": 3, "damage": 9,  "durability": 1562},
    "diamond_sword":  {"name": "钻石剑",   "icon": "🗡️",  "type": "weapon", "tier": 3, "damage": 12, "durability": 1562},
    "diamond_axe":    {"name": "钻石斧",   "icon": "🪓",  "type": "tool",   "tier": 3, "damage": 10, "durability": 1562},

    # === 防具 ===
    "iron_helmet":    {"name": "铁头盔",   "icon": "🪖",  "type": "armor",  "tier": 2, "defense": 2},
    "iron_chestplate":{"name": "铁胸甲",   "icon": "🛡️",  "type": "armor",  "tier": 2, "defense": 4},
    "iron_leggings":  {"name": "铁护腿",   "icon": "👖",  "type": "armor",  "tier": 2, "defense": 3},
    "iron_boots":     {"name": "铁靴子",   "icon": "👢",  "type": "armor",  "tier": 2, "defense": 1},

    # === 食物 ===
    "raw_porkchop":   {"name": "生猪排",   "icon": "🥩",  "type": "food",   "hunger": 3,  "saturation": 1.8},
    "raw_beef":       {"name": "生牛排",   "icon": "🥩",  "type": "food",   "hunger": 3,  "saturation": 1.8},
    "raw_mutton":     {"name": "生羊肉",   "icon": "🍖",  "type": "food",   "hunger": 2,  "saturation": 1.2},
    "raw_chicken":    {"name": "生鸡肉",   "icon": "🍗",  "type": "food",   "hunger": 2,  "saturation": 1.2},
    "bread":          {"name": "面包",     "icon": "🍞",  "type": "food",   "hunger": 5,  "saturation": 6.0},
    "cooked_porkchop":{"name": "熟猪排",   "icon": "🍖",  "type": "food",   "hunger": 8,  "saturation": 12.8},
    "cooked_beef":    {"name": "熟牛排",   "icon": "🥩",  "type": "food",   "hunger": 8,  "saturation": 12.8},
    "apple":          {"name": "苹果",     "icon": "🍎",  "type": "food",   "hunger": 4,  "saturation": 2.4},
    "milk":           {"name": "牛奶",     "icon": "🥛",  "type": "food",   "hunger": 2,  "saturation": 1.2},

    # === 特殊物品 ===
    "torch":          {"name": "火把",     "icon": "🔦",  "type": "special", "tier": 0},
    "crafting_table": {"name": "工作台",   "icon": "🔲",  "type": "special", "tier": 0},
    "furnace":        {"name": "熔炉",     "icon": "🔥",  "type": "special", "tier": 0},
    "bed":            {"name": "床",       "icon": "🛏️",  "type": "special", "tier": 0},
    "bow":            {"name": "弓",       "icon": "🏹",  "type": "weapon", "tier": 1, "damage": 8, "durability": 385},
    "arrow":          {"name": "箭",       "icon": "🏹",  "type": "ammo",   "tier": 0},
    "flint_and_steel":{"name": "打火石",   "icon": "🔥",  "type": "special", "tier": 1},
    "bucket":         {"name": "铁桶",     "icon": "🪣",  "type": "special", "tier": 1},
    "shield":         {"name": "盾牌",     "icon": "🛡️",  "type": "armor",  "tier": 1, "defense": 5},
    "turtle_scute":   {"name": "海龟壳",   "icon": "🐢",  "type": "resource", "tier": 1, "stack": 64},
}


# ═══════════════════════════════════════════════════════════
#  合成配方
# ═══════════════════════════════════════════════════════════
# 格式: { 产物: { "needs": [(物品ID, 数量), ...], "station": "工作台/熔炉/无" } }

CRAFTING_RECIPES = {
    "wood_planks":    {"needs": [("wood_log", 1)],         "yields": 4, "station": "无"},
    "stick":          {"needs": [("wood_planks", 2)],       "yields": 4, "station": "无"},
    "crafting_table": {"needs": [("wood_planks", 4)],       "yields": 1, "station": "无"},
    "torch":          {"needs": [("stick", 1), ("coal", 1)], "yields": 4, "station": "无"},

    # 木制工具（需要工作台）
    "wooden_pickaxe": {"needs": [("wood_planks", 3), ("stick", 2)], "yields": 1, "station": "工作台"},
    "wooden_sword":   {"needs": [("wood_planks", 2), ("stick", 1)], "yields": 1, "station": "工作台"},
    "wooden_axe":     {"needs": [("wood_planks", 3), ("stick", 2)], "yields": 1, "station": "工作台"},

    # 石制工具
    "stone_pickaxe":  {"needs": [("cobblestone", 3), ("stick", 2)], "yields": 1, "station": "工作台"},
    "stone_sword":    {"needs": [("cobblestone", 2), ("stick", 1)], "yields": 1, "station": "工作台"},
    "stone_axe":      {"needs": [("cobblestone", 3), ("stick", 2)], "yields": 1, "station": "工作台"},

    # 铁制工具
    "iron_pickaxe":   {"needs": [("iron_ingot", 3), ("stick", 2)], "yields": 1, "station": "工作台"},
    "iron_sword":     {"needs": [("iron_ingot", 2), ("stick", 1)], "yields": 1, "station": "工作台"},
    "iron_axe":       {"needs": [("iron_ingot", 3), ("stick", 2)], "yields": 1, "station": "工作台"},

    # 铁制防具
    "iron_helmet":     {"needs": [("iron_ingot", 5)], "yields": 1, "station": "工作台"},
    "iron_chestplate": {"needs": [("iron_ingot", 8)], "yields": 1, "station": "工作台"},
    "iron_leggings":   {"needs": [("iron_ingot", 7)], "yields": 1, "station": "工作台"},
    "iron_boots":      {"needs": [("iron_ingot", 4)], "yields": 1, "station": "工作台"},

    # 钻石工具
    "diamond_pickaxe": {"needs": [("diamond", 3), ("stick", 2)], "yields": 1, "station": "工作台"},
    "diamond_sword":   {"needs": [("diamond", 2), ("stick", 1)], "yields": 1, "station": "工作台"},
    "diamond_axe":     {"needs": [("diamond", 3), ("stick", 2)], "yields": 1, "station": "工作台"},

    # 其他
    "furnace":        {"needs": [("cobblestone", 8)], "yields": 1, "station": "工作台"},
    "bread":          {"needs": [("wheat", 3)], "yields": 1, "station": "工作台"},
    "bed":            {"needs": [("wool", 3), ("wood_planks", 3)], "yields": 1, "station": "工作台"},
    "bow":            {"needs": [("stick", 3), ("string", 3)], "yields": 1, "station": "工作台"},
    "shield":         {"needs": [("iron_ingot", 1), ("wood_planks", 5)], "yields": 1, "station": "工作台"},
}

# 熔炉配方
FURNACE_RECIPES = {
    "iron_ingot":    {"needs": [("iron_ore", 1)], "yields": 1},
    "gold_ingot":    {"needs": [("gold_ore", 1)], "yields": 1},
    "cooked_porkchop":{"needs":[("raw_porkchop", 1)], "yields": 1},
    "cooked_beef":   {"needs": [("raw_beef", 1)], "yields": 1},
}


# ═══════════════════════════════════════════════════════════
#  生物群系
# ═══════════════════════════════════════════════════════════

BIOMES = {
    "plains": {
        "name": "平原", "icon": "🌿",
        "desc": "一片开阔的草原，零星点缀着花朵和草丛。",
        "resources": {"wood_log": (2, 5), "coal": (0, 2), "apple": (0, 3), "wheat": (1, 4)},
        "passive_mobs": ["pig", "cow", "sheep", "chicken", "horse"],
        "hostile_spawn_rate": 0.25,
    },
    "forest": {
        "name": "森林", "icon": "🌲",
        "desc": "茂密的树林遮蔽了天空，树冠间漏下斑驳的阳光。",
        "resources": {"wood_log": (4, 10), "apple": (1, 5), "stick": (2, 6), "coal": (0, 1)},
        "passive_mobs": ["pig", "chicken", "sheep"],
        "hostile_spawn_rate": 0.35,
    },
    "desert": {
        "name": "沙漠", "icon": "🏜️",
        "desc": "黄沙漫天，仙人掌零星矗立，阳光灼热得让人窒息。",
        "resources": {"cobblestone": (1, 4), "flint": (1, 3), "gold_ore": (0, 2)},
        "passive_mobs": ["rabbit"],
        "hostile_spawn_rate": 0.30,
    },
    "mountains": {
        "name": "山地", "icon": "🏔️",
        "desc": "陡峭的山崖直插云霄，矿脉裸露在岩壁上。",
        "resources": {"cobblestone": (3, 8), "coal": (1, 4), "iron_ore": (0, 2), "diamond": (0, 1)},
        "passive_mobs": ["sheep", "goat"],
        "hostile_spawn_rate": 0.20,
    },
    "swamp": {
        "name": "沼泽", "icon": "🏞️",
        "desc": "泥泞的湿地散发着腐臭，藤蔓从枯树上垂落。",
        "resources": {"wood_log": (1, 3), "string": (1, 3), "coal": (0, 1), "iron_ore": (0, 1)},
        "passive_mobs": ["chicken", "frog"],
        "hostile_spawn_rate": 0.45,
    },
    "taiga": {
        "name": "针叶林", "icon": "🌲",
        "desc": "高大的云杉覆盖着山丘，空气中弥漫着松香的味道。",
        "resources": {"wood_log": (3, 8), "cobblestone": (0, 3), "coal": (0, 2)},
        "passive_mobs": ["pig", "sheep", "fox"],
        "hostile_spawn_rate": 0.30,
    },
    "ocean": {
        "name": "海洋", "icon": "🌊",
        "desc": "蔚蓝的海水延伸到天际线，远处隐约可见沉船的桅杆。",
        "resources": {"obsidian": (0, 1), "cobblestone": (1, 3), "flint": (0, 2)},
        "passive_mobs": ["turtle", "dolphin"],
        "hostile_spawn_rate": 0.10,
    },
    "caves": {
        "name": "地下洞穴", "icon": "🕳️",
        "desc": "黑暗的洞窟深处，钟乳石倒悬，矿物的微光在黑暗中闪烁。",
        "resources": {"cobblestone": (2, 6), "coal": (2, 5), "iron_ore": (1, 5), "gold_ore": (0, 3), "diamond": (0, 2), "obsidian": (0, 1)},
        "passive_mobs": ["bat"],
        "hostile_spawn_rate": 0.60,
    },
    "nether": {
        "name": "下界", "icon": "🔥",
        "desc": "炽热的岩浆湖在脚下翻涌，空气中弥漫着硫磺的气息。",
        "resources": {"gold_ore": (1, 5), "obsidian": (0, 2), "blaze_rod": (0, 2)},
        "passive_mobs": [],
        "hostile_spawn_rate": 0.80,
    },
    "end": {
        "name": "末地", "icon": "🟣",
        "desc": "虚空之中漂浮着末地石岛屿，紫色的虚空粒子在四周飘荡。",
        "resources": {"obsidian": (2, 5), "ender_pearl": (1, 3)},
        "passive_mobs": ["enderman"],
        "hostile_spawn_rate": 0.50,
    },
}


# ═══════════════════════════════════════════════════════════
#  生物 / 怪物
# ═══════════════════════════════════════════════════════════

MOBS = {
    # === 被动生物 ===
    "pig":   {"name": "猪",   "icon": "🐷", "type": "passive", "hp": 10, "damage": 0, "drops": [("raw_porkchop", 1, 3)]},
    "cow":   {"name": "牛",   "icon": "🐮", "type": "passive", "hp": 10, "damage": 0, "drops": [("raw_beef", 1, 3), ("leather", 0, 2)]},
    "sheep": {"name": "羊",   "icon": "🐑", "type": "passive", "hp": 8,  "damage": 0, "drops": [("wool", 1, 3), ("raw_mutton", 1, 2)]},
    "chicken":{"name": "鸡",  "icon": "🐔", "type": "passive", "hp": 4,  "damage": 0, "drops": [("raw_chicken", 1, 1), ("feather", 1, 2)]},
    "horse": {"name": "马",   "icon": "🐴", "type": "passive", "hp": 20, "damage": 0, "drops": [("leather", 0, 2)]},
    "rabbit":{"name": "兔子", "icon": "🐰", "type": "passive", "hp": 6,  "damage": 0, "drops": [("raw_chicken", 0, 1)]},
    "frog":  {"name": "青蛙", "icon": "🐸", "type": "passive", "hp": 4,  "damage": 0, "drops": []},

    # === 补全生物（之前仅在群系列出却未登记于 MOBS，导致刷怪 KeyError 崩溃）===
    "goat":    {"name": "山羊",   "icon": "🐐", "type": "passive", "hp": 10, "damage": 0, "drops": [("milk", 1, 2), ("leather", 0, 1)]},
    "fox":     {"name": "狐狸",   "icon": "🦊", "type": "passive", "hp": 10, "damage": 0, "drops": [("feather", 0, 2), ("raw_chicken", 0, 1)]},
    "turtle":  {"name": "海龟",   "icon": "🐢", "type": "passive", "hp": 10, "damage": 0, "drops": [("turtle_scute", 1, 1)]},
    "dolphin": {"name": "海豚",   "icon": "🐬", "type": "passive", "hp": 10, "damage": 0, "drops": []},
    "bat":     {"name": "蝙蝠",   "icon": "🦇", "type": "passive", "hp": 6,  "damage": 0, "drops": []},

    # === 中立生物 ===
    "enderman": {"name": "末影人", "icon": "🟣", "type": "neutral", "hp": 40, "damage": 7,
                 "drops": [("ender_pearl", 1, 1)]},
    "wolf":     {"name": "狼",     "icon": "🐺", "type": "neutral", "hp": 20, "damage": 4,
                 "drops": []},

    # === 敌对生物 ===
    "zombie":  {"name": "僵尸",   "icon": "🧟", "type": "hostile", "hp": 20, "damage": 3,
                "drops": [("iron_ingot", 0, 1), ("stick", 0, 1)]},
    "skeleton":{"name": "骷髅",   "icon": "💀", "type": "hostile", "hp": 20, "damage": 4,
                "drops": [("arrow", 1, 3), ("bone", 1, 2)]},
    "creeper": {"name": "爬行者", "icon": "🟢", "type": "hostile", "hp": 20, "damage": 22,
                "drops": [("flint", 0, 2)]},
    "spider":  {"name": "蜘蛛",   "icon": "🕷️", "type": "hostile", "hp": 16, "damage": 2,
                "drops": [("string", 1, 3)]},
    "slime":   {"name": "史莱姆", "icon": "🟩", "type": "hostile", "hp": 10, "damage": 2,
                "drops": [("slime_ball", 1, 2)]},
    "witch":   {"name": "女巫",   "icon": "🧙", "type": "hostile", "hp": 26, "damage": 5,
                "drops": [("ender_pearl", 0, 1)]},

    # === Boss ===
    "ender_dragon": {"name": "末影龙", "icon": "🐉", "type": "boss", "hp": 200, "damage": 10,
                     "drops": [("diamond", 5, 10), ("ender_pearl", 3, 8)]},
}


# ═══════════════════════════════════════════════════════════
#  世界预设地图 (3×3 = 9 个区域)
# ═══════════════════════════════════════════════════════════

WORLD_MAP = [
    # row 0
    ["taiga",     "mountains", "ocean"],
    # row 1
    ["forest",    "plains",    "desert"],
    # row 2
    ["swamp",     "caves",     "forest"],
]

# 玩家起始位置
SPAWN_BIOME = (1, 1)  # plains
