"""地图系统回归测试：模版出口一致性 / 门洞互通 / 区块出口互连。

这三类不变量各对应一个曾真实存在的 bug：
- 出口一致性：tech_nook / data_temple 声明 N/E/W 但只开 N/S/E 口（错放分组）
- 出口互连：随机扩充出口不检查已生成邻居 -> 单边出口（走出去撞墙）
- 门洞互通：energy_core / portal_gate 门洞与大厅之间隔着两行墙 ->
  四门"通而不达"整区块隔离；generator_room 的发电机块压住西侧门廊 ->
  西门死路

运行（需 pygame 与 numpy；无则自动跳过）::

    python -m unittest discover -s tests        # 在本目录下
    python tests/test_map.py                    # 直接跑
"""
import collections
import os
import sys
import unittest
from types import SimpleNamespace

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

try:
    # 2026-10-10 拆包后实现迁入 kaw/ 包；SimpleNamespace 保持 K.* 旧引用写法
    from kaw.world.worldmap import WorldMap
    from kaw.world.pool import _ALL_TEMPLATES, _DIR_DELTA, _OPPOSITE
    K = SimpleNamespace(WorldMap=WorldMap, _ALL_TEMPLATES=_ALL_TEMPLATES,
                        _DIR_DELTA=_DIR_DELTA, _OPPOSITE=_OPPOSITE)
    _HAVE_DEPS = True
    _SKIP_REASON = ''
except Exception as exc:                       # 缺 pygame/numpy 等
    _HAVE_DEPS = False
    _SKIP_REASON = f'需要 kaw 包依赖（pygame/numpy）：{exc!r}'

# 各方向"门洞内侧格"与"边界开口格"（原版约定：出口固定 3 格宽）
OUTER = {'N': ((0, 9), (0, 10), (0, 11)),
         'S': ((20, 9), (20, 10), (20, 11)),
         'W': ((9, 0), (10, 0), (11, 0)),
         'E': ((9, 20), (10, 20), (11, 20))}
INNER = {'N': (1, 10), 'S': (19, 10), 'W': (10, 1), 'E': (10, 19)}


def _walkable(grid):
    return {(r, c) for r in range(21) for c in range(21)
            if grid[r][c] != '#'}


def _reach(grid, walk, start):
    if start not in walk:
        return set()
    seen = {start}
    q = collections.deque([start])
    while q:
        r, c = q.popleft()
        for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nxt = (r + dr, c + dc)
            if nxt in walk and nxt not in seen:
                seen.add(nxt)
                q.append(nxt)
    return seen


@unittest.skipUnless(_HAVE_DEPS, _SKIP_REASON)
class TestTemplates(unittest.TestCase):
    def test_size_and_declared_exits(self):
        """每个模版 21x21；分组声明的出口必须真的开口。"""
        for key, pool in K._ALL_TEMPLATES.items():
            for fn in pool:
                grid = fn()
                self.assertEqual(len(grid), 21, fn.__name__)
                for d in key:
                    for (r, c) in OUTER[d]:
                        self.assertEqual(
                            grid[r][c], '.',
                            f'{fn.__name__} 声明出口 {d} 未开口 @({r},{c})')

    def test_doors_are_mutually_connected(self):
        """同一模版各门的内侧格必须互相连通（防"通而不达"/死路）。"""
        for key, pool in K._ALL_TEMPLATES.items():
            for fn in pool:
                grid = fn()
                walk = _walkable(grid)
                for d in key:
                    comp = _reach(grid, walk, INNER[d])
                    self.assertTrue(
                        comp, f'{fn.__name__} {d} 门内侧就是墙')
                    for d2 in key:
                        if d2 == d:
                            continue
                        self.assertIn(
                            INNER[d2], comp,
                            f'{fn.__name__}：{d} 门进来走不到 {d2} 门')


@unittest.skipUnless(_HAVE_DEPS, _SKIP_REASON)
class TestWorldMap(unittest.TestCase):
    def _fresh(self, seed):
        wm = K.WorldMap(seed=seed)
        wm.ensure_neighbors(0, 0)
        return wm

    def test_no_one_sided_exits(self):
        """相邻区块出口必须成对（无单边出口）。"""
        for seed in range(1, 41):
            wm = self._fresh(seed)
            for (cx, cy), exits in wm._exits.items():
                for d, (dx, dy) in K._DIR_DELTA.items():
                    nb = (cx + dx, cy + dy)
                    if nb in wm._exits and d in exits:
                        self.assertIn(
                            K._OPPOSITE[d], wm._exits[nb],
                            f'seed={seed}：{(cx, cy)} 开 {d} 但 {nb} '
                            f'未开 {K._OPPOSITE[d]}')

    def test_spawn_can_leave_chunk(self):
        """出生点必须能走出所在区块（防"出生点牢笼"——曾因 energy_core
        门洞通而不达，出生后被整个区块隔离）。"""
        for seed in range(1, 11):
            wm = K.WorldMap(seed=seed)
            for dcy in (-1, 0, 1):
                for dcx in (-1, 0, 1):
                    wm.ensure_neighbors(dcx, dcy)
            all_walk = set()
            for (cx, cy), grid in wm._chunks.items():
                for ly in range(21):
                    for lx in range(21):
                        if grid[ly][lx] != '#':
                            all_walk.add((cx * 21 + lx, cy * 21 + ly))
            spawn = wm.find_safe_spawn(0, 0)
            s = (int(spawn[0]), int(spawn[1]))
            seen = {s}
            q = collections.deque([s])
            while q:
                x, z = q.popleft()
                for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    nxt = (x + dx, z + dz)
                    if nxt in all_walk and nxt not in seen:
                        seen.add(nxt)
                        q.append(nxt)
            self.assertGreaterEqual(len(seen), 500,
                                    f'seed={seed} 出生点可达仅 {len(seen)} 格')
            ccx, ccy = s[0] // 21, s[1] // 21
            outside = [p for p in seen
                       if p[0] // 21 != ccx or p[1] // 21 != ccy]
            self.assertTrue(outside,
                            f'seed={seed} 出生点走不出区块（牢笼）')


if __name__ == '__main__':
    unittest.main(verbosity=2)
