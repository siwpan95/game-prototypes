# -*- coding: utf-8 -*-
"""
tools/count_content.py — 内容条目进度自查

输出各内容项当前条目数 vs 目标数的进度表，便于分批次交付时自查。
B1 阶段仅存量内容存在，故大部分目标显示为 0/未达标，属正常。

用法：
    python tools/count_content.py [--root <项目根>]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Dict, List, Tuple

ROOT = Path(__file__).resolve().parent.parent

# (内容类型, 当前计数函数说明, 目标数)
TARGETS: List[Tuple[str, int]] = [
    ("决策卡·存量", 16),
    ("决策卡·王朝新增", 44),
    ("决策卡·现代", 60),
    ("事件·generic", 30),
    ("事件·by_wealth", 30),
    ("事件·by_personality", 32),
    ("事件·by_age", 48),
    ("事件·by_career", 20),
    ("事件·by_trait", 20),
    ("天赋", 60),
    ("职业", 40),
    ("结局", 60),
    ("成就", 40),
]


def _count_cards(root: Path) -> int:
    f = root / "decision_cards.json"
    if not f.exists():
        return 0
    try:
        d = json.loads(f.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return 0
    return len(d.get("cards", []) if isinstance(d, dict) else d)


def _count_group_events(root: Path, group: str) -> int:
    f = root / "events.json"
    total = 0
    if f.exists():
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            d = {}
        g = (d.get("event_templates", {}) or {}).get(group, {}) or {}
        if isinstance(g, list):
            # 兼容扁平列表分组（如 events.json / events_adult.json 的 generic）
            total += len(g)
        elif isinstance(g, dict):
            for items in g.values():
                if isinstance(items, list):
                    total += len(items)
    # content/ 同分组累加
    cd = root / "content"
    if cd.exists() and cd.is_dir():
        for jf in sorted(cd.rglob("events_*.json")):
            try:
                d = json.loads(jf.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                continue
            g = (d.get("event_templates", {}) or {}).get(group, {}) or {}
            if isinstance(g, list):
                # 兼容扁平列表分组（如 events_adult.json / events_generic_extra.json 的 generic）
                total += len(g)
            elif isinstance(g, dict):
                for items in g.values():
                    if isinstance(items, list):
                        total += len(items)
    return total


def _count_json_list_in_dir(root: Path, fname: str) -> int:
    f = root / "content" / fname
    if f.exists():
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return 0
        if isinstance(d, list):
            return len(d)
        if isinstance(d, dict):
            # 可能是 {"talents": [...]} 等包装
            for v in d.values():
                if isinstance(v, list):
                    return len(v)
    return 0


def main(argv: List[str]) -> int:
    root = ROOT
    if "--root" in argv:
        idx = argv.index("--root")
        if idx + 1 < len(argv):
            root = Path(argv[idx + 1])

    counts: Dict[str, int] = {
        "决策卡·存量": _count_cards(root),
        "事件·generic": _count_group_events(root, "generic"),
        "事件·by_wealth": _count_group_events(root, "by_wealth"),
        "事件·by_personality": _count_group_events(root, "by_personality"),
        "事件·by_age": _count_group_events(root, "by_age"),
        "事件·by_career": _count_group_events(root, "by_career"),
        "事件·by_trait": _count_group_events(root, "by_trait"),
        "天赋": _count_json_list_in_dir(root, "talents.json"),
        "职业": _count_json_list_in_dir(root, "careers.json"),
        "结局": _count_json_list_in_dir(root, "endings.json"),
        "成就": _count_json_list_in_dir(root, "achievements.json"),
    }
    # 目标表里其余项（B3/B4 才填充）
    counts.setdefault("决策卡·王朝新增", 0)
    counts.setdefault("决策卡·现代", 0)

    print(f"{'内容类型':<16}{'当前':>8}{'目标':>8}{'进度':>10}")
    print("─" * 42)
    all_ok = True
    for name, target in TARGETS:
        cur = counts.get(name, 0)
        pct = (cur / target * 100) if target else 0
        mark = "✓" if cur >= target else " "
        if cur < target:
            all_ok = False
        print(f"{mark}{name:<15}{cur:>8}{target:>8}{pct:>9.0f}%")
    print("─" * 42)
    print("B1 阶段仅存量内容存在，除存量外显示 0 属正常。")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
