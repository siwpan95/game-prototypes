from abc import ABC, abstractmethod
from game_engine import GameEngine

class BaseUI(ABC):
    @abstractmethod
    def run(self, engine: GameEngine):
        """启动主循环，返回触发的结局列表"""
        pass