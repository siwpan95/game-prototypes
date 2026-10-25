# -*- coding: utf-8 -*-
"""终端文字地牢探险 —— CLI 入口。

用法::

    python 随机地牢.py                  # 默认：内置（纯标准库）
    python 随机地牢.py --engine super   # 接超级引擎（真实地牢图 + 骰系规则）
    python 随机地牢.py --status         # 看引擎可用性与配置
    python 随机地牢.py --seed 7 --fast  # 固定种子 / 关闭打字机延迟

引擎不可用时**自动回退**内置实现（不会崩）；`--engine super --strict` 则强制报错。
"""

from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dungeon import engine as eng  # noqa: E402
from dungeon.game import DEFAULT_SIZE, Game  # noqa: E402
from dungeon.rules import make_rules  # noqa: E402
from dungeon.ui import make_printer  # noqa: E402
from dungeon.world import make_world_source  # noqa: E402


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="随机地牢 · 终端文字地牢探险")
    ap.add_argument("--engine", choices=("builtin", "super", "auto"),
                    default="builtin", help="世界/规则来源（默认 builtin，纯标准库）")
    ap.add_argument("--strict", action="store_true",
                    help="--engine super 但引擎不可用时报错而非回退")
    ap.add_argument("--status", action="store_true", help="打印引擎可用性后退出")
    ap.add_argument("--seed", type=int, default=None, help="随机种子（可复现）")
    ap.add_argument("--size", type=int, default=DEFAULT_SIZE, help="内置模式的地牢边长")
    ap.add_argument("--rooms", type=int, default=6, help="超级引擎模式的房间数")
    ap.add_argument("--fast", action="store_true", help="关闭打字机延迟（便于自动化）")
    ap.add_argument("--hp", type=int, default=20)
    ap.add_argument("--attack", type=int, default=5)
    args = ap.parse_args(argv)

    engine = eng.probe()

    if args.status:
        # --status 是诊断命令，值得真跑一次装配（目录在 ≠ 依赖齐）
        # 注意顺序：ready() 失败会写入 engine.error 并让 available 转 False，
        # 所以先记住"目录/导入是否定位到"，再验证。
        located = engine.available
        if eng.ready(engine):
            print(eng.describe(engine))
        elif located:
            print(f"超级引擎已定位（{engine.root or '已安装'}），但装配失败：{engine.error}")
            print("  常见原因：缺 PyYAML / watchdog / numpy，或 cordis 未定位"
                  "（设 CORDIS_SRC 指向 3dworld/vendor/cordis/src）。")
        else:
            print(eng.describe(engine))
        print(f"默认引擎: {args.engine}｜世界源: "
              f"{'superengine' if args.engine == 'super' and engine.available else 'builtin'}")
        return 0

    want = args.engine
    if want == "super":
        ok, tip = eng.ensure(engine)
        if not ok:
            if args.strict:
                print(f"[地牢] 要求接入超级引擎但不可用：{engine.reason}")
                print(f"[地牢] 修复：{tip}")
                print("DUNGEON_ENGINE_UNAVAILABLE")
                return 2
            print(f"[地牢] 超级引擎不可用（{engine.reason}），回退内置实现。")
            want = "builtin"

    world_source = make_world_source(
        want, engine, **({"rooms": args.rooms} if want == "super"
                         else {"size": args.size}))
    rules = make_rules(want, engine)
    ui = make_printer(delay=0.0 if args.fast else 0.02)

    g = Game(world_source, rules, ui, hp=args.hp, attack=args.attack)
    result = g.play(seed=args.seed)
    print(f"DUNGEON_RESULT={result}")
    return 0 if result == "escaped" else 1


if __name__ == "__main__":
    sys.exit(main())
