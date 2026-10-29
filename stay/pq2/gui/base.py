"""GUI 基础类"""

from abc import ABC, abstractmethod


class View(ABC):
    """视图基类"""

    def __init__(self, game):
        self._game = game

    @abstractmethod
    def show(self):
        """显示视图"""
        pass

    @abstractmethod
    def hide(self):
        """隐藏视图"""
        pass

    @abstractmethod
    def close(self):
        """关闭视图"""
        pass


class GUI(ABC):
    """GUI 基类"""

    def __init__(self, game):
        self._game = game
        self._views = []

    @abstractmethod
    def run(self):
        """启动 GUI 主循环"""
        pass

    @abstractmethod
    def show_main_menu(self):
        pass

    @abstractmethod
    def show_character_creator(self, new_game):
        pass

    @abstractmethod
    def show_game_screen(self):
        pass
