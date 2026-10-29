"""
怪物词缀系统 — 数据从 data/game_data.xlsx（affixes Sheet）加载
如果 Excel 加载失败，回退到内置默认数据。
"""

import random
from typing import Any, Callable, Dict, Optional

from .game_data import get_data

# ── 词缀数据（从 Excel 加载） ─────────────────────────────

def _load_affixes() -> Dict[str, Dict[str, Any]]:
    try:
        data = get_data()
        return data.get("affixes", {})
    except Exception:
        # 内置默认（与 Excel 模板一致）
        return {
            "elite": dict(id="elite", label="精英", icon="⭐", weight=15,
                          hp_mult=2.0, exp_mult=1.5, dodge_bonus=0.0,
                          damage_reduction=0, on_attack="", on_death=""),
            "swift": dict(id="swift", label="迅捷", icon="💨", weight=10,
                          hp_mult=1.0, exp_mult=1.1, dodge_bonus=0.15,
                          damage_reduction=0, on_attack="", on_death=""),
            "hardened": dict(id="hardened", label="硬化", icon="🛡", weight=12,
                             hp_mult=1.0, exp_mult=1.0, dodge_bonus=0.0,
                             damage_reduction=3, on_attack="", on_death=""),
            "cursed": dict(id="cursed", label="诅咒", icon="💀", weight=8,
                          hp_mult=0.7, exp_mult=2.0, dodge_bonus=0.0,
                          damage_reduction=0, on_attack="", on_death=""),
            "burning": dict(id="burning", label="燃烧", icon="🔥", weight=10,
                          hp_mult=1.0, exp_mult=1.2, dodge_bonus=0.0,
                          damage_reduction=0,
                          on_attack="burning_on_attack", on_death=""),
            "phantom": dict(id="phantom", label="幻影", icon="👻", weight=5,
                           hp_mult=1.0, exp_mult=1.3, dodge_bonus=0.0,
                           damage_reduction=0, on_attack="", on_death=""),
        }

# 模块级变量，懒加载
_AFFIX_DEFS: Optional[Dict[str, Dict[str, Any]]] = None

def _get_affixes() -> Dict[str, Dict[str, Any]]:
    global _AFFIX_DEFS
    if _AFFIX_DEFS is None:
        _AFFIX_DEFS = _load_affixes()
    return _AFFIX_DEFS


# ── 词缀效果函数 ──────────────────────────────────────────

def burning_on_attack(world: Any, monster_eid: int,
                      player_eid: int, log_fn: Callable) -> None:
    """燃烧词缀：怪物攻击玩家时附加灼烧（持续伤害 4/tick, 3回合）"""
    from .components import StatusEffectComponent
    se = world.get_component(player_eid, StatusEffectComponent)
    if se is not None:
        se.add("burn", damage=4, turns=3, label="🔥灼烧")
        log_fn("🔥 燃烧怪物反击附带灼烧！你将受到 4×3 回合持续伤害")


# 效果函数映射表（将 Excel 里的函数名字符串映射到实际函数）
_EFFECT_FN_MAP: Dict[str, Callable] = {
    "burning_on_attack": burning_on_attack,
}


def _resolve_fn(fn_name: str) -> Optional[Callable]:
    """将函数名字符串解析为实际函数"""
    return _EFFECT_FN_MAP.get(fn_name)


# ── 公开接口 ──────────────────────────────────────────────

def random_affix() -> Optional[str]:
    """按权重随机选择一个词缀 ID，约 40-60% 概率生成词缀"""
    affixes = _get_affixes()
    if not affixes:
        return None
    total_weight = sum(a["weight"] for a in affixes.values())
    roll = random.randint(1, total_weight + 50)  # +50 表示无词缀的权重
    if roll > total_weight:
        return None  # ~45% 无词缀
    cumulative = 0
    for affix_id, data in affixes.items():
        cumulative += data["weight"]
        if roll <= cumulative:
            return affix_id
    return None


def get_affix_display(affix_id: Optional[str]) -> str:
    """返回词缀的展示文字"""
    if affix_id is None:
        return ""
    affixes = _get_affixes()
    data = affixes.get(affix_id)
    if data is None:
        return ""
    return f" {data['icon']}{data['label']}"


def get_affix_data(affix_id: Optional[str]) -> Optional[Dict[str, Any]]:
    """获取词缀完整数据（供 combat_system 使用）"""
    if affix_id is None:
        return None
    return _get_affixes().get(affix_id)


# 兼容旧代码：模块级常量
AFFIX_DEFS = _get_affixes()
