"""掉落表：加权随机掉落。"""
from __future__ import annotations

import numpy as np


class LootTable:
    """加权随机掉落表。

    entries: [(name, weight, (count_min, count_max)), ...]
    示例：
        t = LootTable([
            ("金币", 50, (1, 10)),
            ("药水", 10, (1, 3)),
            ("传说剑", 1, (1, 1)),
        ])
        drops = t.roll(5)   # 抽 5 次
    """

    def __init__(self, entries: list[tuple], seed: int = 0):
        if not entries:
            raise ValueError("掉落表不能为空")
        self.names = [e[0] for e in entries]
        self.weights = np.array([float(e[1]) for e in entries], dtype=np.float64)
        self.counts = [e[2] for e in entries]
        self.rng = np.random.RandomState(seed)

    def roll(self, n: int = 1, unique: bool = False) -> list[str]:
        """抽取 n 次，返回掉落名称列表（含数量标记）。

        unique=True 时跨掉落不重复（按权重无放回抽样），适合“每个宝箱一件”场景。
        """
        if self.weights.sum() <= 0:
            raise ValueError("权重和必须为正数")
        p = self.weights / self.weights.sum()
        if unique:
            k = min(n, len(self.names))
            idx = self.rng.choice(len(self.names), size=k, replace=False, p=p)
        else:
            idx = self.rng.choice(len(self.names), size=n, p=p)
        out = []
        for i in idx:
            cmin, cmax = self.counts[i]
            cnt = self.rng.randint(cmin, cmax + 1)
            out.append(f"{self.names[i]} x{cnt}" if cnt > 1 else self.names[i])
        return out
