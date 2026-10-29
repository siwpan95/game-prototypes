"""编排层：把 Game / Strategy / Renderer 装配起来跑完一局。

这是原始 ``auto_play_simple`` 的替代品。对比一下职责数量：

原来那一个方法同时负责——决策顺序、清屏、打印棋盘、sleep、计步、
判断结束、打印总结。共 7 项职责，没有一项可以单独复用或测试。

现在它只负责一件事：**驱动循环**。走哪一步问策略，怎么显示问渲染器，
规则对不对问 core。所以给它换一个策略或换一个渲染器都不用改这里的代码。
"""

from __future__ import annotations

from game2048.core.game import Game
from game2048.core.result import EndReason, GameResult
from game2048.render.base import Renderer
from game2048.render.silent import SilentRenderer
from game2048.strategy.base import Strategy

__all__ = ["GameRunner", "DEFAULT_MAX_MOVES"]

DEFAULT_MAX_MOVES = 10_000
"""步数上限，防止病态策略死循环（原始实现写死为 1000）。"""


class GameRunner:
    """驱动一局自动对弈。

    :param game:      对局状态。
    :param strategy:  决策器。
    :param renderer:  渲染器，默认静默。
    :param max_moves: 步数上限。
    """

    __slots__ = ("game", "strategy", "renderer", "max_moves")

    def __init__(
        self,
        game: Game,
        strategy: Strategy,
        renderer: Renderer | None = None,
        max_moves: int = DEFAULT_MAX_MOVES,
    ) -> None:
        if max_moves < 0:
            raise ValueError("max_moves 不能为负数")
        self.game = game
        self.strategy = strategy
        self.renderer = renderer if renderer is not None else SilentRenderer()
        self.max_moves = max_moves

    def run(self) -> GameResult:
        """跑到结束，返回统计结果。"""
        self.renderer.start(self.game.snapshot())
        reason = self._loop()
        result = GameResult(
            snapshot=self.game.snapshot(),
            reason=reason,
            strategy=self.strategy.name,
        )
        self.renderer.finish(result)
        return result

    # ------------------------------------------------------------------ 内部

    def _loop(self) -> EndReason:
        try:
            while True:
                if self.game.is_over():
                    return EndReason.GAME_OVER
                if self.game.moves >= self.max_moves:
                    return EndReason.MAX_MOVES

                direction = self.strategy.choose(self.game.board)
                if direction is None or not self.game.step(direction):
                    return EndReason.NO_MOVE_CHOSEN

                self.renderer.frame(self.game.snapshot())
        except KeyboardInterrupt:
            return EndReason.INTERRUPTED
