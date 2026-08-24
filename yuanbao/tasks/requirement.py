"""任务需求：单个可被检测与收集的子目标。"""
from __future__ import annotations

from typing import Any, Dict


class TaskRequirement:
    """一个收集需求。

    Parameters
    ----------
    description:
        人类可读的描述（如"红细胞且周围恰有1个绿邻居"）。
    pattern:
        传给 :class:`~yuanbao.core.detector.CNNDetector` 的模式字典。
    count:
        需要收集的细胞数量。
    """

    def __init__(self, description: str, pattern: Dict[str, Any], count: int):
        self.description = description
        self.pattern = pattern
        self.count = count
        self.collected: int = 0

    @property
    def done(self) -> bool:
        """是否已收集足量。"""
        return self.collected >= self.count

    def reset(self) -> None:
        self.collected = 0

    def __repr__(self) -> str:
        return f"TaskRequirement({self.description!r}, {self.collected}/{self.count})"
