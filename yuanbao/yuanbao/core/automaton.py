"""带标签的二维元胞自动机引擎。

拓扑为环面（toroidal）：网格边界自动环绕，避免边缘效应。

内部表示
--------
* ``grid[i][j]``    - 0 表示死，1 表示活；
* ``tag_grid[i][j]`` - 0 表示无标签，``1..len(TAGS)`` 为标签索引。

存活规则下细胞的标签从活邻居中随机继承；诞生规则下新细胞的标签也取自活邻居，
这使标签在演化中既会扩散也会因随机选择而混合，为模式检测提供动态素材。
"""
from __future__ import annotations

import random
from typing import List, Optional, Tuple, Union

from yuanbao.config import Config

RandomLike = Union[random.Random, type(random)]


class CellularAutomaton:
    """带标签的二维元胞自动机。"""

    def __init__(self, config: Optional[Config] = None, *, seed: Optional[int] = None):
        self.config = config or Config()
        self.size: int = self.config.GRID_SIZE
        self.tags: List[str] = list(self.config.TAGS)
        self.grid: List[List[int]] = [[0] * self.size for _ in range(self.size)]
        self.tag_grid: List[List[int]] = [[0] * self.size for _ in range(self.size)]
        self._rng: RandomLike = random.Random(seed) if seed is not None else random
        self._random_init()

    # ---- 初始化 ----
    def _random_init(self) -> None:
        density = self.config.INIT_DENSITY
        n_tags = len(self.tags)
        for i in range(self.size):
            for j in range(self.size):
                if self._rng.random() < density:
                    self.grid[i][j] = 1
                    self.tag_grid[i][j] = self._rng.randint(1, n_tags)

    # ---- 邻域 ----
    def _neighbors(self, i: int, j: int) -> List[int]:
        """返回 8 邻域中所有活细胞的标签列表（环面环绕）。"""
        res: List[int] = []
        for di in (-1, 0, 1):
            for dj in (-1, 0, 1):
                if di == 0 and dj == 0:
                    continue
                ni = (i + di) % self.size
                nj = (j + dj) % self.size
                if self.grid[ni][nj]:
                    res.append(self.tag_grid[ni][nj])
        return res

    # ---- 演化 ----
    def step(self) -> None:
        """按 Conway 规则演化一代。"""
        cfg = self.config
        new_grid: List[List[int]] = [[0] * self.size for _ in range(self.size)]
        new_tag: List[List[int]] = [[0] * self.size for _ in range(self.size)]
        for i in range(self.size):
            for j in range(self.size):
                neighbors = self._neighbors(i, j)
                n = len(neighbors)
                if self.grid[i][j] == 1:
                    if cfg.SURVIVE_MIN <= n <= cfg.SURVIVE_MAX:
                        new_grid[i][j] = 1
                        # 标签继承：有活邻居则随机取一个，否则保留自身
                        new_tag[i][j] = self._rng.choice(neighbors) if neighbors else self.tag_grid[i][j]
                else:
                    if cfg.BORN_MIN <= n <= cfg.BORN_MAX:
                        new_grid[i][j] = 1
                        new_tag[i][j] = self._rng.choice(neighbors)
        self.grid, self.tag_grid = new_grid, new_tag

    # ---- 单元操作 ----
    def clear_cell(self, i: int, j: int) -> bool:
        """收集（清空）一个活细胞，返回是否成功。"""
        if 0 <= i < self.size and 0 <= j < self.size and self.grid[i][j] == 1:
            self.grid[i][j] = 0
            self.tag_grid[i][j] = 0
            return True
        return False

    def set_cell(self, i: int, j: int, tag_idx: int) -> None:
        """手工设置一个细胞为活并赋予标签索引。"""
        if 0 <= i < self.size and 0 <= j < self.size:
            self.grid[i][j] = 1
            self.tag_grid[i][j] = tag_idx

    # ---- 状态读取 ----
    def get_state(self) -> Tuple[List[List[int]], List[List[int]]]:
        """返回 (grid, tag_grid) 的深拷贝，外部修改不影响内部。"""
        return [row[:] for row in self.grid], [row[:] for row in self.tag_grid]

    def count_alive(self) -> int:
        return sum(sum(row) for row in self.grid)

    # ---- 文本渲染（CLI 兼容）----
    def display(self) -> None:
        """打印当前网格到 stdout。仅 CLI 使用，GUI 不调用。"""
        color_map = {0: '·', 1: 'R', 2: 'G', 3: 'B', 4: 'Y'}
        for i in range(self.size):
            line = ''.join(
                color_map.get(self.tag_grid[i][j], '?') if self.grid[i][j] else '·'
                for j in range(self.size)
            )
            print(line)
        print('-' * self.size)
