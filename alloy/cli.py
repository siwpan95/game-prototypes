"""
alloy CLI —— 装配自省与引擎副本同步
===========================================

    python -m alloy dump-profile [--json] [--project PATH]
        装配本项目的 engine.yaml 并打印实际装配树（服务/配置覆盖/可选能力）。

    python -m alloy sync <project> [--dry-run | --apply] [--reference PATH]
        对比项目内联副本与引擎本体，生成/应用 engine.patch.yaml：
          - 项目独有文件    → 定制(added)，保留并记入 patch
          - 同名异内容      → 与 --reference（旧版引擎副本）比对：
                等于旧版    → 判定"过期"，apply 时用本体覆盖
                不等于      → 判定"项目定制"，保留并标记待人工核对
          - 本体独有文件    → 升级新增，apply 时复制进项目
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

ENGINE_DIR = Path(__file__).resolve().parent

#: 同步时忽略的目录（环境/版本控制/缓存，不属于引擎源码）
PRUNE_DIRS = {".venv", "__pycache__", ".github", ".git", "saves"}


def _md5(path: Path) -> str:
    return hashlib.md5(path.read_bytes()).hexdigest()


def _walk_files(root: Path) -> List[Path]:
    files: List[Path] = []
    for p in sorted(root.rglob("*")):
        if p.is_file() and not any(part in PRUNE_DIRS for part in p.parts):
            files.append(p)
    return files


# ── dump-profile ─────────────────────────────────────

def cmd_dump_profile(args) -> int:
    from alloy.core.config_loader import load_file, ConfigSyntaxError
    from alloy.core.context import Context
    from alloy.core.profiles import PROFILES, PRESET_FUNCS, assemble_profile, build_report

    project = Path(args.project).resolve() if args.project else Path.cwd()
    cfg_file = project / "engine.yaml"
    config: Dict[str, Any] = {}
    profile = ""
    plugins: List[str] = []
    if cfg_file.exists():
        try:
            raw = load_file(str(cfg_file))
        except ConfigSyntaxError as e:
            print(f"[错误] {cfg_file}: {e}", file=sys.stderr)
            return 2
        profile = str(raw.get("profile", "") or "")
        plugins = [str(p) for p in (raw.get("plugins") or [])]
        config = dict(raw.get("config") or {})
    if not plugins:
        plugins = list(PROFILES.get(profile, PROFILES["base"]))
        if not profile:
            profile = "base（默认）"

    ctx = Context()
    try:
        assemble_profile(ctx, plugins, config)
    except ValueError as e:
        print(f"[错误] {e}", file=sys.stderr)
        return 2
    report = build_report(ctx, profile, plugins, config)
    ctx.dispose()

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0

    print(f"profile: {report['profile']}")
    print(f"plugins: {', '.join(report['plugins'])}")
    print("services:")
    for key, type_name in report["services"].items():
        print(f"  {key:<16} {type_name}")
    if report["config"]:
        print("config overrides:")
        for k, v in report["config"].items():
            print(f"  {k} = {v}")
    print("optional deps:")
    for mod, ok in report["optional_deps"].items():
        print(f"  [{('OK' if ok else '缺失')}] {mod}")
    return 0


# ── sync ─────────────────────────────────────────────

def _classify(project_engine: Path, reference: Optional[Path], exclude: List[str]) -> Dict[str, Any]:
    base_files = {str(p.relative_to(ENGINE_DIR)): p for p in _walk_files(ENGINE_DIR)}
    proj_files = {str(p.relative_to(project_engine)): p for p in _walk_files(project_engine)}

    ref_hashes: Dict[str, str] = {}
    if reference is not None:
        for p in _walk_files(reference):
            ref_hashes[str(p.relative_to(reference))] = _md5(p)

    customized: List[Dict[str, str]] = []
    upgrades: List[str] = []
    stale: List[str] = []
    conflicts: List[str] = []

    for rel in sorted(proj_files):
        if rel.split("/")[0] in exclude:
            continue
        if rel not in base_files:
            customized.append({"path": rel, "kind": "added", "hash": _md5(proj_files[rel])})
    for rel in sorted(base_files):
        if any(part in exclude for part in rel.split("/")):
            continue
        if rel not in proj_files:
            upgrades.append(rel)
            continue
        hb, hp = _md5(base_files[rel]), _md5(proj_files[rel])
        if hb == hp:
            continue
        if rel in ref_hashes and ref_hashes[rel] == hp:
            stale.append(rel)  # 与旧版引擎一致 → 过期，可安全覆盖
        elif reference is not None:
            ref_p = reference / rel
            if ref_p.exists() and proj_files[rel].stat().st_mtime < ref_p.stat().st_mtime:
                stale.append(rel)  # 项目副本早于旧版引擎 → 不可能含定制，可覆盖
            else:
                conflicts.append(rel)
                customized.append({"path": rel, "kind": "modified", "hash": hp, "base_hash": hb})
        else:
            conflicts.append(rel)
            customized.append({"path": rel, "kind": "modified", "hash": hp, "base_hash": hb})

    return {
        "customized": sorted(customized, key=lambda x: x["path"]),
        "upgrades": upgrades,
        "stale": stale,
        "conflicts": conflicts,
    }


def cmd_sync(args) -> int:
    from alloy.core.config_loader import dump_file, load_file

    project = Path(args.project).resolve()
    if not project.is_dir():
        print(f"[错误] 项目目录不存在: {project}", file=sys.stderr)
        return 2
    candidates = [
        project / "alloy",
        project / "tools" / "alloy",
        project / "allin_engine",        # 旧名（未改名的内联副本）
        project / "tools" / "allin_engine",
    ]
    project_engine = next((c for c in candidates if c.is_dir()), None)
    if project_engine is None:
        print(f"[错误] 未找到内联引擎副本（查找: {candidates}）", file=sys.stderr)
        return 2
    reference = Path(args.reference).resolve() if args.reference else None
    exclude = [e for e in (args.exclude or "").split(",") if e]
    take_base = [t.strip() for t in (args.take_base or "").split(",") if t.strip()]

    result = _classify(project_engine, reference, exclude)

    # --take-base：命中的"冲突/定制"文件改为以本体为准（与 upgrades/stale 一并升级）
    taken: List[str] = []
    if take_base:
        import fnmatch

        def _hit(rel: str) -> bool:
            rel = rel.replace("\\", "/")
            return any(fnmatch.fnmatch(rel, pat.replace("\\", "/")) for pat in take_base)

        kept: List[Dict[str, str]] = []
        for item in result["customized"]:
            if item["kind"] == "modified" and _hit(item["path"]):
                taken.append(item["path"])
            else:
                kept.append(item)
        result["customized"] = kept
        result["conflicts"] = [c for c in result["conflicts"] if not _hit(c)]
        taken = sorted(set(taken))
    result["take"] = taken

    patch_file = project / "engine.patch.yaml"
    old_config: Dict[str, Any] = {}
    if patch_file.exists():
        old = load_file(str(patch_file))
        old_config = dict(old.get("config") or {})

    patch = {
        "engine": "alloy",
        "engine_version": getattr(sys.modules.get("alloy"), "__version__", "unknown"),
        "synced_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "customized_files": result["customized"],
        "take_base": take_base,
        "upgrades_applied": [] if not args.apply else result["upgrades"] + result["stale"] + result["take"],
        "config": old_config,
    }

    if args.apply:
        to_copy = result["upgrades"] + result["stale"] + result["take"]
        n_copied = 0
        for rel in to_copy:
            src = ENGINE_DIR / rel
            dst = project_engine / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            n_copied += 1
        patch["upgrades_applied"] = to_copy
        print(f"[apply] 已升级 {n_copied} 个文件（新增 {len(result['upgrades'])} / 覆盖过期 {len(result['stale'])} / 以本体为准 {len(result['take'])}）")
    else:
        print("[dry-run] 未改动任何文件")

    dump_file(str(patch_file), patch)
    print(f"[patch] 已写入 {patch_file}")

    print(f"  定制(added/modified, 保留): {len(result['customized'])}")
    print(f"  待升级(本体新增): {len(result['upgrades'])}")
    print(f"  过期(与旧版一致, 可覆盖): {len(result['stale'])}")
    print(f"  以本体为准(take-base): {len(result['take'])}")
    print(f"  冲突(同名异内容且非旧版, 保留待核对): {len(result['conflicts'])}")
    for rel in result["conflicts"][:20]:
        print(f"    - {rel}")
    return 0


# ── dump-log（P3：agent 审计入口） ──────────────────────

def cmd_dump_log(args) -> int:
    """审计世界事件日志 / 快照+日志存档。"""
    from alloy.core.world_log import WorldLog

    path = Path(args.path).resolve()
    if not path.exists():
        print(f"[错误] 文件不存在: {path}", file=sys.stderr)
        return 2

    data = None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raw = None
    if isinstance(raw, dict) and "entries" in raw:
        log = WorldLog.from_dict(raw)
        kind = "world-log"
        offset_note = ""
    elif isinstance(raw, dict) and "snapshot" in raw:
        # 快照+日志存档：摘要其 events_after
        events = raw.get("events_after") or []
        entries = [{"seq": i + 1, "type": e.get("type"), "payload": e.get("payload")} for i, e in enumerate(events)]
        kind = "save(snapshot+log)"
        offset_note = f"log_offset: {raw.get('log_offset', 0)}"
        summary = _summarize_entries(entries)
        print(f"kind: {kind}")
        if offset_note:
            print(offset_note)
        print(f"events_after: {len(entries)}")
        for line in _summary_lines(summary, args):
            print(line)
        return 0
    else:
        print(f"[错误] 无法识别的日志/存档格式: {path}", file=sys.stderr)
        return 2

    print(f"kind: {kind}")
    print(f"source: {log.source}")
    print(f"seq: {log.seq}  entries: {len(log)}")
    summary = _summarize_entries(log.entries())
    for line in _summary_lines(summary, args):
        print(line)
    if args.json:
        print(json.dumps({"kind": kind, "source": log.source, "seq": log.seq,
                          "by_type": summary["by_type"], "sample": summary["sample"]},
                         ensure_ascii=False, indent=2))
    return 0


def _summarize_entries(entries: list) -> dict:
    by_type: Dict[str, int] = {}
    for e in entries:
        by_type[e["type"]] = by_type.get(e["type"], 0) + 1
    return {"by_type": dict(sorted(by_type.items())), "sample": entries[:5]}


def _summary_lines(summary: dict, args) -> List[str]:
    lines = ["by_type:"]
    for t, n in summary["by_type"].items():
        if args.type and args.type != t:
            continue
        lines.append(f"  {t:<24} {n}")
    lines.append("sample:")
    for e in summary["sample"]:
        if args.type and args.type != e["type"]:
            continue
        lines.append(f"  #{e['seq']} {e['type']}: {json.dumps(e.get('payload'), ensure_ascii=False)[:120]}")
    return lines


def main(argv: Optional[List[str]] = None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    parser = argparse.ArgumentParser(prog="python -m alloy", description="alloy 装配自省与副本同步")
    sub = parser.add_subparsers(dest="cmd")

    p_dump = sub.add_parser("dump-profile", help="装配并打印实际装配树")
    p_dump.add_argument("--json", action="store_true", help="JSON 输出")
    p_dump.add_argument("--project", help="项目目录（默认当前目录）")

    p_log = sub.add_parser("dump-log", help="审计世界事件日志 / 快照+日志存档")
    p_log.add_argument("path", help="WorldLog JSON 或存档文件路径")
    p_log.add_argument("--type", help="只显示指定事件类型")
    p_log.add_argument("--json", action="store_true", help="JSON 输出")

    p_sync = sub.add_parser("sync", help="对比内联副本与本体，生成/应用 engine.patch.yaml")
    p_sync.add_argument("project", help="项目根目录（含内联 alloy 副本）")
    p_sync.add_argument("--dry-run", action="store_true", help="只对比报告，不复制")
    p_sync.add_argument("--apply", action="store_true", help="复制升级文件（保留定制与冲突）")
    p_sync.add_argument("--reference", help="旧版引擎副本路径（用于区分'过期'与'定制'）")
    p_sync.add_argument("--take-base", help="逗号分隔的 glob，命中文件一律以本体为准（如 test/*,core/event_bus.py）")
    p_sync.add_argument("--exclude", help="逗号分隔的排除子目录（除默认 PRUNE 外）")

    args = parser.parse_args(argv)
    if args.cmd == "dump-profile":
        return cmd_dump_profile(args)
    if args.cmd == "dump-log":
        return cmd_dump_log(args)
    if args.cmd == "sync":
        return cmd_sync(args)
    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
