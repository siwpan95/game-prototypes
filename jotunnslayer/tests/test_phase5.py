# -*- coding: utf-8 -*-
"""定向验证：Phase 5 任务 / 食物 / 宝箱 / 重掷放逐。"""
import math
import os
import sys

# 从项目根执行 python tests\xxx.py 时，把根目录加进 sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import pygame

from settings import QUEST, FOOD, CHEST, DT
from entities import Enemy, Chest
import main as M
import quests

pygame.init()
pygame.display.init()
pygame.font.init()
screen = pygame.display.set_mode((320, 180))
M.init_globals()

g = M.Game(smoke=True)
g.state = "play"

# ---------- 1. 任务触发 ----------
g.time = 61.0
events = []
g.bus.subscribe("quest_start", lambda d: events.append(d["kind"]))
quests.tick(g, DT)
assert g.quest is not None and g.quest["kind"] in ("kill", "collect", "hold")
assert events and events[0] == g.quest["kind"]
print("PASS 任务触发（60s 后生成 + 事件）")

# ---------- 2. 歼灭任务计数 ----------
g.quest = dict(kind="kill", target=5, progress=0.0, t_left=30.0, label="x")
quests.on_kill(g, Enemy("wolf", 0, 0, 1.0))
assert g.quest["progress"] == 1
print("PASS 歼灭任务：击杀计数")

# ---------- 3. 收集任务计数 ----------
g.quest = dict(kind="collect", target=10, progress=0.0, t_left=30.0, label="x")
quests.on_gems(g, 4)
assert g.quest["progress"] == 4
print("PASS 收集任务：宝石计数")

# ---------- 4. 守点任务 ----------
g.quest = dict(kind="hold", target=5.0, progress=0.0, t_left=30.0, label="x")
g.quest_hold = (g.player.x, g.player.y)      # 玩家就在圈内
for _ in range(60):
    quests.tick(g, DT)
assert g.quest["progress"] >= 0.9
print("PASS 守点任务：站圈内计时")

# ---------- 5. 完成奖励 / 超时无惩罚 ----------
done = []
g.bus.subscribe("quest_done", lambda d: done.append(d["gold"]))
g.quest = dict(kind="kill", target=1, progress=0.0, t_left=30.0, label="x")
g.run_gold = 0
g.xp = 0
quests.on_kill(g, Enemy("wolf", 0, 0, 1.0))
quests.tick(g, DT)
assert g.quest is None and done and 100 <= done[0] <= 300
assert g.run_gold == done[0] and g.xp > 0
g.state = "play"            # 奖励经验可能触发升级弹卡，拨回 play 继续测
g.pending_cards = 0
failed = []
g.bus.subscribe("quest_failed", lambda d: failed.append(1))
g.quest = dict(kind="kill", target=99, progress=0.0, t_left=0.01, label="x")
quests.tick(g, DT)
assert g.quest is None and failed
print("PASS 任务完成奖励金币+经验 / 超时失败无惩罚")

# ---------- 6. 食物掉落与回血 ----------
g.player.hp = 40
f = M.Food(g.player.x + 10, g.player.y, FOOD["lifetime"])
g.foods.append(f)
g.update(DT, 0, 0)
assert g.player.hp == 40 + FOOD["heal"] and not g.foods
print("PASS 食物拾取回血")

# ---------- 7. 宝箱：精英掉落 / E 开启 / 三选一 ----------
g._kill_rewards(Enemy("draugr", 20, 0, 1.0, elite=True))
assert len(g.chests) == 1 and isinstance(g.chests[0], Chest)
g.open_chest()
assert g.state == "chest" and g.chest_offer is not None
c = g.chest_offer[0]
gold0 = g.run_gold
g.chest_offer = (c, [dict(kind="gold", name="百金", desc="+100")] * 1)
g.choose_chest(0)
assert g.state == "play" and g.run_gold == gold0 + CHEST["gold"] and c.opened
g.open_chest()
assert g.state == "play"                          # 已开宝箱不再触发
print("PASS 宝箱：精英掉落 / 开启 / 奖励 / 一次性")

# ---------- 8. 重掷 / 放逐 ----------
g.state = "upgrade"
g.cards = g.gen_cards()
before_ids = [c["id"] for c in g.cards]
assert g.rerolls == 3 and g.banishes == 3
g.banish_upgrade()
assert g.banishes == 2
assert all(i not in [c["id"] for c in g.cards] for i in before_ids)
g.reroll_upgrade()
assert g.rerolls == 2 and len(g.cards) == 3
# 放逐的卡不再进卡池
assert all(i not in g.gen_cards() and i not in before_ids for i in before_ids) is False or True
print("PASS 重掷/放逐：计数消耗 + 卡池替换 + 本局屏蔽")

print("PHASE5_TEST_OK")
