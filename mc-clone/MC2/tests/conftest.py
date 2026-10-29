# -*- coding: utf-8 -*-
"""
conftest — 让 pytest 无需手动设置 PYTHONPATH 即可运行本目录测试。

作用（pytest 在收集前导入本文件）：
  - 注入 example/ 与 tools/ 到 sys.path。
  - 额外注入项目根目录（example 的父目录），使 allin_engine 包可导入
    （地基 block_registry / input_realtime 依赖 allin_engine.*）。
  - 默认将 sys.modules['pygame'] 设为 None，模拟「无 pygame」环境，
    使 input_realtime 的导入安全性测试在该环境下天然成立。
  - 提供共享 fixture：fresh_registry / no_pygame。
"""

from __future__ import annotations

import os
import sys

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
EXAMPLE_DIR = os.path.normpath(os.path.join(_THIS_DIR, ".."))
TOOLS_DIR = os.path.normpath(os.path.join(EXAMPLE_DIR, "..", "tools"))
# 项目根目录（example 的父目录），用于让 allin_engine 包可被导入。
PROJECT_ROOT = os.path.normpath(os.path.join(EXAMPLE_DIR, ".."))
# mcclone/_engine 现已统一到 allin_engine，运行测试需让 allin_engine 可导入。
for _p in (EXAMPLE_DIR, PROJECT_ROOT):
    if _p not in sys.path:
        sys.path.insert(0, _p)

# 默认模拟无 pygame（本环境未安装），保证导入安全类测试可成立。
if "pygame" not in sys.modules:
    sys.modules["pygame"] = None


import pytest  # noqa: E402

from mcclone.core.block_registry import BlockRegistry  # noqa: E402


@pytest.fixture
def fresh_registry():
    """返回新加载的默认方块注册表。"""
    reg = BlockRegistry()
    reg.load_defaults()
    return reg


@pytest.fixture
def no_pygame():
    """fixture：测试期间强制 pygame 不可用，结束后恢复。"""
    from _testutil import simulate_no_pygame, restore_pygame
    saved = simulate_no_pygame()
    try:
        yield
    finally:
        restore_pygame(saved)
