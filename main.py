"""main.py — MVVM 架构入口
组装 Model / ViewModel / View 三层，启动游戏。
"""
import tkinter as tk
import os
import sys

# 确保项目根目录在搜索路径中
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

from data import ConfigLoader
from viewmodel import GameViewModel
from view import MainWindow


def main():
    config_path = os.path.join(SCRIPT_DIR, "config.xlsx")
    config = ConfigLoader(config_path)

    if not config.load_all():
        print("错误: 无法加载配置文件！请确保 config.xlsx 存在且格式正确。")
        return

    root = tk.Tk()
    vm = GameViewModel(config)
    window = MainWindow(root, vm)
    window.run()


if __name__ == "__main__":
    main()
