"""
UpgradeDef 成本/可见性 单元测试。
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from engine.upgrade import UpgradeDef


def _make_def(key="test_item", costs=None, visibilities=None, limit=0,
              per_second=0, category="dps", era="stone", requires=None):
    """快速构建 UpgradeDef 测试实例。"""
    raw = {
        "key": key, "name": "测试", "description": "测试: ({cost}): {qty}",
        "tip": "测试用", "costs": costs or [10],
        "visibilities": visibilities or [1],
        "limit": limit, "per_second": per_second,
        "category": category, "era": era,
    }
    if requires:
        raw["requires"] = requires
    return UpgradeDef(raw)


class TestUpgradeDef:
    """UpgradeDef 基础逻辑测试。"""

    # ---- get_cost ----

    def test_get_cost_single_cost_grows_exponentially(self):
        d = _make_def(costs=[10])
        # qty=0: 10 * 1.15^0 = 10
        assert d.get_cost(0) == 10
        # qty=5: 10 * 1.15^5 ≈ 20
        assert d.get_cost(5) == int(10 * 1.15 ** 5)
        # qty=10: 10 * 1.15^10 ≈ 40
        assert d.get_cost(10) == int(10 * 1.15 ** 10)

    def test_get_cost_multi_cost_with_limit(self):
        """有限制时，按数组索引取 cost。"""
        d = _make_def(costs=[10, 20, 50, 100], limit=4)
        assert d.get_cost(0) == 10
        assert d.get_cost(1) == 20
        assert d.get_cost(2) == 50
        assert d.get_cost(3) == 100

    def test_get_cost_multi_cost_past_limit(self):
        """超过限制数量时，返回最后一档 cost。"""
        d = _make_def(costs=[10, 50], limit=2)
        assert d.get_cost(0) == 10
        assert d.get_cost(1) == 50
        assert d.get_cost(5) == 50  # 已达上限

    # ---- is_visible ----

    def test_is_visible_true(self):
        d = _make_def(visibilities=[100])
        assert d.is_visible(100, 0) is True
        assert d.is_visible(50, 0) is False

    def test_is_visible_uses_quantity_index(self):
        """多级可见性：当前数量的 visibility 阈值。"""
        d = _make_def(visibilities=[10, 100, 1000])
        # qty=0: 需要 cumulative >= 10
        assert d.is_visible(10, 0) is True
        assert d.is_visible(9, 0) is False
        # qty=1: 需要 cumulative >= 100
        assert d.is_visible(100, 1) is True
        assert d.is_visible(99, 1) is False

    def test_is_visible_clamps_index(self):
        """数量超出数组时使用最后一个阈值。"""
        d = _make_def(visibilities=[10, 100])
        assert d.is_visible(100, 5) is True

    # ---- can_buy ----

    def test_can_buy_no_limit(self):
        d = _make_def(limit=0)
        assert d.can_buy(0) is True
        assert d.can_buy(999) is True

    def test_can_buy_with_limit(self):
        d = _make_def(limit=3)
        assert d.can_buy(0) is True
        assert d.can_buy(1) is True
        assert d.can_buy(2) is True
        assert d.can_buy(3) is False

    # ---- requires ----

    def test_no_requires(self):
        d = _make_def()
        assert d.requires is None

    def test_with_requires(self):
        d = _make_def(requires={"key": "clicker", "level": 3})
        assert d.requires == ("clicker", 3)

    # ---- default values ----

    def test_default_category(self):
        d = _make_def(category="dps")
        assert d.category == "dps"

    def test_default_era(self):
        d = _make_def(era="stone")
        assert d.era == "stone"

    def test_per_second_default_zero(self):
        d = _make_def()
        assert d.per_second == 0
