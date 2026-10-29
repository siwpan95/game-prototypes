# -*- coding: utf-8 -*-
"""arcade 街机合集 · 无头自检（不创建 tkinter 窗口）。

验证两件事：
1. 选单壳 main.py 的 GAMES 清单与 games/<sub>/<entry> 磁盘入口一一对应；
2. games/ski 的纯逻辑引擎（engine.GameEngine）能推进距离、吃旗加分、
   撞树扣分并在分数过低时判定失败。

不 import main.py（避免拉起 tkinter 界面），清单用 ast 静态解析。
"""

from __future__ import annotations

import ast
import os
import random
import subprocess
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


def check(condition, message):
    if not condition:
        raise AssertionError(message)


def load_games_manifest() -> list:
    """从 main.py 源码读取 GAMES 常量，不执行模块（不创建 Tk）。"""
    main_path = os.path.join(BASE_DIR, "main.py")
    with open(main_path, "r", encoding="utf-8") as fh:
        tree = ast.parse(fh.read(), filename=main_path)

    games = None
    for node in tree.body:
        if isinstance(node, ast.Assign):
            targets = [t.id for t in node.targets if isinstance(t, ast.Name)]
            if "GAMES" in targets:
                games = ast.literal_eval(node.value)
                break
    check(games is not None, "main.py 中找不到 GAMES 清单")
    return games


def check_manifest(games: list) -> None:
    check(len(games) == 10, f"GAMES 清单应为 10 个游戏，实际 {len(games)}")
    subs = []
    for item in games:
        check(isinstance(item, (tuple, list)) and len(item) == 3,
              f"GAMES 条目格式错误: {item!r}")
        name, sub, entry = item
        check(all(isinstance(v, str) and v for v in (name, sub, entry)),
              f"GAMES 条目存在空字段: {item!r}")
        subs.append(sub)
        entry_path = os.path.join(BASE_DIR, "games", sub, entry)
        check(os.path.isfile(entry_path), f"游戏入口不存在: {entry_path}")
    check(len(subs) == len(set(subs)), "GAMES 中存在重复目录")
    check(len({g[0] for g in games}) == len(games), "GAMES 中存在重复名称")


def check_ski_engine():
    """直接 import games/ski 的纯逻辑引擎（它只依赖标准库 + 本地 config）。"""
    ski_dir = os.path.join(BASE_DIR, "games", "ski")
    check(os.path.isdir(ski_dir), "缺少 games/ski 目录")
    sys.path.insert(0, ski_dir)
    import config as ski_config          # noqa: E402 - games/ski/config.py
    import engine as ski_engine          # noqa: E402 - games/ski/engine.py

    random.seed(20260826)
    game = ski_engine.GameEngine(ski_config.MODE_ENDLESS)
    game.start()
    check(game.game_started and not game.game_over, "start() 后游戏未进入运行态")
    check(len(game.obstacles) == 20, f"初始障碍物数量异常: {len(game.obstacles)}")

    snapshot = game.get_snapshot()
    required = {"skier_x", "skier_y", "score", "distance", "game_over", "paused"}
    check(required <= set(snapshot), "get_snapshot() 缺少关键字段")

    for _ in range(4):
        events = game.tick()
        check(isinstance(events, list), "tick() 未返回事件列表")
    check(game.distance == 2, f"4 帧后滑行距离异常: {game.distance}")
    game.turn(10)
    check(game.skier_direction == 2, "右转未夹到 +2")
    game.turn(-10)
    check(game.skier_direction == -2, "左转未夹到 -2")

    # 吃旗：+10 分且障碍物被移除
    flag_game = ski_engine.GameEngine(ski_config.MODE_ENDLESS)
    flag_game.start()
    flag_game.score = 0
    flag_game.obstacles = [[flag_game.skier_x, flag_game.skier_y, "flag", False]]
    events = flag_game.tick()
    check(("flag", flag_game.skier_x, flag_game.skier_y) in events,
          f"未产生吃旗事件: {events!r}")
    check(flag_game.score == 10, f"吃旗得分错误: {flag_game.score}")
    check(len(flag_game.obstacles) == 0, "吃掉的旗子未移除")

    # 撞树：-50 分
    tree_game = ski_engine.GameEngine(ski_config.MODE_ENDLESS)
    tree_game.start()
    tree_game.score = 0
    tree_game.obstacles = [[tree_game.skier_x, tree_game.skier_y, "tree", False]]
    events = tree_game.tick()
    check(("tree", tree_game.skier_x, tree_game.skier_y) in events,
          f"未产生撞树事件: {events!r}")
    check(tree_game.score == -50, f"撞树扣分错误: {tree_game.score}")

    # 分数过低：判定失败
    over_game = ski_engine.GameEngine(ski_config.MODE_ENDLESS)
    over_game.start()
    over_game.obstacles = []
    over_game.score = ski_config.GAME_OVER_SCORE - 1
    events = over_game.tick()
    check(over_game.game_over, "分数低于阈值未判定失败")
    check(over_game.death_reason == "score", f"失败原因错误: {over_game.death_reason}")
    check(("game_over", "score") in events, f"未产生 game_over 事件: {events!r}")
    return ski_config.MODE_ENDLESS


def check_calculator_selfcheck():
    """调用 games/calculator 自带的无头自检（独立仓收拢后，覆盖面并入本入口）。"""
    calc_dir = os.path.join(BASE_DIR, "games", "calculator")
    script = os.path.join(calc_dir, "selfcheck.py")
    check(os.path.isfile(script), f"缺少 calculator 自检脚本: {script}")
    proc = subprocess.run(
        [sys.executable, script],
        cwd=calc_dir,
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    check(proc.returncode == 0,
          f"calculator selfcheck 失败(exit {proc.returncode}): {(proc.stdout or '')[-300:]}")
    return (proc.stdout or "").strip().splitlines()[-1] if proc.stdout else ""


def main() -> int:
    try:
        games = load_games_manifest()
        check_manifest(games)
        mode = check_ski_engine()
        calc_note = check_calculator_selfcheck()
        print(
            f"selfcheck ok: 街机清单 {len(games)} 项与磁盘入口全部对应；"
            f"ASCII 滑雪引擎（{mode}）tick 推进 2 格距离、吃旗 +10、撞树 -50、"
            "低分 game_over 判定均正确；"
            f"calculator 自检通过（{calc_note}）"
        )
        return 0
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL: {type(exc).__name__}: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
