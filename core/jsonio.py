# -*- coding: utf-8 -*-
"""
core/jsonio.py — 容错 JSON 读写（永不抛异常给表现层）

- read_json(path, default): 文件缺失/损坏/非 dict 均返回 default，不抛。
- write_json_atomic(path, data): 先写 <path>.tmp 再 os.replace() 原子落盘。
本模块零 UI 依赖，禁止 import tkinter / print / input / time.sleep。
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional


def read_json(path: Any, default: Optional[Any] = None) -> Any:
    """读取 JSON 文件，容错返回 default。

    - 文件不存在 → 返回 default
    - JSON 解析失败 / 顶层非预期类型 → 返回 default
    - 读取过程中任何 IO 异常 → 返回 default
    default 默认是空 dict。
    """
    if default is None:
        default = {}
    p = Path(path)
    if not p.exists() or not p.is_file():
        return default
    try:
        with p.open("r", encoding="utf-8") as f:
            data = json.load(f)
        return data
    except (json.JSONDecodeError, OSError, ValueError):
        return default


def write_json_atomic(path: Any, data: Any, indent: int = 2) -> bool:
    """原子写 JSON：先写临时文件再 os.replace()。

    返回 True 表示成功，False 表示失败（绝不抛异常）。
    写入 UTF-8，ensure_ascii=False。
    """
    p = Path(path)
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        # 用临时文件与最终文件同目录，保证 os.replace 是同一文件系统的原子移动
        fd, tmp_name = tempfile.mkstemp(
            dir=str(p.parent), suffix=".tmp", prefix=p.stem + "."
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=indent)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_name, str(p))
        finally:
            if os.path.exists(tmp_name):
                try:
                    os.remove(tmp_name)
                except OSError:
                    pass
        return True
    except (OSError, TypeError, ValueError):
        return False


def write_json(path: Any, data: Any, indent: int = 2) -> bool:
    """兼容别名：直接写盘（非原子）。保留以供上层简单调用。"""
    return write_json_atomic(path, data, indent)


def list_json_files(directory: Any) -> List[Path]:
    """列出目录下所有 .json 文件（递归），不存在时返回空列表。"""
    d = Path(directory)
    if not d.exists() or not d.is_dir():
        return []
    return sorted(d.rglob("*.json"))
