# affixes.py — 装备稀有度与随机词缀系统
#
# 设计依据（联网检索）：
#  - Roguetemple《Ideas for better procedural algorithms》：通过「扰动列表」
#    （tweak the lists）让每个 run 的掉落组合不同，保证可重玩性。
#  - Roguelike 物品设计共识：稀有度分层 + 随机词缀（前缀/后缀）让掉落具备
#    成长与「构筑」感，而非扁平数值。
#
# 词缀不直接改引擎 Item 类，而是挂在 Item.metadata / InventoryItem.metadata
# 的 "affixes" 列表上；game 在计算有效属性时叠加这些词缀（见 game._recompute_mods）。
from __future__ import annotations

import random
from dataclasses import dataclass, field


# ───────────────────────────────────────────────────────────
#  稀有度分层
#  颜色用 ANSI 转义码（控制台终端普遍支持；无头 --auto 仅多转义符，无害）。
# ───────────────────────────────────────────────────────────
RARITY: list[dict] = [
    {"id": "common",    "name": "普通", "color": "\033[0m",    "affixes": 0, "weight": 50},
    {"id": "magic",     "name": "魔法", "color": "\033[36m",   "affixes": 1, "weight": 28},
    {"id": "rare",      "name": "稀有", "color": "\033[34m",   "affixes": 2, "weight": 14},
    {"id": "epic",      "name": "史诗", "color": "\033[35m",   "affixes": 3, "weight": 6},
    {"id": "legendary", "name": "传说", "color": "\033[33m",   "affixes": 4, "weight": 2},
]
RARITY_MAP = {r["id"]: r for r in RARITY}
RARITY_ORDER = [r["id"] for r in RARITY]

# 每档稀有度在越深的层权重越高（深层更易出好装备）
_FLOOR_SHIFT = {
    "common": -3,
    "magic": 0,
    "rare": 2,
    "epic": 1,
    "legendary": 1,
}


def rarity_color(rarity_id: str) -> str:
    return RARITY_MAP.get(rarity_id, RARITY_MAP["common"])["color"]


def rarity_name(rarity_id: str) -> str:
    return RARITY_MAP.get(rarity_id, RARITY_MAP["common"])["name"]


def roll_rarity(rng: random.Random, floor: int, luck_bonus: int = 0) -> str:
    """按层深 + 幸运加成掷出稀有度。

    越深的层整体越偏向高稀有度；luck_bonus（来自「幸运」perk）整体抬升一档。
    """
    shift = max(0, floor - 1) // 2 + luck_bonus
    weights = []
    for r in RARITY:
        w = r["weight"] + _FLOOR_SHIFT.get(r["id"], 0) * shift
        weights.append(max(1, w))
    total = sum(weights)
    roll = rng.random() * total
    acc = 0
    for r, w in zip(RARITY, weights):
        acc += w
        if roll < acc:
            return r["id"]
    return "common"


