"""国际化：多语言文本字典与名称翻译"""


# 装备/敌人/词缀名称翻译映射
NAME_TRANSLATIONS = {
    # 武器
    "Iron Sword": {"en": "Iron Sword", "zh": "铁剑"},
    "Flame Staff": {"en": "Flame Staff", "zh": "烈焰法杖"},
    "Butcher's Cleaver": {"en": "Butcher's Cleaver", "zh": "屠夫切肉刀"},
    "The Gidbinn": {"en": "The Gidbinn", "zh": "吉德宾匕首"},
    "Rune Master": {"en": "Rune Master", "zh": "符文大师战斧"},
    "The Minotaur": {"en": "The Minotaur", "zh": "牛头人战斧"},
    "Deathbit": {"en": "Deathbit", "zh": "死亡之噬匕首"},
    "Blood Crescent": {"en": "Blood Crescent", "zh": "血色弯刀"},
    "Plague Bearer": {"en": "Plague Bearer", "zh": "瘟疫使者权杖"},
    "Hexfire": {"en": "Hexfire", "zh": "六火魔杖"},
    "Doombringer": {"en": "Doombringer", "zh": "末日使者巨剑"},
    "Wirt's Leg": {"en": "Wirt's Leg", "zh": "维特的腿"},
    # 护甲
    "Leather Armor": {"en": "Leather Armor", "zh": "皮甲"},
    "Chainmail": {"en": "Chainmail", "zh": "锁链甲"},
    "Shadow Cloak": {"en": "Shadow Cloak", "zh": "暗影斗篷"},
    "Greyform": {"en": "Greyform", "zh": "灰铸甲"},
    "Boneweave": {"en": "Boneweave", "zh": "骨织甲"},
    "Stealskull": {"en": "Stealskull", "zh": "盗颅盔"},
    "Demonhide": {"en": "Demonhide", "zh": "魔皮甲"},
    "The Centurion": {"en": "The Centurion", "zh": "百夫长板甲"},
    "Heaven's Will": {"en": "Heaven's Will", "zh": "天意甲"},
    "Harlequin Crest": {"en": "Harlequin Crest", "zh": "小丑皇冠"},
    # 敌人
    "Fallen": {"en": "Fallen", "zh": "堕落者"},
    "Goatman": {"en": "Goatman", "zh": "羊头魔"},
    "Corrupt Mage": {"en": "Corrupt Mage", "zh": "腐化法师"},
    "Skeleton King": {"en": "Skeleton King", "zh": "骷髅王"},
    "Skeleton": {"en": "Skeleton", "zh": "骷髅"},
    "Zombie": {"en": "Zombie", "zh": "僵尸"},
    "Ghoul": {"en": "Ghoul", "zh": "食尸鬼"},
    "Imp": {"en": "Imp", "zh": "小恶魔"},
    "Hellhound": {"en": "Hellhound", "zh": "地狱犬"},
    "Gargoyle": {"en": "Gargoyle", "zh": "石像鬼"},
    "Bone Mage": {"en": "Bone Mage", "zh": "骨法师"},
    "Fallen Shaman": {"en": "Fallen Shaman", "zh": "堕落萨满"},
    "Butcher": {"en": "Butcher", "zh": "屠夫"},
    "Diablo": {"en": "Diablo", "zh": "迪亚波罗"},
    # 词缀
    "Flesh Resilience": {"en": "Flesh Resilience", "zh": "血肉韧性"},
    "Hellish Blade": {"en": "Hellish Blade", "zh": "地狱之刃"},
    "Resource Exhaustion": {"en": "Resource Exhaustion", "zh": "资源枯竭"},
    # 区域
    "Forest": {"en": "Forest", "zh": "森林"},
    "Graveyard": {"en": "Graveyard", "zh": "墓地"},
    "Dungeon": {"en": "Dungeon", "zh": "地下城"},
    "Tristram": {"en": "Tristram", "zh": "崔斯特瑞姆"},
    "Catacombs": {"en": "Catacombs", "zh": "地下墓穴"},
    "Kurast": {"en": "Kurast", "zh": "库拉斯特"},
    "Pandemonium": {"en": "Pandemonium", "zh": "混沌要塞"},
    "Burning Hells": {"en": "Burning Hells", "zh": "燃烧地狱"},
    "Fractured Peaks": {"en": "Fractured Peaks", "zh": "碎裂群峰"},
    "Hell's Throne": {"en": "Hell's Throne", "zh": "地狱王座"},
    # 品质
    "Common": {"en": "Common", "zh": "普通"},
    "Rare": {"en": "Rare", "zh": "稀有"},
    "Epic": {"en": "Epic", "zh": "史诗"},
    "Legendary": {"en": "Legendary", "zh": "传说"},
}


