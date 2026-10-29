"""main.py — MVVM 架构入口
组装 Model / ViewModel / View 三层，启动游戏。

用法：
    python main.py            # 正常启动
    python main.py --smoke    # 自检：构建全部 UI 后 800ms 自动退出（打包验证用）
"""
import tkinter as tk
import os
import sys

# 确保项目根目录在搜索路径中（PyInstaller 打包后为 _MEIPASS）
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if getattr(sys, "frozen", False):
    # PyInstaller 打包运行：资源在 _MEIPASS 临时目录
    SCRIPT_DIR = getattr(sys, "_MEIPASS", SCRIPT_DIR)
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

from data import ConfigLoader
from viewmodel import GameViewModel
from view import MainWindow


def main() -> int:
    smoke = "--smoke" in sys.argv

    config_path = os.path.join(SCRIPT_DIR, "config.xlsx")
    config = ConfigLoader(config_path)

    if not config.load_all():
        print("错误: 无法加载配置文件！请确保 config.xlsx 存在且格式正确。")
        return 1

    root = tk.Tk()
    vm = GameViewModel(config)
    window = MainWindow(root, vm)

    if smoke:
        # 自检模式：UI 构建完成后自动开一局并退出
        def _smoke_run():
            try:
                vm.command_new_game(1)
                print("SMOKE OK: UI 构建成功，新游戏已初始化，自动退出。")
            finally:
                root.quit()
        root.after(800, _smoke_run)
        root.mainloop()
        return 0

    window.run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
