"""
Serializable 嵌套反序列化测试 — 验证修复 ``from __future__ import annotations``
下 field.type 退化为字符串、导致嵌套 dataclass / list[Dataclass] 反序列化失效的问题。
"""

from dataclasses import dataclass, field
from typing import List

from allin_engine.core.serializable import Serializable


@dataclass
class _Item(Serializable):
    name: str
    qty: int = 1


@dataclass
class _Bag(Serializable):
    items: List[_Item] = field(default_factory=list)
    label: str = "bag"


def test_nested_dataclass_roundtrip():
    bag = _Bag(items=[_Item("sword", 2), _Item("shield")])
    data = bag.to_dict()
    bag2 = _Bag.from_dict(data)
    assert isinstance(bag2.items[0], _Item)
    assert bag2.items[0].name == "sword"
    assert bag2.items[0].qty == 2
    assert bag2.items[1].qty == 1
    assert bag2.label == "bag"


def test_nested_list_empty():
    bag = _Bag(items=[])
    bag2 = _Bag.from_dict(bag.to_dict())
    assert bag2.items == []


def test_nested_dataclass_explicit_none_preserved():
    # 显式传入 None 时保留为 None（不替换为 default_factory）
    bag2 = _Bag.from_dict({"items": None})
    assert bag2.items is None
