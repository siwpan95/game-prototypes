"""
理智值组件 — 类型安全版本。

使用 dataclass 实现，支持默认值。
"""

from dataclasses import dataclass

from core.ecs import Component


@dataclass
class Sanity(Component):
    """玩家理智值，影响游戏机制和渲染效果。"""
    value: int = 100
    max_value: int = 100

    def recover(self, amount: int) -> int:
        """恢复理智，返回实际恢复量。"""
        old = self.value
        self.value = min(self.value + amount, self.max_value)
        return self.value - old

    def drain(self, amount: int) -> int:
        """扣除理智，返回实际扣除量。"""
        old = self.value
        self.value = max(self.value - amount, 0)
        return old - self.value

    @property
    def ratio(self) -> float:
        """理智百分比 (0.0 - 1.0)。"""
        return self.value / self.max_value if self.max_value > 0 else 0.0

    @property
    def is_depleted(self) -> bool:
        """理智是否已耗尽。"""
        return self.value <= 0

    def __repr__(self) -> str:
        return f"Sanity({self.value}/{self.max_value})"
