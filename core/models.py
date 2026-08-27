# -*- coding: utf-8 -*-
"""
core/models.py — 轻量数据类（B1 仅定义，后续批次填充逻辑）

定义核心内容的数据载体：Talent / Career / Ending / Achievement / EventItem / CardItem。
本批 B1 只需要 EventItem / CardItem 来支撑内容加载器的索引与默认值补齐；
其余类先定义好骨架，供 B2-B5 直接使用，避免后续重复改动。

本模块零 UI 依赖，禁止 import tkinter / print / input / time.sleep。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class Talent:
    """天赋。"""
    id: str = ""
    name: str = ""
    rarity: str = "common"
    category: str = "misc"
    description: str = ""
    mutex_group: str = ""
    weight: float = 1.0
    effects: Dict[str, Any] = field(default_factory=dict)
    unlocks: List[str] = field(default_factory=list)
    unlock_condition: Optional[str] = None
    inheritable: bool = False


@dataclass
class Career:
    """职业。"""
    id: str = ""
    name: str = ""
    category: str = ""
    tier: int = 1
    requires: Dict[str, Any] = field(default_factory=dict)
    income: int = 0
    effects_per_year: Dict[str, Any] = field(default_factory=dict)
    risk: Dict[str, Any] = field(default_factory=dict)
    description: str = ""
    unlock_events: List[str] = field(default_factory=list)

    @classmethod
    def from_raw(cls, raw: Dict[str, Any]) -> "Career":
        """从原始 dict 构造，补齐可选字段默认值（R9）。"""
        risk = raw.get("risk")
        return cls(
            id=raw.get("id", ""),
            name=raw.get("name", ""),
            category=raw.get("category", ""),
            tier=int(raw.get("tier", 1) or 1),
            requires=raw.get("requires", {}) or {},
            income=int(raw.get("income", 0) or 0),
            effects_per_year=raw.get("effects_per_year", {}) or {},
            risk=risk if isinstance(risk, dict) else {},
            description=raw.get("description", "") or "",
            unlock_events=list(raw.get("unlock_events", [])) if isinstance(raw.get("unlock_events"), list) else [],
        )


@dataclass
class Ending:
    """结局。"""
    id: str = ""
    name: str = ""
    category: str = "normal"
    rarity: str = "common"
    priority: int = 0
    conditions: Dict[str, Any] = field(default_factory=dict)
    text: str = ""
    score_bonus: int = 0
    legacy_tag: str = ""

    @classmethod
    def from_raw(cls, raw: Dict[str, Any]) -> "Ending":
        """从原始 dict 构造，补齐可选字段默认值（R9）。"""
        return cls(
            id=raw.get("id", ""),
            name=raw.get("name", ""),
            category=raw.get("category", "normal") or "normal",
            rarity=raw.get("rarity", "common") or "common",
            priority=int(raw.get("priority", 0) or 0),
            conditions=raw.get("conditions", {}) or {},
            text=raw.get("text", "") or "",
            score_bonus=int(raw.get("score_bonus", 0) or 0),
            legacy_tag=raw.get("legacy_tag", "") or "",
        )


@dataclass
class Achievement:
    """成就。"""
    id: str = ""
    name: str = ""
    category: str = "milestone"
    hidden: bool = False
    trigger: Dict[str, Any] = field(default_factory=dict)
    unlocks: List[str] = field(default_factory=list)
    score_bonus: int = 0
    description: str = ""

    @classmethod
    def from_raw(cls, raw: Dict[str, Any]) -> "Achievement":
        """从原始 dict 构造，补齐可选字段默认值（R9）。"""
        return cls(
            id=raw.get("id", ""),
            name=raw.get("name", ""),
            category=raw.get("category", "milestone") or "milestone",
            hidden=bool(raw.get("hidden", False)),
            trigger=raw.get("trigger", {}) or {},
            unlocks=list(raw.get("unlocks", [])) if isinstance(raw.get("unlocks"), list) else [],
            score_bonus=int(raw.get("score_bonus", 0) or 0),
            description=raw.get("description", "") or "",
        )


@dataclass
class EventItem:
    """一条人生事件（来自 events.json 的单个元素或 content/events_*.json）。

    events 本批只补了 id；options / desc / feedback 原样保留。
    """
    id: str = ""
    desc: str = ""
    options: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    weight: float = 1.0
    conditions: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_raw(cls, raw: Dict[str, Any], fallback_id: str = "") -> "EventItem":
        """从原始 dict 构造，补齐可选字段默认值。"""
        rid = raw.get("id") or fallback_id
        return cls(
            id=rid,
            desc=raw.get("desc", ""),
            options=raw.get("options", {}) or {},
            tags=raw.get("tags", []) or [],
            weight=float(raw.get("weight", 1.0)),
            conditions=raw.get("conditions", {}) or {},
        )

    def to_raw(self) -> Dict[str, Any]:
        """还原为可序列化 dict（保留 id/desc/options，补可选字段）。"""
        return {
            "id": self.id,
            "desc": self.desc,
            "options": self.options,
            "tags": self.tags,
            "weight": self.weight,
            "conditions": self.conditions,
        }


@dataclass
class CardItem:
    """一张决策卡（来自 decision_cards.json 或 content/cards_*.json）。"""
    id: str = ""
    title: str = ""
    description: str = ""
    era: str = "dynasty"
    category: str = "misc"
    tags: List[str] = field(default_factory=list)
    left_choice: Dict[str, Any] = field(default_factory=dict)
    right_choice: Dict[str, Any] = field(default_factory=dict)
    conditions: Dict[str, Any] = field(default_factory=dict)
    weight: float = 1.0
    min_year: int = 0
    max_year: int = 999
    once_per_run: bool = False
    unlock_condition: Optional[str] = None
    requires_talent: List[str] = field(default_factory=list)
    chain_reactions: List[Dict[str, Any]] = field(default_factory=list)

    @classmethod
    def from_raw(cls, raw: Dict[str, Any]) -> "CardItem":
        """从原始 dict 构造，补齐可选字段默认值（R9）。"""
        return cls(
            id=raw.get("id", ""),
            title=raw.get("title", ""),
            description=raw.get("description", ""),
            era=raw.get("era", "dynasty"),
            category=raw.get("category", "misc"),
            tags=raw.get("tags", []) or [],
            left_choice=raw.get("left_choice", {}) or {},
            right_choice=raw.get("right_choice", {}) or {},
            conditions=raw.get("conditions", {}) or {},
            weight=float(raw.get("weight", 1.0)),
            min_year=int(raw.get("min_year", 0)),
            max_year=int(raw.get("max_year", 999)),
            once_per_run=bool(raw.get("once_per_run", False)),
            unlock_condition=raw.get("unlock_condition"),
            requires_talent=raw.get("requires_talent", []) or [],
            chain_reactions=raw.get("chain_reactions", []) or [],
        )

    def to_engine_dict(self) -> Dict[str, Any]:
        """转换为 decision_tree 引擎消费的 dict（深拷贝，避免上层污染）。"""
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "era": self.era,
            "category": self.category,
            "tags": list(self.tags),
            "left_choice": dict(self.left_choice),
            "right_choice": dict(self.right_choice),
            "conditions": dict(self.conditions),
            "weight": self.weight,
            "min_year": self.min_year,
            "max_year": self.max_year,
            "once_per_run": self.once_per_run,
            "unlock_condition": self.unlock_condition,
            "requires_talent": list(self.requires_talent),
            "chain_reactions": [dict(r) for r in self.chain_reactions],
        }
