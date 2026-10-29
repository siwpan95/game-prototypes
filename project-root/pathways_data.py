# pathways_data.py
# 诡秘之主 22条神之途径 完整数据
# 基于亵渎石板与博客园 Sakura-Lu 整理

# ============================================================
# 途径组定义
# ============================================================
PATHWAY_GROUPS = {
    "eternal_darkness": {
        "name": "永恒之暗、万物奇点、时空归一者",
        "source_quality": "永暗之河+灾祸之城",
        "source": "最初造物主",
        "pathways": ["darkness", "eternal_sleeper", "dusk_giant"],
        "interchange_at": 4,
        "description": "序列4及以后可在三条途径间互换；黑暗途径半神可转至混沌魔女途径",
    },
    "god_almighty": {
        "name": "上帝、创造者、造物主、全知全能者、星界之主",
        "source_quality": "混沌海",
        "source": "最初造物主",
        "pathways": ["tyrant", "hanged_man", "visionary", "white_tower", "sun"],
        "interchange_at": 4,
        "description": "序列4及以后可在五条途径间互换",
    },
    "demon_father": {
        "name": "恶魔之父、异类之主、诅咒之源",
        "source_quality": "暗影世界",
        "source": "欲望母树",
        "pathways": ["bound_one", "abyss"],
        "interchange_at": 4,
        "description": "序列4及以后可在两条途径间互换",
    },
    "knowledge_demon": {
        "name": "知识之妖、疯狂奥秘",
        "source_quality": "知识荒野",
        "source": "最初造物主",
        "pathways": ["hermit", "paragon"],
        "interchange_at": 4,
        "description": "序列4及以后可在两条途径间互换",
    },
    "lord_of_mysteries": {
        "name": "诡秘之主、时空之王、命运道标、源堡化身、灵界支配者",
        "source_quality": "源堡",
        "source": "最初造物主",
        "pathways": ["fool", "error", "door"],
        "interchange_at": 3,
        "description": "序列3及以后可在三条途径间互换（低位权柄在序列4质变，故序列3才能转换）",
    },
    "root_god": {
        "name": "根源之神、万物之母、污秽的母巢",
        "source_quality": "母巢",
        "source": "堕落母神",
        "pathways": ["mother", "moon"],
        "interchange_at": 4,
        "description": "序列4及以后可在两条途径间互换",
    },
    "disorder": {
        "name": "失序者、秩序阴影",
        "source_quality": "失序之国",
        "source": "混沌之子",
        "pathways": ["judge", "black_emperor"],
        "interchange_at": 4,
        "description": "序列4及以后可在两条途径间互换",
    },
    "destruction": {
        "name": "毁灭天灾、根源之祸",
        "source_quality": "灾祸之城",
        "source": "最初造物主",
        "pathways": ["red_priest", "chaos_witch"],
        "interchange_at": 4,
        "description": "序列4及以后可在两条途径间互换；象征最初造物主的阴阳两面",
    },
    "key_of_light": {
        "name": "光之钥、无尽的混乱、命运化身",
        "source_quality": "光之钥",
        "source": "最初造物主",
        "pathways": ["wheel_of_fortune"],
        "interchange_at": None,
        "description": "完全独立的途径，就像命运一样不属于任何逻辑范畴",
    },
}

# ============================================================
# 序列等级划分常量
# ============================================================
LOW_SEQUENCE = (9, 8)       # 低序列
MID_SEQUENCE = (7, 6, 5)    # 中序列
HIGH_SEQUENCE = (4, 3)      # 高序列/圣者
ANGEL = (2, 1)              # 天使
TRUE_GOD = (0,)             # 真神

# 仪式起始等级：序列5起需要仪式
RITUAL_START_LEVEL = 5
# 序列0晋升必须：唯一性 + 全部序列1非凡特性
GOD_REQUIREMENTS = "唯一性 + 本途径全部三份序列1非凡特性"

# ============================================================
# 魔药材料池（E1：扮演法 + 魔药晋升的核心资源）
# 每条途径一组主题化材料；get_potion_formula 据此推导各序列配方。
# ============================================================
DEFAULT_MATERIALS = ["灵性之血", "星界之尘", "虚幻之纱", "扭曲符文", "幻梦棱镜"]

POTION_MATERIALS = {
    "darkness":         ["不眠者的眼瞳", "永夜之露", "阴影丝线", "沉眠之尘", "夜枭之羽"],
    "eternal_sleeper":  ["亡者安魂曲", "苍白面具", "冥河之水", "寂静之骨", "梦境残片"],
    "dusk_giant":       ["落日余烬", "巨人指骨", "黄昏之血", "战鼓兽皮", "崩裂大地"],
    "tyrant":           ["雷暴核心", "海神之鳞", "风暴之眼", "王者冠冕碎片", "怒涛结晶"],
    "hanged_man":       ["倒吊人圣痕", "牺牲之泪", "荆棘之冠", "苦难之盐", "救赎之光"],
    "visionary":        ["架空现实之沙", "灵性虹光", "幻梦棱镜", "创造者之笔", "奇迹余烬"],
    "white_tower":      ["知识水晶", "智慧之书页", "符文石板", "真理之钥", "学者之血"],
    "sun":              ["永恒烈阳之火", "光明圣油", "正午之尘", "圣徽碎片", "净化之光"],
    "bound_one":        ["锁链之灵", "契约之血", "禁锢符印", "怨灵丝", "束缚之茧"],
    "abyss":            ["堕落之核", "深渊低语", "恶魔之角", "原罪之尘", "混沌之血"],
    "hermit":           ["隐秘之雾", "孤独之星", "知识之果", "远古符文", "星空碎片"],
    "paragon":          ["完美齿轮", "工匠之锤", "源质合金", "奇迹零件", "创造火花"],
    "fool":             ["源堡之尘", "诡秘之雾", "命运之线", "愚者面具", "巧合之羽"],
    "error":            ["谬误之种", "扭曲符文", "虚幻之纱", "错误之血", "混乱之核"],
    "door":             ["灵界钥匙", "空间之楔", "门后之风", "传送之尘", "维度碎片"],
    "mother":           ["生命之种", "丰饶之壤", "母性之泪", "万物之血", "孕育之果"],
    "moon":             ["月华之露", "银月之鳞", "潮汐之珠", "美神之泪", "幻月碎片"],
    "judge":            ["正义之秤", "律法之书", "审判之剑", "罪罚之印", "秩序之光"],
    "black_emperor":    ["皇帝玉玺", "律令金卷", "权柄之冠", "秩序结晶", "征服之旗"],
    "red_priest":       ["战争之血", "烈焰之芯", "征服之旗", "兵燹之尘", "红祭之刃"],
    "chaos_witch":      ["混沌之蜜", "变形之茧", "魔女之泪", "欲望之花", "原初之雾"],
    "wheel_of_fortune": ["命运之骰", "幸运之羽", "概率之尘", "轮回之环", "混沌之币"],
}

# ============================================================
# 22条途径完整序列数据
# 格式: { 途径key: { name, tarot, group, gender_change, sequences: [...] } }
# 每个序列: { level, name, abilities, required_actions, ritual, curse, special }
# ============================================================

PATHWAYS = {}

# -------------------------------------------------------
# 权柄体系一：永恒之暗（永暗之河+灾祸之城）
# -------------------------------------------------------

PATHWAYS["darkness"] = {
    "name": "黑暗",
    "tarot": "星星",
    "group": "eternal_darkness",
    "gender_change": [],
    "sequences": [
        {
            "level": 9, "name": "不眠者",
            "abilities": ["夜视", "短眠", "黑夜增益", "黑暗感知"],
            "required_actions": ["守夜", "在黑暗中活动", "感知危险"],
        },
        {
            "level": 8, "name": "午夜诗人",
            "abilities": ["格斗精通", "射击精通", "攀爬感应", "诗篇影响"],
            "required_actions": ["吟诵诗篇", "夜间战斗", "感应生灵"],
        },
        {
            "level": 7, "name": "梦魇",
            "abilities": ["入梦", "控梦", "现实梦境交织"],
            "required_actions": ["进入他人梦境", "操控梦境走向"],
        },
        {
            "level": 6, "name": "安魂师",
            "abilities": ["强制安眠", "精神安抚", "欲望压制"],
            "required_actions": ["使人安眠", "安抚精神", "降低欲望"],
        },
        {
            "level": 5, "name": "灵巫",
            "abilities": ["封印灵体", "驱使自然灵", "辨识灵体", "灵性爆发"],
            "required_actions": ["封印灵体", "驱使灵作战"],
            "ritual": "在灵界边缘封印一只强大的灵，作为自己的第一个牙齿封印",
        },
        {
            "level": 4, "name": "守夜人",
            "abilities": ["厄难施加", "顽强生命", "黑暗行走"],
            "required_actions": ["守望黑夜", "抵御厄难"],
            "ritual": "在连续七个无月之夜守护一处圣地不被污染",
        },
        {
            "level": 3, "name": "恐惧主教",
            "abilities": ["安眠权柄", "恐惧掌控", "无声毁灭"],
            "required_actions": ["制造恐惧", "无声消灭"],
            "ritual": "在一座城市中让至少千人同时陷入对黑暗的恐惧，再以安眠结束",
        },
        {
            "level": 2, "name": "隐秘之仆",
            "abilities": ["隐秘实体", "隐秘精神", "隐秘概念"],
            "required_actions": ["隐藏真相", "抹去痕迹"],
            "ritual": "将一件天使级事物成功隐秘一千年（可借助历史孔隙加速）",
        },
        {
            "level": 1, "name": "厄难骑士",
            "abilities": ["厄难驾驭", "黑暗骑士化"],
            "required_actions": ["带来厄难", "收割厄运"],
            "ritual": "骑乘神话生物形态穿越灵界七大厄难之地",
        },
        {
            "level": 0, "name": "黑暗",
            "abilities": ["黑暗权柄", "隐秘领域", "厄难主宰"],
            "required_actions": ["成为黑暗的化身"],
            "ritual": "在永暗之河中沐浴，集齐黑暗唯一性与厄难骑士非凡特性",
        },
    ],
}

