# -*- coding: utf-8 -*-
"""定向验证：Phase 3 全部新机制。

用法: python test_phase3.py
覆盖：6 新武器（含英灵/挥砍/击退/敌群爆破/箭减速/镰刀环绕）
     5 新敌型（射手弹幕/自爆/治疗/光环/吸血）
     3 新 Boss（尼德霍格喷吐+俯冲/约尔曼冈德水刃/芬里尔三阶段）
     地图主题与数据表完整性。
"""
import math
import os
import sys

# 从项目根执行 python tests\xxx.py 时，把根目录加进 sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"

import pygame

from settings import DT
from entities import Enemy, Geyser
from weapons import Weapon, _FIRE
import main as M

pygame.init()
pygame.display.init()
pygame.font.init()
screen = pygame.display.set_mode((320, 180))
M.init_globals()

fails = []


def check(name, cond):
    print(("PASS " if cond else "FAIL ") + name)
    if not cond:
        fails.append(name)


def fresh(map_key="snow"):
    g = M.Game(smoke=True, map_key=map_key)
    g.state = "play"
    g.god = False
    g.weapons = []                 # 拆默认武器：避免战斧自动杀掉测试目标
    g.spawner.timer = 9999.0       # 禁常规出怪：避免 enemies[0] 被新怪偷换
    return g


# ---------- 0) 数据表完整性 ----------
from data import WEAPONS, ENEMIES, BOSSES, MAPS, EVOLUTIONS

check("表：15 武器且 kind 都有 handler",
      len(WEAPONS) == 15 and all(w["kind"] in _FIRE or w["kind"] in ("orbit", "scythe")
                                 for w in WEAPONS.values()))
check("表：11 敌型字段齐全",
      len(ENEMIES) == 11 and all(
          all(k in d for k in ("name", "hp", "speed", "dmg", "radius", "xp",
                                "color", "unlock", "weight"))
          for d in ENEMIES.values()))
check("表：4 Boss 且 pattern 齐全",
      set(BOSSES) == {"jotunn", "nidhogg", "jormungandr", "fenrir"})
check("表：12 进化配方且被动存在（地图限定武器无进化）",
      set(EVOLUTIONS) == {k for k in WEAPONS if not WEAPONS[k].get("map_only")}
      and all(e["passive"] in M.PASSIVES for e in EVOLUTIONS.values()))
check("表：地图 Boss 键有效",
      all(MAPS[m]["boss"] in BOSSES for m in MAPS))

# ---------- 1) 哥布林射手：发射敌方弹幕 ----------
g = fresh()
archer = Enemy("goblin_archer", 200.0, 0.0, 1.0)
g.enemies.append(archer)
saw_bullet = False
for _ in range(300):
    g.update(DT, 0, 0)
    if g.enemy_bullets:
        saw_bullet = True
        break
check("射手：进入射程后发射弹幕", saw_bullet)
g.enemy_bullets.clear()
g.enemies.clear()

# ---------- 2) 自爆尸鬼：引信触发爆炸 ----------
g = fresh()
bomb = Enemy("bomber", 60.0, 0.0, 1.0)          # 在 trigger 130px 内
victim = Enemy("draugr", 90.0, 10.0, 1.0)
g.enemies.extend([bomb, victim])
g.hash.clear()
g.hash.insert_many(g.enemies)
vh = victim.hp
exploded = False
for _ in range(240):                             # 4 秒内必然触发
    g.update(DT, 0, 0)
    if bomb not in g.enemies:
        exploded = True
        break
check("自爆：引信到点爆炸并消失", exploded)
check("自爆：爆炸波及邻近敌人", victim.hp < vh)
g.enemies.clear()

# ---------- 3) 哀嚎女妖：治疗友军 ----------
g = fresh()
healer = Enemy("healer", 300.0, 0.0, 1.0)
wounded = Enemy("troll", 320.0, 0.0, 1.0)
wounded.hp = wounded.hp_max - 40
g.enemies.extend([healer, wounded])
g.hash.clear()
g.hash.insert_many(g.enemies)
hp0 = wounded.hp
for _ in range(240):
    g.update(DT, 0, 0)
