# -*- coding: utf-8 -*-
"""
core/endings.py — 结局解析器（数据驱动，替代硬编码 if/elif 链）

设计要点：
    1. 从 content/endings.json 读取 60 个结局，按 priority 降序遍历，首个条件全部命中者胜出。
    2. 条件求值全部走 getattr + 默认值，任何缺失字段都不抛异常（R6 容错原则）。
    3. 保留 legacy_tag：旧版 12 个硬编码结局迁移后 tag 不变，表现层可据此对照回归。
    4. 兜底：若无任何结局命中（理论上不会，end_normal_quiet_end 条件为空），返回该兜底结局；
       仍失败则返回 None，调用方需自行降级到原文案。

本模块零 UI 依赖：禁止 import tkinter / print / input / time.sleep。

条件 schema（conditions 字典）：
    数值区间   "wealth": [12, 999]          → 12 <= player.wealth <= 999
    数值精确   "career_tier": 5             → player.career_tier == 5
    数值区间   "career_tier": [1, 2]        → 1 <= player.career_tier <= 2
    字符串精确 "mode": "reigns"             → 归一化后模式相等
    字符串精确 "career_category": "medical" → 由 career_id 反查职业门类
    特质任一   "traits_any": ["神秘知识"]    → 任一命中即可
    关系值     "relationships_partner": [80, 999]
    王权维度   "STABILITY": [80, 999]       → player.decision_tree.dimensions[Dimension.STABILITY]
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

# 王权维度键名（大写即视为维度，与属性键区分）
REIGNS_DIM_KEYS = (
    "STRENGTH", "INTELLIGENCE", "CHARISMA", "WEALTH", "MORALITY",
    "STABILITY", "CHURCH", "NOBLES", "COMMONERS", "HEALTH", "HAPPINESS",
)

# 直接从 player 取的数值属性
_PLAYER_NUMERIC = (
    "age", "wealth", "happiness", "charisma", "intelligence",
    "strength", "agility", "luck", "health", "career_tier", "score",
)

# 兜底结局 id（conditions 为空，priority 最低）
FALLBACK_ENDING_ID = "end_normal_quiet_end"


# ───────────────────────────────────────────────────────
# 内容读取（懒加载 + 进程内缓存）
# ───────────────────────────────────────────────────────
_ENDINGS_CACHE: Optional[List[Any]] = None
_CAREER_CATEGORY_MAP: Optional[Dict[str, str]] = None


def _load() -> Tuple[List[Any], Dict[str, str]]:
    """懒加载结局表与「职业 id → 门类」映射。失败时返回空表，不抛异常。"""
    global _ENDINGS_CACHE, _CAREER_CATEGORY_MAP
    if _ENDINGS_CACHE is not None and _CAREER_CATEGORY_MAP is not None:
        return _ENDINGS_CACHE, _CAREER_CATEGORY_MAP

    endings: List[Any] = []
    cat_map: Dict[str, str] = {}
    try:
        from core.content_loader import ContentLoader
        loader = ContentLoader()
        loader.load()
        endings = list(loader.endings())
        for c in loader.careers():
            cid = getattr(c, "id", "")
            if cid:
                cat_map[cid] = getattr(c, "category", "")
    except Exception:
        endings = []
        cat_map = {}

    # 按 priority 降序；同优先级按 id 稳定排序，保证可复现
    endings.sort(key=lambda e: (-int(getattr(e, "priority", 0) or 0), getattr(e, "id", "")))

    _ENDINGS_CACHE = endings
    _CAREER_CATEGORY_MAP = cat_map
    return endings, cat_map


def reload_cache() -> None:
    """清空缓存（内容热更新 / 单元测试用）。"""
    global _ENDINGS_CACHE, _CAREER_CATEGORY_MAP
    _ENDINGS_CACHE = None
    _CAREER_CATEGORY_MAP = None


def all_endings() -> List[Any]:
    """返回全部结局（已按 priority 降序）。"""
    return list(_load()[0])


def get_ending(ending_id: str) -> Optional[Any]:
    """按 id 取单个结局。"""
    for e in _load()[0]:
        if getattr(e, "id", "") == ending_id:
            return e
    return None


# ───────────────────────────────────────────────────────
# 玩家上下文快照
# ───────────────────────────────────────────────────────
def build_context(player: Any, mode: str = "") -> Dict[str, Any]:
    """把 player 压平成条件求值用的扁平字典。任何缺失字段都取安全默认值。"""
    ctx: Dict[str, Any] = {}

    for key in _PLAYER_NUMERIC:
        val = getattr(player, key, 0)
        ctx[key] = val if isinstance(val, (int, float)) else 0

    # 模式：显式传入优先，否则读 player.game_mode，最后归一化
    raw_mode = mode or getattr(player, "game_mode", "") or ""
    try:
        from core import constants
        ctx["mode"] = constants.normalize_mode(raw_mode) if raw_mode else ""
    except Exception:
        ctx["mode"] = raw_mode

    # 特质
    traits = getattr(player, "traits", None)
    ctx["traits"] = list(traits) if isinstance(traits, list) else []

    # 关系值 → relationships_parent / _partner / _friend
    rel = getattr(player, "relationships", None)
    if not isinstance(rel, dict):
        rel = {}
    for who in ("parent", "partner", "friend"):
        v = rel.get(who, 0)
        ctx[f"relationships_{who}"] = v if isinstance(v, (int, float)) else 0

    # 职业门类：由 career_id 反查
    cat_map = _load()[1]
    career_id = getattr(player, "career_id", None)
    ctx["career_category"] = cat_map.get(career_id, "") if career_id else ""

    # 教育
    ctx["education"] = getattr(player, "education", "none") or "none"

    # 王权维度
    dims = _extract_reigns_dims(player)
    ctx.update(dims)

    return ctx


def _extract_reigns_dims(player: Any) -> Dict[str, int]:
    """从 decision_tree 提取 11 个维度值。非王权模式返回空字典。"""
    out: Dict[str, int] = {}
    dt = getattr(player, "decision_tree", None)
    if dt is None:
        return out
    dims = getattr(dt, "dimensions", None)
    if not isinstance(dims, dict):
        return out
    try:
        from decision_tree import Dimension
    except Exception:
        return out
    for name in REIGNS_DIM_KEYS:
        member = getattr(Dimension, name, None)
        if member is None:
            continue
        v = dims.get(member)
        if isinstance(v, (int, float)):
            out[name] = v
    return out


# ───────────────────────────────────────────────────────
# 条件求值
# ───────────────────────────────────────────────────────
def _match_numeric(actual: Any, expect: Any) -> bool:
    """数值匹配：expect 为 [min, max] 区间或标量精确值。"""
    if not isinstance(actual, (int, float)):
        return False
    if isinstance(expect, (list, tuple)):
        if len(expect) != 2:
            return False
        lo, hi = expect[0], expect[1]
        if not isinstance(lo, (int, float)) or not isinstance(hi, (int, float)):
            return False
        return lo <= actual <= hi
    if isinstance(expect, (int, float)):
        return actual == expect
    return False


def match_conditions(conditions: Dict[str, Any], ctx: Dict[str, Any]) -> bool:
    """全部条件命中才返回 True。空条件恒为 True（兜底结局）。"""
    if not isinstance(conditions, dict) or not conditions:
        return True

    for key, expect in conditions.items():
        # 特质任一命中
        if key == "traits_any":
            if not isinstance(expect, (list, tuple)):
                return False
            traits = ctx.get("traits", [])
            if not any(t in traits for t in expect):
                return False
            continue

        # 特质全部命中（预留扩展）
        if key == "traits_all":
            if not isinstance(expect, (list, tuple)):
                return False
            traits = ctx.get("traits", [])
            if not all(t in traits for t in expect):
                return False
            continue

        # 字符串精确匹配
        if key in ("mode", "career_category", "education", "era"):
            if ctx.get(key, "") != expect:
                return False
            continue

        # 王权维度：非王权模式（无该维度）直接判否
        if key in REIGNS_DIM_KEYS:
            if key not in ctx:
                return False
            if not _match_numeric(ctx[key], expect):
                return False
            continue

        # 其余一律按数值处理
        if not _match_numeric(ctx.get(key), expect):
            return False

    return True


# ───────────────────────────────────────────────────────
# 主入口
# ───────────────────────────────────────────────────────
def resolve(player: Any, mode: str = "") -> Optional[Any]:
    """解析玩家最终结局。按 priority 降序，首个全条件命中者胜出。

    参数：
        player  Player 实例（main.py 或 game_gui.py 的都可以，走 getattr）
        mode    显式模式覆盖（traditional / reigns / cultivation）

    返回：
        Ending dataclass 或 None（内容缺失时）
    """
    endings, _ = _load()
    if not endings:
        return None

    ctx = build_context(player, mode)

    for e in endings:
        conds = getattr(e, "conditions", None)
        if not isinstance(conds, dict):
            conds = {}
        # 空条件的兜底结局留到最后再取，避免它抢走高优先级之外的匹配
        if not conds and getattr(e, "id", "") == FALLBACK_ENDING_ID:
            continue
        if match_conditions(conds, ctx):
            return e

    # 兜底
    return get_ending(FALLBACK_ENDING_ID)


def resolve_all_matching(player: Any, mode: str = "", limit: int = 5) -> List[Any]:
    """返回所有命中的结局（按 priority 降序，最多 limit 个）。

    用途：结算页展示「你还差一点就触发了 XX 结局」之类的副结局提示。
    """
    endings, _ = _load()
    if not endings:
        return []
    ctx = build_context(player, mode)
    out: List[Any] = []
    for e in endings:
        conds = getattr(e, "conditions", None)
        if not isinstance(conds, dict):
            conds = {}
        if not conds:
            continue
        if match_conditions(conds, ctx):
            out.append(e)
            if len(out) >= limit:
                break
    return out


# ───────────────────────────────────────────────────────
# 档案写入（结局收集）
# ───────────────────────────────────────────────────────
def record_ending(profile_data: Dict[str, Any], ending: Any) -> Dict[str, Any]:
    """把结局写入 profile：seen_endings 去重追加 + stats 计数。

    参数：
        profile_data  Profile().data 字典（原地修改）
        ending        Ending dataclass

    返回：
        {"is_new": bool, "total_seen": int, "score_bonus": int}
    """
    if not isinstance(profile_data, dict) or ending is None:
        return {"is_new": False, "total_seen": 0, "score_bonus": 0}

    eid = getattr(ending, "id", "")
    if not eid:
        return {"is_new": False, "total_seen": 0, "score_bonus": 0}

    seen = profile_data.get("seen_endings")
    if not isinstance(seen, list):
        seen = []
        profile_data["seen_endings"] = seen

    is_new = eid not in seen
    if is_new:
        seen.append(eid)

    stats = profile_data.get("stats")
    if not isinstance(stats, dict):
        stats = {}
        profile_data["stats"] = stats
    stats["total_endings"] = len(seen)

    return {
        "is_new": is_new,
        "total_seen": len(seen),
        "score_bonus": int(getattr(ending, "score_bonus", 0) or 0),
    }


def collection_summary(profile_data: Dict[str, Any]) -> Dict[str, Any]:
    """结局图鉴统计：已解锁 / 总数 / 分类进度。"""
    endings, _ = _load()
    total = len(endings)
    seen_raw = profile_data.get("seen_endings") if isinstance(profile_data, dict) else None
    seen = set(seen_raw) if isinstance(seen_raw, list) else set()

    by_cat: Dict[str, Dict[str, int]] = {}
    for e in endings:
        cat = getattr(e, "category", "normal") or "normal"
        slot = by_cat.setdefault(cat, {"seen": 0, "total": 0})
        slot["total"] += 1
        if getattr(e, "id", "") in seen:
            slot["seen"] += 1

    return {
        "seen": len(seen & {getattr(e, "id", "") for e in endings}),
        "total": total,
        "by_category": by_cat,
    }
