"""预设游戏数据：武器、护甲、敌人、区域

数据取材自暗黑破坏神（Diablo）系列的真实怪物族群、经典暗金/传说物品与
 Sanctuary 世界中的知名地点（如崔斯特瑞姆、库拉斯特、混沌要塞、燃烧地狱等），
 仅使用名称与原创中文译名/描述，未引用任何受版权保护的文本。
"""
from models import Equipment, Enemy

# ---------------------------- Preset Data ----------------------------
# 品质梯度：Common(普通) < Rare(稀有) < Epic(史诗) < Legendary(传说)
WEAPONS = {
    # 原有基础武器
    "Iron Sword": Equipment("Iron Sword", 5, 0, 20, "Common"),
    "Flame Staff": Equipment("Flame Staff", 6, 0, 50, "Rare"),
    "Butcher's Cleaver": Equipment("Butcher's Cleaver", 9, 0, 120, "Epic"),
    # 暗黑经典暗金/传说武器
    "The Gidbinn": Equipment("The Gidbinn", 11, 0, 140, "Epic"),       # 吉德宾匕首
    "Rune Master": Equipment("Rune Master", 10, 0, 90, "Rare"),        # 符文大师战斧
    "The Minotaur": Equipment("The Minotaur", 9, 0, 95, "Rare"),       # 牛头人战斧
    "Deathbit": Equipment("Deathbit", 8, 0, 80, "Rare"),               # 死亡之噬匕首
    "Blood Crescent": Equipment("Blood Crescent", 9, 0, 90, "Rare"),   # 血色弯刀
    "Plague Bearer": Equipment("Plague Bearer", 13, 0, 180, "Epic"),   # 瘟疫使者权杖
    "Hexfire": Equipment("Hexfire", 12, 0, 160, "Epic"),               # 六火魔杖
    "Doombringer": Equipment("Doombringer", 22, 0, 500, "Legendary"),  # 末日使者巨剑
    "Wirt's Leg": Equipment("Wirt's Leg", 7, 0, 300, "Legendary"),     # 维特的腿（彩蛋）
}

ARMORS = {
    # 原有基础护甲
    "Leather Armor": Equipment("Leather Armor", 0, 3, 20, "Common"),
    "Chainmail": Equipment("Chainmail", 0, 5, 50, "Rare"),
    "Shadow Cloak": Equipment("Shadow Cloak", 0, 8, 120, "Epic"),
    # 暗黑经典暗金/传说护甲
    "Greyform": Equipment("Greyform", 0, 6, 80, "Rare"),              # 灰铸甲
    "Boneweave": Equipment("Boneweave", 0, 5, 70, "Rare"),            # 骨织甲
    "Stealskull": Equipment("Stealskull", 0, 5, 85, "Rare"),          # 盗颅盔
    "Demonhide": Equipment("Demonhide", 0, 9, 150, "Epic"),           # 魔皮甲
    "The Centurion": Equipment("The Centurion", 0, 10, 160, "Epic"),  # 百夫长板甲
    "Heaven's Will": Equipment("Heaven's Will", 0, 9, 150, "Epic"),   # 天意甲
    "Harlequin Crest": Equipment("Harlequin Crest", 0, 7, 600, "Legendary"),  # 小丑皇冠(Shako)
}

ENEMIES = {
    # 原有敌人
    "Fallen": Enemy("Fallen", 20, 6, 2, 30, 15, 1),
    "Goatman": Enemy("Goatman", 35, 9, 4, 60, 30, 2, "Rare"),
    "Corrupt Mage": Enemy("Corrupt Mage", 28, 12, 3, 70, 25, 3, "Rare"),
    "Skeleton King": Enemy("Skeleton King", 70, 14, 8, 150, 80, 10, "Epic"),
    # 暗黑经典怪物族群（Animals / Demons / Undead）
    "Skeleton": Enemy("Skeleton", 24, 7, 2, 25, 12, 1),
    "Zombie": Enemy("Zombie", 30, 6, 3, 28, 14, 1),
    "Ghoul": Enemy("Ghoul", 42, 10, 4, 65, 32, 3, "Rare"),
    "Imp": Enemy("Imp", 26, 8, 2, 30, 16, 1),
    "Hellhound": Enemy("Hellhound", 40, 11, 4, 70, 35, 3, "Rare"),
    "Gargoyle": Enemy("Gargoyle", 48, 10, 6, 75, 38, 4, "Rare"),
    "Bone Mage": Enemy("Bone Mage", 34, 13, 3, 80, 30, 4, "Rare"),
    "Fallen Shaman": Enemy("Fallen Shaman", 38, 11, 4, 72, 33, 3, "Rare"),
    "Butcher": Enemy("Butcher", 90, 18, 9, 220, 120, 12, "Epic"),
    "Diablo": Enemy("Diablo", 260, 28, 14, 800, 500, 40, "Legendary"),
}

REGIONS = {
    # 原有区域（保留，维持既有描述键）
    "Forest": ["Fallen", "Fallen", "Goatman"],
    "Graveyard": ["Skeleton King", "Corrupt Mage", "Fallen"],
    "Dungeon": ["Goatman", "Corrupt Mage", "Corrupt Mage"],
    # 暗黑真实地点
    "Tristram": ["Fallen", "Zombie", "Skeleton", "Fallen Shaman"],
    "Catacombs": ["Skeleton", "Ghoul", "Bone Mage", "Skeleton King"],
    "Kurast": ["Zombie", "Imp", "Fallen Shaman", "Corrupt Mage"],
    "Pandemonium": ["Hellhound", "Gargoyle", "Imp", "Bone Mage"],
    "Burning Hells": ["Hellhound", "Imp", "Gargoyle", "Butcher"],
    "Fractured Peaks": ["Goatman", "Fallen", "Fallen Shaman", "Ghoul"],
    # Boss 专属挑战区
    "Hell's Throne": ["Diablo"],
}
