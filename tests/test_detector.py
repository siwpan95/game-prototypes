"""CNN 模式检测器测试。"""
from __future__ import annotations

import unittest

from yuanbao.config import Config
from yuanbao.core.automaton import CellularAutomaton
from yuanbao.core.detector import CNNDetector


class TestDetector(unittest.TestCase):
    def setUp(self):
        self.cfg = Config(GRID_SIZE=5, INIT_DENSITY=0.0)
        self.ca = CellularAutomaton(self.cfg, seed=0)
        self.detector = CNNDetector(5, self.cfg)

    def _set(self, i: int, j: int, tag: str) -> None:
        self.ca.set_cell(i, j, self.cfg.tag_index(tag))

    def test_detect_red_with_one_green_neighbor(self):
        self._set(2, 2, 'red')
        self._set(2, 3, 'green')
        grid, tag = self.ca.get_state()
        matches = self.detector.detect_pattern(
            grid, tag, {'center': 'red', 'neighbors': {'green': 1}}
        )
        self.assertIn((2, 2), matches)

    def test_no_match_when_count_wrong(self):
        # 中心红 + 2 个绿邻居，但要求恰好 1 个绿 -> 不匹配
        self._set(2, 2, 'red')
        self._set(2, 3, 'green')
        self._set(2, 1, 'green')
        grid, tag = self.ca.get_state()
        matches = self.detector.detect_pattern(
            grid, tag, {'center': 'red', 'neighbors': {'green': 1}}
        )
        self.assertNotIn((2, 2), matches)

    def test_center_tag_must_match(self):
        self._set(2, 2, 'blue')
        self._set(2, 3, 'green')
        grid, tag = self.ca.get_state()
        matches = self.detector.detect_pattern(
            grid, tag, {'center': 'red', 'neighbors': {'green': 1}}
        )
        self.assertEqual(matches, [])

    def test_dead_cell_not_detected(self):
        grid, tag = self.ca.get_state()
        matches = self.detector.detect_pattern(grid, tag, {'center': 'red', 'neighbors': {}})
        self.assertEqual(matches, [])

    def test_pattern_without_neighbors_clause(self):
        # 仅指定 center，不约束邻居数量
        self._set(1, 1, 'yellow')
        self._set(1, 2, 'red')
        self._set(2, 1, 'blue')
        grid, tag = self.ca.get_state()
        matches = self.detector.detect_pattern(grid, tag, {'center': 'yellow'})
        self.assertEqual(matches, [(1, 1)])

    def test_toroidal_neighbor_counted(self):
        # (0,0) 红，(4,4) 绿（环面对角邻居）+ (0,4) 绿 + (4,0) 绿 = 3 个绿
        self._set(0, 0, 'red')
        self._set(4, 4, 'green')
        self._set(0, 4, 'green')
        self._set(4, 0, 'green')
        grid, tag = self.ca.get_state()
        matches = self.detector.detect_pattern(
            grid, tag, {'center': 'red', 'neighbors': {'green': 3}}
        )
        self.assertIn((0, 0), matches)

    def test_unknown_tag_in_pattern(self):
        self._set(2, 2, 'red')
        grid, tag = self.ca.get_state()
        # center 是不存在的标签 -> 不会有任何匹配
        matches = self.detector.detect_pattern(
            grid, tag, {'center': 'purple', 'neighbors': {}}
        )
        self.assertEqual(matches, [])


if __name__ == "__main__":
    unittest.main()
