"""2048 —— 分层实现的命令行版本。

分层约定（依赖方向自上而下，禁止反向依赖）::

    cli  ->  app  ->  strategy / render
                  ->  core

- ``core``     纯领域逻辑，不做任何 I/O，不依赖上层。
- ``strategy`` 决策层，只依赖 ``core`` 的纯函数。
- ``render``   表现层，只读取 ``core`` 的快照。
- ``app``      编排层，把三者装配起来跑一局。
- ``cli``      参数解析与进程入口。
"""

from game2048.core.board import Board
from game2048.core.direction import Direction
from game2048.core.game import Game

__all__ = ["Board", "Direction", "Game"]
__version__ = "1.0.0"
