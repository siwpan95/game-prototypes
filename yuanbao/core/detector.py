"""CNN 风格的空间模式检测器。

所谓"CNN 风格"是指：对网格中每个候选中心位置，以 3x3 卷积核扫描其邻域，
按预设模式判定是否匹配。这里没有可学习参数，而是用**固定核**描述任务需求
（例如"中心为红、恰好 1 个绿邻居"）。

pattern 格式
------------
::

    {
        'center': 'red',                  # 中心细胞必须是 red 标签
        'neighbors': {'green': 1}         # 8 邻域中 green 标签恰好出现 1 次
    }

``neighbors`` 是可选的；省略时只校验中心标签。多个原子 pattern 可由
:class:`~yuanbao.tasks.task.Task` 组合成一个收集任务。
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple

from yuanbao.config import Config


class CNNDetector:
    """固定卷积核模式检测器。"""

    def __init__(self, size: int, config: Optional[Config] = None, *, kernel_size: int = None):
        self.config = config or Config()
        self.size = size
        self.kernel_size = kernel_size if kernel_size is not None else self.config.KERNEL_SIZE
        # 标签名 -> 1-based 索引，构造时一次性建立，避免每次检测重建
        self._tag_to_idx: Dict[str, int] = {tag: i + 1 for i, tag in enumerate(self.config.TAGS)}

    def detect_pattern(
        self,
        grid: List[List[int]],
        tag_grid: List[List[int]],
        pattern: Dict[str, Any],
    ) -> List[Tuple[int, int]]:
        """返回所有满足 ``pattern`` 的活细胞坐标。"""
        matches: List[Tuple[int, int]] = []
        for i in range(self.size):
            for j in range(self.size):
                if grid[i][j] == 0:
                    continue
                if self._check_position(i, j, grid, tag_grid, pattern):
                    matches.append((i, j))
        return matches

    def _check_position(
        self,
        i: int,
        j: int,
        grid: List[List[int]],
        tag_grid: List[List[int]],
        pattern: Dict[str, Any],
    ) -> bool:
        center_idx = self._tag_to_idx.get(pattern.get('center', ''))
        if center_idx is None or tag_grid[i][j] != center_idx:
            return False

        required = pattern.get('neighbors')
        if not required:
            return True

        # 统计 8 邻域中各标签索引的出现次数
        actual: Dict[int, int] = defaultdict(int)
        for di in (-1, 0, 1):
            for dj in (-1, 0, 1):
                if di == 0 and dj == 0:
                    continue
                ni = (i + di) % self.size
                nj = (j + dj) % self.size
                if grid[ni][nj]:
                    actual[tag_grid[ni][nj]] += 1

        # 把需求中的标签名转成索引后比较精确数量
        for tname, cnt in required.items():
            tidx = self._tag_to_idx.get(tname)
            if tidx is None or actual.get(tidx, 0) != cnt:
                return False
        return True