# ───────────────────────────────────────────────────────────
#  词缀池
#  slot: weapon / armor / any
#  stat: 对应 game.mods 的键（attack/defense/crit/lifesteal/regen/fov/special/dr）
#  special: 特殊效果标记（burn/poison/thorns），由战斗系统读取
#  value: [min, max] 随机区间
# ───────────────────────────────────────────────────────────
AFFIXES: list[dict] = [
    # —— 武器词缀 ——
    {"id": "sharp", "name": "锋利的", "slot": "weapon", "stat": "attack",
     "value": [1, 3], "weight": 10, "desc": "攻击力 +{v}"},
    {"id": "keen", "name": "精准的", "slot": "weapon", "stat": "crit",
     "value": [0.04, 0.10], "weight": 7, "desc": "暴击率 +{v}"},
    {"id": "vampiric", "name": "吸血的", "slot": "weapon", "stat": "lifesteal",
     "value": [0.05, 0.12], "weight": 5, "desc": "吸血 +{v}"},
    {"id": "flaming", "name": "燃烧的", "slot": "weapon", "stat": None,
     "special": "burn", "value": [0, 0], "weight": 6,
     "desc": "命中使目标灼烧"},
    {"id": "venomous", "name": "淬毒的", "slot": "weapon", "stat": None,
     "special": "poison", "value": [0, 0], "weight": 6,
     "desc": "命中使目标中毒"},
    {"id": "heavy", "name": "沉重的", "slot": "weapon", "stat": "special",
     "value": [0.10, 0.25], "weight": 5, "desc": "特技伤害 +{v}"},
    # —— 护甲词缀 ——
    {"id": "sturdy", "name": "坚固的", "slot": "armor", "stat": "defense",
     "value": [1, 3], "weight": 10, "desc": "防御力 +{v}"},
    {"id": "thorned", "name": "荆棘的", "slot": "armor", "stat": None,
     "special": "thorns", "value": [2, 5], "weight": 6,
     "desc": "被近身攻击时反弹 {v} 伤害"},
    {"id": "regen", "name": "恢复的", "slot": "armor", "stat": "regen",
     "value": [1, 2], "weight": 6, "desc": "每回合回复 {v} 生命"},
    {"id": "watching", "name": "警觉的", "slot": "armor", "stat": "fov",
     "value": [1, 2], "weight": 5, "desc": "视野 +{v}"},
    {"id": "warding", "name": "庇护的", "slot": "armor", "stat": "dr",
     "value": [1, 2], "weight": 6, "desc": "受击伤害 -{v}"},
]


def _fmt_affix(af: dict) -> str:
    v = af.get("value")
    if isinstance(v, list):          # 防御：未取到数值时退化为下界
        v = v[0] if v else 0
    if af["stat"] in ("crit", "lifesteal", "special"):
        txt = f"{int(round(v * 100))}%"
    elif v:
        txt = f"{v}"
    else:
        txt = ""
    return af["desc"].replace("{v}", txt)


def roll_affixes(rng: random.Random, rarity_id: str,
                 item_kind: str) -> list[dict]:
    """按稀有度掷出若干词缀（与物品类型匹配）。返回词缀实例列表。"""
    count = RARITY_MAP[rarity_id]["affixes"]
    if count <= 0:
        return []
    pool = [a for a in AFFIXES if a["slot"] in (item_kind, "any")]
    if not pool:
        return []
    chosen: list[dict] = []
    available = pool[:]
    for _ in range(count):
        if not available:
            break
        # 加权随机选择
        weights = [a["weight"] for a in available]
        total = sum(weights)
        r = rng.random() * total
        acc = 0
        idx = 0
        for i, w in enumerate(weights):
            acc += w
            if r < acc:
                idx = i
                break
        base = available.pop(idx)
        if base["stat"] in ("crit", "lifesteal", "special"):
            val = round(rng.uniform(*base["value"]), 2)
        elif base["value"][1] > 0:
            val = rng.randint(base["value"][0], base["value"][1])
        else:
            val = 0
        chosen.append({
            "id": base["id"],
            "name": base["name"],
            "stat": base["stat"],
            "special": base.get("special"),
            "value": val,
            "desc": _fmt_affix(dict(base, value=val)),
        })
    return chosen


def describe_affixes(affixes: list[dict]) -> str:
    """把词缀列表格式化为可读字符串（用于背包显示）。"""
    if not affixes:
        return ""
    return "，" + "，".join(a["desc"] for a in affixes)


def make_loot(rng: random.Random, iid: str, item_kind: str,
              floor: int, luck_bonus: int = 0) -> dict:
    """为一个物品 id 掷出完整掉落信息：稀有度 + 词缀。

    返回 {"rarity": str, "affixes": list}。game 将其写入 InventoryItem.metadata。
    """
    rarity = roll_rarity(rng, floor, luck_bonus)
    affixes = roll_affixes(rng, rarity, item_kind)
    return {"rarity": rarity, "affixes": affixes}
