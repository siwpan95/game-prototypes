"""
Progress Quest v2 游戏引擎 — 对齐原版 PQ 数据模型。

核心改动：
- 6 Prime Stats（STR/CON/DEX/INT/WIS/CHA）
- 11 装备槽（新增肩甲）
- 指数升级曲线 1000 * 1.15^level
- 全自动角色创建（随机名/种族/职业/Roll属性）
- 装备随机命名系统
- 怪物变体系统
- 特殊宝物系统
- 强化死亡机制（不掉级，扣经验进度）
"""
import random
from dataclasses import dataclass, field
from typing import List, Dict, Optional

from data import (
    RACES, CLASSES, SPELL_NAMES, SPELL_TYPES,
    WEAPON_BASE, SHIELD_BASE, ARMOR_BASE,
    OFFENSE_POS, OFFENSE_NEG, DEFENSE_POS, DEFENSE_NEG, ITEM_OF,
    EQUIPMENT_SLOTS, WEAPON_SLOTS, SHIELD_SLOTS, ARMOR_SLOTS,
    generate_name, random_race, random_class,
    generate_weapon, generate_shield, generate_armor,
    generate_special, generate_shop_equipment,
    pick_monster_for_level as pq_pick_monster,
    random_spell as pq_random_spell,
)
from data.pq_races import RACE_BONUS_MAP
from data.pq_classes import CLASS_BONUS_MAP

# ==================== 基础数据类 ====================


@dataclass
class Item:
    name: str
    quantity: int = 1


@dataclass
class EquipmentItem:
    """带随机命名的装备"""
    name: str
    atk: int = 0
    def_: int = 0

    @property
    def total(self) -> int:
        return self.atk + self.def_


@dataclass
class Spell:
    name: str
    spell_type: str  # 伤害 / 治疗 / 增益 / 减益
    power: int
    mp_cost: int
    description: str = ""


@dataclass
class Quest:
    name: str
    target_type: str       # 收集 / 击杀
    target: str            # 目标名
    required: int
    reward_type: str       # 装备 / 属性 / 法术 / 金币
    reward_value: str
    current: int = 0
    completed: bool = False

    def progress_str(self) -> str:
        return f"{self.current}/{self.required}"


@dataclass
class ShopItem:
    name: str
    slot: str
    atk: int
    def_: int
    price: int

    @property
    def total(self) -> int:
        return self.atk + self.def_


@dataclass
class SpecialItem:
    """特殊宝物 — 任务奖励用，可卖出换金币"""
    name: str           # 完整名 "Golden Diadem of Fortune"
    base_name: str      # "Diadem"
    attribute: str      # "Golden"
    of_name: str        # "Fortune"
    value: int          # 卖价


# ==================== 头衔系统 ====================

NORMAL_TITLES = [
    "先生", "夫人", "爵士", "军士", "女士",
    "上尉", "酋长", "上将", "圣徒",
]

ADVANCED_TITLES = [
    "国王", "女王", "领主", "贵妇", "总督",
    "市长", "王子", "公主", "酋长",
    "头目", "大主教", "宰相", "男爵夫人", "审判官",
]


def random_normal_title() -> str:
    return random.choice(NORMAL_TITLES)


def random_advanced_title() -> str:
    return random.choice(ADVANCED_TITLES)


# ==================== 怪物 ====================


@dataclass
class Monster:
    name: str
    level: int = 1
    max_hp: int = 50
    hp: int = 50
    attack: int = 8
    defense: int = 3
    xp: int = 30
    loot_table: List[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict):
        return cls(
            name=data["name"],
            level=data.get("level", 1),
            max_hp=data.get("hp", 50),
            hp=data.get("hp", 50),
            attack=data.get("attack", 8),
            defense=data.get("defense", 3),
            xp=data.get("xp", 30),
            loot_table=data.get("loot_table", []),
        )

    @classmethod
    def spawn(cls, player_level: int):
        """生成一个适配玩家等级的怪物（带随机变体）"""
        result = pq_pick_monster(player_level)
        if result is None:
            # fallback
            return cls("巨鼠", 2, 40, 40, 5, 2, 20, ["鼠皮"])
        name, level, max_hp, attack, defense, xp, loot = result
        return cls(
            name=name, level=level,
            max_hp=max_hp, hp=max_hp,
            attack=attack, defense=defense,
            xp=xp, loot_table=loot,
        )


