"""支持 ``python -m yuanbao`` 启动。"""
import sys

from yuanbao.cli import run_cli

if __name__ == "__main__":
    sys.exit(run_cli())
