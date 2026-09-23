# -*- coding: utf-8 -*-
"""
_testutil — MC-Clone 测试公共工具（零依赖，可被所有测试文件复用）。

职责：
  - 在导入期自动注入路径，保证 ``allin_engine`` 与本地模块可导入，
    从而去除各测试文件里的硬编码绝对路径。
  - 提供 pygame 可用性模拟助手（无 pygame 时强制不可用；有则恢复）。
  - 提供与 pytest 解耦的极简 ``TestRunner``，可在纯 ``python`` 下运行。

本文件必须尽量轻量：除标准库外，不依赖任何第三方包。
路径注入逻辑放在模块顶部、任何业务导入之前执行。
"""

from __future__ import annotations

import importlib
import os
import sys
from typing import Callable, List, Tuple

# ─────────────────────────────────────────────────────────────────────────
# 路径注入：基于本文件真实位置推导 example/ 与项目根目录，绝不硬编码盘符。
# ─────────────────────────────────────────────────────────────────────────
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
EXAMPLE_DIR = os.path.normpath(os.path.join(_THIS_DIR, ".."))          # <仓库根>\MC2
TOOLS_DIR = os.path.normpath(os.path.join(EXAMPLE_DIR, "..", "tools"))  # 历史遗留（已弃用）
PROJECT_ROOT = os.path.normpath(os.path.join(EXAMPLE_DIR, ".."))       # <仓库根>

# mcclone/_engine 现已统一到 allin_engine，运行测试需让 allin_engine 可导入。
for _p in (EXAMPLE_DIR, PROJECT_ROOT):
    if _p not in sys.path:
        sys.path.insert(0, _p)


# ─────────────────────────────────────────────────────────────────────────
# pygame 模拟助手
# ─────────────────────────────────────────────────────────────────────────
_MISSING = object()


def simulate_no_pygame() -> object:
    """强制 pygame 不可用（把 sys.modules['pygame'] 设为 None 后重载 input_realtime）。

    返回被替换前的 pygame 状态（用于后续恢复）。
    """
    saved = sys.modules.get("pygame", _MISSING)
    sys.modules.pop("pygame", None)
    sys.modules["pygame"] = None
    from mcclone.input import input_realtime# noqa: F401
    importlib.reload(input_realtime)
    return saved


def restore_pygame(saved) -> None:
    """恢复 pygame 的 sys.modules 状态并重新载入 input_realtime。"""
    sys.modules.pop("pygame", None)
    if saved is not _MISSING:
        sys.modules["pygame"] = saved
    from mcclone.input import input_realtime# noqa: F401
    importlib.reload(input_realtime)


def _fresh_registry():
    """返回新加载的默认方块注册表（供各测试复用）。"""
    from mcclone.core import block_registry# 延迟导入避免循环
    reg = block_registry.BlockRegistry()
    reg.load_defaults()
    return reg


# ─────────────────────────────────────────────────────────────────────────
# 极简测试运行器（兼容 pytest 与纯 python）
# ─────────────────────────────────────────────────────────────────────────

class TestRunner:
    """单文件/单用例计数器，替代 unittest 样板，保证用例互不阻断。

    用法（纯 python）：
        runner = TestRunner("geometry")
        runner.run("clamp", test_clamp)
        failed = runner.exit_code()
        sys.exit(failed)
    """

    def __init__(self, section: str = "") -> None:
        self.section = section
        self.passed = 0
        self.failed = 0
        self.failures: List[Tuple[str, str]] = []

    def run(self, name: str, fn: Callable[[], None]) -> bool:
        """执行单个用例，捕获异常并计数；返回 True 表示通过。"""
        full = f"{self.section}.{name}" if self.section else name
        try:
            fn()
            self.passed += 1
            print(f"  [PASS] {full}")
            return True
        except Exception as exc:  # noqa: BLE001 — 各用例隔离，便于全部展示
            self.failed += 1
            msg = f"{type(exc).__name__}: {exc}"
            self.failures.append((full, msg))
            print(f"  [FAIL] {full} -> {msg}")
            return False

    def summary(self) -> str:
        total = self.passed + self.failed
        return (
            f"  总计 {total} | 通过 {self.passed} | 失败 {self.failed}"
        )

    def exit_code(self) -> int:
        return 1 if self.failed else 0