# ==================== 玩家 ====================


def roll_stats() -> dict:
    """Roll 6 属性：每项 3d6，上限 18"""
    return {
        "strength":     min(18, sum(random.randint(1, 6) for _ in range(3))),
        "constitution": min(18, sum(random.randint(1, 6) for _ in range(3))),
        "dexterity":    min(18, sum(random.randint(1, 6) for _ in range(3))),
        "intelligence": min(18, sum(random.randint(1, 6) for _ in range(3))),
        "wisdom":       min(18, sum(random.randint(1, 6) for _ in range(3))),
        "charisma":     min(18, sum(random.randint(1, 6) for _ in range(3))),
    }


def _apply_bonus(stats: dict, bonuses: dict, bonus_map: dict):
    """将 PQ 种族/职业加成应用到属性字典"""
    for key, val in bonuses.items():
        field = bonus_map.get(key, key.lower())
        if field in stats:
            stats[field] += val


@dataclass
class Player:
    name: str = "内比布"
    race: str = "鬼火精灵"
    klass: str = "符文博学者"
    title: str = ""
    level: int = 1
    xp: int = 0

    # 6 Prime Stats
    strength: int = 10
    constitution: int = 10
    dexterity: int = 10
    intelligence: int = 10
    wisdom: int = 10
    charisma: int = 10

    hp: int = 100
    max_hp: int = 100
    mp: int = 50
    max_mp: int = 50

    chapter: str = "第一章 — 序章"
    gold: int = 0
    current_act: str = ""

    # 11 装备槽
    equipment: Dict[str, EquipmentItem] = field(default_factory=dict)
    inventory: Dict[str, Item] = field(default_factory=dict)
    specials: List[SpecialItem] = field(default_factory=list)
    quests: List[Quest] = field(default_factory=list)
    spells: List[Spell] = field(default_factory=list)
    combat_log: List[str] = field(default_factory=list)

    # ---- 衍生属性 ----

    @property
    def xp_to_next(self) -> int:
        """PQ 公式：1000 * 1.15^level"""
        return max(10, int(1000 * (1.15 ** self.level)))

    @property
    def equip_atk(self) -> int:
        return sum(e.atk for e in self.equipment.values())

    @property
    def equip_def(self) -> int:
        return sum(e.def_ for e in self.equipment.values())

    @property
    def inv_count(self) -> int:
        return sum(item.quantity for item in self.inventory.values())

    @property
    def max_encumbrance(self) -> int:
        return self.strength * 2 + 5

    @property
    def dodge_chance(self) -> float:
        """敏捷提供闪避率"""
        return min(0.30, self.dexterity * 0.01)

    @property
    def spell_defense(self) -> int:
        """智慧提供法术防御"""
        return self.wisdom // 3

    # ========== 工厂方法 ==========

    @staticmethod
    def _safe_int(value, default: int = 0) -> int:
        try:
            return int(value)
        except (ValueError, TypeError):
            return default

    @classmethod
    def auto_create(cls, seed=None):
        """
        完全自动创建角色：
        随机名字 + 随机种族 + 随机职业 + Roll 属性 + 初始装备 + 初始法术
        """
        if seed is not None:
            random.seed(seed)

        # 随机名字
        name = generate_name()

        # 随机种族
        race_name, race_bonus = random_race()

        # 随机职业
        klass_name, class_bonus = random_class()

        # Roll 属性
        stats = roll_stats()
        _apply_bonus(stats, race_bonus, RACE_BONUS_MAP)
        _apply_bonus(stats, class_bonus, CLASS_BONUS_MAP)

        p = cls(
            name=name,
            race=race_name,
            klass=klass_name,
            strength=stats["strength"],
            constitution=stats["constitution"],
            dexterity=stats["dexterity"],
            intelligence=stats["intelligence"],
            wisdom=stats["wisdom"],
            charisma=stats["charisma"],
        )

        # 初始 HP/MP 基于属性
        p.max_hp = int(p.constitution * 4.5 + 10 + 50)
        p.max_mp = int(p.intelligence * 4 + 10 + 30)
        p.hp = p.max_hp
        p.mp = p.max_mp

        # 给一件初始武器和一件初始护甲
        wn, wa = generate_weapon()
        p.equipment["武器"] = EquipmentItem(wn, atk=wa, def_=0)

        # 随机给一件护甲
        armor_slot = random.choice(list(ARMOR_SLOTS))
        an, ad = generate_armor()
        p.equipment[armor_slot] = EquipmentItem(an, atk=0, def_=ad)

        p.combat_log.append(f"🎲 {name} 诞生 — {race_name} {klass_name}")

        return p

    @classmethod
    def from_config(cls, player_config: dict, equipment: dict,
                    inventory: dict, quests: list):
        """
        从 Excel 配置创建角色（兼容旧版 config.xlsx）。
        旧版无 wisdom，自动设为 10；旧版 job→klass。
        注意：quests 不直接加载，由 _auto_fill_quests 从任务池中选择。
        """
        p = cls(
            name=str(player_config.get("姓名", "内比布")),
            race=str(player_config.get("种族", "鬼火精灵")),
            klass=str(player_config.get("职业",
                     player_config.get("klass", "符文博学者"))),
            level=cls._safe_int(player_config.get("等级", 1), 1),
            xp=cls._safe_int(player_config.get("经验", 0), 0),
            strength=cls._safe_int(player_config.get("力量", 10), 10),
            constitution=cls._safe_int(player_config.get("体质", 10), 10),
            dexterity=cls._safe_int(player_config.get("敏捷", 10), 10),
            intelligence=cls._safe_int(player_config.get("智力", 10), 10),
            wisdom=cls._safe_int(player_config.get("智慧", 10), 10),
            charisma=cls._safe_int(player_config.get("魅力", 10), 10),
            hp=cls._safe_int(player_config.get("HP", 100), 100),
            mp=cls._safe_int(player_config.get("MP", 50), 50),
            chapter=str(player_config.get("章节", "第一章 — 序章")),
        )
        p.max_hp = p.hp
        p.max_mp = p.mp

        # 装备
        for slot, d in equipment.items():
            p.equipment[slot] = EquipmentItem(
                d["name"], d.get("atk", 0), d.get("def", 0))

        # 背包
        p.inventory = {name: Item(name, qty)
                       for name, qty in inventory.items()}

        # 任务不在初始化时加载——由 _auto_fill_quests 从任务池中动态选取
        # 保留 quests 参数兼容性但不加载
        p.quests = []
        return p

    # ========== 存档 / 读档 ==========

    def to_save_dict(self) -> dict:
        return {
            "name": self.name,
            "race": self.race,
            "klass": self.klass,
            "title": self.title,
            "level": self.level,
            "xp": self.xp,
            "strength": self.strength,
            "constitution": self.constitution,
            "dexterity": self.dexterity,
            "intelligence": self.intelligence,
            "wisdom": self.wisdom,
            "charisma": self.charisma,
            "hp": self.hp,
            "max_hp": self.max_hp,
            "mp": self.mp,
            "max_mp": self.max_mp,
            "chapter": self.chapter,
            "gold": self.gold,
            "current_act": self.current_act,
            "equipment": {
                s: {"name": e.name, "atk": e.atk, "def": e.def_}
                for s, e in self.equipment.items()
            },
            "inventory": {k: v.quantity for k, v in self.inventory.items()},
            "specials": [
                {"name": s.name, "base_name": s.base_name,
                 "attribute": s.attribute, "of_name": s.of_name,
                 "value": s.value}
                for s in self.specials
            ],
            "quests": [
                {"name": q.name, "target_type": q.target_type,
                 "target": q.target, "required": q.required,
                 "reward_type": q.reward_type,
                 "reward_value": q.reward_value,
                 "current": q.current, "completed": q.completed}
                for q in self.quests
            ],
            "spells": [
                {"name": s.name, "spell_type": s.spell_type,
                 "power": s.power, "mp_cost": s.mp_cost,
                 "description": s.description}
                for s in self.spells
            ],
            "combat_log": self.combat_log[-50:],
            "version": 3,  # 标记版本号，用于兼容
        }

    @classmethod
    def from_save_dict(cls, data: dict):
        """从存档恢复，兼容旧存档（v1/v2 无 wisdom，job→klass）"""
        ver = data.get("version", 0)

        # 兼容旧 key
        klass = data.get("klass", data.get("job", "符文博学者"))

        p = cls(
            name=data["name"],
            race=data["race"],
            klass=klass,
            title=data.get("title", ""),
            level=data["level"],
            xp=data["xp"],
            strength=data["strength"],
            constitution=data["constitution"],
            dexterity=data["agility"] if "agility" in data and ver < 3
                     else data.get("dexterity", data.get("agility", 10)),
            intelligence=data["intelligence"],
            wisdom=data.get("wisdom", 10),  # 旧档无 wisdom
            charisma=data["charisma"],
            hp=data["hp"],
            max_hp=data["max_hp"],
            mp=data.get("mp", 50),
            max_mp=data.get("max_mp", 50),
            chapter=data.get("chapter", "第一章 — 序章"),
            gold=data.get("gold", 0),
            current_act=data.get("current_act", ""),
        )

        # 装备
        p.equipment = {
            s: EquipmentItem(d["name"], d.get("atk", 0), d.get("def", 0))
            for s, d in data.get("equipment", {}).items()
        }

        # 背包
        p.inventory = {
            n: Item(n, q) for n, q in data.get("inventory", {}).items()
        }

        # 特殊宝物
        p.specials = [
            SpecialItem(
                s["name"], s.get("base_name", ""),
                s.get("attribute", ""), s.get("of_name", ""),
                s.get("value", 100),
            )
            for s in data.get("specials", [])
        ]

        # 任务
        p.quests = [
            Quest(q["name"], q.get("target_type", "收集"), q["target"],
                  q["required"], q.get("reward_type", "金币"),
                  q.get("reward_value", "50"),
                  q.get("current", 0), q.get("completed", False))
            for q in data.get("quests", [])
        ]

        # 法术
        p.spells = [
            Spell(s["name"], s.get("spell_type", "伤害"),
                  s.get("power", 20), s.get("mp_cost", 10),
                  s.get("description", ""))
            for s in data.get("spells", [])
        ]

        p.combat_log = data.get("combat_log", [])
        return p

    # ========== 升级 ==========

    def gain_xp(self, amount: int):
        """获取经验，经验获取受 WIS 加成"""
        wisdom_bonus = 1.0 + self.wisdom * 0.02  # 每点 WIS +2%
        actual = int(amount * wisdom_bonus)
        self.xp += actual
        while self.xp >= self.xp_to_next:
            self.level_up()

    def level_up(self):
        """升级：指数 XP 曲线，六属性增长"""
        self.level += 1
        self.xp -= self.xp_to_next

        # 属性增长
        self.strength += random.randint(1, 3)
        self.constitution += random.randint(1, 3)
        self.dexterity += random.randint(1, 3)
        self.intelligence += random.randint(1, 3)
        self.wisdom += random.randint(1, 2)
        self.charisma += random.randint(1, 2)

        # 重新计算 HP/MP 上限
        self.max_hp = int(self.constitution * 4.5 + self.level * 5 + 50)
        self.max_mp = int(self.intelligence * 3 + self.level * 3 + 30)
        self.hp = self.max_hp
        self.mp = self.max_mp

        self.combat_log.append(f"🎉 升至 {self.level} 级！")
        self.check_title_upgrade()

    def check_title_upgrade(self):
        """检查是否获得头衔"""
        if self.level >= 45 and not self.title:
            self.title = random_advanced_title()
            self.combat_log.append(f"👑 获得高级头衔：{self.title}！")
        elif self.level >= 20 and not self.title:
            self.title = random_normal_title()
            self.combat_log.append(f"🎖️ 获得头衔：{self.title}！")

    # ========== 法术 ==========

    def learn_spell(self, spell: Spell):
        if any(s.name == spell.name for s in self.spells):
            self.combat_log.append(f"📖 {spell.name} 威力提升！")
            for s in self.spells:
                if s.name == spell.name:
                    s.power += int(s.power * 0.2)
                    s.mp_cost = max(1, s.mp_cost - 1)
                    break
        else:
            self.spells.append(spell)
            self.combat_log.append(f"✨ 学会新法术：{spell.name}！")

    def _try_cast_spell(self, monster: Monster) -> bool:
        """战斗中施法，WIS 提高施法概率"""
        if not self.spells or self.mp < 5:
            return False

        # WIS 提高施法概率：基础 30%，每点 WIS +1%，上限 50%
        cast_chance = min(0.50, 0.30 + self.wisdom * 0.01)
        if random.random() > cast_chance:
            return False

        spell = random.choice(self.spells)
        if self.mp < spell.mp_cost:
            return False

        self.mp -= spell.mp_cost

        if spell.spell_type == "伤害":
            dmg = spell.power + random.randint(0, self.intelligence // 2)
            # 怪物法术防御（用 level 模拟）
            dmg = max(1, dmg - monster.level // 5)
            monster.hp -= dmg
            self.combat_log.append(
                f"🔮 施放 {spell.name}，造成 {dmg} 点伤害 "
                f"(法力:{self.mp}/{self.max_mp})")
        elif spell.spell_type == "治疗":
            heal = min(spell.power, self.max_hp - self.hp)
            self.hp += heal
            self.combat_log.append(
                f"💚 施放 {spell.name}，恢复 {heal} 点生命 "
                f"(法力:{self.mp}/{self.max_mp})")
        elif spell.spell_type == "增益":
            # WIS 和 INT 强化增益效果
            boost = spell.power + self.intelligence // 4
            self.combat_log.append(
                f"⬆️ 施放 {spell.name}，攻击+{boost} "
                f"(法力:{self.mp}/{self.max_mp})")
        elif spell.spell_type == "减益":
            reduction = spell.power + self.wisdom // 4
            self.combat_log.append(
                f"⬇️ 施放 {spell.name}，敌人防御-{reduction} "
                f"(法力:{self.mp}/{self.max_mp})")
        return True

    # ========== 物品 / 任务 ==========

    def add_item(self, item_name: str, qty: int = 1):
        if item_name in self.inventory:
            self.inventory[item_name].quantity += qty
        else:
            self.inventory[item_name] = Item(item_name, qty)
        self._check_quest_progress(item_name, qty)

    def add_special(self, special: SpecialItem):
        """获得特殊宝物"""
        self.specials.append(special)
        self.combat_log.append(
            f"💎 获得特殊宝物：{special.name} (价值 {special.value}金币)")

    def _check_quest_progress(self, target: str, qty: int):
        """推进任务进度。
        收集任务：掉落物名精确匹配 quest.target
        击杀任务：怪物名包含 quest.target（如 "giant Kobold" 匹配 "Kobold"）
        """
        for quest in self.quests:
            if quest.completed:
                continue
            if quest.target_type == "收集":
                # 精确匹配掉落物品名
                if quest.target == target:
                    quest.current = min(quest.current + qty, quest.required)
                    if quest.current >= quest.required:
                        self._complete_quest(quest)
            elif quest.target_type == "击杀":
                # 子串匹配：任务目标 "Kobold" 匹配怪物名 "giant Kobold"
                if quest.target.lower() in target.lower():
                    quest.current = min(quest.current + 1, quest.required)
                    if quest.current >= quest.required:
                        self._complete_quest(quest)

    def _complete_quest(self, quest: Quest):
        quest.completed = True
        base_xp = 150 + sum(1 for q in self.quests if q.completed) * 10
        self.gain_xp(base_xp)
        self._apply_quest_reward(quest)
        self.combat_log.append(f"✅ 任务完成：{quest.name}")

    def _apply_quest_reward(self, quest: Quest):
        rt, rv = quest.reward_type, quest.reward_value
        if rt == "金币":
            amount = int(rv) if rv.isdigit() else 100
            self.gold += amount
            self.combat_log.append(f"💰 获得 {amount} 金币")
        elif rt == "装备":
            self.add_item(rv, 1)
            self.combat_log.append(f"🎁 获得装备：{rv}")
        elif rt == "特殊宝物":
            spec = generate_special()
            full_name, base, adj, of_name, value = spec
            self.add_special(SpecialItem(full_name, base, adj, of_name, value))
        elif rt == "属性":
            try:
                stat_name, delta = rv.split("+")
                delta = int(delta)
                if "全属性" in stat_name:
                    for attr in ["strength", "constitution", "dexterity",
                                 "intelligence", "wisdom", "charisma"]:
                        setattr(self, attr, getattr(self, attr) + delta)
                    self.combat_log.append(f"📈 {rv}")
                elif "力量" in stat_name:
                    self.strength += delta
                    self.combat_log.append(f"📈 {rv}")
                elif "体质" in stat_name:
                    self.constitution += delta
                    self.combat_log.append(f"📈 {rv}")
                elif "敏捷" in stat_name:
                    self.dexterity += delta
                    self.combat_log.append(f"📈 {rv}")
                elif "智力" in stat_name:
                    self.intelligence += delta
                    self.combat_log.append(f"📈 {rv}")
                elif "智慧" in stat_name:
                    self.wisdom += delta
                    self.combat_log.append(f"📈 {rv}")
                elif "魅力" in stat_name:
                    self.charisma += delta
                    self.combat_log.append(f"📈 {rv}")
            except Exception:
                self.combat_log.append(f"📈 属性提升：{rv}")
        elif rt == "法术":
            spell_data = pq_random_spell()
            spell = Spell(spell_data["name"], spell_data["spell_type"],
                          spell_data["power"], spell_data["mp_cost"],
                          spell_data["description"])
            self.learn_spell(spell)

    # ========== 战斗 ==========

    def combat_tick(self, monster: Monster) -> bool:
        """一回合战斗，WIS 影响法术防御，DEX 影响闪避"""
        # 尝试施法
        self._try_cast_spell(monster)

        # 玩家攻击
        player_atk = self.strength + self.equip_atk + random.randint(1, self.level)
        dmg = max(1, player_atk - monster.defense // 2)
        monster.hp -= dmg
        self.combat_log.append(
            f"⚔️ 对 {monster.name} 造成 {dmg} 点伤害 "
            f"[攻击:{self.strength}+{self.equip_atk}]")

        # 击杀
        if monster.hp <= 0:
            self.combat_log.append(
                f"💀 击败 {monster.name}，获得 {monster.xp} 经验值")
            self.gain_xp(monster.xp)
            for loot in monster.loot_table:
                if random.random() < 0.4:
                    self.add_item(loot)
                    self.combat_log.append(f"📦 获得 {loot}")
            self._check_quest_progress(monster.name, 1)
            return True

        # 敏捷闪避
        if random.random() < self.dodge_chance:
            self.combat_log.append(f"🌀 闪避 {monster.name} 的攻击！")
            return False

        # 怪物反击
        monster_atk = monster.attack + random.randint(1, monster.level)
        defense_value = (self.dexterity // 2 + self.equip_def // 3
                         + self.spell_defense)
        dmg_to_player = max(1, monster_atk - defense_value)
        self.hp -= dmg_to_player
        self.combat_log.append(
            f"💥 {monster.name} 反击造成 {dmg_to_player} 点伤害 "
            f"(生命:{self.hp}/{self.max_hp} 防御:{defense_value})")

        # 死亡
        if self.hp <= 0:
            self.die_and_revive()
        return False

    # ========== 死亡 ==========

    def die_and_revive(self):
        """
        死亡不掉级，损失当前经验进度的 25%，HP/MP 减半。
        随机一件装备耐久下降（ATK/DEF 降低）。
        """
        self.hp = max(1, self.max_hp // 2)
        self.mp = max(1, self.max_mp // 2)

        # 损失经验进度的 25%
        xp_loss = self.xp_to_next // 4
        self.xp = max(0, self.xp - xp_loss)

        # 随机一件装备受损
        if self.equipment:
            slot = random.choice(list(self.equipment.keys()))
            eq = self.equipment[slot]
            if eq.atk > 0:
                eq.atk = max(0, eq.atk - random.randint(1, 3))
            if eq.def_ > 0:
                eq.def_ = max(0, eq.def_ - random.randint(1, 3))
            self.combat_log.append(
                f"💀 不幸战死，经验损失 {xp_loss}，"
                f"{slot}({eq.name}) 受损")

    # ========== 城镇 / 经济 ==========

    def visit_town(self, shop_catalog: list = None):
        """
        自动回城：卖背包 + 卖特殊宝物 + 自动买更好装备。
        CHA 影响卖出价格（+CHA%）。
        """
        # 卖出背包物品
        total_sold = 0
        if self.inventory:
            cha_bonus = 1.0 + self.charisma * 0.03
            for item in list(self.inventory.values()):
                sell_price = max(1, int(item.quantity *
                                 random.randint(5, 15) * cha_bonus))
                total_sold += sell_price
            self.inventory.clear()

        # 卖出特殊宝物
        if self.specials:
            for s in list(self.specials):
                total_sold += s.value
            self.specials.clear()

        if total_sold > 0:
            self.gold += total_sold
            self.combat_log.append(
                f"🏘️ 回城补给：卖出获得 {total_sold} 金币 "
                f"(总资产: {self.gold})")
        else:
            self.combat_log.append("🏘️ 回城补给：背包已空")

        # 自动购买更好装备
        self._auto_buy_equipment(shop_catalog)

    def _auto_buy_equipment(self, shop_catalog: list = None):
        """自动购买装备：对于每个空槽或有总属性更低的槽位，购买更好的"""
        # 如果无商店目录，动态生成 PQ 风格商店物品
        if not shop_catalog:
            shop_catalog = [generate_shop_equipment() for _ in range(30)]

        bought = False
        for item_data in sorted(shop_catalog,
                                key=lambda x: x["atk"] + x["def"],
                                reverse=True):
            slot = item_data["slot"]
            price = item_data["price"]
            if price > self.gold:
                continue
            current = self.equipment.get(slot)
            current_total = current.total if current else -1
            new_total = item_data["atk"] + item_data["def"]
            if new_total > current_total:
                self.equipment[slot] = EquipmentItem(
                    item_data["name"], item_data["atk"], item_data["def"])
                self.gold -= price
                self.combat_log.append(
                    f"🛒 购买 {item_data['name']} "
                    f"[{slot}] 攻击+{item_data['atk']} 防御+{item_data['def']} "
                    f"({price}金币)")
                bought = True

        if not bought:
            self.combat_log.append("🛒 商店逛了一圈，没有更好的装备")

    # ========== 城镇等级折扣 ==========

    @property
    def shop_discount(self) -> float:
        """魅力提供商店折扣，每点 CHA 折扣 1%，上限 30%"""
        return min(0.30, self.charisma * 0.01)
