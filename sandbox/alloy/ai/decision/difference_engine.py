# -*- coding: utf-8 -*-
"""
差分引擎（Difference Engine）
================================

从 zhuangtaiji 项目移植并适配 alloy。灵感来自巴贝奇差分机。

「差分机」（Difference Engine）由查尔斯·巴贝奇于 1822 年提出，利用
**有限差分法** 将多项式求值转化为反复做加法——只需保存若干阶差分，
每前进一步只需做几次加法即可得到下一个函数值。

本模块把这一思想抽取为两类实用能力：

1. FiniteDifference（数值差分）：由初始值表用加法递推后续函数值。
2. StateDiff / ReactiveTracker（状态差量 / 响应式追踪）：比较前后两次
   状态快照产出「差分」(added / removed / changed)，仅当差量命中订阅键时
   触发回调——一种轻量、确定性的「响应式 / 脏检查」，避免对整棵状态树
   盲目重算。这与现代游戏引擎的状态管理与脏标记（dirty flag）同源，
   非常适合驱动渲染/音频的增量更新。
"""
from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional


class FiniteDifference:
    """基于有限差分的递推求值器。"""

    def __init__(self, initial_values: List[float]):
        if len(initial_values) < 2:
            raise ValueError("至少需要 2 个初始值")
        self._orig = list(initial_values)
        self._diffs = self._build_diff_table(list(initial_values))
        self._max_order = len(self._diffs) - 1
        self._count = len(initial_values)

    @staticmethod
    def _build_diff_table(values: List[float]) -> List[List[float]]:
        table = [list(values)]
        cur = values
        while len(cur) > 1:
            nxt = [cur[i + 1] - cur[i] for i in range(len(cur) - 1)]
            table.append(nxt)
            cur = nxt
        return table

    def step(self) -> float:
        for order in range(self._max_order, 0, -1):
            last = self._diffs[order][-1]
            self._diffs[order - 1].append(self._diffs[order - 1][-1] + last)
        value = self._diffs[0][-1]
        self._count += 1
        return value

    def generate(self, count: int) -> List[float]:
        out = []
        for _ in range(count):
            out.append(self.step())
        return out

    @property
    def order(self) -> int:
        return self._max_order

    @property
    def count(self) -> int:
        return self._count

    def history(self) -> List[float]:
        return list(self._diffs[0])


@dataclass
class DiffEntry:
    key: str
    kind: str
    old: Any = None
    new: Any = None


class StateDiff:
    """比较两个字典快照，产出差量。"""

    @staticmethod
    def diff(old: Dict[str, Any], new: Dict[str, Any]) -> List[DiffEntry]:
        entries: List[DiffEntry] = []
        old_keys = set(old.keys())
        new_keys = set(new.keys())
        for k in old_keys - new_keys:
            entries.append(DiffEntry(k, "removed", old=old[k], new=None))
        for k in new_keys - old_keys:
            entries.append(DiffEntry(k, "added", old=None, new=new[k]))
        for k in old_keys & new_keys:
            if old[k] != new[k]:
                entries.append(DiffEntry(k, "changed", old=old[k], new=new[k]))
        return entries

    @staticmethod
    def summary(entries: List[DiffEntry]) -> str:
        if not entries:
            return "无变化"
        parts = []
        for e in entries:
            if e.kind == "added":
                parts.append(f"+{e.key}={e.new}")
            elif e.kind == "removed":
                parts.append(f"-{e.key}")
            else:
                parts.append(f"~{e.key}:{e.old}->{e.new}")
        return " | ".join(parts)


class ReactiveTracker:
    """保存状态快照，仅当差量命中订阅键时触发回调（确定性差分触发）。"""

    def __init__(self, initial: Optional[Dict[str, Any]] = None,
                 on_change: Optional[Callable[[List[DiffEntry], Dict[str, Any]], None]] = None):
        self._state: Dict[str, Any] = dict(initial or {})
        self._on_change = on_change
        self._subscribers: Dict[str, List[Callable[[DiffEntry, Dict[str, Any]], None]]] = {}

    @property
    def state(self) -> Dict[str, Any]:
        return dict(self._state)

    def subscribe(self, key: str,
                  cb: Callable[[DiffEntry, Dict[str, Any]], None]) -> None:
        self._subscribers.setdefault(key, []).append(cb)

    def update(self, patch: Dict[str, Any]) -> List[DiffEntry]:
        new_state = dict(self._state)
        new_state.update(patch)
        entries = StateDiff.diff(self._state, new_state)
        if entries and callable(self._on_change):
            self._on_change(entries, new_state)
        for e in entries:
            for cb in self._subscribers.get(e.key, []):
                cb(e, new_state)
        self._state = new_state
        return entries

    def set(self, key: str, value: Any) -> List[DiffEntry]:
        return self.update({key: value})
