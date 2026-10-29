# progression.py — 角色成长系统（经验 / 等级 / 升级三选一 perk）
#
# 设计依据（联网检索）：zooz《Designing Fair RNG in Roguelikes》提出的
# 「半随机层 / choosable luck」——成长不应是固定奖励，而是「从 3 个随机
# 选项中选 1」，把成长变成玩家有代理权的选择。这正是现代 Roguelike
# （《死亡细胞》卷轴、《以撒》道具）的核心乐趣来源。
from __future__ import annotations

import random
from dataclasses import dataclass, field


# ───────────────────────────────────────────────────────────
#  升级曲线
# ───────────────────────────────────────────────────────────
def xp_for_level(level: int) -> int:
    """升到下一级所需经验：随等级略陡增长，避免后期刷级过廉价。"""
    return int(18 + (level - 1) * 12 + (level - 1) ** 1.55)


@dataclass
class Progression:
    level: int = 1
    xp: int = 0
    xp_next: int = field(default_factory=lambda: xp_for_level(1))
    perks: list[str] = field(default_factory=list)   # 已选 perk id 列表


# ───────────────────────────────────────────────────────────
#  Perk 池（升级三选一）
#  每个 perk：
#    mods   —— 永久属性加成（叠加进 game.perk_mods，存档只重算、不重复触发）
#    instant —— 即时一次性效果（如回血）；仅在选择时触发一次
#  mods 的键与 game.mods 对齐：attack/defense/crit/lifesteal/
#  regen/fov/special/dr/rarity
# ───────────────────────────────────────────────────────────
PERKS: list[dict] = [
    {"id": "vigor", "name": "强健体魄", "desc": "最大生命 +15 并立即回满",
     "mods": {}, "instant": lambda g: (setattr(g.ps, "max_hp", g.ps.max_hp + 15),
                                       g.ps.adjust_hp(15))},
    {"id": "strength", "name": "力量", "desc": "攻击力 +2",
     "mods": {"attack": 2}, "instant": None},
    {"id": "toughness", "name": "坚韧", "desc": "防御力 +1",
     "mods": {"defense": 1}, "instant": None},
    {"id": "precision", "name": "精准", "desc": "暴击率 +6%",
     "mods": {"crit": 0.06}, "instant": None},
    {"id": "bloodthirst", "name": "嗜血", "desc": "吸血 +8%（造成伤害回复生命）",
     "mods": {"lifesteal": 0.08}, "instant": None},
    {"id": "regrowth", "name": "再生", "desc": "每回合回复 1 点生命",
     "mods": {"regen": 1}, "instant": None},
    {"id": "fortune", "name": "幸运", "desc": "战利品稀有度 +1 档",
     "mods": {"rarity": 1}, "instant": None},
    {"id": "swiftness", "name": "迅捷", "desc": "视野半径 +1（更早察觉危险）",
     "mods": {"fov": 1}, "instant": None},
    {"id": "focus", "name": "专注", "desc": "特技伤害 +30%",
     "mods": {"special": 0.30}, "instant": None},
    {"id": "warding", "name": "守护", "desc": "受到的所有伤害 -1（最低 1）",
     "mods": {"dr": 1}, "instant": None},
]

PERK_MAP = {p["id"]: p for p in PERKS}


def compute_perk_mods(perks: list[str]) -> dict:
    """纯函数：从已选 perk 列表聚合出属性加成（不触发即时效果，供读档重算）。"""
    mods: dict = {}
    for pid in perks:
        p = PERK_MAP.get(pid)
        if not p:
            continue
        for k, v in p["mods"].items():
            mods[k] = mods.get(k, 0) + v
    return mods


def roll_perk_choices(rng: random.Random, n: int = 3) -> list[dict]:
    """从 perk 池中随机抽取 n 个互不相同的选项（每次升级三选一）。

    允许不同等级重复选同一 perk（数值叠加，符合 roguelike 构筑感），
    但同一批选项内不重复，保证「三选一」有真实取舍。
    """
    pool = list(PERKS)
    n = min(n, len(pool))
    return rng.sample(pool, n)


def grant_xp(game, amount: int) -> list[int]:
    """给玩家加经验，返回本次跨越的所有新等级列表（可能连续多级）。"""
    prog = game.progression
    prog.xp += max(0, int(amount))
    leveled: list[int] = []
    while prog.xp >= prog.xp_next:
        prog.xp -= prog.xp_next
        prog.level += 1
        prog.xp_next = xp_for_level(prog.level)
        leveled.append(prog.level)
    return leveled


def apply_perk(game, perk_id: str) -> None:
    """应用一个 perk（叠加属性加成 + 触发即时效果）。"""
    perk = PERK_MAP.get(perk_id)
    if perk is None:
        return
    for k, v in perk["mods"].items():
        game.perk_mods[k] = game.perk_mods.get(k, 0) + v
    if perk["instant"] is not None:
        perk["instant"](game)
    game.progression.perks.append(perk_id)
    game._recompute_mods()
