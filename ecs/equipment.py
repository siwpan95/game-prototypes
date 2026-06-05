"""
装备掉落系统 — 数据从 data/game_data.xlsx（equipment Sheet）加载
ECS 架构：EquipmentComponent 挂在玩家实体上，存储在 equipment.py 定义的数据中。
"""

import random
from typing import Any, Dict, List, Optional

from .game_data import get_data


# ── 装备数据（从 Excel 加载） ──────────────────────────────────

def _load_equipment() -> Dict[str, Dict[str, Any]]:
    try:
        data = get_data()
        return data.get("equipment", {})
    except Exception:
        # 内置默认（与 Excel 模板一致）
        return {
            "iron_sword": dict(id="iron_sword", name="铁剑", desc="ATK+3",
                                icon="⚔", weight=30,
                                bonuses={"atk_base": 3}),
            "spiked_club": dict(id="spiked_club", name="狼牙棒",
                                 desc="ATK+6, 暴击+3%", icon="🔨", weight=18,
                                 bonuses={"atk_base": 6, "crit_chance": 0.03}),
            "mage_robe": dict(id="mage_robe", name="魔导师长袍",
                              desc="闪避+5%", icon="👘", weight=15,
                              bonuses={"dodge_chance": 0.05}),
            "vampire_fang": dict(id="vampire_fang", name="吸血鬼之牙",
                                  desc="攻击偷取 8% 伤害为 HP", icon="🦷",
                                  weight=10, bonuses={"lifesteal": 0.08}),
            "dragon_scale": dict(id="dragon_scale", name="龙鳞甲",
                                 desc="HP上限+30", icon="🛡", weight=12,
                                 bonuses={"max_hp": 30}),
            "lucky_coin": dict(id="lucky_coin", name="幸运硬币",
                               desc="暴击+5%, EXP获得+10%", icon="🪙",
                               weight=8,
                               bonuses={"crit_chance": 0.05,
                                         "exp_bonus": 0.10}),
            "time_hourglass": dict(id="time_hourglass", name="时空沙漏",
                                    desc="技能冷却-1s", icon="⏳", weight=7,
                                    bonuses={"cd_reduction": -1}),
        }


_EQUIPMENT_DEFS: Optional[Dict[str, Dict[str, Any]]] = None


def _get_equipment() -> Dict[str, Dict[str, Any]]:
    global _EQUIPMENT_DEFS
    if _EQUIPMENT_DEFS is None:
        _EQUIPMENT_DEFS = _load_equipment()
    return _EQUIPMENT_DEFS


# ── 掉落逻辑 ──────────────────────────────────────────────

def roll_equipment_drop(drop_rate: float = 0.35) -> Optional[Dict[str, Any]]:
    """按权重随机选择一个装备掉落，返回装备 dict 或 None"""
    if random.random() > drop_rate:
        return None
    eq_defs = _get_equipment()
    if not eq_defs:
        return None
    total = sum(e["weight"] for e in eq_defs.values())
    roll = random.randint(1, total)
    cumulative = 0
    for eq in eq_defs.values():
        cumulative += eq["weight"]
        if roll <= cumulative:
            return dict(eq)  # 返回副本，防止修改原数据
    return None


def get_base_drop_rate() -> float:
    return 0.35


def get_equipment_by_id(eq_id: str) -> Optional[Dict[str, Any]]:
    """按 ID 获取装备定义"""
    return _get_equipment().get(eq_id)
