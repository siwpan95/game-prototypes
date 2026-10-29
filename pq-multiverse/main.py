"""
Progress Quest Multiverse - 主入口
用法：
  python main.py                  # 显示开始界面，选择主题后进入游戏（主题版引擎）
  python main.py --pq             # 使用 PQ 架构版引擎（队列系统/Tick引擎/确定随机数）
  python main.py --theme warcraft # 跳过开始界面，直接进入指定主题
  python main.py --pq --theme diablo  # PQ 架构版 + 指定主题
  python main.py --list           # 列出所有可用主题
"""

import sys
import os
import argparse

# 将 src 目录加入路径
SRC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from core.themed_engine import ThemedGameEngine


def list_themes():
    """列出所有可用主题"""
    themes = ThemedGameEngine.list_themes()
    print("\n可用主题：")
    for t in themes:
        display_name = ThemedGameEngine.get_theme_display_name(t)
        print(f"  {t:12s} - {display_name}")
    print("\n用法: python main.py --theme <主题名>")
    print("选项: --pq  使用 PQ 架构版引擎")


def run_with_start_screen(use_pq=False):
    """通过开始界面启动游戏"""
    import tkinter as tk
    from ui.start_screen import StartScreen

    # 根据参数选择 UI
    if use_pq:
        from ui.tkinter_ui_pq import PqMainWindow
    else:
        from ui.tkinter_ui_themed import PqMainWindow

    root = tk.Tk()

    def on_start(theme_name, char_name, race, char_class):
        # 销毁开始界面的所有组件
        for widget in root.winfo_children():
            widget.destroy()
        # 恢复窗口属性
        root.resizable(True, True)
        # 创建主窗口
        PqMainWindow(root, theme_name=theme_name,
                     char_name=char_name, race=race, char_class=char_class)

    StartScreen(root, on_start)
    root.mainloop()


def run_direct(theme_name, use_pq=False):
    """跳过开始界面，直接进入指定主题"""
    import tkinter as tk

    # 根据参数选择 UI
    if use_pq:
        from ui.tkinter_ui_pq import PqMainWindow
    else:
        from ui.tkinter_ui_themed import PqMainWindow

    print(f"正在加载主题: {theme_name} ...")
    if use_pq:
        print("使用 PQ 架构版引擎（队列系统/Tick引擎/确定随机数）")
    root = tk.Tk()
    PqMainWindow(root, theme_name=theme_name)
    root.mainloop()


def main():
    parser = argparse.ArgumentParser(description="Progress Quest Multiverse")
    parser.add_argument("--theme", default=None,
                        help="跳过开始界面，直接进入指定主题 (使用 --list 查看可用主题)")
    parser.add_argument("--list", action="store_true", help="列出所有可用主题")
    parser.add_argument("--pq", action="store_true",
                        help="使用 PQ 架构版引擎（集成队列系统/Tick引擎/确定随机数）")
    args = parser.parse_args()

    if args.list:
        list_themes()
        return

    # 检查 tkinter 是否可用
    try:
        import tkinter
    except ImportError:
        print("当前 Python 环境缺少 tkinter！")
        print("请确保使用本地 Python 3.14 运行：")
        print('  "C:/Users/13122/AppData/Local/Programs/Python/Python314/python.exe" main.py')
        sys.exit(1)

    if args.theme:
        run_direct(args.theme, use_pq=args.pq)
    else:
        run_with_start_screen(use_pq=args.pq)


if __name__ == "__main__":
    main()
