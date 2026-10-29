"""细胞工厂启动入口（默认 GUI）。

等价用法：
    python main.py            # 启动 GUI
    python main.py --cli      # 命令行模式
    python -m yuanbao         # 同上
    python yuanbao.py         # 旧入口，向后兼容
"""
from yuanbao.cli import run_cli

if __name__ == "__main__":
    raise SystemExit(run_cli())
