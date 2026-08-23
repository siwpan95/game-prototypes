"""run.py — 地牢冒险者 启动入口。

用法：
    python run.py                 # 交互式游玩（WASD 移动，撞怪进入战斗）
    python run.py --seed 7       # 指定种子
    python run.py --floors 8     # 指定层数
    python run.py --auto         # 无头自动演示（自检 / 不需要键盘）
    python run.py --load         # 从 savegame.json 续玩
    python run.py --save         # 以默认设置开局并立即存盘（用于测试/云存档）
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from game import Game
import savegame as savegame_mod


def main() -> None:
    ap = argparse.ArgumentParser(
        description="地牢冒险者 — procgen 生成世界 + alloy 驱动的可玩 Roguelike"
    )
    ap.add_argument("--seed", type=int, default=20260717, help="随机种子")
    ap.add_argument("--floors", type=int, default=5, help="地牢总层数")
    ap.add_argument("--auto", action="store_true",
                    help="无交互自动演示（用于自检，不需要键盘输入）")
    ap.add_argument("--load", action="store_true",
                    help="从 savegame.json 读档续玩")
    ap.add_argument("--save", action="store_true",
                    help="开局即存盘（默认路径 savegame.json）")
    ap.add_argument("--save-path", type=str, default=None,
                    help="指定存档文件路径（配合 --load / --save）")
    args = ap.parse_args()

    if args.load:
        if not os.path.exists(args.save_path or savegame_mod.DEFAULT_SAVE_PATH):
            print("没有找到存档文件。")
            return
        game = savegame_mod.load_game(args.save_path)
    else:
        game = Game(seed=args.seed, floors=args.floors)
        if args.save:
            game.save(args.save_path)

    if args.auto:
        status = game.run_auto()
        print(game.render())
        print("\n最终状态：", status)
    else:
        game.run_interactive()


if __name__ == "__main__":
    main()