PATHWAYS["eternal_sleeper"] = {
    "name": "永眠者",
    "tarot": "死神",
    "group": "eternal_darkness",
    "gender_change": [],
    "sequences": [
        {
            "level": 9, "name": "收尸人",
            "abilities": ["亡灵亲和", "寒冷忍耐", "腐烂抵御", "灵视恶灵"],
            "required_actions": ["收殓尸体", "与亡灵相处"],
        },
        {
            "level": 8, "name": "掘墓人",
            "abilities": ["灵界行走", "死灵国度感知", "节点寻觅"],
            "required_actions": ["掘墓", "寻觅灵界节点"],
        },
        {
            "level": 7, "name": "通灵者",
            "abilities": ["通灵术", "灵体沟通", "亡灵召唤"],
            "required_actions": ["与灵沟通", "主持通灵仪式"],
        },
        {
            "level": 6, "name": "死灵导师",
            "abilities": ["灵界沟通", "信使招募", "亡者之语"],
            "required_actions": ["招募信使", "使用亡者之语"],
        },
        {
            "level": 5, "name": "看门人",
            "abilities": ["冥界感应", "青铜大门召唤", "灵体囚禁"],
            "required_actions": ["守护冥界入口", "囚禁灵体"],
            "ritual": "在冥界入口守候三十个日夜，见证一次大规模死亡事件",
        },
        {
            "level": 4, "name": "不死者",
            "abilities": ["六十轮回", "死而复生", "能力大幅增强"],
            "required_actions": ["经历一次死亡", "从死亡中归来"],
            "ritual": "在六十年周期结束时，于三天内历经三种不同的死亡方式并复生",
            "special": "每六十年死去、复活并失忆一次",
        },
        {
            "level": 3, "name": "摆渡人",
            "abilities": ["冥河之力", "死亡引导", "灵体摆渡"],
            "required_actions": ["摆渡灵魂", "引导死亡"],
            "ritual": "在冥界之河上摆渡一万个灵魂",
        },
        {
            "level": 2, "name": "死亡执政官",
            "abilities": ["死亡审判", "灵魂裁决"],
            "required_actions": ["审判亡者", "执掌死亡"],
            "ritual": "审判一位天使级存在的死亡",
        },
        {
            "level": 1, "name": "苍白皇帝",
            "abilities": ["苍白领域", "亡者帝国"],
            "required_actions": ["建立亡者之国", "苍白统治"],
            "ritual": "在灵界建立一处属于自己的亡者国度",
        },
        {
            "level": 0, "name": "永眠者",
            "abilities": ["永眠权柄", "死亡终结", "冥界主宰"],
            "required_actions": ["成为死亡的终点"],
            "ritual": "集齐永眠者唯一性与苍白皇帝非凡特性",
        },
    ],
}

PATHWAYS["dusk_giant"] = {
    "name": "黄昏巨人",
    "tarot": "力量",
    "group": "eternal_darkness",
    "gender_change": [],
    "sequences": [
        {
            "level": 9, "name": "战士",
            "abilities": ["超越力量", "超越敏捷", "全武器精通"],
            "required_actions": ["刻苦训练", "掌握多种武器"],
        },
        {
            "level": 8, "name": "格斗家",
            "abilities": ["格斗大师", "超凡抵抗", "体质增强"],
            "required_actions": ["格斗训练", "对抗超凡力量"],
        },
        {
            "level": 7, "name": "武器大师",
            "abilities": ["超凡武器精通", "封印物操控", "负面抵抗"],
            "required_actions": ["使用封印物", "掌握非凡武器"],
        },
        {
            "level": 6, "name": "黎明骑士",
            "abilities": ["巨人力量", "晨曦领域", "黎明铠甲", "晨曦巨剑", "光之风暴"],
            "required_actions": ["在黎明时战斗", "净化黑暗生物"],
        },
        {
            "level": 5, "name": "守护者",
            "abilities": ["铁壁防御", "伤害承担", "晨曦净化", "幻觉免疫"],
            "required_actions": ["守护同伴", "承受伤害"],
            "ritual": "在战斗中守护至少十位同伴，独自承受一次致命攻击而不死",
        },
        {
            "level": 4, "name": "猎魔人",
            "abilities": ["意图掩饰", "占卜干扰", "精神力强化", "猎魔之眼", "神圣制作"],
            "required_actions": ["猎杀恶魔", "辨识怪物", "制作圣物"],
            "ritual": "猎杀一只完整的恶魔（序列6及以上），用其非凡特性制作圣膏",
        },
        {
            "level": 3, "name": "银骑士",
            "abilities": ["银白铠甲", "光中隐藏", "晨曦巨剑强化", "银白细剑", "水银化"],
            "required_actions": ["猎杀六种强大生物", "在神灵祝福下晋升"],
            "ritual": "猎杀六种不同强大生物，在神灵祝福下被强大生物遗骸包围服食魔药",
        },
        {
            "level": 2, "name": "荣耀者",
            "abilities": ["荣耀领域", "战争光环"],
            "required_actions": ["获得荣耀", "传播威名"],
            "ritual": "在一场改变王国命运的战争中取得决定性荣耀",
        },
        {
            "level": 1, "name": "神明之手",
            "abilities": ["神之手", "裁决之力"],
            "required_actions": ["执行神之意志"],
            "ritual": "代替神灵之手完成一场审判",
        },
        {
            "level": 0, "name": "黄昏巨人",
            "abilities": ["黄昏权柄", "巨人真身", "力量主宰"],
            "required_actions": ["见证黄昏", "引领终末"],
            "ritual": "在真正的黄昏中集齐黄昏巨人唯一性与神明之手非凡特性",
        },
    ],
}

# -------------------------------------------------------
# 权柄体系二：上帝（混沌海）
# -------------------------------------------------------

PATHWAYS["tyrant"] = {
    "name": "暴君",
    "tarot": "教皇",
    "group": "god_almighty",
    "gender_change": [],
    "sequences": [
        {
            "level": 9, "name": "水手",
            "abilities": ["完美平衡", "水下力量", "潜水能力"],
            "required_actions": ["海上航行", "水下活动"],
        },
        {
            "level": 8, "name": "暴怒之民",
            "abilities": ["愤怒爆发", "力量暴涨", "速度暴涨"],
            "required_actions": ["在愤怒中战斗", "暴风雨中行动"],
        },
        {
            "level": 7, "name": "航海家",
            "abilities": ["天文地理", "磁场感应", "洋流直觉", "水域法术"],
            "required_actions": ["远洋航行", "感知天象", "施展水域法术"],
        },
        {
            "level": 6, "name": "风眷者",
            "abilities": ["御风飞行", "风刃切割", "气旋操控"],
            "required_actions": ["御风而行", "制造风暴"],
        },
        {
            "level": 5, "name": "海洋歌者",
            "abilities": ["歌声干扰", "歌声增幅", "灵性吟唱"],
            "required_actions": ["在海上歌唱", "用歌声影响他人"],
            "ritual": "在暴风雨中的孤舟上连续歌唱三天三夜，引来海洋生物环绕",
        },
        {
            "level": 4, "name": "灾难主祭",
            "abilities": ["龙卷风", "自然灾害", "前置能力大幅强化"],
            "required_actions": ["制造灾难", "主持祭祀"],
            "ritual": "在一场海上灾难中存活并吸收灾难的残余力量",
        },
        {
            "level": 3, "name": "海王",
            "abilities": ["海域支配", "海底行走", "海啸掀起", "海洋生物支配"],
            "required_actions": ["支配一片海域", "号令海洋生物"],
            "ritual": "在深海最深处与一只海怪之王搏斗并胜出，掌控一片海域",
        },
        {
            "level": 2, "name": "天灾",
            "abilities": ["天灾领域", "毁灭风暴"],
            "required_actions": ["制造天灾", "毁灭岛屿"],
            "ritual": "用一场风暴摧毁一座被诅咒的岛屿及其上的一切",
        },
        {
            "level": 1, "name": "雷神",
            "abilities": ["雷电权柄", "电流化身", "光速移动"],
            "required_actions": ["驾驭雷电", "成为风暴"],
            "ritual": "在雷暴中心被闪电击中而不死，吸收雷霆之力",
        },
        {
            "level": 0, "name": "暴君",
            "abilities": ["电流光速化", "星球级灾难", "暴君权柄"],
            "required_actions": ["获得数以十万计信徒", "挑战其他序列0"],
            "ritual": "拥有数以十万计因恐惧而服从的信徒，单独挑战别的序列0并成功存活",
        },
    ],
}

