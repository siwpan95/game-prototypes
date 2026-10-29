"""策略抽象。

上层（``app``）只依赖这个接口，不认识任何具体策略；
具体策略通过 :data:`REGISTRY` 注册，CLI 用名字取用。
这样新增一个 AI 只需要加一个文件 + 一行注册，不用改动编排层。
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from game2048.core.board import Board
from game2048.core.direction import Direction

__all__ = ["Strategy", "REGISTRY", "register", "create", "available_names"]


class Strategy(ABC):
    """决定"下一步往哪走"的决策器。

    实现约定：只读取传入的棋盘，**绝不**修改它，也不做任何 I/O。
    """

    name: str = "unnamed"
    description: str = ""

    @abstractmethod
    def choose(self, board: Board) -> Direction | None:
        """给出下一步方向；无路可走时返回 ``None``。"""

    def __repr__(self) -> str:  # pragma: no cover - 调试用
        return f"<Strategy {self.name}>"


REGISTRY: dict[str, type[Strategy]] = {}
"""策略名 -> 策略类。"""


def register(cls: type[Strategy]) -> type[Strategy]:
    """类装饰器：把策略登记到 :data:`REGISTRY`。"""
    key = cls.name
    if key in REGISTRY:
        raise ValueError(f"策略名重复: {key}")
    REGISTRY[key] = cls
    return cls


def create(name: str, **kwargs: object) -> Strategy:
    """按名字实例化策略。"""
    try:
        cls = REGISTRY[name]
    except KeyError:
        legal = ", ".join(available_names())
        raise ValueError(f"未知策略 {name!r}，可选: {legal}") from None
    return cls(**kwargs)  # type: ignore[arg-type]


def available_names() -> tuple[str, ...]:
    """所有已注册的策略名（字典序）。"""
    return tuple(sorted(REGISTRY))
