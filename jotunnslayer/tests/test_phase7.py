# -*- coding: utf-8 -*-
"""定向验证：Phase 7 难度系数 / 无尽模式 / 新地图与机关。"""
import math
import os
import sys

# 从项目根执行 python tests\xxx.py 时，把根目录加进 sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import pygame

from settings import DT, DIFFICULTIES
from data import MAPS
from entities import Enemy
import main as M
import hazards

pygame.init()
pygame.display.init()
pygame.font.init()
screen = pygame.display.set_mode((320, 180))
M.init_globals()

# ---------- 1. 难度：敌人数值倍率 ----------
g = M.Game(smoke=True, map_key="snow")
g.difficulty_key = "insane"
g.spawn_enemy("draugr")
e = g.enemies[0]
assert e.hp_max == int(18 * DIFFICULTIES["insane"]["hp"])
assert abs(e.dmg - 8 * DIFFICULTIES["insane"]["dmg"]) < 1e-6
assert abs(e.speed - 55.0 * DIFFICULTIES["insane"]["speed"]) < 1e-6
print("PASS 难度：敌人 HP/伤害/速度倍率")

# ---------- 2. 难度：金币倍率 ----------
g2 = M.Game(smoke=True)
g2.difficulty_key = "hard"
g2._kill_rewards(Enemy("draugr", 0, 0, 1.0, elite=True))
assert g2.run_gold == int(50 * 1.5)
print("PASS 难度：精英金币 ×1.5")

# ---------- 3. 无尽：Boss 循环 + 不判胜 ----------
g3 = M.Game(smoke=True, map_key="snow")
g3.endless = True
g3.state = "play"
g3.next_boss_at = 0.0
g3.time = 1.0
g3.update(DT, 0, 0)
assert g3.boss is not None
g3.boss.hp = 0
g3.update(DT, 0, 0)
assert g3.state == "play" and not g3.victory and g3.boss is None
assert not g3.spawner.boss_sent
assert g3.next_boss_at > g3.time
print("PASS 无尽：Boss 击杀后继续 + 60s 后下一只")

# ---------- 4. 无尽：难度爬升 ----------
g4 = M.Game(smoke=True)
g4.endless = True
g4.time = 301.0
d = g4.diff()
assert abs(d["hp"] - 1.5) < 1e-6      # 1.0 * (1 + 0.5*1)
print("PASS 无尽：5 分钟难度 ×1.5 爬升")

# ---------- 5. 五张地图数据 ----------
assert len(MAPS) == 5
assert MAPS["mine"].get("carts") and MAPS["mine"]["boss"] == "jormungandr"
assert MAPS["temple"].get("pillar")
assert MAPS["hel"].get("geyser") and MAPS["hel"]["boss"] == "fenrir"
print("PASS 五张地图数据（含机关字段与专属 Boss）")

# ---------- 6. 矿车机关 ----------
g5 = M.Game(smoke=True, map_key="mine")
g5.state = "play"
g5.cart_t = -(MAPS["mine"]["carts"]["warn"] + 0.1)
hazards.tick(g5, DT)
assert len(g5.carts) == 1
c = g5.carts[0]
hp0 = g5.player.hp
g5.player.iframes = 0.0
c["x"], c["y"] = g5.player.x + 5, g5.player.y   # 直接压脸
hazards.tick(g5, DT)
assert g5.player.hp < hp0
print("PASS 矿车：预警后发车 + 撞伤玩家")

# ---------- 7. 神柱脉冲 ----------
g6 = M.Game(smoke=True, map_key="temple")
g6.state = "play"
g6.pillar_t = 0.0
hazards.tick(g6, DT)
assert g6.pillar_wave is not None
w = g6.pillar_wave
w["x"], w["y"] = g6.player.x + 100, g6.player.y   # 玩家在圈内
w["t"] = 0.4
x0, y0 = g6.player.x, g6.player.y
hazards.tick(g6, DT)
assert math.hypot(g6.player.x - x0, g6.player.y - y0) > 10.0
print("PASS 神柱：预警 -> 脉冲推人")

print("PHASE7_TEST_OK")
