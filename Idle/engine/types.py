"""
类型定义 — TypedDict 精确描述 JSON 数据结构，替代裸 dict。
"""
from typing import TypedDict, NotRequired


class SkillDef(TypedDict):
    key: str
    name: str
    tip: str
    cooldown: int
    era: str
    icon: str
    effect_type: str          # "instant_dps" | "dps_mult" | "crit_clicks" | "auto_click" | "combo"
    effect_value: float
    duration: NotRequired[int]
    charges: NotRequired[int]
    click_mult: NotRequired[float]
    dps_mult: NotRequired[float]


class EraDef(TypedDict):
    key: str
    name: str
    threshold: float
    description: str
    color: str
    bonus_dps: float
    bonus_click: float


class HeroDef(TypedDict):
    key: str
    name: str
    icon: str
    tier: int
    description: str
    unlock_gold: int
    upgrade_cost: int
    upgrade_mult: float
    max_level: int
    passive_dps_bonus: NotRequired[float]
    passive_click_bonus: NotRequired[float]
    crit_chance: NotRequired[float]


class HeroState(TypedDict):
    level: int
    equipped: NotRequired[dict | None]


class ChallengeDef(TypedDict):
    key: str
    name: str
    tip: str
    prestige_mult: float
    restrict_click: NotRequired[bool]
    restrict_dps: NotRequired[bool]
    time_limit: NotRequired[int]
    target_era: NotRequired[str]


class PrestigeUpgradeDef(TypedDict):
    key: str
    name: str
    tip: str
    cost: int
    max_level: int
    effect_type: str          # "dps_mult" | "click_mult" | "start_gold" | "skill_cd"
    effect_per_level: float


class EquipmentItem(TypedDict):
    name: str
    rarity: str               # "common" | "magic" | "legendary" | "mythic" | "immortal"
    bonus: int
    color: str


class EquipmentTier(TypedDict):
    rarity: str
    name: str
    color: str
    drop_per_tick: float
    bonus_min: int
    bonus_max: int


class CategoryDef(TypedDict):
    name: str
    color: str
    icon: NotRequired[str]