PATHWAYS["hanged_man"] = {
    "name": "倒吊人",
    "tarot": "倒吊人",
    "group": "god_almighty",
    "gender_change": [],
    "sequences": [
        {
            "level": 9, "name": "秘祈人",
            "abilities": ["灵感高涨", "神秘感知", "祭祀知识", "仪式魔法"],
            "required_actions": ["向隐秘存在祈祷", "主持祭祀仪式"],
        },
        {
            "level": 8, "name": "倾听者",
            "abilities": ["隐秘耳语", "扭曲能力", "独特力量"],
            "required_actions": ["倾听隐秘存在的声音", "承受耳语"],
            "special": "若无法晋升，很难存活超过五年",
        },
        {
            "level": 7, "name": "隐修士",
            "abilities": ["阴影藏匿", "阴影移动", "高恢复能力"],
            "required_actions": ["隐修苦行", "在阴影中生存"],
        },
        {
            "level": 6, "name": "蔷薇主教",
            "abilities": ["血肉魔法", "体内寄生", "血肉吞噬"],
            "required_actions": ["操控血肉", "补充血肉"],
        },
        {
            "level": 5, "name": "牧羊人",
            "abilities": ["灵魂吞噬", "放牧灵魂", "七魂驱使"],
            "required_actions": ["吞噬灵魂", "放牧怨魂"],
            "ritual": "吞噬七个不同序列非凡者的灵魂，完成一次完整的放牧循环",
        },
        {
            "level": 4, "name": "黑骑士",
            "abilities": ["黑骑士变身", "血肉重组", "放牧外放", "阴影统御", "堕落影分身"],
            "required_actions": ["化身为黑骑士", "统御黑暗"],
            "ritual": "在午夜时分以骑士之礼斩杀一位同序列的敌人",
        },
        {
            "level": 3, "name": "三首圣堂",
            "abilities": ["三首并行", "阴暗催化", "阴影替身"],
            "required_actions": ["催化阴暗面", "三重施法"],
            "ritual": "催化三个不同敌人的阴暗面使其独立并分别击败它们",
        },
        {
            "level": 2, "name": "秽语长老",
            "abilities": ["语言漏洞催化", "阴暗独立", "秽语诅咒"],
            "required_actions": ["发现语言漏洞", "催化分裂"],
            "ritual": "让一位圣者的阴暗面独立并将其击败吸收",
        },
        {
            "level": 1, "name": "暗天使",
            "abilities": ["暗之天使", "堕落之翼"],
            "required_actions": ["拥抱堕落", "成为暗之化身"],
            "ritual": "在堕落领域中与一位天使级存在完成黑暗契约",
        },
        {
            "level": 0, "name": "倒吊人",
            "abilities": ["堕落领域", "阴暗主宰"],
            "required_actions": ["成为堕落的象征"],
            "ritual": "集齐倒吊人唯一性与暗天使非凡特性",
        },
    ],
}

PATHWAYS["visionary"] = {
    "name": "空想家",
    "tarot": "正义",
    "group": "god_almighty",
    "gender_change": [],
    "sequences": [
        {
            "level": 9, "name": "观众",
            "abilities": ["敏锐观察", "表情解读", "举止分析"],
            "required_actions": ["观察他人", "分析行为"],
        },
        {
            "level": 8, "name": "读心者",
            "abilities": ["以太体观察", "念头读取", "人心掌握"],
            "required_actions": ["读取念头", "观察以太体"],
        },
        {
            "level": 7, "name": "心理医生",
            "abilities": ["读心", "心理暗示", "精神安抚", "龙威震慑"],
            "required_actions": ["治疗心理问题", "施加心理暗示"],
        },
        {
            "level": 6, "name": "催眠师",
            "abilities": ["鳞片防御", "心智修改", "战斗催眠", "心理学隐身"],
            "required_actions": ["催眠目标", "修改心智"],
        },
        {
            "level": 5, "name": "梦境行者",
            "abilities": ["入梦", "梦境引导", "梦境修改"],
            "required_actions": ["进入梦境", "操控梦境"],
            "ritual": "在一千个人的梦境中留下自己的足迹而不被察觉",
        },
        {
            "level": 4, "name": "操纵师",
            "abilities": ["心灵岛屿修改", "精神瘟疫", "失控增幅", "虚拟人格"],
            "required_actions": ["操纵心智", "制造精神瘟疫"],
            "ritual": "通过集体潜意识大海修改一个人的完整心灵岛屿结构",
        },
        {
            "level": 3, "name": "织梦者",
            "abilities": ["以假乱真梦境", "虚拟人格分离", "梦中复生"],
            "required_actions": ["编织梦境", "分离虚拟人格"],
            "ritual": "编织一个能让圣者迷失其中至少一年的虚拟梦境",
        },
        {
            "level": 2, "name": "洞察者",
            "abilities": ["思维感知", "范围读心", "文字关联感知"],
            "required_actions": ["洞察一切", "感知思维"],
            "ritual": "同时感知一万个人的即时思维内容",
        },
        {
            "level": 1, "name": "作家",
            "abilities": ["巧合制造", "命运编排", "叙事之力"],
            "required_actions": ["编排巧合", "书写命运"],
            "ritual": "通过叙事之力让一座城市的所有居民按照自己编排的巧合生活一年",
        },
        {
            "level": 0, "name": "空想家",
            "abilities": ["空想具现", "虚拟分身", "意识复生"],
            "required_actions": ["成为现实的编织者"],
            "ritual": "集齐空想家唯一性与作家非凡特性；所想的必将成为现实",
        },
    ],
}

PATHWAYS["white_tower"] = {
    "name": "白塔",
    "tarot": "塔",
    "group": "god_almighty",
    "gender_change": [],
    "sequences": [
        {
            "level": 9, "name": "阅读者",
            "abilities": ["记忆增强", "理解增强", "仪式魔法"],
            "required_actions": ["大量阅读", "学习知识"],
        },
        {
            "level": 8, "name": "推理学员",
            "abilities": ["观察力提升", "逻辑思维", "仪式魔法专家"],
            "required_actions": ["推理练习", "逻辑分析"],
        },
        {
            "level": 7, "name": "侦探",
            "abilities": ["格斗能力", "行动力强化", "武器精通", "逻辑推理大师"],
            "required_actions": ["侦破案件", "推理真相"],
        },
        {
            "level": 6, "name": "博学家",
            "abilities": ["博学全能", "解析能力", "能力模仿"],
            "required_actions": ["学习各种知识", "解析非凡能力"],
        },
        {
            "level": 5, "name": "秘术导师",
            "abilities": ["秘术掌握", "自创法术", "独特法术"],
            "required_actions": ["掌握秘术", "发明法术"],
            "ritual": "独自发明一种全新的阶位法术并成功施展三次",
        },
        {
            "level": 4, "name": "预言家",
            "abilities": ["命运感知", "预言能力", "神秘学大师"],
            "required_actions": ["做出预言", "感知命运"],
            "ritual": "预言三件必定发生的事并全部应验",
        },
        {
            "level": 3, "name": "洞悉者",
            "abilities": ["世界规则洞悉", "弱点暴露", "杠杆撬动"],
            "required_actions": ["洞悉本质", "发现杠杆"],
            "ritual": "完全洞悉一位半神的全部秘密，找到撬动其命运的核心杠杆",
        },
        {
            "level": 2, "name": "智天使",
            "abilities": ["智慧领域", "全知之域"],
            "required_actions": ["追求全知", "智慧积累"],
            "ritual": "在灵界白塔中回答一百个来自不同时代智者的问题",
        },
        {
            "level": 1, "name": "全知之眼",
            "abilities": ["全知之视", "万物洞悉"],
            "required_actions": ["看透一切", "记录一切"],
            "ritual": "以全知之眼凝视世界一百年（可借助时间加速）",
        },
        {
            "level": 0, "name": "白塔",
            "abilities": ["全知全能", "知识权柄"],
            "required_actions": ["成为全知的象征"],
            "ritual": "集齐白塔唯一性与全知之眼非凡特性",
        },
    ],
}