def get_translated_name(name: str, lang: str = "en") -> str:
    """获取翻译后的名称"""
    trans = NAME_TRANSLATIONS.get(name, {})
    return trans.get(lang, name)


# ---------------------------- Language Dictionary ----------------------------
LANG = {
    "en": {
        # Main Menu
        "game_title": "DIABLO",
        "game_subtitle": "CATACLYSM ERA",
        "game_tagline": "Dark Fantasy Action RPG",
        "btn_new_game": "New Game",
        "btn_continue": "Continue",
        "btn_settings": "Settings",
        "btn_exit": "Exit",
        "btn_idle": "Idle / Auto-Play",
        "btn_idle_stop": "Stop Idle",

        # Character Creation
        "create_char_title": "Create Character",
        "create_char_prompt": "Enter character name:",
        "name_required": "Name Required",
        "name_required_msg": "Please enter a character name!",
        "char_created": "Success",
        "char_created_msg": "Character {name} created!",

        # Load Game
        "load_success": "Load Success",
        "load_welcome": "Welcome back, {name}!",
        "no_save": "No Save",
        "no_save_msg": "No save file found. Please start a new game.",

        # Main Hub
        "main_menu": "Main Menu",
        "btn_explore": "Explore World",
        "btn_workshop": "Hell Workshop",
        "btn_status": "Character Status",
        "btn_contract": "Pain Contract",
        "btn_save": "Save Game",
        "btn_return_menu": "Return to Menu",

        # Contract
        "contract_title": "Pain Contract",
        "contract_active": "ACTIVATED",
        "contract_deactivated": "DEACTIVATED",
        "contract_active_msg": "Pain Contract ACTIVATED!\nEnemies +50% stronger, but rewards DOUBLED!",
        "contract_deactivated_msg": "Pain Contract DEACTIVATED!\nEnemies and rewards return to normal.",
        "contract_active_tag": "[PAIN CONTRACT ACTIVE]",

        # Save
        "save_title": "Save",
        "save_success": "Game saved successfully!",

        # Explore
        "explore_title": "Explore World",
        "select_region": "Select Region:",
        "btn_return_main": "Return to Main",
        "btn_return_explore": "Return to Explore",

        # 3D Dungeon
        "dungeon_3d_title": "Dungeon View",
        "dungeon_controls": "Controls:",
        "dungeon_btn_left": "← Left",
        "dungeon_btn_right": "Right →",
        "dungeon_btn_forward": "↑ Forward",
        "dungeon_btn_backward": "↓ Back",
        "btn_enter_battle": "⚔ Enter Battle",
        "btn_exit_dungeon": "← Return to Explore",
        "auto_enter_tip": "Auto-entering battle in 2.5s...",

        # Status & Stats
        "level": "Level",
        "exp_tag": "(EXP:",
        "name_tag": "Name:",

        # Combat
        "battle": "Battle",
        "enemy": "Enemy",
        "player": "Player",
        "atk": "ATK",
        "def": "DEF",
        "hp": "HP",
        "mp": "MP",
        "combat_log": "Combat Log:",
        "btn_attack": "Attack",
        "btn_heavy": "Heavy Strike (5MP)",
        "btn_defend": "Defend",
        "btn_flee_pct": "Flee (50%)",
        "btn_flee": "Flee",
        "btn_return_main_hub": "Return to Main",
        "btn_return_workshop": "Return to Workshop",
        "def_stance": "[Defense Stance - Next damage halved]",
        "you_dealt": "You dealt {dmg} damage. Enemy HP: {hp}",
        "heavy_dealt": "Heavy strike dealt {dmg} damage! Enemy HP: {hp}",
        "not_enough_mp": "Not enough MP!",
        "def_entered": "You enter defense stance. Next damage halved.",
        "flee_success": "Flee successful!",
        "flee_failed": "Flee failed!",
        "def_reduced": "Defense reduced damage! Enemy dealt {dmg} damage.",
        "enemy_attacked": "Enemy counterattacked for {dmg} damage.",
        "victory": "VICTORY! Gained {exp} EXP, {gold} Gold, {soul} Souls.",
        "pain_contract_bonus": "[PAIN CONTRACT] Rewards DOUBLED!",
        "level_up": "LEVEL UP! Now Level {level}!",
        "level_up_stats": "HP+10 MP+5 ATK+2 DEF+2",
        "equip_obtained": "Equipment obtained: {name} (Quality: {quality})",

        # Equipment Dialog
        "new_equip_title": "New Equipment",
        "new_equip_header": "New Equipment!",
        "quality": "Quality",
        "btn_equip_weapon": "Equip as Weapon",
        "btn_equip_armor": "Equip as Armor",
        "btn_discard": "Discard",
        "equipped_weapon": "Weapon equipped: {name}",
        "equipped_armor": "Armor equipped: {name}",
        "discarded": "Discarded equipment.",

        # Defeat
        "defeat_title": "Defeat",
        "defeat_msg": "You have fallen! Game Over.",

        # Status
        "status_title": "Character Status",
        "basic_info": "=== Basic Info ===",
        "attributes": "=== Attributes ===",
        "equipment": "=== Equipment ===",
        "resources": "=== Resources ===",
        "weapon": "Weapon",
        "armor": "Armor",
        "gold": "Gold",
        "souls": "Souls",
        "pain_contract": "Pain Contract",
        "contract_active_st": "Active",
        "contract_inactive": "Inactive",
        "none": "None",
        "base": "Base",
        "weapon_bonus": "Weapon",
        "armor_bonus": "Armor",
        "soul": "Soul",

        # Hell Workshop
        "workshop_title": "Hell Workshop",
        "current_souls": "Current Souls: {souls}",
        "not_enough_souls": "Not enough Souls! Need at least 10 souls.",
        "earn_more": "Defeat monsters or complete challenges to earn more.",
        "btn_back": "Back",
        "create_challenge": "=== Create Custom Challenge ===",
        "map_name_label": "Map Name:",
        "map_default": "Unnamed Trial",
        "difficulty_label": "Difficulty (1-5):",
        "select_affixes": "Select Affixes (Multiple allowed):",
        "cost_label": "Estimated Cost: {cost} souls",
        "btn_start_challenge": "Start Challenge",
        "not_enough_souls_warn": "Not Enough Souls",
        "need_souls_msg": "Need {need} souls, you have {have}.",
        "entering": "Entering: {name}",
        "difficulty_affixes": "Difficulty: {diff} | Affixes: {affixes}",
        "affix_exhaustion": "[Affix] Resource Exhaustion: No MP recovery in combat",
        "challenge_complete": "Challenge Complete! Gained {souls} souls!",
        "bonus_reward": "Bonus reward: {name} (Quality: {quality})",
        "challenge_success": "Challenge Success",
        "challenge_success_msg": "Congratulations! Gained {souls} souls!",
        "challenge_reward_title": "Bonus Reward",
        "challenge_reward_header": "Challenge Reward!",
        "challenge_failed": "Challenge Failed",
        "challenge_failed_msg": "Challenge failed, souls not refunded.\nTry again!",
        "recovered_mp": "Recovered {mp} MP.",
        "exhaustion_active": "[Resource Exhaustion - No MP recovery]",
        "boss": "BOSS",
        "challenger": "Challenger",

        # Settings
        "settings_title": "Settings",
        "game_settings": "=== Game Settings ===",
        "show_tips": "Show Tips & Hints",
        "auto_save": "Auto-Save on Exit",
        "idle_speed": "Idle Speed",
        "idle_fast": "Fast",
        "idle_normal": "Normal",
        "idle_slow": "Slow",
        "language": "Language",
        "english": "English",
        "chinese": "Chinese",
        "about": "=== About ===",
        "about_title": "Diablo: Cataclysm Era",
        "version": "Version 1.0",
        "about_desc": "A Dark Fantasy Action RPG",

        # Exit
        "exit_title": "Exit",
        "exit_msg": "Are you sure you want to exit the game?",

        # Loading
        "loading_title": "Loading",
        "loading_tip": "Loading game assets...",

        # Tips
        "tip_explore": "Explore different regions to find better equipment!",
        "tip_contract": "Pain Contract doubles rewards but makes enemies stronger.",
        "tip_workshop": "Hell Workshop offers challenging custom battles.",

        # 区域描述
        "region_forest": "Enemies: Fallen, Goatman",
        "region_graveyard": "Enemies: Skeleton King, Corrupt Mage, Fallen",
        "region_dungeon": "Enemies: Goatman, Corrupt Mage",
        "region_tristram": "Enemies: Fallen, Zombie, Skeleton, Fallen Shaman",
        "region_catacombs": "Enemies: Skeleton, Ghoul, Bone Mage, Skeleton King",
        "region_kurast": "Enemies: Zombie, Imp, Fallen Shaman, Corrupt Mage",
        "region_pandemonium": "Enemies: Hellhound, Gargoyle, Imp, Bone Mage",
        "region_burning_hells": "Enemies: Hellhound, Imp, Gargoyle, Butcher",
        "region_fractured_peaks": "Enemies: Goatman, Fallen, Fallen Shaman, Ghoul",
        "region_hells_throne": "Enemies: Diablo (Final Boss)",
        "region_enemies": "Enemies:",

        # 词缀
        "affix_flesh": "Enemy HP +50%",
        "affix_hellish": "Enemy ATK +30%",
        "affix_exhaustion_desc": "No MP recovery",
        "affixes_label": "Affixes:",

        # 地下城
        "dungeon_pos": "Pos",
        "dungeon_facing": "Facing",
    },
    "zh": {
        # Main Menu
        "game_title": "暗黑破坏神",
        "game_subtitle": "灾厄纪元",
        "game_tagline": "暗黑奇幻动作RPG",
        "btn_new_game": "新游戏",
        "btn_continue": "继续游戏",
        "btn_settings": "设置",
        "btn_exit": "退出",
        "btn_idle": "托管挂机",
        "btn_idle_stop": "停止托管",

        # Character Creation
        "create_char_title": "创建角色",
        "create_char_prompt": "请输入角色名称：",
        "name_required": "需要名称",
        "name_required_msg": "请输入角色名称！",
        "char_created": "创建成功",
        "char_created_msg": "角色 {name} 创建成功！",

        # Load Game
        "load_success": "读取成功",
        "load_welcome": "欢迎回来，{name}！",
        "no_save": "没有存档",
        "no_save_msg": "未找到存档文件，请开始新游戏。",

        # Main Hub
        "main_menu": "主菜单",
        "btn_explore": "探索世界",
        "btn_workshop": "地狱工坊",
        "btn_status": "角色状态",
        "btn_contract": "痛苦契约",
        "btn_save": "保存游戏",
        "btn_return_menu": "返回主菜单",

        # Contract
        "contract_title": "痛苦契约",
        "contract_active": "已激活",
        "contract_deactivated": "已关闭",
        "contract_active_msg": "痛苦契约已激活！\n敌人强度+50%，但奖励翻倍！",
        "contract_deactivated_msg": "痛苦契约已关闭！\n敌人强度和奖励恢复正常。",
        "contract_active_tag": "【痛苦契约已激活】",

        # Save
        "save_title": "保存",
        "save_success": "游戏保存成功！",

        # Explore
        "explore_title": "探索世界",
        "select_region": "选择区域：",
        "btn_return_main": "返回主菜单",
        "btn_return_explore": "返回探索",

        # 3D Dungeon
        "dungeon_3d_title": "地下城视图",
        "dungeon_controls": "控制：",
        "dungeon_btn_left": "← 左转",
        "dungeon_btn_right": "右转 →",
        "dungeon_btn_forward": "↑ 前进",
        "dungeon_btn_backward": "↓ 后退",
        "btn_enter_battle": "⚔ 进入战斗",
        "btn_exit_dungeon": "← 返回探索",
        "auto_enter_tip": "2.5秒后自动进入战斗...",

        # Status & Stats
        "level": "等级",
        "exp_tag": "(经验：",
        "name_tag": "名称：",

        # Combat
        "battle": "战斗",
        "enemy": "敌人",
        "player": "玩家",
        "atk": "攻击",
        "def": "防御",
        "hp": "生命",
        "mp": "魔法",
        "combat_log": "战斗日志：",
        "btn_attack": "攻击",
        "btn_heavy": "重击 (5MP)",
        "btn_defend": "防御",
        "btn_flee_pct": "逃跑 (50%)",
        "btn_flee": "逃跑",
        "btn_return_main_hub": "返回主界面",
        "btn_return_workshop": "返回工坊",
        "def_stance": "【防御姿态 - 下次伤害减半】",
        "you_dealt": "你造成了 {dmg} 点伤害。敌人HP：{hp}",
        "heavy_dealt": "重击造成 {dmg} 点伤害！敌人HP：{hp}",
        "not_enough_mp": "魔法值不足！",
        "def_entered": "你进入防御姿态，下次伤害减半。",
        "flee_success": "逃跑成功！",
        "flee_failed": "逃跑失败！",
        "def_reduced": "防御减少伤害！敌人造成 {dmg} 点伤害。",
        "enemy_attacked": "敌人反击，造成 {dmg} 点伤害。",
        "victory": "胜利！获得 {exp} 经验、{gold} 金币、{soul} 魂。",
        "pain_contract_bonus": "【痛苦契约】奖励翻倍！",
        "level_up": "升级！当前等级 {level}！",
        "level_up_stats": "生命+10 魔法+5 攻击+2 防御+2",
        "equip_obtained": "获得装备：{name}（品质：{quality}）",

        # Equipment Dialog
        "new_equip_title": "新装备",
        "new_equip_header": "获得新装备！",
        "quality": "品质",
        "btn_equip_weapon": "装备为武器",
        "btn_equip_armor": "装备为护甲",
        "btn_discard": "丢弃",
        "equipped_weapon": "已装备武器：{name}",
        "equipped_armor": "已装备护甲：{name}",
        "discarded": "已丢弃装备。",

        # Defeat
        "defeat_title": "战败",
        "defeat_msg": "你倒下了！游戏结束。",

        # Status
        "status_title": "角色状态",
        "basic_info": "=== 基本信息 ===",
        "attributes": "=== 属性 ===",
        "equipment": "=== 装备 ===",
        "resources": "=== 资源 ===",
        "weapon": "武器",
        "armor": "护甲",
        "gold": "金币",
        "souls": "魂",
        "pain_contract": "痛苦契约",
        "contract_active_st": "已激活",
        "contract_inactive": "未激活",
        "none": "无",
        "base": "基础",
        "weapon_bonus": "武器",
        "armor_bonus": "护甲",
        "soul": "魂",

        # Hell Workshop
        "workshop_title": "地狱工坊",
        "current_souls": "当前魂数：{souls}",
        "not_enough_souls": "魂不足！至少需要10点魂。",
        "earn_more": "击败怪物或完成任务来获取更多魂。",
        "btn_back": "返回",
        "create_challenge": "=== 创建自定义挑战 ===",
        "map_name_label": "地图名称：",
        "map_default": "无名试炼",
        "difficulty_label": "难度 (1-5)：",
        "select_affixes": "选择词缀（可多选）：",
        "cost_label": "预计消耗：{cost} 魂",
        "btn_start_challenge": "开始挑战",
        "not_enough_souls_warn": "魂不足",
        "need_souls_msg": "需要 {need} 魂，你只有 {have} 魂。",
        "entering": "进入：{name}",
        "difficulty_affixes": "难度：{diff} | 词缀：{affixes}",
        "affix_exhaustion": "【词缀】资源枯竭：战斗中无法恢复魔法",
        "challenge_complete": "挑战完成！获得 {souls} 魂！",
        "bonus_reward": "额外奖励：{name}（品质：{quality}）",
        "challenge_success": "挑战成功",
        "challenge_success_msg": "恭喜！获得 {souls} 魂！",
        "challenge_reward_title": "额外奖励",
        "challenge_reward_header": "挑战奖励！",
        "challenge_failed": "挑战失败",
        "challenge_failed_msg": "挑战失败，魂不予退还。\n请再试一次！",
        "recovered_mp": "恢复了 {mp} 点魔法。",
        "exhaustion_active": "【资源枯竭 - 无法恢复魔法】",
        "boss": "首领",
        "challenger": "挑战者",

        # Settings
        "settings_title": "设置",
        "game_settings": "=== 游戏设置 ===",
        "show_tips": "显示提示与技巧",
        "auto_save": "退出时自动保存",
        "idle_speed": "挂机速度",
        "idle_fast": "极速",
        "idle_normal": "标准",
        "idle_slow": "慢速",
        "language": "语言",
        "english": "英语",
        "chinese": "中文",
        "about": "=== 关于 ===",
        "about_title": "暗黑破坏神：灾厄纪元",
        "version": "版本 1.0",
        "about_desc": "一款暗黑奇幻动作RPG游戏",

        # Exit
        "exit_title": "退出",
        "exit_msg": "确定要退出游戏吗？",

        # Loading
        "loading_title": "加载中",
        "loading_tip": "正在加载游戏资源...",

        # Tips
        "tip_explore": "探索不同区域可以找到更好的装备！",
        "tip_contract": "痛苦契约可获得双倍奖励，但敌人也会更强。",
        "tip_workshop": "地狱工坊提供具有挑战性的自定义战斗。",

        # 区域描述
        "region_forest": "敌人：堕落者、羊头魔",
        "region_graveyard": "敌人：骷髅王、腐化法师、堕落者",
        "region_dungeon": "敌人：羊头魔、腐化法师",
        "region_tristram": "敌人：堕落者、僵尸、骷髅、堕落萨满",
        "region_catacombs": "敌人：骷髅、食尸鬼、骨法师、骷髅王",
        "region_kurast": "敌人：僵尸、小恶魔、堕落萨满、腐化法师",
        "region_pandemonium": "敌人：地狱犬、石像鬼、小恶魔、骨法师",
        "region_burning_hells": "敌人：地狱犬、小恶魔、石像鬼、屠夫",
        "region_fractured_peaks": "敌人：羊头魔、堕落者、堕落萨满、食尸鬼",
        "region_hells_throne": "敌人：迪亚波罗（最终首领）",
        "region_enemies": "敌人：",

        # 词缀
        "affix_flesh": "敌人生命+50%",
        "affix_hellish": "敌人攻击+30%",
        "affix_exhaustion_desc": "无法恢复魔法",
        "affixes_label": "词缀：",

        # 地下城
        "dungeon_pos": "位置",
        "dungeon_facing": "朝向",
    }
}
