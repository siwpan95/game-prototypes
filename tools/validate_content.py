# -*- coding: utf-8 -*-
"""
tools/validate_content.py — 内容 schema 校验 CLI（B1 批次准入门禁）

退出码非 0 即批次不准入。

主要检查：
1. --check-player-parity：用 AST 对比 main.py 与 game_gui.py 两个 Player.__init__
   的字段赋值集合（仅比较可序列化公开字段，排除运行时-only 属性），不一致即报错。
   （RK1 双端字段漂移 — 本项目最高风险项）
2. min_<dimension> 白名单：遍历所有决策卡 conditions 中以 min_ 开头的键，后缀必须命中
   11 个合法维度之一（STRENGTH/INTELLIGENCE/.../HAPPINESS），否则静默失效且无报错（RK3）。
3. id 命名规范与唯一性：事件 legacy id 走 ev_legacy_ 白名单；决策卡 id 合法（白名单豁免）。
4. 数量配比（可选，基础统计）。

用法：
    python tools/validate_content.py [--check-player-parity] [--root <项目根>]
   不带参数时执行全部检查。
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple

# 复用 core 常量（项目根加入 sys.path 以便 import）
ROOT = Path(__file__).resolve().parent.parent


def _ensure_core_importable() -> None:
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))


# ─────────────────────────────────────────────────────────────
# 双端 Player.__init__ 字段集对比（RK1）
# ─────────────────────────────────────────────────────────────
# 运行时-only 属性：不参与序列化，双端命名差异（如 sbti_types / _sbti_types）豁免
PARITY_EXEMPT = {
    "_sbti_types", "sbti_types",   # 静态字典，不序列化
    "decision_tree",               # 引擎对象，不可序列化
    "cultivation_events",          # GUI 侧运行期生成
    "adventure_stage", "cultivation_stage", "current_step",
    "bg_step_keys", "backgrounds", "events_data", "main_frame",
}


def _extract_player_init_fields(source_path: Path) -> Set[str]:
    """AST 解析文件，提取 class Player 的 __init__ 中 self.<attr> = ... 的字段名。"""
    tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))
    fields: Set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == "Player":
            for item in node.body:
                if isinstance(item, ast.FunctionDef) and item.name == "__init__":
                    for stmt in ast.walk(item):
                        if isinstance(stmt, ast.Assign):
                            for target in stmt.targets:
                                if (
                                    isinstance(target, ast.Attribute)
                                    and isinstance(target.value, ast.Name)
                                    and target.value.id == "self"
                                ):
                                    fields.add(target.attr)
                        elif isinstance(stmt, ast.AnnAssign):
                            # 带类型注解的赋值：self.x: List[str] = []
                            # 注意 ast.AnnAssign 的 target 是单数（node.target，非 targets）
                            target = stmt.target
                            if (
                                isinstance(target, ast.Attribute)
                                and isinstance(target.value, ast.Name)
                                and target.value.id == "self"
                            ):
                                fields.add(target.attr)
    return fields


def check_player_parity(root: Path) -> Tuple[bool, str]:
    """对比 main.py 与 game_gui.py 的 Player.__init__ 公共可序列化字段集。"""
    main_py = root / "main.py"
    gui_py = root / "game_gui.py"
    if not main_py.exists() or not gui_py.exists():
        return False, f"缺失文件：{main_py if not main_py.exists() else gui_py}"

    f_main = _extract_player_init_fields(main_py)
    f_gui = _extract_player_init_fields(gui_py)

    def serializable(fs: Set[str]) -> Set[str]:
        return {f for f in fs if not f.startswith("_") and f not in PARITY_EXEMPT}

    s_main = serializable(f_main)
    s_gui = serializable(f_gui)

    only_main = s_main - s_gui
    only_gui = s_gui - s_main

    if not only_main and not only_gui:
        return True, (
            f"双端 Player 公共可序列化字段一致（共 {len(s_main)} 个）。"
        )

    msgs = []
    if only_main:
        msgs.append(f"main.py 有但 game_gui.py 缺: {sorted(only_main)}")
    if only_gui:
        msgs.append(f"game_gui.py 有但 main.py 缺: {sorted(only_gui)}")
    return False, "双端 Player 字段漂移:\n  " + "\n  ".join(msgs)


# ─────────────────────────────────────────────────────────────
# min_<dimension> 白名单（RK3）
# ─────────────────────────────────────────────────────────────
_VALID_MIN_DIMS: Set[str] = {
    "strength", "intelligence", "charisma", "wealth", "morality",
    "stability", "church", "nobles", "commoners", "health", "happiness",
}


def check_min_dimensions(root: Path) -> Tuple[bool, List[str]]:
    """遍历所有决策卡（根 + content/）conditions 的 min_ 键，校验维度合法性。"""
    problems: List[str] = []
    card_sources: List[Path] = []
    cards_file = root / "decision_cards.json"
    if cards_file.exists():
        card_sources.append(cards_file)
    content_dir = root / "content"
    if content_dir.exists() and content_dir.is_dir():
        card_sources.extend(sorted(content_dir.rglob("cards_*.json")))

    for src in card_sources:
        try:
            data = json.loads(src.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            problems.append(f"{src.name}: 无法解析")
            continue
        cards = data.get("cards", []) if isinstance(data, dict) else data
        if not isinstance(cards, list):
            continue
        for card in cards:
            if not isinstance(card, dict):
                continue
            cid = card.get("id", "<无 id>")
            conds = card.get("conditions", {}) or {}
            if not isinstance(conds, dict):
                continue
            for key in conds.keys():
                if key.startswith("min_"):
                    dim = key[len("min_"):]
                    if dim not in _VALID_MIN_DIMS:
                        problems.append(
                            f"{src.name} / 卡 {cid}: 非法维度后缀 '{key}' "
                            f"（合法维度：{sorted(_VALID_MIN_DIMS)}）"
                        )
    return (len(problems) == 0), problems


# ─────────────────────────────────────────────────────────────
# id 命名规范与唯一性
# ─────────────────────────────────────────────────────────────
_EVENT_ID_RE = re.compile(r"^ev_[a-z0-9_]{3,50}$")
_EVENT_LEGACY_RE = re.compile(r"^ev_legacy_[a-z0-9_]+_\d+$")
_CARD_ID_WHITELIST = {
    "war_declaration", "famine", "plague", "heresy", "noble_revolt",
    "foreign_marriage", "economic_reform", "border_raid", "trade_agreement",
    "natural_disaster", "cultural_renaissance", "succession_crisis",
    "spy_discovery", "religious_schism", "peasant_uprising", "royal_feast",
}


def check_event_ids(root: Path) -> Tuple[bool, List[str]]:
    problems: List[str] = []
    # 根 events.json
    events_file = root / "events.json"
    if events_file.exists():
        try:
            data = json.loads(events_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            problems.append("events.json: 无法解析")
            data = {}
        templates = data.get("event_templates", {}) if isinstance(data, dict) else {}
        all_ids: Set[str] = set()
        for group_key, group in templates.items():
            if not isinstance(group, dict):
                continue
            for sub_key, items in group.items():
                if not isinstance(items, list):
                    continue
                for ev in items:
                    if not isinstance(ev, dict):
                        continue
                    eid = ev.get("id")
                    if not eid:
                        problems.append(f"events.json: 缺少 id（{group_key}/{sub_key}）")
                        continue
                    if not (_EVENT_ID_RE.match(eid) or _EVENT_LEGACY_RE.match(eid)):
                        problems.append(f"events.json: 事件 id 格式非法 '{eid}'")
                    if eid in all_ids:
                        problems.append(f"events.json: 事件 id 重复 '{eid}'")
                    all_ids.add(eid)
    return (len(problems) == 0), problems


def check_card_ids(root: Path) -> Tuple[bool, List[str]]:
    problems: List[str] = []
    cards_file = root / "decision_cards.json"
    ids: Set[str] = set()
    if cards_file.exists():
        try:
            data = json.loads(cards_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            problems.append("decision_cards.json: 无法解析")
            return False, problems
        cards = data.get("cards", []) if isinstance(data, dict) else data
        if isinstance(cards, list):
            for card in cards:
                if not isinstance(card, dict):
                    continue
                cid = card.get("id")
                if not cid:
                    problems.append("decision_cards.json: 缺少 id")
                    continue
                if cid not in _CARD_ID_WHITELIST:
                    problems.append(
                        f"decision_cards.json: 存量卡 id '{cid}' 不在白名单"
                    )
                if cid in ids:
                    problems.append(f"decision_cards.json: id 重复 '{cid}'")
                ids.add(cid)
    if len(ids) != 16:
        problems.append(f"decision_cards.json: 期望 16 张存量卡，实际 {len(ids)} 张")
    return (len(problems) == 0), problems


# ─────────────────────────────────────────────────────────────
# 内容深合并回归（RK: content/ 静默覆盖存量内容）
# ─────────────────────────────────────────────────────────────
def check_content_merge(root: Path) -> Tuple[bool, List[str]]:
    """断言 ContentLoader 深合并后存量内容未被 content/ 覆盖。

    历史 bug：_deep_merge 对同键 list 直接用 extra 整体覆盖，导致 content/
    下的 cards_*.json / events_*.json 静默抹掉根目录存量条目。
    这里用 >= 而非等值断言，因为 content/ 仍在增量填充中。
    """
    problems: List[str] = []
    _ensure_core_importable()
    try:
        from core.content_loader import ContentLoader
    except ImportError as exc:
        return False, [f"无法导入 ContentLoader: {exc}"]

    try:
        loader = ContentLoader().load()
    except Exception as exc:  # noqa: BLE001 — 门禁工具需捕获任何加载期异常
        return False, [f"ContentLoader().load() 抛异常: {exc!r}"]

    card_count = len(loader.cards())
    if card_count < 16:
        problems.append(
            f"决策卡总数 {card_count} < 16，存量 decision_cards.json 疑似被 content/ 覆盖"
        )

    generic = loader.events_dict().get("generic", {}) or {}
    generic_count = len(generic)
    if generic_count < 4:
        problems.append(
            f"events_dict()['generic'] 条目数 {generic_count} < 4，"
            f"存量 events.json 疑似被 content/ 覆盖"
        )

    steps = loader.backgrounds().get("steps")
    if not steps:
        problems.append(
            "backgrounds().get('steps') 为空，出身流程读取失败（键名/形状不匹配）"
        )

    if not problems:
        step_count = len(steps) if isinstance(steps, dict) else 0
        return True, [
            f"卡 {card_count} 张 / generic 事件组 {generic_count} 个 / "
            f"出身步骤 {step_count} 步"
        ]
    return False, problems


# ─────────────────────────────────────────────────────────────
# 主流程
# ─────────────────────────────────────────────────────────────
def main(argv: List[str]) -> int:
    parser = argparse.ArgumentParser(description="人生重开模拟器 内容校验工具")
    parser.add_argument("--root", default=str(ROOT), help="项目根目录")
    parser.add_argument("--check-player-parity", action="store_true",
                        help="仅检查双端 Player.__init__ 字段一致性")
    args = parser.parse_args(argv)

    root = Path(args.root)
    _ensure_core_importable()

    only_parity = args.check_player_parity

    failures: List[str] = []
    checks_run = 0

    # 1) 双端 Player 字段一致性（始终运行，最高风险项）
    checks_run += 1
    ok, msg = check_player_parity(root)
    print(f"[check-player-parity] {'PASS' if ok else 'FAIL'}: {msg}")
    if not ok:
        failures.append(msg)

    if only_parity:
        return 0 if not failures else 1

    # 2) min_<dimension> 白名单
    checks_run += 1
    ok, probs = check_min_dimensions(root)
    print(f"[min-dimension] {'PASS' if ok else 'FAIL'}: {len(probs)} 个问题")
    for p in probs:
        print(f"    - {p}")
    if not ok:
        failures.append("min_<dimension> 校验失败")

    # 3) 事件 id
    checks_run += 1
    ok, probs = check_event_ids(root)
    print(f"[event-id] {'PASS' if ok else 'FAIL'}: {len(probs)} 个问题")
    for p in probs:
        print(f"    - {p}")
    if not ok:
        failures.append("事件 id 校验失败")

    # 4) 决策卡 id
    checks_run += 1
    ok, probs = check_card_ids(root)
    print(f"[card-id] {'PASS' if ok else 'FAIL'}: {len(probs)} 个问题")
    for p in probs:
        print(f"    - {p}")
    if not ok:
        failures.append("决策卡 id 校验失败")

    # 5) 内容深合并回归（存量内容未被 content/ 覆盖）
    checks_run += 1
    ok, probs = check_content_merge(root)
    if ok:
        print(f"[content-merge] PASS: {probs[0] if probs else '存量内容未被覆盖'}")
    else:
        print(f"[content-merge] FAIL: {len(probs)} 个问题")
        for p in probs:
            print(f"    - {p}")
        failures.append("内容深合并校验失败")

    print("─" * 50)
    if failures:
        print(f"校验未通过：{len(failures)} 项失败。退出码 1。")
        return 1
    print(f"全部 {checks_run} 项检查通过。退出码 0。")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