PATHWAYS["sun"] = {
    "name": "太阳",
    "tarot": "太阳",
    "group": "god_almighty",
    "gender_change": [],
    "sequences": [
        {
            "level": 9, "name": "歌颂者",
            "abilities": ["勇气之歌", "力量之歌", "服从之歌"],
            "required_actions": ["歌颂光明", "鼓舞他人"],
        },
        {
            "level": 8, "name": "祈光人",
            "abilities": ["太阳法术", "光明仪式", "死灵克制"],
            "required_actions": ["祈求光明", "驱散亡灵"],
        },
        {
            "level": 7, "name": "太阳神官",
            "abilities": ["光明之火", "免疫恐惧", "神圣誓约", "净化之斩", "太阳光环", "召唤圣光", "制造圣水"],
            "required_actions": ["主持圣礼", "净化邪恶"],
        },
        {
            "level": 6, "name": "公证人",
            "abilities": ["公证有效", "公证无效", "契约制作"],
            "required_actions": ["公证契约", "履行誓约"],
        },
        {
            "level": 5, "name": "光之祭司",
            "abilities": ["纯净光华", "死灵克星", "光环净化"],
            "required_actions": ["释放圣光", "净化亡灵"],
            "ritual": "在一座被死灵占据的城市中释放圣光，净化至少一百只亡灵",
        },
        {
            "level": 4, "name": "无暗者",
            "abilities": ["净化精神污染", "削弱非凡能力", "逐级排出非凡特性"],
            "required_actions": ["驱逐黑暗", "净化污染"],
            "ritual": "净化一位半神非凡特性中的精神污染",
        },
        {
            "level": 3, "name": "正义导师",
            "abilities": ["正义审判", "光明教义"],
            "required_actions": ["伸张正义", "教导光明"],
            "ritual": "在一场审判中让真相大白于天下，罪人当众忏悔",
        },
        {
            "level": 2, "name": "逐光者",
            "abilities": ["追逐光明", "极致净化"],
            "required_actions": ["追寻终极光明"],
            "ritual": "追逐太阳的轨迹环行世界一周",
        },
        {
            "level": 1, "name": "纯白天使",
            "abilities": ["纯白圣光", "天使审判"],
            "required_actions": ["成为纯白化身"],
            "ritual": "在纯白圣光中审判一位堕落天使",
        },
        {
            "level": 0, "name": "太阳",
            "abilities": ["契约权柄", "光明权柄", "神圣制裁"],
            "required_actions": ["成为光明的化身"],
            "ritual": "集齐太阳唯一性与纯白天使非凡特性",
        },
    ],
}

# -------------------------------------------------------
# 权柄体系三：恶魔之父（暗影世界）
# -------------------------------------------------------

PATHWAYS["bound_one"] = {
    "name": "被缚者",
    "tarot": "节制",
    "group": "demon_father",
    "gender_change": [],
    "sequences": [
        {
            "level": 9, "name": "囚犯",
            "abilities": ["强健身躯", "敏锐知觉", "犯罪技巧"],
            "required_actions": ["承受囚禁", "磨练犯罪技巧"],
            "curse": "欲望加强",
        },
        {
            "level": 8, "name": "疯子",
            "abilities": ["疯狂爆发", "精神抵抗", "全能力提升"],
            "required_actions": ["爆发疯狂", "牺牲理智"],
            "curse": "疯狂条件下容易失控",
        },
        {
            "level": 7, "name": "狼人",
            "abilities": ["狼人变身", "恐怖力量", "敏捷速度", "毒性爪牙", "黑暗法术", "狼人转化"],
            "required_actions": ["在红月下狩猎", "控制杀戮欲望"],
            "curse": "无法压制杀戮和嗜血欲望，逐步失去人类感情",
        },
        {
            "level": 6, "name": "活尸",
            "abilities": ["钢铁身躯", "死亡法术", "亡者驱使", "寒冷腐烂之力"],
            "required_actions": ["驱使亡灵", "操控尸体"],
            "curse": "渴望服食血液和新鲜血肉，满月痛苦甚至失去战斗能力",
        },
        {
            "level": 5, "name": "怨魂",
            "abilities": ["幽影转化", "灵魂攻击", "镜中穿梭", "灵界启示", "强行附体"],
            "required_actions": ["以幽魂形态存在", "攻击生灵灵魂"],
            "ritual": "在红月之下吸食一个序列6以上非凡者的完整灵魂",
            "curse": "红月满圆之夜必须吸食人类灵魂或变得虚弱",
        },
        {
            "level": 4, "name": "木偶",
            "abilities": ["无生命操控", "环境武器化", "束缚领域"],
            "required_actions": ["操控环境", "制造陷阱"],
            "ritual": "操控一千件不同的无生命物品完成一场战斗",
            "special": "诅咒被消除",
        },
        {
            "level": 3, "name": "沉默门徒",
            "abilities": ["沉默施法", "法术沉默"],
            "required_actions": ["在沉默中施法"],
            "ritual": "在完全沉默的状态下击败一位同序列的敌人",
        },
        {
            "level": 2, "name": "古代邪物",
            "abilities": ["变形诅咒", "野兽转化"],
            "required_actions": ["施加变形诅咒"],
            "ritual": "将一位半神目标变形诅咒为不具备战斗力的动物持续一个月",
        },
        {
            "level": 1, "name": "神孽",
            "abilities": ["大范围狂乱", "灵性囚笼", "暴毙诅咒"],
            "required_actions": ["制造狂乱", "施加暴毙诅咒"],
            "ritual": "让一座城市超过半数居民同时陷入狂乱并恢复",
        },
        {
            "level": 0, "name": "被缚者",
            "abilities": ["诅咒主宰", "异类之主"],
            "required_actions": ["成为诅咒之源"],
            "ritual": "集齐被缚者唯一性与神孽非凡特性",
        },
    ],
}

PATHWAYS["abyss"] = {
    "name": "深渊",
    "tarot": "恶魔",
    "group": "demon_father",
    "gender_change": [],
    "sequences": [
        {
            "level": 9, "name": "罪犯",
            "abilities": ["强壮身体", "敏锐知觉", "全武器精通", "犯罪本能"],
            "required_actions": ["犯罪", "残害他人"],
            "special": "身和心处于恶欲统治下，良知未彻底泯灭",
        },
        {
            "level": 8, "name": "折翼天使",
            "abilities": ["冷血无情", "非人身躯", "毒火", "恶语诅咒"],
            "required_actions": ["失去良知", "与恶欲同流"],
            "special": "失去良知与恶欲同流",
        },
        {
            "level": 7, "name": "连环杀手",
            "abilities": ["恶魔知识", "连环杀人仪式", "恶魔投影召唤", "占卜干扰"],
            "required_actions": ["连环杀人", "取悦恶魔"],
            "special": "用特殊连环杀人案取悦恶魔",
        },
        {
            "level": 6, "name": "恶魔",
            "abilities": ["危险预知", "恶魔化", "毒素免疫", "诅咒抵抗", "毒焰操纵", "硫磺火球", "污秽之语"],
            "required_actions": ["预知危险", "施展污秽之语"],
            "special": "序列6即获得神话生物形态（无神话伤害，使用会增加失控倾向）",
        },
        {
            "level": 5, "name": "欲望使徒",
            "abilities": ["掌控欲望", "欲望化身", "精神冲击", "远程操控"],
            "required_actions": ["操纵欲望", "催化堕落"],
            "ritual": "让九十九个人因自己的欲望而堕落至无法挽回的地步",
        },
        {
            "level": 4, "name": "魔鬼",
            "abilities": ["高智商犯罪", "思维削弱", "迷幻状态", "欲望引爆", "心灵摧毁"],
            "required_actions": ["精神博弈", "引爆欲望"],
            "ritual": "让一位圣者级人物在完全清醒的状态下自愿堕入深渊",
        },
        {
            "level": 3, "name": "呓语者",
            "abilities": ["语言失控", "远程诅咒", "反向影响", "声音传递"],
            "required_actions": ["用语言使人失控"],
            "ritual": "仅凭一句话让一位半神陷入不可逆转的疯狂",
        },
        {
            "level": 2, "name": "鲜血大公",
            "abilities": ["鲜血掌控", "体液支配", "恐惧汲取"],
            "required_actions": ["掌控鲜血", "散播恐惧"],
            "ritual": "用一位天使的鲜血绘制覆盖整座城市的仪式阵法",
        },
        {
            "level": 1, "name": "污秽君王",
            "abilities": ["污秽领域", "腐蚀支配", "污染之源"],
            "required_actions": ["制造污秽", "散布腐蚀"],
            "ritual": "将一片大陆级别的区域污染为不可生存的死地",
        },
        {
            "level": 0, "name": "深渊",
            "abilities": ["堕落权柄", "诅咒主宰", "异类之王"],
            "required_actions": ["成为深渊本身"],
            "ritual": "集齐深渊唯一性与污秽君王非凡特性",
        },
    ],
}

# -------------------------------------------------------
# 权柄体系四：知识之妖（知识荒野）
# -------------------------------------------------------

