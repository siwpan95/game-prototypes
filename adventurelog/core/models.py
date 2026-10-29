# -*- coding: utf-8 -*-
"""游戏数据模型 — D&D 风格地牢探索"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional
import random


# ============================================================
# 种族
# ============================================================
@dataclass
class Race:
    name: str
    desc: str
    hp_mod: int = 0
    atk_mod: int = 0
    def_mod: int = 0
    spd_mod: int = 0
    mp_mod: int = 0


# ============================================================
# 职业
# ============================================================
@dataclass
class JobDef:
    name: str
    emoji: str
    color: str
    base_hp: int
    base_atk: int
    base_def: int
    base_spd: int
    initial_skills: List[str] = field(default_factory=list)


# ============================================================
# 技能
# ============================================================
@dataclass
class Skill:
    name: str
    desc: str
    skill_type: str   # "attack" / "heal" / "buff"
    power: float
    mp_cost: int = 0
    cooldown: int = 0
    cooldown_remaining: int = 0
    # --- 学习限制 ---
    job_limit: List[str] = field(default_factory=list)   # 空列表=无职业限制
    level_req: int = 0                                   # 最低等级，0=无要求
    stat_req: Dict[str, int] = field(default_factory=dict)  # e.g. {"atk":15,"mp":20}

    def reset_cd(self):
        self.cooldown_remaining = 0

    def can_learn(self, adv: "Adventurer", job_key: str) -> "tuple[bool, str]":
        """
        检查 adventurer 是否满足学习条件。
        返回 (可学?, 原因说明)
        """
        # 等级要求
        if self.level_req > 0 and adv.level < self.level_req:
            return False, f"需要 Lv.{self.level_req}（当前 Lv.{adv.level}）"

        # 职业限制
        if self.job_limit and job_key not in self.job_limit:
            limit_str = "/".join(self.job_limit)
            return False, f"仅限 {limit_str} 学习"

        # 属性要求
        if self.stat_req:
            loader = __import__("data.loader", fromlist=["get_loader"]).get_loader()
            engine = None  # 属性用基础值判断，不计算装备加成
            fail_parts = []
            for stat_key, min_val in self.stat_req.items():
                cur_val = 0
                if stat_key == "hp":
                    cur_val = adv.max_hp
                elif stat_key == "mp":
                    cur_val = adv.max_mp
                elif stat_key == "atk":
                    cur_val = adv.atk
                elif stat_key == "def_":
                    cur_val = adv.def_
                elif stat_key == "spd":
                    cur_val = adv.spd
                if cur_val < min_val:
                    labels = {"hp":"HP","mp":"MP","atk":"ATK","def_":"DEF","spd":"SPD"}
                    fail_parts.append(f"{labels.get(stat_key,stat_key)}{cur_val}/{min_val}")
            if fail_parts:
                return False, "属性不足: " + ", ".join(fail_parts)

        return True, ""


# ============================================================
# 装备
# ============================================================
@dataclass
class Equipment:
    name: str
    slot: str        # "weapon" / "armor" / "accessory" / "shield"
    hp_bonus: int = 0
    atk_bonus: int = 0
    def_bonus: int = 0
    spd_bonus: int = 0
    tier: int = 1    # 1=普通 2=精良 3=稀有 4=史诗

    @property
    def price(self):
        base = {"weapon": 50, "armor": 40, "accessory": 30, "shield": 45}[self.slot]
        bonus_sum = self.atk_bonus + self.def_bonus + self.hp_bonus + self.spd_bonus
        return base + bonus_sum * 5 + (self.tier - 1) * 30

    def bonus_text(self):
        parts = []
        if self.atk_bonus: parts.append(f"ATK+{self.atk_bonus}")
        if self.def_bonus: parts.append(f"DEF+{self.def_bonus}")
        if self.hp_bonus: parts.append(f"HP+{self.hp_bonus}")
        if self.spd_bonus: parts.append(f"SPD+{self.spd_bonus}")
        return " ".join(parts) if parts else "(无加成)"


# ============================================================
# 消耗品
# ============================================================
@dataclass
class Consumable:
    name: str
    desc: str
    item_type: str       # "heal" / "mp_restore" / "revive" / "buff" / "cleanse"
    effect_value: int = 0
    price: int = 0       # 可为0，由 base_price 公式兜底
    emoji: str = "🧪"

    @property
    def base_price(self) -> int:
        """公式化基础价格（基于物品类型和效果值）"""
        price_map = {
            "heal":       lambda v: int(v * 0.45) + 8,   # 治疗药水: 50×0.45+8≈30
            "mp_restore": lambda v: int(v * 0.6) + 12,   # 魔力药水: 40×0.6+12=36
            "buff":       lambda v: int(v * 0.5) + 25,   # 力量药剂: 30×0.5+25=40
            "revive":     lambda v: 200,                  # 复活卷轴: 固定200
            "cleanse":    lambda v: 20,                   # 解毒剂: 固定20
        }
        calc = price_map.get(self.item_type)
        if calc:
            return calc(self.effect_value)
        return self.price or 10


# ============================================================
# 怪物
# ============================================================
@dataclass
class Monster:
    name: str
    hp: int
    atk: int
    def_: int
    spd: int
    gold: int
    exp: int
    emoji: str = "👾"
    color: str = "#ff4444"
    skills: List[str] = field(default_factory=list)  # 怪物技能名列表

    def copy_scaled(self, scale: float, gold_mult: float = 1.0, exp_mult: float = 1.0):
        return Monster(
            self.name,
            int(self.hp * scale), int(self.atk * scale),
            int(self.def_ * scale), self.spd,
            int(self.gold * scale * gold_mult),
            int(self.exp * scale * exp_mult),
            self.emoji, self.color, list(self.skills),
        )


# ============================================================
# 地下城
# ============================================================
@dataclass
class Dungeon:
    name: str
    floors: int
    monster_names: List[str]
    boss_name: str
    difficulty: int
    gold_mult: float = 1.0
    exp_mult: float = 1.0
    event_chance: float = 0.25    # 每层触发事件的概率
    trap_chance: float = 0.15      # 陷阱概率


# ============================================================
# 探索事件
# ============================================================
@dataclass
class ExploreEvent:
    name: str
    desc: str
    event_type: str     # "trap" / "treasure" / "npc" / "rest" / "riddle"
    choices: List[Dict] = field(default_factory=list)  # [{text, effect_type, effect_value, success_chance}]


# ============================================================
# 冒险者
# ============================================================
@dataclass
class Adventurer:
    name: str
    job_key: str
    level: int = 1
    exp: int = 0
    exp_to_next: int = 100
    hp: int = 100
    max_hp: int = 100
    mp: int = 50
    max_mp: int = 50
    atk: int = 10
    def_: int = 5
    spd: int = 10
    race_key: str = "人类"
    equipment: Dict[str, Optional[str]] = field(default_factory=lambda: {
        "weapon": None, "armor": None, "accessory": None, "shield": None,
    })
    skills: List[str] = field(default_factory=list)
    dead: bool = False   # 是否阵亡（需要复活）

    def is_alive(self) -> bool:
        return self.hp > 0 and not self.dead
