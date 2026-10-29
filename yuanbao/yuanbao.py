"""细胞工厂 - 向后兼容入口。

原单文件实现已迁移至 ``yuanbao`` 包（见 ``yuanbao/`` 目录）。
本文件仅保留以便旧脚本 ``python yuanbao.py`` 仍可运行。

推荐改用：
    python main.py            # 启动 GUI
    python -m yuanbao         # 同上
    python -m yuanbao --cli   # 命令行模式
"""
import sys

from yuanbao.cli import run_cli

if __name__ == "__main__":
    sys.exit(run_cli())