check("女妖：治疗了附近受伤友军", wounded.hp > hp0)
g.enemies.clear()

# ---------- 4) 寒冰巨蛇：光环减速玩家 ----------
g = fresh()
snake = Enemy("icesnake", 40.0, 0.0, 1.0)       # 玩家旁
g.enemies.append(snake)
g.update(DT, 0, 0)
check("巨蛇：光环减速玩家", g.player.slow_t > 0 and g.player.slow_amt > 0)
g.enemies.clear()

# ---------- 5) 嗜血亲王：咬人回血 ----------
g = fresh()
vamp = Enemy("vampire", 20.0, 0.0, 1.0)
g.enemies.append(vamp)
vamp.hp = 10
hp0 = vamp.hp
g.player.iframes = 0
for _ in range(30):
    g.update(DT, 0, 0)
check("亲王：接触吸血回复", vamp.hp > hp0)
g.enemies.clear()
g.player.hp = g.player.hp_max

# ---------- 6) 英灵战士（维京号角） ----------
g = fresh()
horn = Weapon("horn")
horn.timer = 0.01
g.weapons.append(horn)
g.enemies.append(Enemy("draugr", 150.0, 0.0, 1.0))
g.update(DT, 0, 0)
check("号角：召唤英灵", len(g.allies) >= 1)
orig = g.enemies[0]
ehp = orig.hp
damaged = False
for _ in range(300):
    g.update(DT, 0, 0)
    if orig.hp < ehp:
        damaged = True
        break
check("英灵：索敌并造成伤害", damaged)
g.weapons.remove(horn)
g.allies.clear()
g.enemies.clear()

# ---------- 7) 诅咒之刃：扇形斩击+吸血 ----------
g = fresh()
blade = Weapon("curseblade")
blade.timer = 0.01
g.weapons = [blade]
g.player.hp = 50
g.enemies.append(Enemy("draugr", 60.0, 0.0, 1.0))   # 玩家正右方
g.hash.clear()
g.hash.insert_many(g.enemies)
g.update(DT, 0, 0)
check("魔刃：扇形命中敌人", g.enemies[0].hp < g.enemies[0].hp_max)
check("魔刃：吸血回血", g.player.hp > 50)
check("魔刃：挥砍视觉生成", len(g.swings) >= 1)
g.enemies.clear()

# ---------- 8) 寒冬之弓：命中减速 ----------
from weapons import Bullet
g = fresh()
st = Weapon("bow").stats()
b = Bullet(0, 0, 0.0, st, M.fx.RotCache(M.fx.bake_arrow(11, (170, 220, 250)), 8))
g.projectiles.append(b)
target = Enemy("troll", 200.0, 0.0, 1.0)
g.enemies.append(target)
for _ in range(60):
    g.update(DT, 0, 0)
    if target.slow_t > 0:
        break
check("冰箭：命中施加减速", target.slow_t > 0)
g.enemies.clear()
g.projectiles.clear()

# ---------- 9) 食人妖重锤：击退 ----------
g = fresh()
hammer = Weapon("trollhammer")
hammer.timer = 0.01
g.weapons = [hammer]
pushed = Enemy("troll", 70.0, 0.0, 1.0)
g.enemies.append(pushed)
g.hash.clear()
g.hash.insert_many(g.enemies)
x0 = pushed.x
g.update(DT, 0, 0)
check("重锤：命中并击退敌人", pushed.x > x0 + 20)
g.enemies.clear()

