"""静默渲染器：什么都不输出。

批量跑对局做策略对比时用它，把 I/O 开销和刷屏彻底去掉。
原始实现做不到这一点——打印是写死在主循环里的。
"""

from __future__ import annotations

from game2048.core.game import GameSnapshot
from game2048.core.result import GameResult
from game2048.render.base import Renderer

__all__ = ["SilentRenderer"]


class SilentRenderer(Renderer):
    """空实现，同时记录被调用的帧数，便于测试编排层。"""

    def __init__(self) -> None:
        self.frames = 0
        self.finished = False

    def frame(self, snapshot: GameSnapshot) -> None:
        self.frames += 1

    def finish(self, result: GameResult) -> None:
        self.finished = True
