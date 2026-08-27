# -*- coding: utf-8 -*-
"""
core/challenges.py — 挑战模式引擎（联网调研成果 · BitLife 社区挑战 + 成就驱动解锁）

设计来源：
    BitLife 社区创造的挑战玩法（Zero to Hero / Criminal Empire / No Education）
    让固定内容产生持续新鲜感。Vampire Survivors 用"成就解锁扩池"让同样内容量
    "感觉更大"。两者结合：挑战是"目标+约束+奖励"三层包装，套在现有玩法外，
    不增加引擎复杂度。

机制：
    1. profile.active_challenge 存当前激活的挑战 id（None 表示无挑战）
    2. start_challenge(profile, challenge_id) 校验前置（是否已解锁）后激活，
       返回 start_override 供出身阶段应用
    3. validate_run(player, challenge) 全流程校验限制（违反不结束游戏，仅标记）
    4. check_win(player, profile, challenge) 结算时检查胜利条件
    5. complete_challenge(profile, challenge_id) 发放奖励（解锁天赋/出身/成就/模式）
    6. profile.unlocked_challenges 记录已完成的挑战 id

容错（R6 风格）：challenges.json 缺失/损坏 → 挑战模式不可用但不崩溃。
零 UI 依赖。所有提示通过返回值传递，绝不 print。
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from core import paths


_cache: Dict[str, Any] = {"data": None, "mtime": None}


def _load_data() -> Dict[str, Any]:
    fp = paths.CONTENT_DIR / "challenges.json"
    try:
        if not fp.exists():
            return {"challenges": []}
        mtime = fp.stat().st_mtime
        if _cache["data"] is not None and _cache["mtime"] == mtime:
            return _cache["data"]
        with open(fp, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict) or not isinstance(data.get("challenges"), list):
            return {"challenges": []}
        _cache["data"] = data
        _cache["mtime"] = mtime
        return data
    except (json.JSONDecodeError, OSError, ValueError):
        return {"challenges": []}


def all_challenges() -> List[Dict[str, Any]]:
    return _load_data().get("challenges", []) or []


def get_challenge(challenge_id: str) -> Optional[Dict[str, Any]]:
    for c in all_challenges():
        if c.get("id") == challenge_id:
            return c
    return None


def ensure_challenge_state(profile: Dict[str, Any]) -> Dict[str, Any]:
    """确保 profile 含合法的挑战相关字段。"""
    if not isinstance(profile.get("unlocked_challenges"), list):
        profile["unlocked_challenges"] = []
    if not isinstance(profile.get("completed_challenges"), list):
        profile["completed_challenges"] = []
    if "active_challenge" not in profile or not isinstance(profile["active_challenge"], (str, type(None))):
        profile["active_challenge"] = None
    return profile


def is_unlocked(profile: Dict[str, Any], challenge_id: str) -> bool:
    """挑战是否已解锁（默认全部可玩，除非 challenge.unlock_required）。"""
    ensure_challenge_state(profile)
    c = get_challenge(challenge_id)
    if not c:
        return False
    # 简化策略：所有挑战默认可玩（降低门槛，鼓励尝试）
    # 若需链式解锁，可在 challenge 加 requires_unlock 字段
    return True


def start_challenge(profile: Dict[str, Any], challenge_id: str) -> Dict[str, Any]:
    """激活一个挑战。

    返回：
        {"ok": bool, "start_override": dict, "message": str}
    """
    ensure_challenge_state(profile)
    c = get_challenge(challenge_id)
    if not c:
        return {"ok": False, "start_override": {}, "message": "挑战不存在"}
    if profile.get("active_challenge") is not None:
        return {"ok": False, "start_override": {},
                "message": "已有进行中的挑战，需先完成或放弃"}
    profile["active_challenge"] = challenge_id
    return {
        "ok": True,
        "start_override": c.get("start_override", {}) or {},
        "message": f"挑战已激活：{c.get('name', challenge_id)}。{c.get('flavor', '')}",
    }


def abandon_challenge(profile: Dict[str, Any]) -> bool:
    """放弃当前挑战（不结算奖励）。返回是否成功放弃。"""
    ensure_challenge_state(profile)
    if profile.get("active_challenge") is None:
        return False
    profile["active_challenge"] = None
    return True


def active_challenge(profile: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """返回当前激活的挑战定义（无则 None）。"""
    ensure_challenge_state(profile)
    cid = profile.get("active_challenge")
    if not cid:
        return None
    return get_challenge(cid)


def validate_restrictions(player: Any, challenge: Dict[str, Any]) -> Dict[str, Any]:
    """校验玩家是否违反挑战限制。

    返回：
        {"violations": [str,...], "ok": bool}
    违反不结束游戏，仅标记（表现层可提示，最终结算时记为挑战失败）。
    """
    violations: List[str] = []
    restrictions = challenge.get("restrictions") or {}
    if not isinstance(restrictions, dict):
        return {"violations": [], "ok": True}

    # max_dimension（王权模式维度上限）
    max_dim = restrictions.get("max_dimension") or {}
    if isinstance(max_dim, dict) and getattr(player, "decision_tree", None) is not None:
        dt = player.decision_tree
        for dim, cap in max_dim.items():
            if hasattr(dt, "dimensions") and dim in dt.dimensions:
                if dt.dimensions[dim] > cap:
                    violations.append(f"{dim} 超过上限 {cap}（当前 {dt.dimensions[dim]}）")

    # must_keep_trait
    must_trait = restrictions.get("must_keep_trait")
    if must_trait and isinstance(must_trait, str):
        traits = getattr(player, "traits", []) or []
        if must_trait not in traits:
            violations.append(f"已失去必备特质：{must_trait}")

    # max_education
    max_edu = restrictions.get("max_education")
    if max_edu:
        chain = ("none", "high_school", "bachelor", "master", "phd")
        cur = getattr(player, "education", "none")
        if cur in chain and max_edu in chain and chain.index(cur) > chain.index(max_edu):
            violations.append(f"教育程度 {cur} 超过挑战上限 {max_edu}")

    return {"violations": violations, "ok": not violations}


def check_win(player: Any, profile: Dict[str, Any], challenge: Dict[str, Any]) -> Dict[str, Any]:
    """检查胜利条件是否满足。

    返回：
        {"won": bool, "reasons_met": [str], "reasons_unmet": [str]}
    """
    met: List[str] = []
    unmet: List[str] = []
    conds = challenge.get("win_conditions") or {}
    if not isinstance(conds, dict):
        return {"won": False, "reasons_met": [], "reasons_unmet": ["胜利条件缺失"]}

    # wealth_gte
    if "wealth_gte" in conds:
        v = conds["wealth_gte"]
        if getattr(player, "wealth", 0) >= v:
            met.append(f"财富≥{v}")
        else:
            unmet.append(f"财富≥{v}（当前 {getattr(player,'wealth',0)}）")
    # age_lte / age_gte
    if "age_lte" in conds:
        v = conds["age_lte"]
        if getattr(player, "age", 0) <= v:
            met.append(f"年龄≤{v}")
        else:
            unmet.append(f"年龄≤{v}（当前 {getattr(player,'age',0)}）")
    if "age_gte" in conds:
        v = conds["age_gte"]
        if getattr(player, "age", 0) >= v:
            met.append(f"年龄≥{v}")
        else:
            unmet.append(f"年龄≥{v}（当前 {getattr(player,'age',0)}）")
    # career_tier_gte
    if "career_tier_gte" in conds:
        v = conds["career_tier_gte"]
        if getattr(player, "career_tier", 0) >= v:
            met.append(f"职业等级≥{v}")
        else:
            unmet.append(f"职业等级≥{v}（当前 {getattr(player,'career_tier',0)}）")
    # happiness_gte
    if "happiness_gte" in conds:
        v = conds["happiness_gte"]
        if getattr(player, "happiness", 0) >= v:
            met.append(f"幸福≥{v}")
        else:
            unmet.append(f"幸福≥{v}（当前 {getattr(player,'happiness',0)}）")
    # has_trait
    ht = conds.get("has_trait")
    if ht:
        traits = getattr(player, "traits", []) or []
        if ht in traits:
            met.append(f"持有特质：{ht}")
        else:
            unmet.append(f"需持有特质：{ht}")
    # mode
    m = conds.get("mode")
    if m:
        cur = getattr(player, "game_mode", "") or ""
        if cur == m:
            met.append(f"模式：{m}")
        else:
            unmet.append(f"需在 {m} 模式（当前 {cur or '未设定'}）")
    # bankruptcies_gte
    if "bankruptcies_gte" in conds:
        v = conds["bankruptcies_gte"]
        count = sum(1 for e in (getattr(player, "run_log", []) or [])
                    if isinstance(e, dict) and e.get("event") == "bankruptcy")
        if count >= v:
            met.append(f"破产≥{v}次")
        else:
            unmet.append(f"破产≥{v}次（当前 {count}）")
    # distinct_career_categories_tier3_gte
    if "distinct_career_categories_tier3_gte" in conds:
        v = conds["distinct_career_categories_tier3_gte"]
        cats = set()
        for e in (getattr(player, "run_log", []) or []):
            if isinstance(e, dict) and e.get("event") == "career_reached" \
                    and e.get("tier", 0) >= 3:
                cats.add(e.get("category"))
        if len(cats) >= v:
            met.append(f"不同职业门类tier3≥{v}")
        else:
            unmet.append(f"不同职业门类tier3≥{v}（当前 {len(cats)}）")
    # mode_switched_to
    mst = conds.get("mode_switched_to")
    if mst:
        switched = any(isinstance(e, dict) and e.get("event") == "mode_switch"
                       and e.get("to") == mst
                       for e in (getattr(player, "run_log", []) or []))
        if switched:
            met.append(f"已切换至 {mst} 模式")
        else:
            unmet.append(f"需切换至 {mst} 模式")

    return {"won": not unmet, "reasons_met": met, "reasons_unmet": unmet}


def complete_challenge(profile: Dict[str, Any], challenge_id: str) -> Dict[str, Any]:
    """完成挑战，发放奖励。

    返回：
        {"ok": bool, "reward": dict, "message": str}
    """
    ensure_challenge_state(profile)
    c = get_challenge(challenge_id)
    if not c:
        return {"ok": False, "reward": {}, "message": "挑战不存在"}
    if challenge_id in profile.get("completed_challenges", []):
        return {"ok": False, "reward": {}, "message": "挑战已完成过"}
    if profile.get("active_challenge") != challenge_id:
        return {"ok": False, "reward": {}, "message": "挑战未激活"}

    profile["completed_challenges"].append(challenge_id)
    profile["active_challenge"] = None
    reward = c.get("reward") or {}

    # 解锁物写入 profile（天赋池/出身选项/模式/成就）
    if reward.get("unlock_talent"):
        ut = reward["unlock_talent"]
        if isinstance(ut, str) and ut not in profile.get("unlocked_talents", []):
            profile.setdefault("unlocked_talents", []).append(ut)
    if reward.get("unlock_background_option"):
        ub = reward["unlock_background_option"]
        if isinstance(ub, str) and ub not in profile.get("unlocked_background_options", []):
            profile.setdefault("unlocked_background_options", []).append(ub)
    if reward.get("unlock_mode"):
        um = reward["unlock_mode"]
        if isinstance(um, str) and um not in profile.get("unlocked_modes", []):
            profile.setdefault("unlocked_modes", []).append(um)
    if reward.get("unlock_achievement"):
        # 成就解锁由成就系统统一处理，这里仅记录触发
        pass

    return {
        "ok": True,
        "reward": reward,
        "message": f"挑战完成：{c.get('name', challenge_id)}！奖励已发放。",
    }


def challenge_summary(profile: Dict[str, Any]) -> Dict[str, Any]:
    """返回挑战进度摘要（供图鉴展示）。"""
    ensure_challenge_state(profile)
    completed = profile.get("completed_challenges", []) or []
    active = profile.get("active_challenge")
    return {
        "total": len(all_challenges()),
        "completed": len(completed),
        "completed_ids": list(completed),
        "active_id": active,
        "active": get_challenge(active) if active else None,
    }
