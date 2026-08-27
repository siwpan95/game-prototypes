# events.py
# 数据驱动事件系统（E3）
#
# 事件以 JSON 描述（data/events.json）：每条含 title / narrative / 可选 condition /
# choices[]；每个 choice 含 text 与 effects（作用于 SAN / 锚 / 消化 / 材料）。
#
# pick_event(character, state)   -> 按条件筛选并随机抽取一条事件（dict 浅拷贝）
# resolve_choice(state, event, index) -> 结算玩家选择，返回要写入日志的行列表
#
# 逻辑层与 UI 完全分离：events.py 不依赖 tkinter，可被无头单测直接覆盖；
# GUI 侧由 gui/panels/event_panel.py 负责渲染与按钮绑定。
import os
import json
import random
from pollution import PollutionSource
from abilities import apply_ability_effects
from factions import FACTIONS, grant_reputation


EVENTS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "events.json")

_CACHE = None


def load_events() -> list:
    """从 JSON 载入全部事件定义"""
    if not os.path.exists(EVENTS_PATH):
        return []
    with open(EVENTS_PATH, encoding="utf-8") as f:
        return json.load(f)


def _events() -> list:
    global _CACHE
    if _CACHE is None:
        _CACHE = load_events()
    return _CACHE


def _meets_condition(ev: dict, character, state) -> bool:
    """事件条件筛选（min_level / max_level 基于序列等级，数字越小位格越高）"""
    cond = ev.get("condition")
    if not cond:
        return True
    lvl = character.LEVEL
    if "min_level" in cond and lvl > cond["min_level"]:
        return False
    if "max_level" in cond and lvl < cond["max_level"]:
        return False
    return True


def pick_event(character, state, rng: random.Random = random) -> dict | None:
    """按条件筛选可用事件并随机抽一条；无可用则返回 None。"""
    pool = [e for e in _events() if _meets_condition(e, character, state)]
    if not pool:
        return None
    return dict(rng.choice(pool))  # 浅拷贝，避免把运行时状态写回原始定义


def resolve_choice(state, event: dict, choice_index: int) -> list:
    """结算玩家在事件中的选择，返回日志行列表（副作用已应用到 state）。"""
    ch = state.character
    logs: list = []
    choices = event.get("choices", [])
    if choice_index < 0 or choice_index >= len(choices):
        return [f"⚠ 事件《{event.get('title')}》无此选项"]

    choice = choices[choice_index]
    logs.append(f"▸ 你选择：「{choice.get('text')}」")

    eff = choice.get("effects", {})

    # 理智 SAN（连续值）
    if "san" in eff:
        delta = eff["san"]
        if delta >= 0:
            new = ch.pollution.recover(delta)
        else:
            ch.pollution.accumulate(PollutionSource("knowledge", -delta / 20.0))
            new = ch.pollution.san
        sign = "+" if delta >= 0 else ""
        logs.append(f"   理智 {sign}{delta} → {new:.0f}（{ch.pollution.san_status()}）")

    # 锚（人性）
    if "anchor" in eff and ch.anchor is not None:
        ch.anchor.humanity = max(0.0, min(100.0, ch.anchor.humanity + eff["anchor"]))
        sign = "+" if eff["anchor"] >= 0 else ""
        logs.append(f"   锚人性 {sign}{eff['anchor']} → {ch.anchor.humanity:.0f}")

    # 消化（被动扮演，直接补足若干缺失的扮演行为；E5 走质量权重 +0.5）
    if "digestion" in eff and ch.required_actions:
        need = set(ch.required_actions) - set(ch.digestion_actions)
        add = min(int(eff["digestion"]), len(need))
        for a in list(need)[:add]:
            ch.add_digestion(a, 0.5)   # 事件结算属于被动扮演
        if add:
            logs.append(f"   扮演消化 +{add}（{ch.digestion_ratio:.0%}）")

    # 材料（魔药配方资源）
    if "materials" in eff:
        for m in eff["materials"]:
            state.inventory.add(m, 1)
        logs.append(f"   获得材料：{'、'.join(eff['materials'])}")

    # 获得「当前晋升所需」的缺失材料（与 E1 酿造系统联动）
    if "needed_materials" in eff and ch.LEVEL > 0:
        from pathways_data import get_potion_formula
        formula = get_potion_formula(ch.PATHWAY_KEY, ch.LEVEL - 1)
        miss = [m for m in [formula["main"]] + formula["supplementary"]
                if state.inventory.count(m) < 1]
        n = min(int(eff["needed_materials"]), len(miss))
        for m in miss[:n]:
            state.inventory.add(m, 1)
        if n:
            logs.append(f"   获得所需材料：{'、'.join(miss[:n])}")

    # 自定义日志
    if "log" in choice:
        logs.append(f"   {choice['log']}")

    # 阵营声望（E7）：事件可提升某阵营声望
    if "faction" in eff:
        for fk, d in eff["faction"].items():
            grant_reputation(state, fk, int(d))
            flabel = FACTIONS.get(fk, {}).get("label", fk)
            logs.append(f"   🤝 声望 +{d}：{flabel}")

    # 能力效果化（E6）：角色所拥有的能力在事件中产生差异
    apply_ability_effects(ch, state, logs)

    return logs
