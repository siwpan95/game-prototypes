# -*- coding: utf-8 -*-
"""
core/content_loader.py — 内容总加载器（B1：存量 JSON + content/ 深合并）

设计要点：
- 根目录存量 JSON（backgrounds.json / events.json / decision_cards.json）原地保留；
  content/ 目录（B3 起填充）做深合并叠加。删掉 content/ 仍能游玩（R10）。
- 坏文件（缺失/损坏/非 dict）跳过不崩，记录到 self.errors。
- 建 id 索引并查重；补可选字段默认值（R9）。
- 本模块零 UI 依赖，禁止 import tkinter / print / input / time.sleep。
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from core import jsonio
from core import paths
from core.models import CardItem, Career, Ending, Achievement, EventItem, Talent


# 事件分组键（R8：4 个分组键不得删除或重命名）
# P0-7 新增 by_career / by_trait 两个分组键（仅新增不删除，符合 R8）
EVENT_GROUP_KEYS = ("generic", "by_wealth", "by_personality", "by_age", "by_career", "by_trait")


class ContentLoader:
    """统一内容加载器。"""

    def __init__(self) -> None:
        self.errors: List[str] = []
        self.raw: Dict[str, Any] = {}
        self.index: Dict[str, Any] = {}
        self._cards_by_id: Dict[str, CardItem] = {}
        self._events_merged: Dict[str, Any] = {}

    # ───────────────────────────────────────────────────────
    # 加载入口
    # ───────────────────────────────────────────────────────
    def load(self) -> "ContentLoader":
        """执行全量加载（根目录存量 + content/ 深合并）。幂等。"""
        self.errors = []
        self.raw = {}
        self.index = {}
        self._cards_by_id = {}
        self._events_merged = {}

        # 1) 根目录存量
        root_data: Dict[str, Any] = {}
        for fname in (paths.BACKGROUND_FILE, paths.EVENTS_FILE, paths.CARDS_FILE):
            data = jsonio.read_json(paths.ROOT / fname, default=None)
            if data is None:
                self.errors.append(f"根目录缺失或无法解析: {fname}")
                continue
            if not isinstance(data, dict):
                self.errors.append(f"根目录文件顶层非 dict: {fname}")
                continue
            root_data = self._deep_merge(root_data, data)

        # 2) content/ 目录深合并（内容目录不存在时直接跳过，R10）
        content_data: Dict[str, Any] = {}
        if paths.CONTENT_DIR.exists() and paths.CONTENT_DIR.is_dir():
            for jf in sorted(paths.CONTENT_DIR.rglob("*.json")):
                data = jsonio.read_json(jf, default=None)
                if data is None:
                    self.errors.append(f"内容文件无法解析: {jf.name}")
                    continue
                if not isinstance(data, dict):
                    self.errors.append(f"内容文件顶层非 dict: {jf.name}")
                    continue
                content_data = self._deep_merge(content_data, data)
        else:
            # content/ 不存在是正常情况（B1 阶段），不视为错误
            pass

        self.raw = self._deep_merge(root_data, content_data)
        self._build_index()
        return self

    # ───────────────────────────────────────────────────────
    # 深合并
    # ───────────────────────────────────────────────────────
    def _deep_merge(self, base: Any, extra: Any) -> Any:
        """深合并：dict 递归；list 拼接（去重保留顺序，按 id 或整体判等）；
        其余类型 extra 覆盖 base。"""
        if isinstance(base, list) and isinstance(extra, list):
            # 同为 list：按 id 去重追加，绝不整体覆盖
            # （否则 content/ 的 cards/events 会静默抹掉根目录存量条目）
            return self._merge_list(base, extra)
        if not isinstance(base, dict) or not isinstance(extra, dict):
            # 非 dict：extra 覆盖 base（base 为 None 也成立）
            return extra
        result = dict(base)
        for key, val in extra.items():
            if key in result:
                result[key] = self._deep_merge(result[key], val)
            else:
                result[key] = val
        return result

    def _merge_list(self, base: List[Any], extra: List[Any]) -> List[Any]:
        """列表拼接，按 id 去重；无 id 的项直接追加。"""
        out: List[Any] = list(base)
        seen_ids = {
            item.get("id") for item in base if isinstance(item, dict) and item.get("id")
        }
        for item in extra:
            if isinstance(item, dict) and item.get("id"):
                if item["id"] in seen_ids:
                    continue
                seen_ids.add(item["id"])
            out.append(item)
        return out

    # ───────────────────────────────────────────────────────
    # 索引构建
    # ───────────────────────────────────────────────────────
    def _build_index(self) -> None:
        # 决策卡
        cards_raw = self.raw.get("cards", []) or []
        if not isinstance(cards_raw, list):
            cards_raw = []
        for c in cards_raw:
            if not isinstance(c, dict):
                continue
            item = CardItem.from_raw(c)
            if not item.id:
                self.errors.append("决策卡缺少 id，已跳过")
                continue
            if item.id in self._cards_by_id:
                self.errors.append(f"决策卡 id 重复: {item.id}")
                continue
            self._cards_by_id[item.id] = item

        # 事件：合并 event_templates（根目录 + content/ 同名分组/子组拼接）
        templates = self.raw.get("event_templates", {}) or {}
        if not isinstance(templates, dict):
            templates = {}
        merged: Dict[str, Any] = {}
        for group_key in EVENT_GROUP_KEYS:
            group = templates.get(group_key, {}) or {}
            if isinstance(group, list):
                # 兼容 list 形状分组（如 events.json 的 generic 是列表而非 dict）
                merged[group_key] = {}
                for idx, item in enumerate(group):
                    if not isinstance(item, dict):
                        continue
                    eid = item.get("id") or f"_generic_{idx}"
                    merged[group_key][eid] = [item]
                continue
            if not isinstance(group, dict):
                continue
            merged[group_key] = {}
            for sub_key, items in group.items():
                if not isinstance(items, list):
                    continue
                merged[group_key][sub_key] = list(items)
        self._events_merged = merged
        self.index["cards"] = list(self._cards_by_id.keys())
        self.index["events_groups"] = {k: list(v.keys()) for k, v in merged.items()}

    # ───────────────────────────────────────────────────────
    # 对外查询接口
    # ───────────────────────────────────────────────────────
    def cards(self, era: Optional[str] = None) -> List[CardItem]:
        """返回决策卡列表。era 为 None 返回全部；否则只返回 era in (era, 'any') 的卡。"""
        result = list(self._cards_by_id.values())
        if era is not None:
            result = [c for c in result if c.era in (era, "any", "")]
        return result

    def card(self, card_id: str) -> Optional[CardItem]:
        """按 id 取单张卡。"""
        return self._cards_by_id.get(card_id)

    def events(self, group: str, sub: Optional[str] = None) -> List[Dict[str, Any]]:
        """返回事件列表。group 为 'generic' 等分组键；sub 为子组（如 'rich'/'20s'）。
        sub 为 None 时返回该分组下所有子组合并（保留顺序、去重）。"""
        g = self._events_merged.get(group, {}) or {}
        if sub is not None:
            return list(g.get(sub, []) or [])
        out: List[Dict[str, Any]] = []
        seen_ids = set()
        for items in g.values():
            for ev in items:
                eid = ev.get("id") if isinstance(ev, dict) else None
                if eid and eid in seen_ids:
                    continue
                if eid:
                    seen_ids.add(eid)
                out.append(ev)
        return out

    def events_dict(self) -> Dict[str, Any]:
        """返回合并后的完整 event_templates（供表现层按原逻辑遍历）。"""
        return self._events_merged

    def backgrounds(self) -> Dict[str, Any]:
        """返回出身库，双形状兼容，缺失返回空 dict（绝不抛异常）。

        形状 1（包裹层）：``{"backgrounds": {"title":..., "steps": {...}}}``
        形状 2（平铺，根目录 backgrounds.json 实际形状）：
            ``{"title":..., "description":..., "steps": {...}}``
            —— 平铺键会被 _deep_merge 直接并入 self.raw，故需回退组装。
        优先返回形状 1；其 steps 为空时回退形状 2。返回值必含 ``steps``。
        """
        wrapped = self.raw.get("backgrounds")
        if isinstance(wrapped, dict) and isinstance(wrapped.get("steps"), dict) \
                and wrapped.get("steps"):
            return wrapped

        # 回退：从 raw 顶层平铺键组装
        flat: Dict[str, Any] = {}
        for key in ("title", "description", "steps"):
            val = self.raw.get(key)
            if val is not None:
                flat[key] = val
        steps = flat.get("steps")
        if isinstance(steps, dict) and steps:
            return flat

        # 两种形状都拿不到 steps：能给多少给多少，最差返回 {}
        if isinstance(wrapped, dict) and wrapped:
            return wrapped
        return {}

    def talents(self) -> List[Any]:
        """返回天赋列表（content/talents.json → List[Talent]）。

        降级策略（R10）：文件缺失 / JSON 损坏 / 结构非法时一律返回空列表，
        绝不抛异常——删掉整个 content/ 目录游戏仍须能玩。
        坏条目（非 dict / 缺 id / id 重复）逐条跳过并记入 self.errors。
        """
        raw_list = self.raw.get("talents", []) or []
        if not isinstance(raw_list, list):
            self.errors.append("talents 顶层非 list，已忽略")
            return []

        result: List[Talent] = []
        seen_ids: set = set()
        for raw in raw_list:
            if not isinstance(raw, dict):
                self.errors.append("天赋条目非 dict，已跳过")
                continue
            tid = raw.get("id") or ""
            if not tid:
                self.errors.append("天赋缺少 id，已跳过")
                continue
            if tid in seen_ids:
                self.errors.append(f"天赋 id 重复: {tid}")
                continue
            seen_ids.add(tid)
            try:
                weight = float(raw.get("weight", 1.0))
            except (TypeError, ValueError):
                weight = 1.0
            effects = raw.get("effects") or {}
            unlocks = raw.get("unlocks") or []
            result.append(
                Talent(
                    id=tid,
                    name=raw.get("name", "") or "",
                    rarity=raw.get("rarity", "common") or "common",
                    category=raw.get("category", "misc") or "misc",
                    description=raw.get("description", "") or "",
                    mutex_group=raw.get("mutex_group", "") or "",
                    weight=weight,
                    effects=effects if isinstance(effects, dict) else {},
                    unlocks=list(unlocks) if isinstance(unlocks, list) else [],
                    unlock_condition=raw.get("unlock_condition") or None,
                    inheritable=bool(raw.get("inheritable", False)),
                )
            )
        return result

    def careers(self) -> List[Career]:
        """返回职业列表（content/careers.json → List[Career]）。

        降级策略（R10）：文件缺失 / JSON 损坏 / 结构非法时返回空列表，
        绝不抛异常。坏条目逐条跳过并记入 self.errors。
        """
        raw_list = self.raw.get("careers", []) or []
        if not isinstance(raw_list, list):
            self.errors.append("careers 顶层非 list，已忽略")
            return []
        result: List[Career] = []
        seen_ids: set = set()
        for raw in raw_list:
            if not isinstance(raw, dict):
                self.errors.append("职业条目非 dict，已跳过")
                continue
            cid = raw.get("id") or ""
            if not cid:
                self.errors.append("职业缺少 id，已跳过")
                continue
            if cid in seen_ids:
                self.errors.append(f"职业 id 重复: {cid}")
                continue
            seen_ids.add(cid)
            try:
                result.append(Career.from_raw(raw))
            except (TypeError, ValueError) as e:
                self.errors.append(f"职业 {cid} 解析失败: {e}")
        return result

    def career(self, career_id: str) -> Optional[Career]:
        """按 id 取单个职业。"""
        for c in self.careers():
            if c.id == career_id:
                return c
        return None

    def careers_by_category(self, category: str) -> List[Career]:
        """按门类取职业列表，按 tier 升序。"""
        out = [c for c in self.careers() if c.category == category]
        out.sort(key=lambda c: c.tier)
        return out

    def endings(self) -> List[Ending]:
        """返回结局列表（content/endings.json → List[Ending]）。

        降级策略（R10）：文件缺失 / 损坏 / 非法时返回空列表。
        坏条目逐条跳过并记入 self.errors。
        """
        raw_list = self.raw.get("endings", []) or []
        if not isinstance(raw_list, list):
            self.errors.append("endings 顶层非 list，已忽略")
            return []
        result: List[Ending] = []
        seen_ids: set = set()
        for raw in raw_list:
            if not isinstance(raw, dict):
                self.errors.append("结局条目非 dict，已跳过")
                continue
            eid = raw.get("id") or ""
            if not eid:
                self.errors.append("结局缺少 id，已跳过")
                continue
            if eid in seen_ids:
                self.errors.append(f"结局 id 重复: {eid}")
                continue
            seen_ids.add(eid)
            try:
                result.append(Ending.from_raw(raw))
            except (TypeError, ValueError) as e:
                self.errors.append(f"结局 {eid} 解析失败: {e}")
        # 按 priority 降序排序（高优先级先匹配）
        result.sort(key=lambda e: e.priority, reverse=True)
        return result

    def ending(self, ending_id: str) -> Optional[Ending]:
        """按 id 取单个结局。"""
        for e in self.endings():
            if e.id == ending_id:
                return e
        return None

    def achievements(self) -> List[Achievement]:
        """返回成就列表（content/achievements.json → List[Achievement]）。

        降级策略（R10）：文件缺失 / 损坏 / 非法时返回空列表。
        坏条目逐条跳过并记入 self.errors。
        """
        raw_list = self.raw.get("achievements", []) or []
        if not isinstance(raw_list, list):
            self.errors.append("achievements 顶层非 list，已忽略")
            return []
        result: List[Achievement] = []
        seen_ids: set = set()
        for raw in raw_list:
            if not isinstance(raw, dict):
                self.errors.append("成就条目非 dict，已跳过")
                continue
            aid = raw.get("id") or ""
            if not aid:
                self.errors.append("成就缺少 id，已跳过")
                continue
            if aid in seen_ids:
                self.errors.append(f"成就 id 重复: {aid}")
                continue
            seen_ids.add(aid)
            try:
                result.append(Achievement.from_raw(raw))
            except (TypeError, ValueError) as e:
                self.errors.append(f"成就 {aid} 解析失败: {e}")
        return result

    def achievement(self, achievement_id: str) -> Optional[Achievement]:
        """按 id 取单个成就。"""
        for a in self.achievements():
            if a.id == achievement_id:
                return a
        return None

    # ───────────────────────────────────────────────────────
    # 工具
    # ───────────────────────────────────────────────────────
    def has_content_dir(self) -> bool:
        return paths.CONTENT_DIR.exists() and paths.CONTENT_DIR.is_dir()

    @staticmethod
    def is_legacy_event_id(eid: str) -> bool:
        """判断事件 id 是否走 ev_legacy_ 白名单豁免。"""
        return bool(re.match(r"^ev_legacy_[a-z0-9_]+_\d+$", eid or ""))
