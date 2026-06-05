"""
随机事件系统 — 数据从 data/game_data.xlsx（events Sheet）加载
罐头游戏核心：每击杀 N 只怪物触发一次随机事件。
神秘商人事件返回装备 dict，由 View 弹窗处理交互。
"""

import json
import random
from typing import Any, Callable, Dict, Optional

from .game_data import get_data

# ── 事件效果函数（硬编码，函数无法存 Excel）────────────

def _event_merchant(world: Any, player_eid: int,
                     log_fn: Callable[[str], None]) -> Optional[Dict]:
    """神秘商人：返回随机装备 dict（含价格），由 View 弹窗处理交互"""
    from .equipment import roll_equipment_drop
    eq = roll_equipment_drop(drop_rate=1.0)  # 100% 掉落
    if eq is None:
        return None
    # 根据装备权重设定经验池价格
    w = eq.get("weight", 10)
    eq["price"] = 5 if w <= 8 else (8 if w <= 15 else 12)
    return eq


def _event_exp_rain(world: Any, player_eid: int,
                     log_fn: Callable[[str], None]) -> None:
    """经验雨：经验池+10~30"""
    from .components import ExpComponent
    exp_c = world.get_component(player_eid, ExpComponent)
    if exp_c is None:
        return
    amount = random.randint(10, 30)
    exp_c.exp_pool += amount
    log_fn(f"🌧 经验雨！经验池 +{amount}（池内 {exp_c.exp_pool}）")


def _event_blessing(world: Any, player_eid: int,
                     log_fn: Callable[[str], None]) -> None:
    """祝福之光：HP 完全恢复"""
    from .components import HPComponent
    hp_c = world.get_component(player_eid, HPComponent)
    if hp_c is None:
        return
    hp_c.hp = hp_c.max_hp
    log_fn(f"✨ 祝福之光！HP 完全恢复（{hp_c.hp}/{hp_c.max_hp}）")


def _event_monster_riot(world: Any, player_eid: int,
                         log_fn: Callable[[str], None]) -> None:
    """怪物暴动：随机一只怪物立即复活"""
    from .components import MonsterTag, HPComponent, NameComponent
    candidates: list[int] = []
    for eid, hp_c, _ in world.get_components(HPComponent, MonsterTag):
        if not hp_c.alive:
            candidates.append(eid)
    if not candidates:
        log_fn("🐺 怪物暴动！但没有可复活的怪物")
        return
    eid = random.choice(candidates)
    hp_c = world.get_component(eid, HPComponent)
    if hp_c:
        hp_c.alive = True
        hp_c.hp = hp_c.max_hp
    name_c = world.get_component(eid, NameComponent)
    name = name_c.name if name_c else "怪物"
    log_fn(f"🐺 怪物暴动！{name} 立即复活了！")


# ── 效果函数映射表 ─────────────────────────────────────

_FN_MAP: Dict[str, Callable] = {
    "event_merchant": _event_merchant,
    "event_exp_rain": _event_exp_rain,
    "event_blessing": _event_blessing,
    "event_monster_riot": _event_monster_riot,
}


def _resolve_fn(fn_name: str) -> Optional[Callable]:
    return _FN_MAP.get(fn_name)


# ── 事件数据（从 Excel 加载）────────────────────────────

def _load_events() -> Dict[str, Dict[str, Any]]:
    try:
        data = get_data()
        raw = data.get("events", {})
        result = {}
        for eid, edef in raw.items():
            edef = dict(edef)
            fn_name = edef.pop("effect_fn", "") or ""
            edef["effect"] = _resolve_fn(fn_name)
            result[eid] = edef
        return result
    except Exception:
        # 内置默认
        return {
            "merchant": dict(id="merchant", name="神秘商人", weight=20,
                             effect=_event_merchant),
            "exp_rain": dict(id="exp_rain", name="经验雨", weight=25,
                             effect=_event_exp_rain),
            "blessing": dict(id="blessing", name="祝福之光", weight=20,
                             effect=_event_blessing),
            "monster_riot": dict(id="monster_riot", name="怪物暴动", weight=15,
                                 effect=_event_monster_riot),
        }


_EVENT_DEFS: Optional[Dict[str, Dict[str, Any]]] = None


def _get_events() -> Dict[str, Dict[str, Any]]:
    global _EVENT_DEFS
    if _EVENT_DEFS is None:
        _EVENT_DEFS = _load_events()
    return _EVENT_DEFS


# ── 公开接口 ─────────────────────────────────────────

def trigger_random_event(world: Any, player_eid: int,
                        log_fn: Callable[[str], None]) -> Optional[Dict]:
    """
    按权重随机触发一个事件。
    返回：
      - None：没有触发事件
      - dict：神秘商人事件，包含装备信息，由调用方弹窗处理
      - True：其他事件已处理完毕
    """
    events = _get_events()
    if not events:
        return None
    total = sum(e["weight"] for e in events.values())
    roll = random.randint(1, total)
    cumulative = 0
    for ev in events.values():
        cumulative += ev["weight"]
        if roll <= cumulative:
            log_fn(f"\n ═══ 随机事件：{ev['name']} ═══")
            effect = ev.get("effect")
            result = None
            if effect is not None:
                result = effect(world, player_eid, log_fn)
                # 神秘商人：返回装备 dict，需要交互
                if ev.get("id") == "merchant" and result is not None:
                    log_fn(f"__EVENT__{json.dumps({'event': 'merchant', 'equip': result}, ensure_ascii=False)}")
            log_fn(" ═════════════════════════\n")
            return result if ev.get("id") == "merchant" else True
    return None
