"""终端渲染，沿用原始 ``print_board`` 的 ASCII 表格风格，但宽度随棋盘尺寸自适应
（原来 ``"=" * 25`` 是写死的，换成 5x5 棋盘就会错位）。

原来清屏、``time.sleep``、打印全都混在 ``auto_play_simple`` 的循环体里，
导致核心循环既管逻辑又管显示，还没法关掉输出去跑批量测试。
现在这些副作用全部收敛在这个类里。
"""

from __future__ import annotations

import os
import sys
import time
from typing import TextIO

from game2048.core.game import GameSnapshot
from game2048.core.result import GameResult
from game2048.render.base import Renderer

__all__ = ["ConsoleRenderer"]


class ConsoleRenderer(Renderer):
    """ASCII 表格渲染。

    :param delay:      每帧之间的停顿秒数，0 表示不停顿。
    :param clear:      是否在每帧前清屏。
    :param title:      表头文字。
    :param stream:     输出流，默认为 ``sys.stdout``（测试时可注入 StringIO）。
    :param cell_width: 单元格宽度。
    """

    def __init__(
        self,
        delay: float = 0.1,
        clear: bool = True,
        title: str = "2048 (自动模式)",
        stream: TextIO | None = None,
        cell_width: int = 5,
    ) -> None:
        if delay < 0:
            raise ValueError("delay 不能为负数")
        if cell_width < 3:
            raise ValueError("cell_width 至少为 3")
        self.delay = delay
        self.clear = clear
        self.title = title
        self.cell_width = cell_width
        self._stream = stream if stream is not None else sys.stdout

    # ------------------------------------------------------------------ 接口

    def start(self, snapshot: GameSnapshot) -> None:
        self.frame(snapshot)

    def frame(self, snapshot: GameSnapshot) -> None:
        if self.clear:
            self._clear_screen()
        self._write(self.render_board(snapshot))
        self._write(f"得分: {snapshot.score}, 步数: {snapshot.moves}\n")
        if self.delay:
            time.sleep(self.delay)

    def finish(self, result: GameResult) -> None:
        self._write(self.render_board(result.snapshot))
        self._write(
            f"游戏结束! 最终得分: {result.score}, 总步数: {result.moves}\n"
            f"最大方块: {result.max_tile}\n"
            f"结束原因: {result.reason}\n"
        )

    # ------------------------------------------------------------ 纯字符串化

    def render_board(self, snapshot: GameSnapshot) -> str:
        """把棋面渲染成字符串（纯函数，方便直接断言）。"""
        board = snapshot.board
        width = self.cell_width
        separator = "+" + ("-" * width + "+") * board.size
        bar = "=" * len(separator)

        lines = ["", bar, self.title.center(len(bar)), bar]
        for row in board.rows():
            lines.append(separator)
            cells = "".join(
                (" " * width if value == 0 else f"{value:^{width}}") + "|"
                for value in row
            )
            lines.append("|" + cells)
        lines.append(separator)
        return "\n".join(lines) + "\n"

    # ------------------------------------------------------------------ 内部

    def _write(self, text: str) -> None:
        self._stream.write(text)

    @staticmethod
    def _clear_screen() -> None:
        os.system("cls" if os.name == "nt" else "clear")
