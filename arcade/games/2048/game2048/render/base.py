"""渲染抽象。

编排层只认这个接口，因此"跑一局棋"和"怎么显示"彻底解耦：
终端展示、静默跑分、将来接 GUI 或 Web，都只是换一个实现。
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from game2048.core.game import GameSnapshot
from game2048.core.result import GameResult

__all__ = ["Renderer"]


class Renderer(ABC):
    """把棋局状态呈现出去。"""

    def start(self, snapshot: GameSnapshot) -> None:
        """一局开始时调用一次。"""

    @abstractmethod
    def frame(self, snapshot: GameSnapshot) -> None:
        """每一步调用，绘制当前棋面。"""

    def finish(self, result: GameResult) -> None:
        """一局结束时调用一次。"""