PATHWAYS["hermit"] = {
    "name": "隐者",
    "tarot": "隐者",
    "group": "knowledge_demon",
    "gender_change": [],
    "sequences": [
        {
            "level": 9, "name": "窥秘人",
            "abilities": ["魔法入门", "巫术入门", "占星术", "纸牌占卜"],
            "required_actions": ["窥探秘密", "学习神秘知识"],
        },
        {
            "level": 8, "name": "格斗学者",
            "abilities": ["技巧格斗", "体质强化"],
            "required_actions": ["格斗训练", "学以致用"],
        },
        {
            "level": 7, "name": "巫师",
            "abilities": ["巫术魔法", "材料施法"],
            "required_actions": ["准备施法材料", "施展巫术"],
        },
        {
            "level": 6, "name": "卷轴教授",
            "abilities": ["卷轴制作", "知识传授"],
            "required_actions": ["制作魔法卷轴", "教授学徒"],
        },
        {
            "level": 5, "name": "星象师",
            "abilities": ["星象识别", "占星法术", "本质洞察"],
            "required_actions": ["观测星象", "解读命运"],
            "ritual": "在无云的夜晚准确预言三颗流星的陨落轨迹",
        },
        {
            "level": 4, "name": "神秘学家",
            "abilities": ["解析神话血液", "历史魔法", "神秘学大师"],
            "required_actions": ["解析神话生物", "转化历史为魔法"],
            "ritual": "完全解析一滴神话生物的血液",
        },
        {
            "level": 3, "name": "预言大师",
            "abilities": ["长期预言", "即时预言"],
            "required_actions": ["做出预言", "洞悉未来"],
            "ritual": "做出一个涉及万人以上的长期预言并被证实",
        },
        {
            "level": 2, "name": "贤者",
            "abilities": ["信息转化", "生命重构"],
            "required_actions": ["化解灾难", "转化信息"],
            "ritual": "阻止一场大型灾难，将自身转化为信息洪流再重构",
        },
        {
            "level": 1, "name": "知识皇帝",
            "abilities": ["知识洪流", "信息植入", "以太体崩溃", "超凡信息伪造"],
            "required_actions": ["灌输知识", "伪造信息"],
            "ritual": "将海量知识瞬间植入一位天使的以太体使其濒临崩溃",
        },
        {
            "level": 0, "name": "隐者",
            "abilities": ["知识权柄", "隐秘智慧"],
            "required_actions": ["成为知识的化身"],
            "ritual": "集齐隐者唯一性与知识皇帝非凡特性",
        },
    ],
}

PATHWAYS["paragon"] = {
    "name": "完美者",
    "tarot": "女祭司",
    "group": "knowledge_demon",
    "gender_change": [],
    "sequences": [
        {
            "level": 9, "name": "通识者",
            "abilities": ["广博知识", "化学精通", "机械精通"],
            "required_actions": ["学习知识", "动手制作"],
        },
        {
            "level": 8, "name": "考古学家",
            "abilities": ["历史知识", "野外生存", "遗迹禁忌"],
            "required_actions": ["考古发掘", "探索遗迹"],
        },
        {
            "level": 7, "name": "鉴定师",
            "abilities": ["超凡物品鉴定", "能力评估", "危险规避"],
            "required_actions": ["鉴定物品", "评估风险"],
        },
        {
            "level": 6, "name": "机械专家",
            "abilities": ["制造大师", "超凡物品制作", "负面效果降低"],
            "required_actions": ["制造物品", "改良设计"],
        },
        {
            "level": 5, "name": "天文学家",
            "abilities": ["星辰之力", "星术"],
            "required_actions": ["观测星辰", "利用星辰之力"],
            "ritual": "在天文台连续观测星空一整年，记录下所有可见星辰的运动",
        },
        {
            "level": 4, "name": "炼金术士",
            "abilities": ["灵魂注入", "生命炼成", "物品活化"],
            "required_actions": ["炼制物品", "注入灵魂"],
            "ritual": "为自己制造的物品注入真正的灵魂——另一种形式的生命炼成",
        },
        {
            "level": 3, "name": "奥秘学者",
            "abilities": ["奥秘之妖", "知识活化"],
            "required_actions": ["探索奥秘", "掌握知识本质"],
            "ritual": "发现并掌握一项被历史遗忘的古代文明的核心奥秘",
        },
        {
            "level": 2, "name": "知识导师",
            "abilities": ["看破本质", "神话形态洞察"],
            "required_actions": ["传授知识", "洞察本质"],
            "ritual": "教导一百位非凡者掌握一项由自己创造的技术",
        },
        {
            "level": 1, "name": "启蒙者",
            "abilities": ["黑暗之光", "文明启蒙"],
            "required_actions": ["启蒙文明", "传播知识"],
            "ritual": "让一个处于黑暗时代的文明完成知识启蒙",
        },
        {
            "level": 0, "name": "完美者",
            "abilities": ["文明发祥", "千年智慧", "完美权柄"],
            "required_actions": ["成为文明的象征"],
            "ritual": "集齐完美者唯一性与启蒙者非凡特性",
        },
    ],
}

# -------------------------------------------------------
# 权柄体系五：诡秘之主（源堡）
# -------------------------------------------------------

PATHWAYS["fool"] = {
    "name": "愚者",
    "tarot": "愚者",
    "group": "lord_of_mysteries",
    "gender_change": [],
    "sequences": [
        {
            "level": 9, "name": "占卜家",
            "abilities": ["占星术", "卡牌占卜", "灵摆", "灵视", "灵数", "手相"],
            "required_actions": ["占卜", "解读命运"],
        },
        {
            "level": 8, "name": "小丑",
            "abilities": ["完美协调", "直觉预判", "危险预感", "纸牌投掷", "表情控制"],
            "required_actions": ["逗人发笑", "预判危险"],
        },
        {
            "level": 7, "name": "魔术师",
            "abilities": ["抽纸为兵", "骨骼软化", "幻术制造", "火焰控制", "火焰跳跃", "空气子弹", "纸人替身", "伤害转移", "水下呼吸"],
            "required_actions": ["表演魔术", "欺骗观众"],
        },
        {
            "level": 6, "name": "无面人",
            "abilities": ["容貌变化", "气味改变", "魔法增强"],
            "required_actions": ["变成他人", "隐藏身份"],
        },
        {
            "level": 5, "name": "秘偶大师",
            "abilities": ["灵体之线视觉", "灵体操控", "秘偶化", "秘偶驱使"],
            "required_actions": ["操控灵体之线", "制作秘偶"],
            "ritual": "在美人鱼的歌声中服用魔药",
        },
        {
            "level": 4, "name": "诡法师",
            "abilities": ["伤害转移强化", "空气炮弹", "动物变身", "秘偶换位", "大批秘偶", "幻术质变"],
            "required_actions": ["导演戏剧", "谋杀强敌"],
            "ritual": "在大部分自身出力的谋划或战斗中谋杀一位序列4或以上者，导演盛大的戏剧，在众多观众注目下完成",
        },
        {
            "level": 3, "name": "古代学者",
            "abilities": ["历史召唤", "过去借力", "历史孔隙躲藏", "秘偶强化", "火焰跳跃强化"],
            "required_actions": ["脱离现实", "研究历史"],
            "ritual": "完全脱离现实三百年，在自身已成为历史不属于当前时代后服用魔药",
        },
        {
            "level": 2, "name": "奇迹师",
            "abilities": ["愿望实现", "奇迹制造", "复活", "历史场景召唤"],
            "required_actions": ["收集愿望", "制造奇迹"],
            "ritual": "将一段古代历史重现于今日",
        },
        {
            "level": 1, "name": "诡秘侍者",
            "abilities": ["灵体之线唤起", "诡秘联系", "神国雏形"],
            "required_actions": ["制造秘偶城市", "编织命运"],
            "ritual": "制造一个纯粹由秘偶组成的城市，让其中所有人都有各自独立的命运轨迹，并在灵界形成对应区域",
        },
        {
            "level": 0, "name": "愚者",
            "abilities": ["愚弄万物", "智商强制降低", "神国瞬造", "奇迹创造"],
            "required_actions": ["欺骗时间、历史或命运"],
            "ritual": "欺骗一次时间、历史或命运",
        },
    ],
}

PATHWAYS["error"] = {
    "name": "错误",
    "tarot": "恋人",
    "group": "lord_of_mysteries",
    "gender_change": [],
    "sequences": [
        {
            "level": 9, "name": "偷盗者",
            "abilities": ["窃取", "敏捷之手", "卓越观察", "短剑精通"],
            "required_actions": ["偷窃", "潜入"],
        },
        {
            "level": 8, "name": "诈骗师",
            "abilities": ["魅力", "口才", "思维误导", "精神干扰", "敏捷速度"],
            "required_actions": ["编织谎言", "欺诈他人"],
        },
        {
            "level": 7, "name": "解密学者",
            "abilities": ["神秘学知识", "灵性直觉", "观察推导", "真相还原"],
            "required_actions": ["解密神秘事件", "推导真相"],
        },
        {
            "level": 6, "name": "盗火人",
            "abilities": ["能力偷盗", "非凡偷取"],
            "required_actions": ["偷盗能力", "盗取非凡"],
        },
        {
            "level": 5, "name": "窃梦家",
            "abilities": ["梦境影响", "念头偷盗", "记忆窃取"],
            "required_actions": ["偷窃梦境", "窃取念头"],
            "ritual": "偷走一个序列5非凡者最重要的念头，使其永久遗忘",
        },
        {
            "level": 4, "name": "寄生者",
            "abilities": ["分身制造", "寄生生物", "浅层寄生", "深层控制"],
            "required_actions": ["制造分身", "寄生宿主"],
            "ritual": "制造一个能独立生存的分身并让其寄生一位半神",
        },
        {
            "level": 3, "name": "欺瞒导师",
            "abilities": ["深度欺瞒", "神秘学伪装", "伪造隐藏"],
            "required_actions": ["完成欺瞒", "伪造现实"],
            "ritual": "完成一次让天使级存在都无法识破的欺瞒",
        },
        {
            "level": 2, "name": "命运木马",
            "abilities": ["命运还原", "命运篡改"],
            "required_actions": ["还原命运", "篡改命运"],
            "ritual": "在命运层面上篡改一件已发生的历史事件使其无人能还原真相",
        },
        {
            "level": 1, "name": "时之虫",
            "abilities": ["生命窃取", "时间窃取"],
            "required_actions": ["窃取生命", "操控时间"],
            "ritual": "窃取一位天使一千年的寿命",
        },
        {
            "level": 0, "name": "错误",
            "abilities": ["一切错误的化身", "逻辑谬误", "规则漏洞"],
            "required_actions": ["成为错误本身"],
            "ritual": "集齐错误唯一性与时之虫非凡特性",
        },
    ],
}

