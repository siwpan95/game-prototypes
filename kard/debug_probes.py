"""KARD 调试探针 — 关键路径诊断日志。

通过环境变量控制：
  KARD_DEBUG=1          开启全部探针
  KARD_DEBUG_MODULES=main,combat  只开启指定模块（逗号分隔）

用法：
  from debug_probes import probe
  probe("main::phase", "MENU→PLAYER_TURN", {"room": 5, "asc": 2})

输出格式：
  [#001] main::phase | MENU→PLAYER_TURN | room=5 asc=2
"""

from __future__ import annotations
import os
import time

# ── 开关 ─────────────────────────────────────────────────────────────
DEBUG_PROBES = os.environ.get("KARD_DEBUG", "0") == "1"
_enabled_modules_raw = os.environ.get("KARD_DEBUG_MODULES", "")
_enabled_modules: set[str] = set(
    m.strip() for m in _enabled_modules_raw.split(",") if m.strip()
) if _enabled_modules_raw else set()

_probe_count: int = 0
_start_time: float = time.time()


# ── 探针函数 ─────────────────────────────────────────────────────────

def probe(location: str, msg: str = "", data: dict | None = None,
          module: str = "") -> None:
    """在关键路径输出诊断信息。

    Args:
        location: 位置标识，如 "main::phase_change"
        msg: 简短描述
        data: 可选的结构化数据 dict
        module: 所属模块（空字符串表示始终输出）
    """
    if not DEBUG_PROBES:
        return
    if module and _enabled_modules and module not in _enabled_modules:
        return

    global _probe_count
    _probe_count += 1
    elapsed = time.time() - _start_time

    parts = [f"[#{_probe_count:03d} {elapsed:7.2f}s] {location}"]
    if msg:
        parts.append(f" | {msg}")
    if data:
        items = [f"{k}={v}" for k, v in data.items()]
        parts.append(" | " + " ".join(items))

    print(" ".join(parts))


def probe_enter(location: str, data: dict | None = None, module: str = "") -> None:
    """进入关键函数的探针（带时间戳）。"""
    probe(location, "ENTER", data, module)


def probe_exit(location: str, data: dict | None = None, module: str = "") -> None:
    """退出关键函数的探针。"""
    probe(location, "EXIT", data, module)


def probe_state_summary() -> None:
    """输出当前探针计数摘要。"""
    if not DEBUG_PROBES:
        return
    print(f"[PROBES] 总计 {_probe_count} 次探针触发，"
          f"运行 {time.time() - _start_time:.1f}s")


def is_enabled(module: str = "") -> bool:
    """检查探针系统是否启用（以及指定模块是否激活）。"""
    if not DEBUG_PROBES:
        return False
    if module and _enabled_modules and module not in _enabled_modules:
        return False
    return True
