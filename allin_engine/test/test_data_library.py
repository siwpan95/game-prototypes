"""
DataLibrary / JSONLoader 回归测试 — 锁定 P2 修复：
- DataLibrary 必须能注册 id 为 0 的合法数据项（修复 `if item_id:` 的 falsy 丢弃）
- JSONLoader 必须返回与缓存相互独立的副本（修复共享可变状态）
"""

import json
import os
import tempfile

from allin_engine.core.data_library import DataLibrary
from allin_engine.utils.json_loader import JSONLoader


class _Rec:
    def __init__(self, d: dict):
        self.id = d["id"]
        self.name = d.get("name", "")


def test_data_library_registers_id_zero():
    lib = DataLibrary(factory=_Rec, item_key="items", item_name="记录")
    lib.register_batch([
        _Rec({"id": 0, "name": "zero"}),
        _Rec({"id": 1, "name": "one"}),
    ])
    assert lib.count == 2, f"id=0 的数据项被 falsy 丢弃，count={lib.count}"
    assert lib.get(0) is not None and lib.get(0).name == "zero"
    assert lib.get(1) is not None and lib.get(1).name == "one"


def test_json_loader_returns_independent_copies():
    d = tempfile.mkdtemp()
    p = os.path.join(d, "x.json")
    with open(p, "w", encoding="utf-8") as f:
        json.dump({"items": [1, 2, 3]}, f)
    loader = JSONLoader(d)
    a = loader.load("x.json")
    a["items"].append(99)          # 修改调用方持有对象
    b = loader.load("x.json")      # 再次加载（命中缓存）
    assert b["items"] == [1, 2, 3], "缓存对象被调用方修改污染（共享可变状态）"