PATHWAYS["door"] = {
    "name": "门",
    "tarot": "魔术师",
    "group": "lord_of_mysteries",
    "gender_change": [],
    "sequences": [
        {
            "level": 9, "name": "学徒",
            "abilities": ["穿墙", "开门"],
            "required_actions": ["穿越障碍", "开启门户"],
        },
        {
            "level": 8, "name": "戏法大师",
            "abilities": ["小型元素魔法", "油腻术", "各种戏法"],
            "required_actions": ["表演戏法", "糊弄观众"],
        },
        {
            "level": 7, "name": "占星人",
            "abilities": ["占卜", "前置能力增强"],
            "required_actions": ["占星", "解读星象"],
        },
        {
            "level": 6, "name": "记录官",
            "abilities": ["能力记录", "能力复现"],
            "required_actions": ["记录能力", "复现能力"],
            "special": "可记录20项序列9-7、15项序列6-5、3项序列4-3的能力各使用一次",
        },
        {
            "level": 5, "name": "旅行家",
            "abilities": ["短距闪现", "长距传送", "空间跳跃"],
            "required_actions": ["旅行各地", "穿越空间"],
            "ritual": "在一年内走遍七大洲，在每个大洲留下自己的足迹",
        },
        {
            "level": 4, "name": "秘法师",
            "abilities": ["空间隐藏", "分身闪现", "天使级记录"],
            "required_actions": ["创造秘密空间", "记录高级能力"],
            "ritual": "创造一个连天使都无法发现的空间隐藏之所",
        },
        {
            "level": 3, "name": "漫游者",
            "abilities": ["漫游能力", "即时脱离"],
            "required_actions": ["漫游各界", "自由脱离"],
            "ritual": "在灵界、星界、冥界各漫游至少一年",
        },
        {
            "level": 2, "name": "旅法师",
            "abilities": ["还原传送", "空间互换", "时空放逐"],
            "required_actions": ["留下传说", "还原场景"],
            "ritual": "在九个不属于这个世界的地方留下传说",
        },
        {
            "level": 1, "name": "星之匙",
            "abilities": ["星界之门", "万界钥匙"],
            "required_actions": ["开启星界之门"],
            "ritual": "找到并开启一扇通往未知宇宙深处的星界之门",
        },
        {
            "level": 0, "name": "门",
            "abilities": ["封印操控", "万界传送", "空间主宰"],
            "required_actions": ["成为万门之门"],
            "ritual": "集齐门唯一性与星之匙非凡特性",
        },
    ],
}

# -------------------------------------------------------
# 权柄体系六：根源之神（母巢）
# -------------------------------------------------------

PATHWAYS["mother"] = {
    "name": "母亲",
    "tarot": "世界",
    "group": "root_god",
    "gender_change": [2, 1, 0],  # 序列2、1、0强制变性为女性
    "sequences": [
        {
            "level": 9, "name": "耕种者",
            "abilities": ["种子辨识", "天气预测", "高力量"],
            "required_actions": ["耕种土地", "辨识植物"],
        },
        {
            "level": 8, "name": "医师",
            "abilities": ["治疗", "草药知识"],
            "required_actions": ["治疗伤者", "照顾病患"],
        },
        {
            "level": 7, "name": "丰收祭司",
            "abilities": ["催化生长", "促进繁衍"],
            "required_actions": ["主持丰收仪式", "催生作物"],
        },
        {
            "level": 6, "name": "生物学家",
            "abilities": ["杂交生物", "生物特性掌握"],
            "required_actions": ["杂交实验", "研究生物"],
        },
        {
            "level": 5, "name": "德鲁伊",
            "abilities": ["动物掌握", "自然之力"],
            "required_actions": ["与动物共处", "掌握超凡生物习性"],
            "ritual": "完全掌握多种普通动物和三种超凡生物的生活习性和肉体结构",
        },
        {
            "level": 4, "name": "古代炼金师",
            "abilities": ["生命炼成", "生物创造"],
            "required_actions": ["炼制生命", "创造生物"],
            "ritual": "成功创造一种全新的、能自我繁衍的生命形态",
        },
        {
            "level": 3, "name": "抬棺人",
            "abilities": ["生死界限", "生命终结"],
            "required_actions": ["见证生死", "跨越界限"],
            "ritual": "抬着棺材走遍生死之间的边界",
        },
        {
            "level": 2, "name": "荒芜主母",
            "abilities": ["荒芜领域", "生命终结之力"],
            "required_actions": ["带来荒芜", "终结生命"],
            "ritual": "让一片繁茂的大地归于荒芜后再使其重生",
            "special": "晋升导致男性强制变为女性",
        },
        {
            "level": 1, "name": "自然行者",
            "abilities": ["自然之力", "万物生长"],
            "required_actions": ["行走自然", "促进万物生长"],
            "ritual": "徒步走遍世界上所有的自然生态系统",
            "special": "晋升导致男性强制变为女性",
        },
        {
            "level": 0, "name": "母亲",
            "abilities": ["生命权柄", "万物之母"],
            "required_actions": ["成为万物的母亲"],
            "ritual": "集齐母亲唯一性与自然行者非凡特性",
            "special": "晋升导致男性强制变为女性",
        },
    ],
}

PATHWAYS["moon"] = {
    "name": "月亮",
    "tarot": "月亮",
    "group": "root_god",
    "gender_change": [1, 0],  # 序列1、0强制变性为女性
    "sequences": [
        {
            "level": 9, "name": "药师",
            "abilities": ["药剂调配", "植物驯化", "健康灵视"],
            "required_actions": ["调配药剂", "治疗病人"],
        },
        {
            "level": 8, "name": "驯兽师",
            "abilities": ["动物驯化", "感官分享", "超凡生物沟通"],
            "required_actions": ["驯化动物", "驱使动物"],
        },
        {
            "level": 7, "name": "吸血鬼",
            "abilities": ["寿命提升", "颜值魅力", "黑暗之翼", "腐蚀之爪", "深渊枷锁", "血仆转化"],
            "required_actions": ["吸食血液", "转化血仆"],
            "special": "厌恶阳光，以富含灵性的血液为主食",
        },
        {
            "level": 6, "name": "魔药教授",
            "abilities": ["灵性材料辨识", "超凡药剂", "超凡香水", "药剂开发"],
            "required_actions": ["制作魔药", "开发新药剂"],
        },
        {
            "level": 5, "name": "深红学者",
            "abilities": ["满月环境", "月光瞬移", "月光重组", "梦魇抵抗"],
            "required_actions": ["在满月下活动", "利用月光"],
            "ritual": "在十二次满月之夜各吸收一种不同的灵性材料",
        },
        {
            "level": 4, "name": "巫王",
            "abilities": ["千年寿命", "月亮黑暗法术", "黑暗凝视", "蝙蝠分解", "月光替身"],
            "required_actions": ["布置月亮仪式", "使用黑暗凝视"],
            "ritual": "在月光下布置覆盖一座城市的巨型仪式",
        },
        {
            "level": 3, "name": "召唤大师",
            "abilities": ["灵界召唤", "天使契约", "异变召唤"],
            "required_actions": ["召唤强大生物", "签订契约"],
            "ritual": "与一位天使签订平等的召唤契约",
        },
        {
            "level": 2, "name": "创生者",
            "abilities": ["创造之力", "生命赋予"],
            "required_actions": ["创造生命", "赋予力量"],
            "ritual": "创造出一种全新的智慧生命形态",
        },
        {
            "level": 1, "name": "美神",
            "abilities": ["绝美容颜", "不可抗拒魅力", "魅惑领域"],
            "required_actions": ["成为美的化身"],
            "ritual": "让一万个人因自身魅力而自愿献上忠诚",
            "special": "晋升导致雄性强制变雌性",
        },
        {
            "level": 0, "name": "月亮",
            "abilities": ["月亮权柄", "生命繁衍", "美丽主宰"],
            "required_actions": ["成为月亮的化身"],
            "ritual": "集齐月亮唯一性与美神非凡特性",
            "special": "晋升导致男性强制变为女性",
        },
    ],
}

