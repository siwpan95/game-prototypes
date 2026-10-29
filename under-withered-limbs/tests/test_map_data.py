"""MapData 单元测试 — 地图字符替换与读取。"""
import pytest
from core.map_data import MapData
from core.config import FILL_CHAR


class TestMapDataLoad:
    """地图加载验证。"""

    def test_default_map_has_correct_size(self, map_data):
        assert len(map_data.grid) == 32         # ROWS
        assert all(len(row) == 40 for row in map_data.grid)  # COLS

    def test_known_wall_char(self, map_data):
        """行 0 第 0 列应该是墙。"""
        assert map_data.get(0, 0) == "墙"

    def test_known_door_char(self, map_data):
        """行 3 第 18 列应该是阁楼门。"""
        assert map_data.get(18, 3) == "门"

    def test_known_floor_char(self, map_data):
        """行 13 第 19 列（玩家初始位）应该是地板。"""
        assert map_data.get(19, 13) == "░"

    def test_known_dark_char(self, map_data):
        """行 18 第 12 列应该是暗（走廊暗区起点）。"""
        assert map_data.get(12, 18) == "暗"


class TestMapDataGet:
    """get() 边界与越界行为。"""

    def test_in_bounds(self, map_data_empty):
        assert map_data_empty.get(1, 1) == "E"

    def test_col_too_large(self, map_data):
        assert map_data.get(999, 0) == FILL_CHAR

    def test_col_negative(self, map_data):
        assert map_data.get(-1, 0) == FILL_CHAR

    def test_row_too_large(self, map_data):
        assert map_data.get(0, 999) == FILL_CHAR

    def test_row_negative(self, map_data):
        assert map_data.get(0, -1) == FILL_CHAR


class TestMapDataSet:
    """set() 行为。"""

    def test_set_in_bounds(self, map_data_empty):
        map_data_empty.set(0, 0, "Z")
        assert map_data_empty.get(0, 0) == "Z"

    def test_set_out_of_bounds_no_crash(self, map_data):
        """越界 set 不应崩溃。"""
        map_data.set(999, 999, "X")   # 不应 raise


class TestMapDataReplaceAt:
    """replace_at() 精确替换。"""

    def test_matches_and_replaces(self, map_data_empty):
        map_data_empty.replace_at(0, 0, "A", "Z")
        assert map_data_empty.get(0, 0) == "Z"

    def test_no_match_does_nothing(self, map_data_empty):
        map_data_empty.replace_at(0, 0, "X", "Z")
        assert map_data_empty.get(0, 0) == "A"

    def test_attic_door_replace(self, map_data):
        """阁楼门 col=18,row=3 的"门"能被 replace_at 匹配。"""
        assert map_data.get(18, 3) == "门"
        map_data.replace_at(18, 3, "门", "░")
        assert map_data.get(18, 3) == "░"

    def test_attic_door_wrong_coords_no_op(self, map_data):
        """col=19,row=3 是"墙"不是"门"，replace_at("门")不会误触发。"""
        assert map_data.get(19, 3) == "墙"
        map_data.replace_at(19, 3, "门", "░")   # 不该匹配
        assert map_data.get(19, 3) == "墙"       # 维持原样


class TestMapDataReplaceArea:
    """replace_area() 集合版替换。"""

    def test_replace_set_members(self, map_data_empty):
        map_data_empty.set(0, 0, "X")
        map_data_empty.set(1, 1, "X")
        map_data_empty.replace_area(0, 2, 0, 2, {"X"}, "O")
        assert map_data_empty.get(0, 0) == "O"
        assert map_data_empty.get(1, 1) == "O"

    def test_leave_non_members(self, map_data_empty):
        map_data_empty.replace_area(0, 2, 0, 2, {"X"}, "O")
        # 所有字母都不在 {"X"} 中，应保持不变
        assert map_data_empty.get(1, 1) == "E"

    def test_basement_dark_clear(self, map_data):
        """row22-29 的"暗"能被 replace_area 清除。"""
        assert map_data.get(20, 22) == "暗"
        map_data.replace_area(17, 22, 21, 29, {"暗"}, "░")
        assert map_data.get(20, 22) == "░"


class TestMapDataReplaceRegion:
    """replace_region() 单字符版区域替换。"""

    def test_replace_all_matching(self, map_data_empty):
        map_data_empty.replace_region(0, 2, 0, 2, "A", "Z")
        assert map_data_empty.get(0, 0) == "Z"
        # 其他位置不应变
        assert map_data_empty.get(1, 1) == "E"
