# -*- coding: utf-8 -*-
"""
test_block_registry — BlockRegistry / BlockDef 补充测试（registry 模块）。

覆盖注册表读写、缺失键异常、JSON 叠加/覆盖、BlockDef 序列化，
以及 props 空值安全。纯函数式，可被 pytest 或内置运行器收集。
路径注入由 _testutil / conftest 负责，无需硬编码。
"""

from __future__ import annotations

import os

from mcclone.core.block_registry import (
    BlockRegistry, BlockDef,
    AIR, STONE, DIRT, GRASS, WATER, SAND,
)


def test_register_and_get():
    reg = BlockRegistry()
    reg.register(BlockDef(9, "obsidian", "X", "black"))
    assert reg.get(9).name == "obsidian"
    assert 9 in reg


def test_register_override_by_id():
    reg = BlockRegistry()
    reg.register(BlockDef(1, "stone", "#", "gray"))
    reg.register(BlockDef(1, "granite", "%", "red"))  # 同 id 覆盖
    assert reg.get(1).name == "granite"


def test_get_missing_id_raises():
    reg = BlockRegistry()
    reg.load_defaults()
    try:
        reg.get(99)
        raise AssertionError("get(99) 应抛 KeyError")
    except KeyError:
        pass


def test_get_by_name_missing_raises():
    reg = BlockRegistry()
    reg.load_defaults()
    try:
        reg.get_by_name("unobtainium")
        raise AssertionError("get_by_name 未知名应抛 KeyError")
    except KeyError:
        pass


def test_ids_sorted_ascending():
    reg = BlockRegistry()
    reg.register(BlockDef(3, "c"))
    reg.register(BlockDef(1, "a"))
    reg.register(BlockDef(2, "b"))
    assert reg.ids() == [1, 2, 3]


def test_blockdef_to_from_dict_roundtrip():
    b = BlockDef(7, "lava", "*", "red", solid=True, transparent=False,
                 props={"light": 15})
    d = b.to_dict()
    assert d["id"] == 7 and d["name"] == "lava" and d["props"]["light"] == 15
    b2 = BlockDef.from_dict(d)
    assert b2.id == b.id and b2.name == b.name and b2.props == b.props
    assert b2.solid is True and b2.transparent is False


def test_blockdef_props_none_safety():
    b = BlockDef(11, "void", " ")
    assert b.props == {}, "props 默认应为独立空 dict"
    b.props["k"] = 1
    b2 = BlockDef(12, "void2", " ")
    assert b2.props == {}, "新实例的 props 不应被其它实例污染"


def test_from_json_overrides_default():
    json_path = os.path.join(os.path.dirname(__file__), "..", "data", "blocks.default.json")
    reg = BlockRegistry.from_json(json_path)
    # 默认 6 块都在；JSON 与默认一致
    assert reg.ids() == [0, 1, 2, 3, 4, 5]
    assert reg.get(AIR).transparent is True
    assert reg.get(STONE).glyph == "#"
    assert reg.get(GRASS).glyph == '"'
    assert reg.get(WATER).color == "blue"
    assert reg.get(SAND).color == "yellow"
