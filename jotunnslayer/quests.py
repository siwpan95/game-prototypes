# -*- coding: utf-8 -*-
"""局内限时任务（Phase 5）：歼灭 / 收集 / 守点。

任务时间线：首次 60s 触发，之后每 60-90s 一个，期限 40s。
完成奖励金币+经验爆发；失败仅扣时间无惩罚。任务计时随游戏暂停冻结
（update 只在 play 状态运行）。
"""
import math
import random

from settings import QUEST, COL


def spawn(game):
    kind = random.choice(("kill", "collect", "hold"))
    if kind == "kill":
        target = random.randint(*QUEST["kill_target"])
        label = f"歼灭 {target} 个敌人"
    elif kind == "collect":
        target = random.randint(*QUEST["collect_target"])
        label = f"拾取 {target} 颗宝石"
    else:
        target = float(QUEST["hold_target"])
        label = f"坚守阵地 {target:.0f} 秒"
    game.quest = dict(kind=kind, target=target, progress=0.0,
                      t_left=QUEST["duration"], label=label)
    if kind == "hold":
        p = game.player
        a = random.uniform(0, math.tau)
        d = random.uniform(260.0, 420.0)
        game.quest_hold = (p.x + math.cos(a) * d, p.y + math.sin(a) * d)
    game._floater(f"任务：{label}", COL["gold"], 22)
    game.bus.emit("quest_start", dict(kind=kind))


def tick(game, dt):
    if game.state != "play":
        return
    if game.quest is None and game.time >= game.next_quest_at:
        spawn(game)
    q = game.quest
    if q is None:
        return
    q["t_left"] -= dt
    if q["kind"] == "hold":
        hx, hy = game.quest_hold
        p = game.player
        if (p.x - hx) ** 2 + (p.y - hy) ** 2 <= QUEST["hold_radius"] ** 2:
            q["progress"] += dt
    if q["progress"] >= q["target"]:
        gold = random.randint(QUEST["gold_min"], QUEST["gold_max"])
        game.run_gold += gold
        game.gain_xp(QUEST["xp_reward"])
        game._floater(f"任务完成 +{gold}金", COL["gold"], 24)
        game.bus.emit("quest_done", dict(kind=q["kind"], gold=gold))
        game.quest = None
        game.next_quest_at = game.time + random.uniform(
            QUEST["interval_min"], QUEST["interval_max"])
    elif q["t_left"] <= 0:
        game._floater("任务失败", (150, 156, 170), 20)
        game.bus.emit("quest_failed", dict(kind=q["kind"]))
        game.quest = None
        game.next_quest_at = game.time + random.uniform(
            QUEST["interval_min"], QUEST["interval_max"])


def on_kill(game, e):
    q = game.quest
    if q and q["kind"] == "kill":
        q["progress"] += 1


def on_gems(game, n):
    q = game.quest
    if q and q["kind"] == "collect":
        q["progress"] += n
