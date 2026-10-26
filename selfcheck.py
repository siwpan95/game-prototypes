#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""sandbox 无头自检：视野（阴影投射）+ 距离场寻路 + 成长曲线（不 import tkinter/game）。

``run.py`` / ``gui.py`` / ``game.py`` 会建控制台或 tkinter 窗口；本自检只取纯逻辑模块：

1. ``fov.py``：递归阴影投射——半径约束、墙角遮挡（墙后不漏光）、墙格本身可见；
2. ``pathfinding.py``：Dijkstra 距离场 / 下坡寻路 / 视线判定——开阔地步数、
   墙后不可达、留门可达、下坡逐步收敛到目标；
3. ``progression.py``：经验曲线单调、perk 聚合可叠加、三选一互不重复。

这些模块只依赖标准库（fov/pathfinding/progression 均不 import alloy/procgen）。
"""
from __future__ import annotations

import random
import sys
from pathlib import Path

sys.dont_write_bytecode = True          # 不在项目里留 .pyc
try:
    sys.stdout.reconfigure(errors="replace")
except Exception:
    pass

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))


class CheckError(RuntimeError):
    pass


def check(condition, message):
    if not condition:
        raise CheckError(message)


def check_fov(fov_module):
    width = height = 12
    origin_x, origin_y, radius = 5, 5, 4

    visible = fov_module.compute_fov(origin_x, origin_y, radius,
                                     lambda x, y: False, width, height)
    check((origin_x, origin_y) in visible, "视野不包含观察者自身")
    check((7, 5) in visible, "开阔地半径内格子不可见")
    check((9, 5) not in visible, "视野超出半径仍可见")
    for x, y in visible:
        distance_sq = (x - origin_x) ** 2 + (y - origin_y) ** 2
        check(distance_sq < radius * radius,
              f"可见格超出半径：{(x, y)} dist2={distance_sq}")

    # 竖墙 x=6 完全遮挡：墙格自身可见，墙后一格不漏光。
    walls = {(6, y) for y in range(height)}
    blocked = lambda x, y: (x, y) in walls      # noqa: E731 - 小函数无需命名
    visible = fov_module.compute_fov(3, 6, 6, blocked, width, height)
    check((6, 6) in visible, "墙格自身应被照亮")
    check((7, 6) not in visible, "墙后格子仍可见（视野漏光）")
    check(all(x <= 6 for x, _y in visible), "视线穿过了整列墙")


def check_pathfinding(pathfinding_module):
    width = height = 10
    dist = pathfinding_module.compute_dijkstra(1, 1, lambda x, y: True, width, height)
    check(dist[1][1] == 0, "目标点距离不是 0")
    check(dist[5][5] == 8, f"开阔地 (5,5)->(1,1) 步数错误：{dist[5][5]}")

    x, y, steps = 5, 5, 0
    previous = dist[y][x]
    while (x, y) != (1, 1) and steps < 20:
        direction = pathfinding_module.step_downhill(x, y, dist, width, height, set())
        check(direction is not None, f"下坡寻路在 {(x, y)} 处卡住")
        x, y = x + direction[0], y + direction[1]
        steps += 1
        current = dist[y][x]
        check(current == previous - 1,
              f"下坡未逐步收敛：{previous} -> {current} at {(x, y)}")
        previous = current
    check((x, y) == (1, 1), f"下坡寻路未到达目标：{(x, y)}")
    check(steps == 8, f"下坡路径长度错误：{steps}")

    # 整列墙 x=5 完全阻断 -> 左侧到右侧目标不可达。
    sealed = lambda x, y: x != 5                # noqa: E731
    dist = pathfinding_module.compute_dijkstra(9, 9, sealed, width, height)
    check(dist[0][0] == pathfinding_module.UNREACHABLE, "被墙隔断的区域仍标记为可达")
    check(dist[9][9] == 0, "目标点自身距离不是 0")

    # 留一个门 (5,5) -> 必须绕经门：Manhattan 10 + 8 = 18 步。
    door = lambda x, y: not (x == 5 and y != 5)  # noqa: E731
    dist = pathfinding_module.compute_dijkstra(9, 9, door, width, height)
    check(dist[0][0] == 18, f"留门后最短路步数错误：{dist[0][0]}")
    check(dist[5][5] == 8, f"门格到目标步数错误：{dist[5][5]}")

    # 视线：中间有墙 -> 遮挡；末端是墙 -> 端点不计遮挡。
    check(pathfinding_module.clear_los(0, 0, 4, 0, lambda x, y: False), "空旷直线视线被拦")
    check(not pathfinding_module.clear_los(0, 0, 4, 0, lambda x, y: (x, y) == (2, 0)),
          "中间墙未遮挡视线")
    check(pathfinding_module.clear_los(0, 0, 4, 0, lambda x, y: (x, y) == (4, 0)),
          "视线终点自身的墙不应算遮挡")


def check_progression(progression_module):
    first = progression_module.xp_for_level(1)
    later = progression_module.xp_for_level(5)
    check(first > 0 and later > first, f"经验曲线非单调：{first} -> {later}")

    mods = progression_module.compute_perk_mods(["strength", "toughness", "strength"])
    check(mods == {"attack": 4, "defense": 1},
          f"perk 聚合/叠加错误：{mods!r}")
    check(progression_module.compute_perk_mods(["no-such-perk"]) == {},
          "未知 perk 不应产生加成")

    picks = progression_module.roll_perk_choices(random.Random(11), 3)
    check(len(picks) == 3, f"三选一选项数量错误：{len(picks)}")
    check(len({perk["id"] for perk in picks}) == 3, "三选一出现重复选项")


def main():
    import fov
    import pathfinding
    import progression

    check_fov(fov)
    check_pathfinding(pathfinding)
    check_progression(progression)
    print(
        "selfcheck ok: FOV (radius, wall occlusion, no light leak) + Dijkstra map "
        "(8-step downhill path, sealed=UNREACHABLE, door=18 steps, LOS) + perk aggregation"
    )


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # noqa: BLE001 - 自检入口需要把任何失败转成 FAIL + 退出码 1
        print(f"FAIL: {type(exc).__name__}: {exc}")
        raise SystemExit(1)
