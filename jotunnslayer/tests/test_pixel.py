# -*- coding: utf-8 -*-
"""定向验证：像素风精灵唯一性 / 宝箱怪 / 地图限定武器。"""
import os
import sys

# 从项目根执行 python tests\xxx.py 时，把根目录加进 sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import pygame

from data import ENEMIES, BOSSES, WEAPONS
from entities import Enemy, Chest
import pixel_art
import main as M

pygame.init()
pygame.display.init()
pygame.font.init()
screen = pygame.display.set_mode((320, 180))
M.init_globals()

# ---------- 1. 每敌型独立剪影（像素数据两两不同） ----------
sigs = {}
for key in ENEMIES:
    spr = pixel_art.bake_enemy_sprite(key, ENEMIES[key]["radius"])
    assert spr.get_width() > 0
    sig = pygame.image.tobytes(spr, "RGBA")
    for other, osig in sigs.items():
        assert sig != osig, f"{key} 与 {other} 的精灵完全相同"
    sigs[key] = sig
print(f"PASS 像素精灵：{len(sigs)} 敌型剪影两两不同")

# ---------- 2. Boss 独立剪影 ----------
bsigs = {}
for key in BOSSES:
    spr = pixel_art.bake_boss_sprite(key, BOSSES[key]["radius"])
    sig = pygame.image.tobytes(spr, "RGBA")
    for other, osig in bsigs.items():
        assert sig != osig, f"boss {key} 与 {other} 相同"
    bsigs[key] = sig
print("PASS Boss 像素剪影两两不同")

# ---------- 3. 宝箱怪：潜伏 -> 靠近惊醒 -> 击杀掉宝箱 ----------
g = M.Game(smoke=True)
g.state = "play"
m = Enemy("mimic", 300, 0, 1.0)
g.enemies.append(m)
g.hash.insert_many([m])
m.update(g, 1 / 60)
assert m.awake is False                      # 距离 300 > 220：继续潜伏
wakes = []
g.bus.subscribe("mimic_wake", lambda d: wakes.append(1))
g.player.x = 250.0
m.update(g, 1 / 60)
assert m.awake and wakes                      # 靠近惊醒 + 事件
print("PASS 宝箱怪：潜伏 / 靠近惊醒 / 事件")

# 受击惊醒
m2 = Enemy("mimic", 0, 0, 1.0)
assert m2.awake is False
g.deal_damage(m2, 1)
assert m2.awake
# 击杀掉宝箱
g.chests.clear()
m2.hp = 0
g._kill_rewards(m2)
assert len(g.chests) == 1 and isinstance(g.chests[0], Chest)
print("PASS 宝箱怪：受击惊醒 / 击杀必掉宝箱")

# ---------- 4. 地图限定武器卡池过滤 ----------
g2 = M.Game(smoke=True, map_key="snow")
ids = [c["id"] for c in g2.gen_cards() for _ in range(0)]  # 占位
all_ids = set()
for _ in range(60):
    for c in g2.gen_cards():
        all_ids.add(c["id"])
assert "new:dynamite" not in all_ids
g3 = M.Game(smoke=True, map_key="mine")
mine_ids = set()
for _ in range(60):
    for c in g3.gen_cards():
        mine_ids.add(c["id"])
assert "new:dynamite" in mine_ids
assert all("map_only" in WEAPONS[w] for w in ("dynamite", "sun_hammer", "helfire"))
print("PASS 地图限定武器：矿坑出炸药桶 / 雪原不出")

# ---------- 5. 炸药桶 AOE ----------
g4 = M.Game(smoke=True, map_key="mine")
g4.state = "play"
v1 = Enemy("draugr", 40, 0, 1.0)
v2 = Enemy("draugr", 200, 0, 1.0)
g4.enemies += [v1, v2]
g4._boom_explode(0, 0, 30, 110)
assert v1.hp < v1.hp_max and v2.hp == v2.hp_max     # 圈内伤 / 圈外无恙
print("PASS 炸药桶：AOE 圈内通伤")

# ---------- 6. 冥界余烬吸血 ----------
from weapons import _pulse_at
g5 = M.Game(smoke=True, map_key="hel")
g5.state = "play"
v = Enemy("draugr", 30, 0, 1.0)
g5.enemies.append(v)
g5.hash.insert_many([v])
g5.player.hp = 50
st = dict(radius=130.0, damage=13, size=0, lifesteal=2)
_pulse_at(g5, st, g5.player.x, g5.player.y, (200, 100, 60))
assert v.hp < v.hp_max and g5.player.hp > 50
print("PASS 冥界余烬：脉冲吸血")

print("PIXEL_TEST_OK")
