# -*- coding: utf-8 -*-
"""
core/heirlooms.py — 传家宝系统（联网调研成果 · BitLife Heirlooms + 中国式家长传家宝）

设计来源：
    BitLife 的 Heirlooms 机制——角色死亡后，传家物品会传给下一代，部分特质
    和资产会"跨代积累"。中国式家长的"传家宝"则贴合中文语境。两者都是纯数据
    层机制，无需图形/引擎改造，适配 Tkinter 约束。

机制：
    1. profile.lineage.heirlooms 存当前家族持有的传家宝 id 列表
    2. 每局开始时，apply_heirlooms(player, profile) 把持有传家宝的 effects
       应用到 Player（init 属性 / modifiers / 维度 / 解锁）
    3. 角色死亡时，roll_inheritance(profile, rng) 按各传家宝的 inherit_chance
       概率决定是否传入下一代；未传入的从 lineage.heirlooms 移除
    4. 成就/结局/挑战解锁新传家宝时，unlock_heirloom(profile, heirloom_id)
       将其首次加入 lineage 池

容错（R6 风格）：
    - heirlooms.json 缺失/损坏 → 视为空池，游戏正常运行
    - profile.lineage 缺失 → 自动创建空结构
    - 单条传家宝 effects 字段非法 → 跳过该条，不抛异常

零 UI 依赖。所有提示通过返回值传递，绝不 print。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from core import paths


# 内存缓存（避免每次访问都读盘）
_cache: Dict[str, Any] = {"data": None, "mtime": None}


def _load_heirlooms_data() -> Dict[str, Any]:
    """加载 heirlooms.json，带 mtime 缓存。失败返回空 dict。"""
    fp = paths.CONTENT_DIR / "heirlooms.json"
    try:
        if not fp.exists():
            return {"heirlooms": []}
        mtime = fp.stat().st_mtime
        if _cache["data"] is not None and _cache["mtime"] == mtime:
            return _cache["data"]
        with open(fp, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict) or not isinstance(data.get("heirlooms"), list):
            return {"heirlooms": []}
        _cache["data"] = data
        _cache["mtime"] = mtime
        return data
    except (json.JSONDecodeError, OSError, ValueError):
        return {"heirlooms": []}


def all_heirlooms() -> List[Dict[str, Any]]:
    """返回全部传家宝定义列表。"""
    return _load_heirlooms_data().get("heirlooms", []) or []


def get_heirloom(heirloom_id: str) -> Optional[Dict[str, Any]]:
    """按 id 取单个传家宝定义。"""
    for h in all_heirlooms():
        if h.get("id") == heirloom_id:
            return h
    return None


def ensure_lineage(profile: Dict[str, Any]) -> Dict[str, Any]:
    """确保 profile.heirlooms_state 结构存在（缺失则建默认）。

    设计说明：profile.lineage 是 PRD Q3 预留的 list 字段（前向兼容，不动它）。
    传家宝系统使用独立的 heirlooms_state dict，避免与预留字段冲突。
    """
    lin = profile.get("heirlooms_state")
    if not isinstance(lin, dict):
        lin = {"heirlooms": [], "generations": 0, "history": []}
        profile["heirlooms_state"] = lin
        return lin
    if not isinstance(lin.get("heirlooms"), list):
        lin["heirlooms"] = []
    if not isinstance(lin.get("generations"), int):
        lin["generations"] = 0
    if not isinstance(lin.get("history"), list):
        lin["history"] = []
    profile["heirlooms_state"] = lin
    return lin


def held_heirloom_ids(profile: Dict[str, Any]) -> List[str]:
    """返回当前家族持有的传家宝 id 列表（去重保序）。"""
    lin = ensure_lineage(profile)
    seen = set()
    out: List[str] = []
    for hid in lin.get("heirlooms", []) or []:
        if isinstance(hid, str) and hid and hid not in seen:
            seen.add(hid)
            out.append(hid)
    return out


def apply_heirlooms(player: Any, profile: Dict[str, Any]) -> Dict[str, Any]:
    """把持有的传家宝 effects 应用到 Player。

    支持的 effects：
      init.{stat}          → setattr(player, stat, getattr(player, stat) + val)
      init_dimensions.{DIM}→ player.decision_tree 调整（若存在）
      modifiers.*          → 写入 player.talent_modifiers（与天赋 modifiers 同结构）
      unlocks              → player.unlocked_modes.extend（去重）

    返回应用摘要 dict（供表现层展示）：
        {"applied": [{"id":..,"name":..,"effects_summary":[...]}, ...], "skipped": [...]}
    """
    summary: Dict[str, Any] = {"applied": [], "skipped": []}
    for hid in held_heirloom_ids(profile):
        h = get_heirloom(hid)
        if not h:
            summary["skipped"].append({"id": hid, "reason": "定义未找到"})
            continue
        effects = h.get("effects") or {}
        if not isinstance(effects, dict):
            summary["skipped"].append({"id": hid, "reason": "effects 字段非法"})
            continue

        applied_lines: List[str] = []
        # init 属性
        init = effects.get("init") or {}
        if isinstance(init, dict):
            for stat, val in init.items():
                if not isinstance(val, (int, float)):
                    continue
                if hasattr(player, stat):
                    try:
                        setattr(player, stat, getattr(player, stat) + val)
                        applied_lines.append(f"{stat}{'+' if val>=0 else ''}{val}")
                    except (TypeError, AttributeError):
                        pass
        # init_dimensions（王权模式）
        init_dims = effects.get("init_dimensions") or {}
        if isinstance(init_dims, dict) and getattr(player, "decision_tree", None) is not None:
            dt = player.decision_tree
            for dim, val in init_dims.items():
                if isinstance(val, (int, float)) and hasattr(dt, "dimensions"):
                    try:
                        dt.dimensions[dim] = dt.dimensions.get(dim, 50) + val
                        applied_lines.append(f"{dim}{'+' if val>=0 else ''}{val}")
                    except (TypeError, KeyError, AttributeError):
                        pass
        # modifiers（与天赋 modifiers 同结构，合并到 player）
        modifiers = effects.get("modifiers") or {}
        if isinstance(modifiers, dict) and modifiers:
            existing = getattr(player, "talent_modifiers", None)
            if not isinstance(existing, dict):
                existing = {}
                setattr(player, "talent_modifiers", existing, )
            for mkey, mval in modifiers.items():
                if mkey in existing and isinstance(existing[mkey], list) and isinstance(mval, list):
                    existing[mkey].extend(mval)
                elif mkey in existing and isinstance(existing[mkey], (int, float)) and isinstance(mval, (int, float)):
                    existing[mkey] = existing[mkey] * mval  # 乘法叠加
                else:
                    existing[mkey] = mval
            applied_lines.append("修饰器已生效")
        # unlocks
        unlocks = h.get("unlocks") or effects.get("unlocks") or []
        if isinstance(unlocks, list) and unlocks:
            um = getattr(player, "unlocked_modes", None)
            if not isinstance(um, list):
                um = []
                setattr(player, "unlocked_modes", um)
            for u in unlocks:
                if isinstance(u, str) and u not in um:
                    um.append(u)
            applied_lines.append(f"解锁：{','.join(unlocks)}")

        summary["applied"].append({
            "id": hid,
            "name": h.get("name", hid),
            "rarity": h.get("rarity", "common"),
            "effects_summary": applied_lines,
        })
    return summary


def unlock_heirloom(profile: Dict[str, Any], heirloom_id: str) -> bool:
    """解锁一个传家宝（首次加入家族持有池）。

    返回 True 表示新解锁，False 表示已持有或定义不存在。
    """
    if not heirloom_id or get_heirloom(heirloom_id) is None:
        return False
    lin = ensure_lineage(profile)
    held = lin.get("heirlooms", []) or []
    if heirloom_id in held:
        return False
    held.append(heirloom_id)
    lin["heirlooms"] = held
    return True


def roll_inheritance(profile: Dict[str, Any], rng=None) -> Dict[str, Any]:
    """角色死亡时，按 inherit_chance 决定传家宝是否传入下一代。

    传入的保留在 lineage.heirlooms；未传入的从池中移除（永久丢失，制造'传承风险'）。
    generations += 1。

    返回：
        {"kept": [id,...], "lost": [id,...], "lost_names": [name,...]}
    """
    import random as _r
    rng = rng or _r
    lin = ensure_lineage(profile)
    held = list(lin.get("heirlooms", []) or [])
    kept: List[str] = []
    lost: List[str] = []
    lost_names: List[str] = []

    for hid in held:
        h = get_heirloom(hid)
        if not h:
            lost.append(hid)
            continue
        chance = h.get("inherit_chance", 0.5)
        try:
            chance = float(chance)
        except (TypeError, ValueError):
            chance = 0.5
        chance = max(0.0, min(1.0, chance))
        if rng.random() < chance:
            kept.append(hid)
        else:
            lost.append(hid)
            lost_names.append(h.get("name", hid))

    lin["heirlooms"] = kept
    lin["generations"] = int(lin.get("generations", 0)) + 1
    return {"kept": kept, "lost": lost, "lost_names": lost_names}


def lineage_summary(profile: Dict[str, Any]) -> Dict[str, Any]:
    """返回家族传承摘要（供图鉴展示）。只读。"""
    lin = ensure_lineage(profile)
    held = held_heirloom_ids(profile)
    items = []
    for hid in held:
        h = get_heirloom(hid)
        if h:
            items.append({
                "id": hid,
                "name": h.get("name", hid),
                "rarity": h.get("rarity", "common"),
                "description": h.get("description", ""),
            })
    return {
        "generations": lin.get("generations", 0),
        "heirlooms": items,
        "heirloom_count": len(items),
    }
