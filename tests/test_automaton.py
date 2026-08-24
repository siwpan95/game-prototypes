"""元胞自动机引擎测试。"""
from __future__ import annotations

import unittest

from yuanbao.config import Config
from yuanbao.core.automaton import CellularAutomaton


class TestAutomaton(unittest.TestCase):
    def test_grid_dimensions(self):
        ca = CellularAutomaton(Config(GRID_SIZE=10), seed=42)
        self.assertEqual(len(ca.grid), 10)
        self.assertEqual(len(ca.grid[0]), 10)
        self.assertEqual(len(ca.tag_grid), 10)

    def test_seed_reproducible(self):
        a = CellularAutomaton(Config(GRID_SIZE=15), seed=7)
        b = CellularAutomaton(Config(GRID_SIZE=15), seed=7)
        self.assertEqual(a.grid, b.grid)
        self.assertEqual(a.tag_grid, b.tag_grid)

    def test_different_seed_differs(self):
        a = CellularAutomaton(Config(GRID_SIZE=20, INIT_DENSITY=0.5), seed=1)
        b = CellularAutomaton(Config(GRID_SIZE=20, INIT_DENSITY=0.5), seed=2)
        self.assertNotEqual(a.grid, b.grid)

    def test_step_changes_state(self):
        ca = CellularAutomaton(Config(GRID_SIZE=20, INIT_DENSITY=0.5), seed=1)
        before = ca.get_state()
        ca.step()
        after = ca.get_state()
        self.assertNotEqual(before, after)

    def test_clear_cell(self):
        ca = CellularAutomaton(Config(GRID_SIZE=5, INIT_DENSITY=1.0), seed=0)
        alive = [(i, j) for i in range(5) for j in range(5) if ca.grid[i][j] == 1]
        self.assertTrue(alive, "应有活细胞")
        i, j = alive[0]
        self.assertTrue(ca.clear_cell(i, j))
        self.assertEqual(ca.grid[i][j], 0)
        self.assertEqual(ca.tag_grid[i][j], 0)
        # 重复清空应失败
        self.assertFalse(ca.clear_cell(i, j))

    def test_clear_cell_out_of_bounds(self):
        ca = CellularAutomaton(Config(GRID_SIZE=5), seed=0)
        self.assertFalse(ca.clear_cell(-1, 0))
        self.assertFalse(ca.clear_cell(0, 99))

    def test_toroidal_wrap(self):
        # 3x3 全活，(0,0) 的 8 邻居应全部存活（环面环绕）
        ca = CellularAutomaton(Config(GRID_SIZE=3, INIT_DENSITY=1.0), seed=0)
        neighbors = ca._neighbors(0, 0)
        self.assertEqual(len(neighbors), 8)

    def test_get_state_is_copy(self):
        ca = CellularAutomaton(Config(GRID_SIZE=5), seed=0)
        g, _t = ca.get_state()
        g[0][0] = 99
        self.assertNotEqual(ca.grid[0][0], 99)

    def test_count_alive(self):
        ca = CellularAutomaton(Config(GRID_SIZE=4, INIT_DENSITY=1.0), seed=0)
        self.assertEqual(ca.count_alive(), 16)
        ca.clear_cell(0, 0)
        self.assertEqual(ca.count_alive(), 15)

    def test_set_cell(self):
        ca = CellularAutomaton(Config(GRID_SIZE=5, INIT_DENSITY=0.0), seed=0)
        self.assertEqual(ca.count_alive(), 0)
        ca.set_cell(2, 2, 1)
        self.assertEqual(ca.grid[2][2], 1)
        self.assertEqual(ca.tag_grid[2][2], 1)
        self.assertEqual(ca.count_alive(), 1)


if __name__ == "__main__":
    unittest.main()