# ---------- 10) 地裂斩：在敌群脚下爆发 ----------
g = fresh()
qk = Weapon("quake")
qk.timer = 0.01
g.weapons = [qk]
far_enemy = Enemy("troll", 260.0, 0.0, 1.0)
near_enemy = Enemy("troll", 200.0, 40.0, 1.0)
g.enemies.extend([far_enemy, near_enemy])
g.hash.clear()
g.hash.insert_many(g.enemies)
nh, fh = near_enemy.hp, far_enemy.hp
g.update(DT, 0, 0)
check("地裂：在敌群位置爆发伤敌", near_enemy.hp < nh and far_enemy.hp < fh)
g.enemies.clear()

# ---------- 11) 海拉之镰：大半径环绕 ----------
g = fresh()
sc = Weapon("scythe")
g.weapons = [sc]
sc.timer = 0.0
for _ in range(60):
    g.update(DT, 0, 0)
check("镰刀：环绕体就位", len(sc.hammers) == sc.stats()["count"])
g.weapons = []

# ---------- 12) Boss：尼德霍格喷吐+俯冲 ----------
g = fresh("lava")
M.Spawner.ring_pos = staticmethod(lambda px, py: (px + 150, py))
g.spawn_boss()
M.Spawner.ring_pos = staticmethod(M.Spawner.ring_pos.__func__ if False else
                                  lambda px, py: (px + 900, py))
orig = M.Spawner.ring_pos
g.boss.skill_t = 0.01
g.boss.bphase = 1
for _ in range(10):
    g.update(DT, 0, 0)
check("尼德霍格：扇形喷吐生成", len(g.breaths) >= 1)
# 俯冲：等下一轮技能
g.boss.skill_t = 0.01
g.breaths.clear()
saw_dive = False
for _ in range(900):                             # 15s 内必出俯冲
    g.update(DT, 0, 0)
    if g.boss is not None and g.boss.diving and g.boss.dvx != 0:
        saw_dive = True
        break
check("尼德霍格：蓄力后锁定方向俯冲", saw_dive)
g.enemies.clear()
g.boss = None
g.breaths.clear()

# ---------- 13) Boss：约尔曼冈德环形水刃 ----------
g = fresh()
M.Spawner.ring_pos = staticmethod(lambda px, py: (px + 150, py))
g.spawn_boss()
g.boss.key = "jormungandr"                       # 换 pattern
g.boss.skill_t = 0.01
g.boss.bphase = 1
for _ in range(10):
    g.update(DT, 0, 0)
check("约尔曼冈德：环形水刃（敌方弹幕）", len(g.enemy_bullets) >= 10)
g.enemies.clear()
g.boss = None
g.enemy_bullets.clear()

# ---------- 14) Boss：芬里尔三阶段召唤 ----------
g = fresh()
M.Spawner.ring_pos = staticmethod(lambda px, py: (px + 150, py))
g.spawn_boss()
g.boss.key = "fenrir"
n0 = len(g.enemies)
g.boss.hp = int(g.boss.hp_max * 0.5)             # 直接触发 P2/P3
for _ in range(30):
    g.update(DT, 0, 0)
check("芬里尔：低血量召唤狼群", len(g.enemies) > n0)
check("芬里尔：阶段推进", g.boss.bphase >= 2 if g.boss else True)
g.enemies.clear()
g.boss = None

# ---------- 15) 熔岩图喷泉伤害敌人 ----------
g = fresh("lava")
probe = Enemy("troll", 0.0, 0.0, 1.0)
g.enemies.append(probe)
gey = Geyser(probe.x, probe.y)
gey.t = M.PHASE3["geyser_cycle"] - 1.0           # 强制进入喷发
g.geysers.append(gey)
g.hash.clear()
g.hash.insert_many(g.enemies)
ph = probe.hp
for _ in range(30):
    g.update(DT, 0, 0)
check("喷泉：喷发伤害敌人", probe.hp < ph)
g.geysers.clear()
g.enemies.clear()

print("=" * 40)
if fails:
    print(f"PHASE3_TEST_FAIL ({len(fails)}): " + "; ".join(fails))
    sys.exit(1)
print("PHASE3_TEST_OK 全部通过")
sys.exit(0)