# -------------------------------------------------------
# 权柄体系七：失序者（失序之国）
# -------------------------------------------------------

PATHWAYS["judge"] = {
    "name": "审判者",
    "tarot": "审判",
    "group": "disorder",
    "gender_change": [],
    "sequences": [
        {
            "level": 9, "name": "仲裁人",
            "abilities": ["令人信服", "权威魅力", "拳头说服"],
            "required_actions": ["仲裁纠纷", "建立权威"],
        },
        {
            "level": 8, "name": "治安官",
            "abilities": ["过目不忘", "超凡感应", "痕迹追踪"],
            "required_actions": ["维持治安", "追踪罪犯"],
        },
        {
            "level": 7, "name": "审讯者",
            "abilities": ["全武器精通", "爆破专家", "精神穿刺"],
            "required_actions": ["审讯犯人", "爆破作业"],
        },
        {
            "level": 6, "name": "法官",
            "abilities": ["口才精通", "审判之力"],
            "required_actions": ["主持审判", "做出裁决"],
        },
        {
            "level": 5, "name": "惩戒骑士",
            "abilities": ["规则制定", "违规必中", "攻击增幅"],
            "required_actions": ["制定规则", "惩戒违规者"],
            "ritual": "制定一套规则并使至少一百人自愿遵守",
        },
        {
            "level": 4, "name": "律令法师",
            "abilities": ["非凡禁用", "现实增强", "削弱非凡"],
            "required_actions": ["颁布律令", "禁用非凡"],
            "ritual": "在一个区域内颁布律令禁用某种非凡能力至少三天",
        },
        {
            "level": 3, "name": "混乱猎手",
            "abilities": ["混乱感知", "秩序恢复"],
            "required_actions": ["猎杀混乱", "恢复秩序"],
            "ritual": "在混乱之地恢复秩序并使当地居民自愿接受律法",
        },
        {
            "level": 2, "name": "平衡者",
            "abilities": ["力量平衡观察", "平衡调控"],
            "required_actions": ["维持平衡", "调整力量"],
            "ritual": "在一场权力斗争中维持双方力量平衡直到纠纷和平解决",
        },
        {
            "level": 1, "name": "秩序之手",
            "abilities": ["秩序分割", "战场划分"],
            "required_actions": ["用秩序之力分割空间"],
            "ritual": "用秩序的力量将一片大陆分割为不同规则的领域",
        },
        {
            "level": 0, "name": "审判者",
            "abilities": ["审判权柄", "秩序主宰"],
            "required_actions": ["成为秩序的化身"],
            "ritual": "集齐审判者唯一性与秩序之手非凡特性",
        },
    ],
}

PATHWAYS["black_emperor"] = {
    "name": "黑皇帝",
    "tarot": "皇帝",
    "group": "disorder",
    "gender_change": [],
    "sequences": [
        {
            "level": 9, "name": "律师",
            "abilities": ["规则漏洞发现", "秩序打击", "口才说服", "思维引导"],
            "required_actions": ["寻找漏洞", "扭曲规则"],
        },
        {
            "level": 8, "name": "野蛮人",
            "abilities": ["可怕力量", "强健体魄", "物理精神双抵抗"],
            "required_actions": ["使用蛮力", "以力破法"],
        },
        {
            "level": 7, "name": "贿赂者",
            "abilities": ["贿赂削弱", "贿赂魅惑", "贿赂狂妄", "贿赂关联"],
            "required_actions": ["给予贿赂", "利用利益"],
        },
        {
            "level": 6, "name": "腐化男爵",
            "abilities": ["规则扭曲", "意图扭曲", "贿赂强化"],
            "required_actions": ["扭曲规则", "腐化秩序"],
        },
        {
            "level": 5, "name": "混乱导师",
            "abilities": ["距离扭曲", "攻击扭曲", "空间封锁"],
            "required_actions": ["制造混乱", "扭曲空间"],
            "ritual": "在一座城市中制造无法被归因的持续混乱至少一周",
        },
        {
            "level": 4, "name": "堕落伯爵",
            "abilities": ["攻击放大", "攻击转向", "意图扭曲强化"],
            "required_actions": ["放大混乱", "扭曲攻击"],
            "ritual": "将一位半神的攻击放大到天使级别并转向其自身",
        },
        {
            "level": 3, "name": "狂乱法师",
            "abilities": ["狂乱领域", "魔法扭曲"],
            "required_actions": ["制造狂乱", "扭曲魔法"],
            "ritual": "让一位天使陷入狂乱并使其魔法全部反噬自身",
        },
        {
            "level": 2, "name": "熵之公爵",
            "abilities": ["熵增掌控", "秩序瓦解"],
            "required_actions": ["增加熵值", "瓦解秩序"],
            "ritual": "让一个国家的法律体系在一年内自然瓦解",
        },
        {
            "level": 1, "name": "弑序亲王",
            "abilities": ["秩序弑杀", "规则终结"],
            "required_actions": ["弑杀秩序", "终结规则"],
            "ritual": "亲手终结一套已经运行超过一千年的秩序体系",
        },
        {
            "level": 0, "name": "黑皇帝",
            "abilities": ["陵寝复活", "秩序扭曲", "规则主宰"],
            "required_actions": ["建立国度", "扭曲规则", "建造陵寝"],
            "ritual": "拥有自己的国度，让名字与皇帝称号联系成为民众常识；建立一套严密复杂但有违正常情况的规则；驱使民众建立九座陵寝并让大量信仰自己的民众在其中祭祀",
            "special": "黑皇帝就算死亡也可从九座陵寝复活；唯一让其死亡的办法是诞生新的黑皇帝",
        },
    ],
}

# -------------------------------------------------------
# 权柄体系八：毁灭天灾（灾祸之城）
# -------------------------------------------------------

PATHWAYS["red_priest"] = {
    "name": "红祭司",
    "tarot": "战车",
    "group": "destruction",
    "gender_change": [4, 3, 2, 1, 0],  # 序列4、3、2、1、0强制变性为男性
    "sequences": [
        {
            "level": 9, "name": "猎人",
            "abilities": ["追踪", "陷阱", "猎杀"],
            "required_actions": ["追踪猎物", "设置陷阱", "猎杀目标"],
        },
        {
            "level": 8, "name": "挑衅者",
            "abilities": ["辱骂挑衅", "憎恶吸引", "陷阱专家"],
            "required_actions": ["挑衅敌人", "吸引仇恨"],
        },
        {
            "level": 7, "name": "纵火家",
            "abilities": ["火焰制作", "火焰控制"],
            "required_actions": ["纵火", "控制火焰"],
        },
        {
            "level": 6, "name": "阴谋家",
            "abilities": ["阴谋策划", "阴谋察觉", "非凡误导"],
            "required_actions": ["策划阴谋", "误导敌人"],
        },
        {
            "level": 5, "name": "收割者",
            "abilities": ["弱点发现", "物理攻击强化"],
            "required_actions": ["发现弱点", "收割敌人"],
            "ritual": "在战场上收割一百个敌人的生命",
        },
        {
            "level": 4, "name": "铁血骑士",
            "abilities": ["铁血勇气", "环境武器化", "伤害分摊", "部下共享感官"],
            "required_actions": ["率领部下", "分摊伤害"],
            "ritual": "率领一支军队在必败的战争中坚持到最后一刻",
            "special": "晋升导致雌性强制变雄性",
        },
        {
            "level": 3, "name": "战争主教",
            "abilities": ["战争领域", "军队加成"],
            "required_actions": ["指挥战争", "传播战火"],
            "ritual": "指挥一场涉及三个以上国家的战争并获胜",
            "special": "晋升导致雌性强制变雄性",
        },
        {
            "level": 2, "name": "天气术士",
            "abilities": ["大范围天气改变"],
            "required_actions": ["改变天气", "制造气候灾难"],
            "ritual": "在很大区域内随意改变天气持续一整年",
            "special": "晋升导致雌性强制变雄性",
        },
        {
            "level": 1, "name": "征服者",
            "abilities": ["征服领域", "战争权柄"],
            "required_actions": ["征服大陆", "统治万军"],
            "ritual": "征服一片大陆上的所有国家",
            "special": "晋升导致雌性强制变雄性",
        },
        {
            "level": 0, "name": "红祭司",
            "abilities": ["战争权柄", "力量本质"],
            "required_actions": ["掀起世界大战", "获得足够胜利"],
            "ritual": "掀起一场席卷大陆的战争并获得足够胜利",
            "special": "晋升导致雌性强制变雄性",
        },
    ],
}

