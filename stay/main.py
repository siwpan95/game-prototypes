#!/usr/bin/env python3
"""Progress Quest 2 — The Progression (Python 移植版)

用法:
    python main.py                  # 启动游戏
    python main.py --savefile path  # 加载存档
"""

import sys
import argparse
from pq2.game import Game
from pq2.types import LoadError, GameState
from pq2.gui.tkinter_gui import TkGUI


def main():
    parser = argparse.ArgumentParser(
        description="Progress Quest 2 — The Progression"
    )
    parser.add_argument(
        "--savefile", type=str, default="",
        help="Load the saved game file"
    )
    args = parser.parse_args()

    game = Game()

    if args.savefile:
        error, recovered = game.load_game_with_recovery(args.savefile)
        if error != LoadError.None_:
            print(f"加载存档失败: {args.savefile} ({error.name})")
            return 1
        if recovered:
            print("存档已损坏，已从备份自动恢复。")

    gui = TkGUI(game)
    gui.run()

    return 0


if __name__ == "__main__":
    sys.exit(main())
