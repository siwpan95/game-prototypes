# -*- coding: utf-8 -*-
"""
core/runtime.py — CLI / GUI 共用的运行时接线层

职责：把散落的子系统（profile / streaks / heirlooms / challenges / endings）
收口成两个生命周期钩子，让 main.py 与 game_gui.py 只需各调一次，
避免两套表现层重复实现同一套业务流程。

    session_start()        进程启动时调一次 → 连胜打卡，返回浮层素材
    begin_run(player)      新一局开始前调 → 应用挑战覆写 + 传家宝加成 + 连胜 buff
    finish_run(player)     结局页渲染前调 → 解析结局 + 写档案 + 判挑战 + 掷传承

本模块零 UI 依赖：禁止 import tkinter / print / input / time.sleep。
所有函数永不抛异常，失败时返回结构完整的降级结果（R6）。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from core import paths

# ───────────────────────────────────────────────────────
# Profile 单例（进程内共享，避免 CLI/GUI 各读一份导致覆盖丢失）
# ───────────────────────────────────────────────────────
_PROFILE: Optional[Any] = None


def get_profile() -> Any:
    """取全局 Profile 实例（懒加载 + 缓存）。永不抛异常。"""
    global _PROFILE
    if _PROFILE is not None:
        return _PROFILE
    try:
        from core.profile import Profile
        _PROFILE = Profile(paths.PROFILE_PATH).load()
    except Exception:
        # 极端降级：伪 Profile，保证调用方不崩
        class _NullProfile:
            data: Dict[str, Any] = {}
            message = ""
            was_corrupt = False

            def save(self) -> bool:
                return False

        _PROFILE = _NullProfile()
    return _PROFILE


def save_profile() -> bool:
    """写回档案。失败返回 False，不抛异常。"""
    try:
        return bool(get_profile().save())
    except Exception:
        return False


def reset_profile_cache() -> None:
    """清空单例（测试用）。"""
    global _PROFILE
    _PROFILE = None


# ───────────────────────────────────────────────────────
# 1) 进程启动：连胜打卡
# ───────────────────────────────────────────────────────
def session_start() -> Dict[str, Any]:
    """进程启动时调用一次，记录今日登录并返回连胜浮层素材。

    返回：
        {
          "ok": bool,
          "streak": int,            # 当前连胜天数
          "best": int,              # 历史最佳
          "is_new_day": bool,       # 今天是否首次登录（False 表示同日重复启动）
          "message": str,           # 浮层主文案
          "milestone": dict|None,   # 命中的里程碑奖励
          "next_milestone": int|None,
        }
    """
    fallback = {"ok": False, "streak": 0, "best": 0, "is_new_day": False,
                "broken": False, "message": "", "milestone": None,
                "next_milestone": None}
    try:
        from core import streaks
        prof = get_profile()
        before = streaks.get_streak_summary(prof.data).get("last_play_date")
        res = streaks.record_play(prof.data)
        after = streaks.get_streak_summary(prof.data)
        save_profile()
        return {
            "ok": True,
            "streak": res.get("streak", 0),
            "best": after.get("max_streak", res.get("streak", 0)),
            "is_new_day": before != after.get("last_play_date"),
            "broken": bool(res.get("broken", False)),
            "message": res.get("message", ""),
            "milestone": res.get("milestone_reward"),
            "next_milestone": after.get("next_milestone"),
        }
    except Exception:
        return fallback


# ───────────────────────────────────────────────────────
# 2) 开局：应用挑战覆写 / 传家宝 / 连胜 buff
# ───────────────────────────────────────────────────────
def begin_run(player: Any) -> Dict[str, Any]:
    """新一局开始前调用。原地修改 player，返回本局生效的加成清单。

    返回：
        {
          "challenge": dict|None,   # 本局激活的挑战
          "start_override": dict,   # 挑战强制的开局覆写（已应用）
          "heirlooms": [dict],      # 生效的传家宝（含效果摘要）
          "streak_buff": dict,      # 连胜增益（已应用）
          "notes": [str],           # 给表现层直接显示的中文提示
        }
    """
    out: Dict[str, Any] = {
        "challenge": None, "start_override": {}, "heirlooms": [],
        "streak_buff": {}, "notes": [],
    }
    prof = get_profile()

    # ── 档案计数 ──
    try:
        prof.data["total_runs"] = int(prof.data.get("total_runs", 0)) + 1
    except Exception:
        pass

    # ── 挑战：开局覆写 ──
    try:
        from core import challenges
        c = challenges.active_challenge(prof.data)
        if c:
            out["challenge"] = c
            ov = c.get("start_override") or {}
            if isinstance(ov, dict):
                out["start_override"] = ov
                for key, val in ov.items():
                    if key.endswith("_blacklist") or key.endswith("_whitelist"):
                        continue  # 名单类由天赋/卡池系统各自消费
                    if isinstance(val, (int, float)) and hasattr(player, key):
                        setattr(player, key, val)
                    elif isinstance(val, str) and hasattr(player, key):
                        setattr(player, key, val)
            out["notes"].append(f"挑战「{c.get('name','?')}」已激活：{c.get('flavor','')}")
    except Exception:
        pass

    # ── 传家宝：属性加成 ──
    try:
        from core import heirlooms
        summary = heirlooms.apply_heirlooms(player, prof.data)
        applied = summary.get("applied") or []
        out["heirlooms"] = applied
        for item in applied:
            out["notes"].append(
                f"传家宝「{item.get('name','?')}」生效：{item.get('effects_summary','')}"
            )
    except Exception:
        pass

    # ── 连胜 buff ──
    try:
        from core import streaks
        buff = streaks.consume_pending_buff(prof.data)
        if buff:
            out["streak_buff"] = buff
            parts: List[str] = []
            for key, val in buff.items():
                if not isinstance(val, (int, float)):
                    continue
                cur = getattr(player, key, None)
                if isinstance(cur, (int, float)):
                    setattr(player, key, cur + val)
                    parts.append(f"{key}{'+' if val >= 0 else ''}{val}")
            if parts:
                out["notes"].append("连胜奖励生效：" + "、".join(parts))
    except Exception:
        pass

    save_profile()
    return out


# ───────────────────────────────────────────────────────
# 3) 收局：结局解析 + 档案写入 + 挑战判定 + 传承掷骰
# ───────────────────────────────────────────────────────
def finish_run(player: Any, mode: str = "") -> Dict[str, Any]:
    """一局结束时调用。解析结局、写档案、判挑战、掷传承。

    返回：
        {
          "ending": Ending|None,
          "ending_name": str,
          "ending_text": str,
          "ending_rarity": str,
          "ending_category": str,
          "is_new_ending": bool,
          "collection": {"seen": int, "total": int, ...},
          "also_matched": [Ending],   # 副结局（差一点就是它）
          "challenge_result": dict|None,
          "inheritance": dict|None,
          "notes": [str],
        }
    """
    out: Dict[str, Any] = {
        "ending": None, "ending_name": "", "ending_text": "",
        "ending_rarity": "common", "ending_category": "normal",
        "is_new_ending": False, "collection": {},
        "also_matched": [], "challenge_result": None,
        "inheritance": None, "notes": [],
    }
    prof = get_profile()

    # ── 结局解析 ──
    try:
        from core import endings as E
        e = E.resolve(player, mode)
        if e is not None:
            out["ending"] = e
            out["ending_name"] = getattr(e, "name", "")
            out["ending_text"] = getattr(e, "text", "")
            out["ending_rarity"] = getattr(e, "rarity", "common")
            out["ending_category"] = getattr(e, "category", "normal")
            rec = E.record_ending(prof.data, e)
            out["is_new_ending"] = rec.get("is_new", False)
            if rec.get("is_new"):
                out["notes"].append(f"新结局解锁：{out['ending_name']}")
            # 副结局：排除主结局本身
            others = [x for x in E.resolve_all_matching(player, mode, limit=4)
                      if getattr(x, "id", "") != getattr(e, "id", "")]
            out["also_matched"] = others[:3]
        out["collection"] = E.collection_summary(prof.data)
    except Exception:
        pass

    # ── 档案统计 ──
    try:
        stats = prof.data.setdefault("stats", {})
        age = getattr(player, "age", 0)
        if isinstance(age, (int, float)) and age > stats.get("longest_life", 0):
            stats["longest_life"] = int(age)
        score = getattr(player, "score", 0)
        bonus = int(getattr(out["ending"], "score_bonus", 0) or 0) if out["ending"] else 0
        total_score = (score if isinstance(score, (int, float)) else 0) + bonus
        if total_score > stats.get("best_score", 0):
            stats["best_score"] = int(total_score)
    except Exception:
        pass

    # ── 挑战判定 ──
    try:
        from core import challenges
        c = challenges.active_challenge(prof.data)
        if c:
            win = challenges.check_win(player, prof.data, c)
            result: Dict[str, Any] = {
                "challenge": c,
                "won": win.get("won", False),
                "reasons_met": win.get("reasons_met", []),
                "reasons_unmet": win.get("reasons_unmet", []),
                "reward": {},
                "message": "",
            }
            if win.get("won"):
                comp = challenges.complete_challenge(prof.data, c.get("id", ""))
                result["reward"] = comp.get("reward", {})
                result["message"] = comp.get("message", "")
                out["notes"].append(f"挑战达成：{c.get('name','?')}")
            else:
                challenges.abandon_challenge(prof.data)
                result["message"] = f"挑战「{c.get('name','?')}」失败，条件未满足。"
                out["notes"].append(result["message"])
            out["challenge_result"] = result
    except Exception:
        pass

    # ── 传家宝传承掷骰 ──
    try:
        from core import heirlooms
        if heirlooms.held_heirloom_ids(prof.data):
            inh = heirlooms.roll_inheritance(prof.data)
            out["inheritance"] = inh
            if inh.get("lost_names"):
                out["notes"].append("传承失落：" + "、".join(inh["lost_names"]))
            if inh.get("kept"):
                names = []
                for hid in inh["kept"]:
                    h = heirlooms.get_heirloom(hid)
                    names.append(h.get("name", hid) if h else hid)
                out["notes"].append("传给下一代：" + "、".join(names))
    except Exception:
        pass

    save_profile()
    return out


# ───────────────────────────────────────────────────────
# 只读摘要（供图鉴 / 状态栏）
# ───────────────────────────────────────────────────────
def overview() -> Dict[str, Any]:
    """一次性取回所有系统的展示摘要。"""
    prof = get_profile()
    data = prof.data
    out: Dict[str, Any] = {
        "total_runs": data.get("total_runs", 0),
        "stats": data.get("stats", {}),
        "streak": {}, "lineage": {}, "challenges": {}, "endings": {},
    }
    try:
        from core import streaks
        out["streak"] = streaks.get_streak_summary(data)
    except Exception:
        pass
    try:
        from core import heirlooms
        out["lineage"] = heirlooms.lineage_summary(data)
    except Exception:
        pass
    try:
        from core import challenges
        out["challenges"] = challenges.challenge_summary(data)
    except Exception:
        pass
    try:
        from core import endings as E
        out["endings"] = E.collection_summary(data)
    except Exception:
        pass
    return out