PATHWAYS["chaos_witch"] = {
    "name": "混沌魔女",
    "tarot": "皇后",
    "group": "destruction",
    "gender_change": [7, 4, 3, 2, 1, 0],  # 序列7、4、3、2、1、0强制变性为女性
    "sequences": [
        {
            "level": 9, "name": "刺客",
            "abilities": ["身体轻盈", "鹰眼视力", "黑暗视觉", "阴影躲藏", "一击爆发"],
            "required_actions": ["暗杀目标", "躲藏阴影"],
        },
        {
            "level": 8, "name": "教唆者",
            "abilities": ["诱发恶欲", "激化矛盾", "魅惑", "误导", "说服"],
            "required_actions": ["教唆犯罪", "挑拨离间"],
        },
        {
            "level": 7, "name": "女巫",
            "abilities": ["容貌魅力提升", "隐形", "镜子替身", "魔杖替身", "黑魔法", "反占卜", "黑焰", "冰霜"],
            "required_actions": ["施展黑魔法", "使用替身"],
            "special": "晋升导致雄性强制变雌性",
        },
        {
            "level": 6, "name": "欢愉",
            "abilities": ["诱惑", "蛛丝", "快乐赋予", "容貌全面提升"],
            "required_actions": ["诱惑目标", "给予欢愉"],
        },
        {
            "level": 5, "name": "痛苦",
            "abilities": ["大范围疾病", "痛苦散播"],
            "required_actions": ["制造疾病", "散播痛苦"],
            "ritual": "让一千人同时因自己的疾病法术而感到痛苦",
        },
        {
            "level": 4, "name": "绝望",
            "abilities": ["大面积传染疾病", "灾难传播", "绝望制造"],
            "required_actions": ["传播灾难", "制造绝望"],
            "ritual": "让一座城市陷入彻底的绝望，至少一半居民放弃希望",
            "special": "晋升导致雄性强制变雌性",
        },
        {
            "level": 3, "name": "不老",
            "abilities": ["大幅寿命", "全阶段魅力", "青春永驻", "复生", "石化", "镜中穿梭"],
            "required_actions": ["保持不老", "镜中旅行"],
            "ritual": "在镜之世界中度过一百年而不被自己的倒影吞噬",
            "special": "晋升导致雄性强制变雌性",
        },
        {
            "level": 2, "name": "灾难",
            "abilities": ["陨石召唤", "地震", "海啸", "火山爆发"],
            "required_actions": ["制造天灾", "毁灭城市"],
            "ritual": "同时制造陨石、地震、海啸三种天灾摧毁一座百万人口城市",
            "special": "晋升导致雄性强制变雌性",
        },
        {
            "level": 1, "name": "末日",
            "abilities": ["末日场景", "文明终结"],
            "required_actions": ["制造末日", "终结文明"],
            "ritual": "在一定领域内制造末日一般的场景并持续七天",
            "special": "晋升导致雄性强制变雌性",
        },
        {
            "level": 0, "name": "混沌魔女",
            "abilities": ["发为蛇", "万物阴性化", "全境石化"],
            "required_actions": ["成为混沌阴性之源"],
            "ritual": "集齐混沌魔女唯一性与末日非凡特性",
            "special": "晋升导致雄性强制变雌性",
        },
    ],
}

# -------------------------------------------------------
# 权柄体系九：光之钥
# -------------------------------------------------------

PATHWAYS["wheel_of_fortune"] = {
    "name": "命运之轮",
    "tarot": "命运之轮",
    "group": "key_of_light",
    "gender_change": [],
    "sequences": [
        {
            "level": 9, "name": "怪物",
            "abilities": ["灵感极高", "未来画面", "危险直觉"],
            "required_actions": ["接受异常感知", "预知未来碎片"],
        },
        {
            "level": 8, "name": "机器",
            "abilities": ["恐怖计算力", "精准控制", "格斗天赋", "射击天赋", "占卜", "反占卜"],
            "required_actions": ["精确计算", "精准行动"],
        },
        {
            "level": 7, "name": "幸运者",
            "abilities": ["被动幸运", "幸运波动"],
            "required_actions": ["享受好运", "节制幸运"],
            "special": "幸运不固定有高低起伏，很难完全依靠",
        },
        {
            "level": 6, "name": "灾祸教士",
            "abilities": ["灾祸预见", "环境适应", "精神风暴"],
            "required_actions": ["预见灾祸", "制造精神风暴"],
        },
        {
            "level": 5, "name": "赢家",
            "abilities": ["幸运掌控", "直觉预判", "厄运给予"],
            "required_actions": ["积累幸运", "在关键时刻翻盘"],
            "ritual": "在完全不利的局面中凭借幸运翻盘获胜",
        },
        {
            "level": 4, "name": "厄运法师",
            "abilities": ["好运施加", "厄运施加"],
            "required_actions": ["改变他人运势", "施加厄运"],
            "ritual": "让一位幸运之人经历连续一个月的厄运",
        },
        {
            "level": 3, "name": "混乱行者",
            "abilities": ["混乱行走", "命运扰动"],
            "required_actions": ["在混乱中行走", "扰动命运"],
            "ritual": "在命运的乱流中行走而不迷失自我",
        },
        {
            "level": 2, "name": "先知",
            "abilities": ["预知未来", "命运视界"],
            "required_actions": ["预知一系列未来"],
            "ritual": "直接预知一百年后的世界图景",
        },
        {
            "level": 1, "name": "巨蛇",
            "abilities": ["命运重置", "影响消除"],
            "required_actions": ["重置命运", "消除影响"],
            "ritual": "重置一个区域内一段时间的部分或所有人的命运",
        },
        {
            "level": 0, "name": "命运之轮",
            "abilities": ["命运化身", "概率主宰"],
            "required_actions": ["成为命运本身"],
            "ritual": "集齐命运之轮唯一性与巨蛇非凡特性",
        },
    ],
}

# ============================================================
# 便利工具函数
# ============================================================

def get_pathway(pathway_key: str) -> dict:
    """获取途径完整数据"""
    if pathway_key not in PATHWAYS:
        raise KeyError(f"未知途径: {pathway_key}")
    return PATHWAYS[pathway_key]

def get_sequence_data(pathway_key: str, level: int) -> dict:
    """获取特定序列数据"""
    pathway = get_pathway(pathway_key)
    for seq in pathway["sequences"]:
        if seq["level"] == level:
            return seq
    raise KeyError(f"途径 {pathway_key} 无序列 {level}")

def get_all_pathway_keys() -> list:
    """获取所有途径key"""
    return list(PATHWAYS.keys())

def get_pathways_in_group(group_key: str) -> list:
    """获取某途径组内所有途径"""
    if group_key not in PATHWAY_GROUPS:
        raise KeyError(f"未知途径组: {group_key}")
    return PATHWAY_GROUPS[group_key]["pathways"]

def get_interchange_at(pathway_key: str) -> int | None:
    """获取途径可互换的最小等级"""
    pathway = get_pathway(pathway_key)
    group_key = pathway["group"]
    return PATHWAY_GROUPS[group_key]["interchange_at"]

def get_compatible_pathways(pathway_key: str) -> list:
    """获取当前途径可互换的途径列表（不含自身）"""
    pathway = get_pathway(pathway_key)
    group_key = pathway["group"]
    all_in_group = PATHWAY_GROUPS[group_key]["pathways"]
    return [k for k in all_in_group if k != pathway_key]

def needs_ritual(level: int) -> bool:
    """判断该等级是否需要晋升仪式"""
    return level <= RITUAL_START_LEVEL

def will_gender_change(pathway_key: str, level: int) -> bool:
    """判断晋升到该等级是否会改变性别"""
    pathway = get_pathway(pathway_key)
    return level in pathway.get("gender_change", [])

def get_gender_change_message(pathway_key: str, level: int) -> str | None:
    """获取性别转换提示信息"""
    pathway = get_pathway(pathway_key)
    gender_changes = pathway.get("gender_change", [])
    if level in gender_changes:
        seq = get_sequence_data(pathway_key, level)
        target_gender = seq.get("special", "")
        if "雄性" in target_gender or "雌性" in target_gender:
            return target_gender
        # 通用推断
        if pathway_key in ("red_priest",):
            return "晋升导致雌性强制变雄性"
        if pathway_key in ("chaos_witch", "mother", "moon"):
            return "晋升导致雌性强制变雌性"
    return None


# ============================================================
# 魔药配方推导（E1）
# ============================================================
def get_potion_formula(pathway_key: str, level: int) -> dict:
    """返回晋升到指定序列 level 所需的魔药配方。

    配方 = 主材料（对应序列非凡特性）+ 若干辅助材料（随等级变化，主题取自
    POTION_MATERIALS 材料池）。低序列 1 份辅助材料，中序列 2 份，高序列 3 份。

    返回: {"main": str, "supplementary": list[str], "pathway_key": str, "level": int}
    """
    seq = get_sequence_data(pathway_key, level)
    pool = POTION_MATERIALS.get(pathway_key, DEFAULT_MATERIALS)
    main = f"{seq['name']}非凡特性"
    # 辅助材料数量：低序列(≥8)1 份，中序列(5~7)2 份，高序列(≤4)3 份
    n = 1 if level >= 8 else (2 if level >= 5 else 3)
    sup = [pool[(level + i) % len(pool)] for i in range(n)]
    return {"main": main, "supplementary": sup, "pathway_key": pathway_key, "level": level}
