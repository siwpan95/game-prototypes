"""任务：若干需求的聚合。"""
from __future__ import annotations

from typing import List

from yuanbao.tasks.requirement import TaskRequirement


class Task:
    """一个任务由多个 :class:`TaskRequirement` 组成，全部完成才算完成。"""

    def __init__(self, name: str, requirements: List[TaskRequirement]):
        self.name = name
        self.requirements: List[TaskRequirement] = requirements
        self.completed: bool = False

    def check_completion(self) -> bool:
        """检查是否所有需求都已满足；满足则置 completed=True。"""
        if all(req.done for req in self.requirements):
            self.completed = True
        return self.completed

    def reset(self) -> None:
        self.completed = False
        for r in self.requirements:
            r.reset()

    def status(self) -> str:
        """多行文本状态，CLI 用。"""
        parts = [f"任务: {self.name}"]
        for req in self.requirements:
            parts.append(f"  - {req.description}: {req.collected}/{req.count}")
        parts.append("状态: " + ("完成" if self.completed else "进行中"))
        return "\n".join(parts)

    @property
    def progress(self) -> float:
        """0.0~1.0 的整体进度，GUI 进度条用。"""
        if not self.requirements:
            return 1.0
        total = sum(r.count for r in self.requirements)
        if total == 0:
            return 1.0
        got = sum(min(r.collected, r.count) for r in self.requirements)
        return got / total
