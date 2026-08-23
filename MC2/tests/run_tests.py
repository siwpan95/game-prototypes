# -*- coding: utf-8 -*-
"""
run_tests — MC-Clone 通用测试运行器（零第三方依赖）。

功能：
  - 自动发现 tests/ 下所有 ``test_*.py``（排除 _testutil.py）。
  - 逐个导入并执行其 ``main()``（约定返回失败用例数），汇总总结果。
  - 提供 ``--pytest`` 开关：若已安装 pytest，则转交 pytest 执行（可选）。
  - 路径注入交给 _testutil，无需硬编码、无需手动设置 PYTHONPATH。

用法：
  python tests/run_tests.py            # 纯 python 运行全部测试用例
  python tests/run_tests.py --pytest   # 优先用 pytest 运行（需 pip install pytest）
  python tests/run_tests.py geometry   # 仅运行文件名含 'geometry' 的测试模块

退出码：存在失败用例则为 1，全绿为 0。
"""

from __future__ import annotations

import glob
import importlib
import os
import sys

# 路径注入（在任何业务导入前）
import _testutil  # noqa: F401  (导入即触发 sys.path 注入)
from _testutil import EXAMPLE_DIR, TOOLS_DIR

_TESTS_DIR = os.path.dirname(os.path.abspath(__file__))


def _discover(pattern_filter: str | None = None) -> list[str]:
    """返回 tests/ 下候选测试模块名（去扩展名），已排序。"""
    files = sorted(glob.glob(os.path.join(_TESTS_DIR, "test_*.py")))
    mods = []
    for f in files:
        base = os.path.splitext(os.path.basename(f))[0]
        if base == "_testutil":
            continue
        if pattern_filter and pattern_filter not in base:
            continue
        mods.append(base)
    return mods


def _run_with_pytest(mods: list[str]) -> int:
    """尝试用 pytest 运行；失败则回退到纯 python 运行器。"""
    try:
        import pytest  # noqa: F401
    except Exception:  # noqa: BLE001
        print("[warn] 未检测到 pytest，回退到内置运行器。", flush=True)
        return _run_builtin(mods)
    args = [os.path.join(_TESTS_DIR, m + ".py") for m in mods]
    return int(pytest.main(args))


def _run_builtin(mods: list[str]) -> int:
    total_failed = 0
    total_passed = 0
    ran_modules = 0
    print("=" * 70)
    print(f" MC-Clone 测试运行器  (example={EXAMPLE_DIR})")
    print(f" 引擎路径 = {TOOLS_DIR}")
    print("=" * 70)

    for mod in mods:
        try:
            m = importlib.import_module(mod)
        except Exception as exc:  # noqa: BLE001
            print(f"\n[ERROR] 无法导入模块 {mod!r}: {exc}")
            total_failed += 1
            continue
        main_fn = getattr(m, "main", None)
        if not callable(main_fn):
            # 没有 main() 约定的模块：尝试按 pytest 风格收集 test_* 函数
            ran = _run_pytest_style(m)
            total_failed += ran["failed"]
            total_passed += ran["passed"]
            if ran["ran"]:
                ran_modules += 1
            continue
        print(f"\n{'#' * 70}\n# 模块: {mod}\n{'#' * 70}")
        failed = main_fn() or 0
        total_failed += failed
        ran_modules += 1

    print("\n" + "=" * 70)
    print(f" 运行模块数: {ran_modules} | 累计失败: {total_failed} | 累计通过: {total_passed}")
    print("=" * 70)
    return 1 if total_failed else 0


def _run_pytest_style(m) -> dict:
    """对无 main() 的模块，扫描顶层 test_* 函数并用 TestRunner 执行。"""
    from _testutil import TestRunner
    runner = TestRunner(getattr(m, "__name__", "module"))
    ran = False
    for name in dir(m):
        if name.startswith("test_") and callable(getattr(m, name)):
            runner.run(name, getattr(m, name))
            ran = True
    return {"ran": ran, "failed": runner.failed, "passed": runner.passed}


def main() -> int:
    args = sys.argv[1:]
    use_pytest = "--pytest" in args
    filter_arg = next((a for a in args if not a.startswith("--")), None)

    mods = _discover(filter_arg)
    if not mods:
        print(f"[warn] 未找到匹配测试模块 filter={filter_arg!r}")
        return 0

    if use_pytest:
        return _run_with_pytest(mods)
    return _run_builtin(mods)


if __name__ == "__main__":
    sys.exit(main())
