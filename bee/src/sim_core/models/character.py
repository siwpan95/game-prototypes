# -*- coding: utf-8 -*-
"""角色数据模型 — 种族/职业/技能支持从 Excel 动态加载"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional


# ============================================================
# 种族数据模型
# ============================================================

@dataclass
class RaceData:
    """种族数据（可从 Excel 加载，也可硬编码回退）"""
    race_id: str          # 内部ID，如 "HUMAN"
    display_name: str     # 显示名，如 "人类"
    description: str      # 种族描述
    stat_mods: Dict[str, int]  # 属性修正 {"str": 1, "dex": 1, ...}

    @property
    def value(self):
        """兼容旧 Enum 接口: (display_name, description, stat_mods)"""
        return (self.display_name, self.description, self.stat_mods)

    @property
    def name(self):
        """兼容旧代码中 .race.name 用于序列化的行为 → 返回 race_id"""
        return self.race_id


# ============================================================
# 职业数据模型
# ============================================================

@dataclass
class ClassData:
    """职业数据（可从 Excel 加载，也可硬编码回退）"""
    class_id: str          # 内部ID，如 "WARRIOR"
    display_name: str      # 显示名，如 "战士"
    category_name: str     # 分类名，如 "战士"
    base_hp: int           # 基础 HP，如 12
    primary_stats: List[str]  # 主属性，如 ["strength", "constitution"]

    @property
    def value(self):
        """兼容旧 Enum 接口: (display_name, category_name)"""
        return (self.display_name, self.category_name)

    @property
    def name(self):
        """兼容旧代码中 .char_class.name 用于序列化的行为 → 返回 class_id"""
        return self.class_id

    @property
    def base_attack(self):
        """基础攻击力（用于角色创建预览）"""
        # 战士类职业基础攻击力更高
        martial = {"WARRIOR", "BARBARIAN", "PALADIN", "RANGER"}
        agile = {"ROGUE", "MONK", "DRUID"}
        caster = {"MAGE", "CLERIC", "WARLOCK"}
        if self.class_id in martial:
            return 8
        elif self.class_id in agile:
            return 6
        elif self.class_id in caster:
            return 4
        return 5


# ============================================================
# 种族注册表（兼容旧 Race 枚举接口）
# ============================================================

class _RaceRegistry:
    """动态种族注册表，支持 for r in Race / Race.HUMAN / list(Race)"""

    _list: List[RaceData] = []
    _by_id: Dict[str, RaceData] = {}
    _by_display: Dict[str, RaceData] = {}
    _initialized: bool = False

    @classmethod
    def _ensure_fallback(cls):
        """加载硬编码回退数据（Excel 不可用时）"""
        if cls._initialized:
            return

        fallback = [
            ("HUMAN",      "人类",   "适应力强",           {"str":  1, "dex":  1, "con":  1, "int":  1, "wis":  1, "cha":  1}),
            ("ELF",        "精灵",   "敏捷与智力出众",     {"str": -1, "dex":  2, "con": -1, "int":  2, "wis":  1, "cha":  0}),
            ("DWARF",      "矮人",   "体质与力量见长",     {"str":  2, "dex": -1, "con":  2, "int": -1, "wis":  1, "cha": -1}),
            ("HALFLING",   "半身人", "幸运与敏捷并存",     {"str": -2, "dex":  2, "con":  0, "int":  1, "wis":  0, "cha":  2}),
            ("GNOME",      "侏儒",   "智力与感知出众",     {"str": -2, "dex":  1, "con":  0, "int":  2, "wis":  0, "cha":  1}),
            ("HALFORC",    "半兽人", "力量与体质混合",     {"str":  2, "dex":  0, "con":  1, "int": -2, "wis": -1, "cha": -1}),
            ("TIEFFLING",  "提夫林", "魅力与智力兼具",     {"str":  0, "dex":  1, "con":  0, "int":  1, "wis": -1, "cha":  2}),
            ("DRAGONBORN", "龙裔",   "力量与魅力并存",     {"str":  2, "dex":  0, "con":  1, "int": -1, "wis":  0, "cha":  1}),
        ]
        for rid, dname, desc, mods in fallback:
            rd = RaceData(race_id=rid, display_name=dname, description=desc, stat_mods=mods.copy())
            cls._list.append(rd)
            cls._by_id[rid] = rd
            cls._by_display[dname] = rd
        cls._initialized = True

    @classmethod
    def load_from_config(cls, configs: List[dict]):
        """从 Excel 配置加载种族数据（兼容中/英文字段名）"""
        cls._list.clear()
        cls._by_id.clear()
        cls._by_display.clear()
        for cfg in configs:
            race_id = str(cfg.get("race_id") or cfg.get("种族ID") or "").strip()
            display_name = str(cfg.get("display_name") or cfg.get("名称") or "").strip()
            if not race_id:
                continue
            if not display_name:
                display_name = race_id
            rd = RaceData(
                race_id=race_id,
                display_name=display_name,
                description=str(cfg.get("description") or "").strip(),
                stat_mods={
                    "str": int(cfg.get("str_mod", 0)),
                    "dex": int(cfg.get("dex_mod", 0)),
                    "con": int(cfg.get("con_mod", 0)),
                    "int": int(cfg.get("int_mod", 0)),
                    "wis": int(cfg.get("wis_mod", 0)),
                    "cha": int(cfg.get("cha_mod", 0)),
                },
            )
            cls._list.append(rd)
            cls._by_id[race_id] = rd
            cls._by_display[display_name] = rd
        cls._initialized = True

    # ---- 迭代接口 ----
    def __iter__(self):
        self._ensure_fallback()
        return iter(self._list)

    def __len__(self):
        self._ensure_fallback()
        return len(self._list)

    # ---- 属性访问 Race.HUMAN ----
    def __getattr__(self, name):
        if name.startswith('_'):
            raise AttributeError(name)
        self._ensure_fallback()
        item = self._by_id.get(name)
        if item is not None:
            return item
        raise AttributeError(f"未知种族ID: {name}")

    def __repr__(self):
        self._ensure_fallback()
        return f"<RaceRegistry({len(self._list)}个种族)>"


# 模块级单例 — 兼容 from src.app.models.character import Race
Race = _RaceRegistry()


# ============================================================
# 职业注册表（兼容旧 CharClass 枚举接口）
# ============================================================

class _ClassRegistry:
    """动态职业注册表，支持 for c in CharClass / CharClass.WARRIOR / list(CharClass)"""

    _list: List[ClassData] = []
    _by_id: Dict[str, ClassData] = {}
    _by_display: Dict[str, ClassData] = {}
    _initialized: bool = False

    @classmethod
    def _ensure_fallback(cls):
        """加载硬编码回退数据"""
        if cls._initialized:
            return

        fallback = [
            ("WARRIOR",   "战士",   "战士",   12, ["strength",     "constitution"]),
            ("MAGE",      "法师",   "法师",    6, ["intelligence"]),
            ("CLERIC",    "牧师",   "牧师",    8, ["wisdom",       "charisma"]),
            ("ROGUE",     "盗贼",   "盗贼",    8, ["dexterity",    "intelligence"]),
            ("RANGER",    "游侠",   "游侠",   10, ["dexterity",    "wisdom"]),
            ("PALADIN",   "圣骑士", "圣骑士", 10, ["strength",     "charisma"]),
            ("WARLOCK",   "术士",   "术士",    8, ["charisma",     "constitution"]),
            ("MONK",      "武僧",   "武僧",    8, ["dexterity",    "wisdom"]),
            ("DRUID",     "德鲁伊", "德鲁伊",  8, ["wisdom",       "constitution"]),
            ("BARBARIAN", "野蛮人", "野蛮人", 12, ["strength",     "constitution"]),
        ]
        for cid, dname, cname, hp, pstats in fallback:
            cd = ClassData(class_id=cid, display_name=dname, category_name=cname,
                           base_hp=hp, primary_stats=pstats.copy())
            cls._list.append(cd)
            cls._by_id[cid] = cd
            cls._by_display[dname] = cd
        cls._initialized = True

    @classmethod
    def load_from_config(cls, configs: List[dict]):
        """从 Excel 配置加载职业数据（兼容中/英文字段名）"""
        cls._list.clear()
        cls._by_id.clear()
        cls._by_display.clear()
        for cfg in configs:
            class_id = str(cfg.get("class_id") or cfg.get("职业ID") or "").strip()
            if not class_id:
                continue
            display_name = str(cfg.get("display_name") or cfg.get("名称") or "").strip()
            if not display_name:
                display_name = class_id
            category_name = str(cfg.get("category_name") or cfg.get("分类名") or "").strip()
            if not category_name:
                category_name = display_name
            base_hp = int(cfg.get("base_hp") or cfg.get("基础HP") or 8)
            p1 = str(cfg.get("primary_stat1") or cfg.get("主属性1") or "").strip()
            p2 = str(cfg.get("primary_stat2") or cfg.get("主属性2") or "").strip()
            primary = [s for s in [p1, p2] if s]
            cd = ClassData(
                class_id=class_id,
                display_name=display_name,
                category_name=category_name,
                base_hp=base_hp,
                primary_stats=primary,
            )
            cls._list.append(cd)
            cls._by_id[class_id] = cd
            cls._by_display[display_name] = cd
        cls._initialized = True

    # ---- 迭代接口 ----
    def __iter__(self):
        self._ensure_fallback()
        return iter(self._list)

    def __len__(self):
        self._ensure_fallback()
        return len(self._list)

    # ---- 属性访问 CharClass.WARRIOR ----
    def __getattr__(self, name):
        if name.startswith('_'):
            raise AttributeError(name)
        self._ensure_fallback()
        item = self._by_id.get(name)
        if item is not None:
            return item
        raise AttributeError(f"未知职业ID: {name}")

    def __repr__(self):
        self._ensure_fallback()
        return f"<ClassRegistry({len(self._list)}个职业)>"


# 模块级单例 — 兼容 from src.app.models.character import CharClass
CharClass = _ClassRegistry()


# ============================================================
# 技能定义（可从 Excel 加载，也可硬编码回退）
# ============================================================

# 硬编码回退 — 每个职业 3 个技能
_FALLBACK_SKILL_DEFS = {
    "WARRIOR": [
        {"name": "猛击", "description": "强力一击，伤害×1.5", "effect_type": "damage_multiplier", "effect_value": 1.5, "cooldown": 3.0, "level_req": 1},
        {"name": "防御姿态", "description": "防御提高50%", "effect_type": "defense_buff", "effect_value": 0.5, "cooldown": 30.0, "level_req": 5},
        {"name": "旋风斩", "description": "范围攻击×1.2", "effect_type": "area_damage", "effect_value": 1.2, "cooldown": 15.0, "level_req": 10},
    ],
    "MAGE": [
        {"name": "火球术", "description": "发射火球，法术伤害×1.8", "effect_type": "magic_damage", "effect_value": 1.8, "cooldown": 2.5, "level_req": 1},
        {"name": "冰锥术", "description": "喷射冰锥，减速敌人", "effect_type": "magic_damage_slow", "effect_value": 1.2, "cooldown": 4.0, "level_req": 5},
        {"name": "闪电链", "description": "闪电弹射×2.0", "effect_type": "lightning_chain", "effect_value": 2.0, "cooldown": 8.0, "level_req": 10},
    ],
    "CLERIC": [
        {"name": "治疗术", "description": "恢复生命", "effect_type": "heal", "effect_value": 1.0, "cooldown": 5.0, "level_req": 1},
        {"name": "神圣之光", "description": "神圣伤害×1.5", "effect_type": "holy_damage", "effect_value": 1.5, "cooldown": 8.0, "level_req": 5},
        {"name": "庇护所", "description": "防护罩减伤50%", "effect_type": "shield", "effect_value": 0.5, "cooldown": 20.0, "level_req": 10},
    ],
    "ROGUE": [
        {"name": "背刺", "description": "背后暴击×2.0", "effect_type": "damage_multiplier", "effect_value": 2.0, "cooldown": 4.0, "level_req": 1},
        {"name": "毒刃", "description": "涂毒持续伤害", "effect_type": "poison", "effect_value": 0.3, "cooldown": 12.0, "level_req": 5},
        {"name": "隐身", "description": "潜行必暴击", "effect_type": "stealth", "effect_value": 1.0, "cooldown": 30.0, "level_req": 10},
    ],
    "RANGER": [
        {"name": "精准射击", "description": "必中要害", "effect_type": "guaranteed_crit", "effect_value": 1.0, "cooldown": 6.0, "level_req": 1},
        {"name": "陷阱", "description": "放置陷阱", "effect_type": "trap", "effect_value": 1.0, "cooldown": 15.0, "level_req": 5},
        {"name": "野兽伙伴", "description": "召唤野兽助战", "effect_type": "summon", "effect_value": 1.0, "cooldown": 60.0, "level_req": 10},
    ],
    "PALADIN": [
        {"name": "审判", "description": "神圣审判×1.5", "effect_type": "holy_damage", "effect_value": 1.5, "cooldown": 5.0, "level_req": 1},
        {"name": "圣光术", "description": "治疗", "effect_type": "heal", "effect_value": 1.0, "cooldown": 8.0, "level_req": 5},
        {"name": "无敌", "description": "无敌3秒", "effect_type": "invincible", "effect_value": 3.0, "cooldown": 120.0, "level_req": 15},
    ],
    "BARBARIAN": [
        {"name": "狂暴", "description": "攻击×1.5 防御降低", "effect_type": "berserk", "effect_value": 1.5, "cooldown": 20.0, "level_req": 1},
        {"name": "斩杀", "description": "低血量额外伤害×2", "effect_type": "execute", "effect_value": 2.0, "cooldown": 5.0, "level_req": 5},
        {"name": "战吼", "description": "全体buff+30%", "effect_type": "battle_cry", "effect_value": 0.3, "cooldown": 30.0, "level_req": 10},
    ],
    "WARLOCK": [
        {"name": "暗影箭", "description": "暗影伤害×1.5", "effect_type": "shadow_damage", "effect_value": 1.5, "cooldown": 2.5, "level_req": 1},
        {"name": "生命汲取", "description": "吸血50%伤害", "effect_type": "life_drain", "effect_value": 0.5, "cooldown": 4.0, "level_req": 5},
        {"name": "恶魔召唤", "description": "召唤恶魔", "effect_type": "summon_demon", "effect_value": 1.0, "cooldown": 60.0, "level_req": 10},
    ],
    "MONK": [
        {"name": "疾风连击", "description": "连续攻击×1.3", "effect_type": "flurry", "effect_value": 1.3, "cooldown": 3.0, "level_req": 1},
        {"name": "振魂掌", "description": "真气伤害×1.5", "effect_type": "chi_damage", "effect_value": 1.5, "cooldown": 6.0, "level_req": 5},
        {"name": "金钟罩", "description": "减伤80%", "effect_type": "shield", "effect_value": 0.8, "cooldown": 45.0, "level_req": 10},
    ],
    "DRUID": [
        {"name": "变形术", "description": "变熊+生存", "effect_type": "shape_shift", "effect_value": 1.0, "cooldown": 10.0, "level_req": 1},
        {"name": "荆棘术", "description": "缠绕敌人", "effect_type": "entangle", "effect_value": 1.0, "cooldown": 8.0, "level_req": 5},
        {"name": "自然之怒", "description": "自然伤害×2.0", "effect_type": "nature_wrath", "effect_value": 2.0, "cooldown": 20.0, "level_req": 10},
    ],
}

# 全局技能定义字典 {class_id: [skill_dicts]}
CLASS_SKILL_DEFS: Dict[str, List[dict]] = {}
_skill_defs_loaded = False


def _ensure_skill_defs():
    """确保技能定义已初始化（回退到硬编码）"""
    global _skill_defs_loaded
    if _skill_defs_loaded:
        return
    if not CLASS_SKILL_DEFS:
        CLASS_SKILL_DEFS.update({k: [s.copy() for s in v] for k, v in _FALLBACK_SKILL_DEFS.items()})
    _skill_defs_loaded = True


def load_skill_defs_from_config(configs: List[dict]):
    """从 Excel 配置加载技能定义（兼容中/英文字段名）"""
    global _skill_defs_loaded
    CLASS_SKILL_DEFS.clear()
    for cfg in configs:
        class_id = str(cfg.get("class_id") or cfg.get("所属职业") or "").strip()
        if not class_id:
            continue
        skill = {
            "name": str(cfg.get("name") or cfg.get("名称") or "").strip(),
            "description": str(cfg.get("description") or "").strip(),
            "effect_type": str(cfg.get("effect_type") or "").strip(),
            "effect_value": float(cfg.get("effect_value", 1.0)),
            "cooldown": float(cfg.get("cooldown", 5.0)),
            "level_req": int(cfg.get("level_req", 1)),
        }
        CLASS_SKILL_DEFS.setdefault(class_id, []).append(skill)
    _skill_defs_loaded = True


# ============================================================
# 角色属性 & 技能数据类型
# ============================================================

@dataclass
class CharacterStats:
    """角色六维属性"""
    strength: int = 10
    dexterity: int = 10
    constitution: int = 10
    intelligence: int = 10
    wisdom: int = 10
    charisma: int = 10

    @staticmethod
    def generate_for_class_race(cls_obj, race_obj):
        """生成角色创建预览属性（用于人物创建界面）"""
        import random as _random
        rng = _random.Random()

        # 基础 + 种族修正
        base_stats = {
            "strength":     10 + race_obj.stat_mods.get("str", 0),
            "dexterity":    10 + race_obj.stat_mods.get("dex", 0),
            "constitution": 10 + race_obj.stat_mods.get("con", 0),
            "intelligence": 10 + race_obj.stat_mods.get("int", 0),
            "wisdom":       10 + race_obj.stat_mods.get("wis", 0),
            "charisma":     10 + race_obj.stat_mods.get("cha", 0),
        }

        # 职业主属性 +2
        for stat in cls_obj.primary_stats:
            if stat in base_stats:
                base_stats[stat] += 2

        # 随机微调
        for stat in base_stats:
            base_stats[stat] += rng.randint(-1, 2)
            base_stats[stat] = max(3, min(30, base_stats[stat]))

        return CharacterStats(**base_stats)


@dataclass
class Skill:
    """技能"""
    name: str
    description: str
    effect_type: str  # magic_damage / heal / buff / etc.
    effect_value: float
    cooldown: float
    current_cooldown: float = 0.0
    level_req: int = 1

    def use(self):
        self.current_cooldown = self.cooldown

    def tick(self, dt: float):
        if self.current_cooldown > 0:
            self.current_cooldown = max(0.0, self.current_cooldown - dt)

    def is_ready(self) -> bool:
        return self.current_cooldown <= 0


# ============================================================
# 角色数据模型
# ============================================================

@dataclass
class Character:
    """角色数据模型"""
    name: str
    race: RaceData          # 种族（动态对象）
    char_class: ClassData   # 职业（动态对象）
    level: int = 1
    exp: int = 0
    exp_to_next: int = 100
    hp: int = 100
    max_hp: int = 100
    mp: int = 50
    max_mp: int = 50
    gold: int = 0
    stats: CharacterStats = field(default_factory=CharacterStats)
    skills: List[Skill] = field(default_factory=list)
    equipment: Dict[str, Optional[object]] = field(default_factory=dict)
    inventory: List[object] = field(default_factory=list)
    kills: int = 0
    deaths: int = 0
    quests_completed: int = 0
    total_play_time: float = 0.0
    base_attack_bonus: int = 0     # 永久攻击加成（配方合成 attack_boost 产出）
    buffs: Dict[str, float] = field(default_factory=dict)

    _STAT_MAP = {"str": "strength", "dex": "dexterity", "con": "constitution",
                  "int": "intelligence", "wis": "wisdom", "cha": "charisma"}

    @classmethod
    def create(cls, name: str, race, char_class, seed: int = None) -> "Character":
        """工厂方法：创建角色并应用种族和职业加成"""
        import random as _random
        rng = _random.Random(seed) if seed is not None else _random

        # 基础属性 + 种族修正
        base = {"strength": 10, "dexterity": 10, "constitution": 10,
                "intelligence": 10, "wisdom": 10, "charisma": 10}
        for stat_abbr, bonus in race.stat_mods.items():
            full = cls._STAT_MAP.get(stat_abbr, stat_abbr)
            if full in base:
                base[full] += bonus

        # 职业主属性 +2
        for stat_name in char_class.primary_stats:
            if stat_name in base:
                base[stat_name] += 2

        # 随机微调 ±1~2
        for stat in base:
            base[stat] += rng.randint(-1, 2)

        # 限制范围
        for stat in list(base):
            base[stat] = max(3, min(30, base[stat]))

        stats = CharacterStats(**base)

        # 计算 HP/MP
        s = stats
        max_hp = char_class.base_hp + s.constitution * 2
        max_mp = 10 + s.intelligence + s.wisdom

        # 初始化技能
        skills = cls._init_skills(char_class.class_id, 1, rng)

        char = cls(
            name=name,
            race=race,
            char_class=char_class,
            stats=stats,
            max_hp=max_hp,
            hp=max_hp,
            max_mp=max_mp,
            mp=max_mp,
            skills=skills,
            exp_to_next=int(1 ** 2 * 50 + 50),
        )
        return char

    @staticmethod
    def calc_max_hp(constitution: int, class_hp_bonus: int = 8) -> int:
        """根据体质和职业HP加成计算最大生命值"""
        return class_hp_bonus + constitution * 2

    @staticmethod
    def _init_skills(class_id: str, level: int, rng) -> list:
        """初始化角色技能"""
        _ensure_skill_defs()
        skills = []
        for skill_def in CLASS_SKILL_DEFS.get(class_id, []):
            if skill_def["level_req"] <= level:
                skills.append(Skill(**skill_def))
        return skills

    # ======== 战斗/属性方法 ========

    def get_attack_power(self) -> int:
        """计算攻击力"""
        weapon = self.equipment.get("WEAPON")
        base = weapon.damage if weapon and hasattr(weapon, "damage") else 5 + self.level // 2
        base += getattr(self, "base_attack_bonus", 0)  # 配方合成的永久攻击加成
        bonus = self.stats.strength // 2
        mult = self.buffs.get("damage_multiplier", 1.0)
        bonus += int((mult - 1.0) * base)
        return max(1, int(base + bonus))

    def get_defense(self) -> int:
        """计算防御力"""
        total = 0
        for slot in ["HEAD", "CHEST", "HANDS", "LEGS", "FEET"]:
            item = self.equipment.get(slot)
            if item and hasattr(item, "defense"):
                total += item.defense
        bonus = self.stats.constitution // 3 + self.stats.dexterity // 5
        return max(1, total + bonus)

    def take_damage(self, damage: int) -> int:
        """受到伤害，返回实际伤害值
        
        闭环关键：保底 1 点伤害，确保 DDA 能感知死亡风险。
        公式：actual = max(1, raw_damage - defense // 3)
        硬核肉鸽：阵亡即 HP=0，不自动复活。
        """
        actual = max(1, damage - self.get_defense() // 3)
        self.hp = max(0, self.hp - actual)
        if self.hp <= 0:
            self.deaths += 1
            self.hp = 0  # 硬核肉鸽：不复活
        return actual

    def heal(self, amount: int) -> int:
        """治疗，返回实际恢复量"""
        old = self.hp
        self.hp = min(self.max_hp, self.hp + amount)
        return self.hp - old

    def gain_exp(self, amount: int):
        """获得经验，触发升级"""
        self.exp += amount
        while self.exp >= self.exp_to_next:
            self.exp -= self.exp_to_next
            self.level += 1
            self.max_hp += 10
            self.hp = self.max_hp
            self.max_mp += 5
            self.mp = self.max_mp
            self.exp_to_next = int(self.level ** 2 * 50 + 50)
            # 检查新技能解锁
            for skill_def in CLASS_SKILL_DEFS.get(self.char_class.class_id, []):
                if skill_def["level_req"] == self.level:
                    self.skills.append(Skill(**skill_def))

    # ======== 装备方法 ========

    def can_equip(self, item) -> bool:
        """检查是否可以装备"""
        if not item or not hasattr(item, "level_req"):
            return False
        return item.level_req <= self.level

    def _get_equip_slot(self, item) -> Optional[str]:
        """获取物品对应的装备槽位键"""
        from .item import Weapon as WeaponModel, Armor as ArmorModel, Accessory as AccessoryModel
        if isinstance(item, WeaponModel):
            return "WEAPON"
        elif isinstance(item, ArmorModel):
            return item.slot.name if hasattr(item.slot, "name") else str(item.slot)
        elif isinstance(item, AccessoryModel):
            return item.slot.name if hasattr(item.slot, "name") else str(item.slot)
        return None

    def try_auto_equip(self, item) -> bool:
        """尝试自动装备物品，返回是否成功装备"""
        if not self.can_equip(item):
            return False

        slot = self._get_equip_slot(item)
        if slot is None:
            return False

        current = self.equipment.get(slot)
        # 比较品质：装备品质更高才替换
        if current and hasattr(current, "quality") and hasattr(item, "quality"):
            item_quality = item.quality.value[1]
            cur_quality = current.quality.value[1]
            if cur_quality > item_quality:
                return False
            if cur_quality == item_quality:
                if hasattr(current, "damage") and hasattr(item, "damage"):
                    if current.damage >= item.damage:
                        return False
                if hasattr(current, "defense") and hasattr(item, "defense"):
                    if current.defense >= item.defense:
                        return False

        self.equipment[slot] = item
        return True

    # ======== 序列化 ========

    def to_dict(self) -> dict:
        """序列化为字典 — 保存 race_id / class_id 便于跨版本兼容"""
        return {
            "name": self.name,
            "race": self.race.race_id,
            "char_class": self.char_class.class_id,
            "level": self.level,
            "exp": self.exp,
            "exp_to_next": self.exp_to_next,
            "hp": self.hp,
            "max_hp": self.max_hp,
            "mp": self.mp,
            "max_mp": self.max_mp,
            "gold": self.gold,
            "stats": {
                "strength": self.stats.strength,
                "dexterity": self.stats.dexterity,
                "constitution": self.stats.constitution,
                "intelligence": self.stats.intelligence,
                "wisdom": self.stats.wisdom,
                "charisma": self.stats.charisma,
            },
            "kills": self.kills,
            "deaths": self.deaths,
            "quests_completed": self.quests_completed,
            "total_play_time": self.total_play_time,
            "base_attack_bonus": self.base_attack_bonus,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Character":
        """从字典恢复角色"""
        _ensure_skill_defs()
        stats = CharacterStats(**data.get("stats", {}))

        # 通过注册表查找种族/职业（兼容旧存档中的 ID）
        race_id = data.get("race", "HUMAN")
        try:
            race = getattr(Race, race_id)
        except AttributeError:
            Race._ensure_fallback()
            race = Race._by_id.get(race_id, list(Race)[0])

        class_id = data.get("char_class", "WARRIOR")
        try:
            char_class = getattr(CharClass, class_id)
        except AttributeError:
            CharClass._ensure_fallback()
            char_class = CharClass._by_id.get(class_id, list(CharClass)[0])

        return cls(
            name=data["name"],
            race=race,
            char_class=char_class,
            level=data.get("level", 1),
            exp=data.get("exp", 0),
            exp_to_next=data.get("exp_to_next", 100),
            hp=data.get("hp", 100),
            max_hp=data.get("max_hp", 100),
            mp=data.get("mp", 50),
            max_mp=data.get("max_mp", 50),
            gold=data.get("gold", 0),
            stats=stats,
            kills=data.get("kills", 0),
            deaths=data.get("deaths", 0),
            quests_completed=data.get("quests_completed", 0),
            total_play_time=data.get("total_play_time", 0.0),
            base_attack_bonus=int(data.get("base_attack_bonus", 0) or 0),
        )


# ============================================================
# 组队系统
# ============================================================

class Party:
    """队伍管理 — 主角 + 队友"""

    MAX_MEMBERS = 4

    def __init__(self, hero: Character):
        self.hero = hero          # 主角（主要角色）
        self.members: List[Character] = [hero]  # 队伍列表，第一个永远是主角

    @property
    def party_size(self) -> int:
        return len(self.members)

    @property
    def is_full(self) -> bool:
        return len(self.members) >= self.MAX_MEMBERS

    def add_member(self, char: Character) -> bool:
        """添加队友，返回是否成功"""
        if self.is_full:
            return False
        self.members.append(char)
        return True

    def remove_member(self, char: Character) -> bool:
        """移除队友（主角不可移除）"""
        if char == self.hero:
            return False
        self.members.remove(char)
        return True

    def replace_member(self, old: Character, new: Character) -> bool:
        """替换队友"""
        if old == self.hero:
            return False
        self.members[self.members.index(old)] = new
        return True

    def get_alive(self) -> List[Character]:
        """获取所有存活成员"""
        return [m for m in self.members if m.hp > 0]

    def get_defeated(self) -> List[Character]:
        """获取所有阵亡成员"""
        return [m for m in self.members if m.hp <= 0]

    def get_member_names(self) -> List[str]:
        """获取所有成员名字"""
        return [f"{m.char_class.display_name}·{m.name}" for m in self.members]


# ============================================================
# 统一初始化入口（由应用启动时调用）
# ============================================================

def init_race_class_config(data_service=None):
    """使用硬编码回退数据初始化种族/职业/技能配置（零 I/O）

    如需从 JSON 加载扩展数据（额外种族/职业/技能），
    调用 apply_json_config(data_service)。
    """
    Race._ensure_fallback()
    CharClass._ensure_fallback()
    _ensure_skill_defs()


def apply_json_config(data_service):
    """按需从 JSON 加载扩展的种族/职业/技能配置（随用随取）

    一般在首次需要完整数据时调用，例如角色创建界面打开时。
    """
    try:
        race_config = data_service.get_race_config()
        if race_config:
            _RaceRegistry.load_from_config(race_config)

        class_config = data_service.get_class_config()
        if class_config:
            _ClassRegistry.load_from_config(class_config)

        skill_config = data_service.get_skill_config()
        if skill_config:
            load_skill_defs_from_config(skill_config)
    except Exception as e:
        print(f"[Character] JSON 配置加载失败，使用回退数据: {e}")
