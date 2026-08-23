"""ViewModel 层 - 状态管理与命令分发。

不依赖任何 UI 框架，通过回调 (listener) 通知视图层。
View 调用命令方法 -> ViewModel 修改 GameState -> 发事件 -> View 刷新。
"""
from .game_viewmodel import GameViewModel, GameEvent

__all__ = ["GameViewModel", "GameEvent"]
