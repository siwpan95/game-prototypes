# -*- coding: utf-8 -*-
"""定向验证：Phase 4 角色系统 + Q 键主动技。"""
import math
import os
import sys

# 从项目根执行 python tests\xxx.py 时，把根目录加进 sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import pygame

from entities import Enemy
import main as M

pygame.init()
pygame.display.init()
pygame.font.init()
screen = pygame.display.set_mode((320, 180))
M.init_globals()

# ---------- 1. 角色配置 ----------
g = M.Game(smoke=True, char_key="seeress")
assert g.skill_cfg["kind"] == "icespear"
assert g.weapons[0].key == "rune_ring"
assert g.player.hp_max == 90
print("PASS 角色配置（战巫：卢恩法阵 / HP90 / 冰锥）")

# ---------- 2. 冰锥：锁定最强敌 + 减速字段 + 冷却 ----------
g.state = "play"
e1 = Enemy("troll", 300, 0, 1.0)      # hp95 最强，在 +x 方向
e2 = Enemy("wolf", -300, 0, 1.0)
g.enemies += [e1, e2]
g.cast_skill()
assert g.skill_t > 0
assert len(g.projectiles) == 1
b = g.projectiles[0]
assert b.damage == 60 and b.slow_amt == 0.5 and b.vx > 0
print("PASS 冰锥：锁定最强敌 / 减速字段 / 冷却启动")

# ---------- 3. 冷却拦截 ----------
n = len(g.projectiles)
g.cast_skill()
assert len(g.projectiles) == n
print("PASS 冷却期间拦截重复施放")

# ---------- 4. 狂暴：攻速 +30% / 受伤 +20% ----------
g2 = M.Game(smoke=True, char_key="berserker")
g2.state = "play"
assert abs(g2.player.cooldown_mult() - 1.0) < 1e-6
g2.cast_skill()
assert g2.player.berserk_t > 0
assert abs(g2.player.cooldown_mult() - 0.7) < 1e-6
hp0 = g2.player.hp
g2.player.hurt(10)
assert abs(g2.player.hp - (hp0 - 12)) < 1e-6
print("PASS 狂暴：冷却×0.7 / 受伤×1.2")

# ---------- 5. 盾击：位移 + 击晕 + 伤害 ----------
g3 = M.Game(smoke=True, char_key="warden")
g3.state = "play"
x0, y0 = g3.player.x, g3.player.y
victim = Enemy("draugr", g3.player.x + 60, g3.player.y, 1.0)
g3.enemies.append(victim)
g3.cast_skill()
assert math.hypot(g3.player.x - x0, g3.player.y - y0) > 200.0
assert victim.slow_t > 0 and victim.hp < victim.hp_max
print("PASS 盾击：位移 / 击晕 / 伤害")

# ---------- 6. 冷却与全局 CDR 联动 ----------
g4 = M.Game(smoke=True, char_key="warden")
g4.state = "play"
base_cd = g4.skill_cfg["cooldown"]
g4.boons.add("heimdall", "horn", 1.0)          # 加拉尔号角 5% CDR
g4.cast_skill()
assert abs(g4.skill_t - base_cd * g4.cdr_mult()) < 1e-6
print("PASS 技能冷却吃全局 CDR（赐福联动）")

# ---------- 7. 事件：skill_cast ----------
seen = []
g4.bus.subscribe("skill_cast", lambda d: seen.append(d["kind"]))
g4.skill_t = 0.0
g4.cast_skill()
assert seen == ["shieldbash"]
print("PASS skill_cast 事件发布")

print("PHASE4_TEST_OK")
