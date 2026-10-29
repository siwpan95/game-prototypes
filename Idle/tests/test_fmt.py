"""
数字格式化 单元测试 — 覆盖普通值、大数、溢出递归。
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.fmt import fmt_num, fmt_gold, fmt_dps


class TestFmtNum:
    """fmt_num 格式化函数测试。"""

    def test_small_integer(self):
        assert fmt_num(0) == "0"
        assert fmt_num(100) == "100"
        assert fmt_num(9999) == "9,999"

    def test_large_under_1e15(self):
        """小于 10^15 用千分位。"""
        assert fmt_num(10 ** 14) == "100,000,000,000,000"

    def test_between_1e15_and_1e308(self):
        """10^15 ~ 10^308 用「尾数+指数」科学记法（无 + 号）。"""
        result = fmt_num(10 ** 20)
        assert result == "1.00e20"
        assert "e+" not in result

    def test_non_power_of_ten(self):
        """非整 10 幂的大数，尾数保留 2 位小数。"""
        result = fmt_num(12345 * 10 ** 50)
        assert result == "1.23e54"

    def test_beyond_1e308_recursion(self):
        """超过 float 上限的超大整数仍用统一科学记法。"""
        huge = 10 ** 400
        result = fmt_num(huge)
        # 统一为 "1.00e400"，不得再出现递归分块的 "e+e+" 形式
        assert result == "1.00e400"
        assert "e+" not in result
        assert len(result) > 0

    def test_float_input(self):
        assert fmt_num(3.14) == "3"
        assert fmt_num(1500.7) == "1,500"


class TestFmtGold:
    """fmt_gold 金币格式化测试。"""

    def test_small(self):
        assert fmt_gold(0) == "0"
        assert fmt_gold(1000) == "1,000"

    def test_large_uses_fmt_num(self):
        assert fmt_gold(10 ** 20) == fmt_num(10 ** 20)


class TestFmtDps:
    """fmt_dps 数值格式化测试。"""

    def test_uses_fmt_num(self):
        assert fmt_dps(0) == "0"
        assert fmt_dps(10 ** 20) == fmt_num(10 ** 20)
