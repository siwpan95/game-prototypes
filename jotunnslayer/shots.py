# -*- coding: utf-8 -*-
"""无头渲染截图：主菜单/战斗/升级/赐福/星图/Boss/熔岩/角色/地图/设置/统计。

输出到 shots/ 目录，运行：python shots.py
"""
import os

SHOT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "shots")
os.makedirs(SHOT_DIR, exist_ok=True)

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"

import pygame

from settings import WIDTH, HEIGHT, DT
from weapons import Weapon
from entities import Gem
import main as M
import ui

pygame.init()
pygame.display.init()
pygame.font.init()
screen = pygame.display.set_mode((WIDTH, HEIGHT))
M.init_globals()


def save(name):
    pygame.image.save(screen, os.path.join(SHOT_DIR, name))


g = M.Game(smoke=True)
g.god = True

# ---- 1) 主菜单 ----
g.draw_world(screen)
ui.draw_menu(screen, g)
save("shot_title.png")

# ---- 2) 战斗（武器成长 + 尸潮 + 赐福） ----
g.state = "play"
for key in ("axe", "mjolnir", "raven"):
    w = Weapon(key)
    w.level = 3
    g.weapons.append(w)
g.weapons[0].level = 5
g.weapons[0].evolved = True                      # 展示进化形态（血怒旋斧）
for _ in range(3):
    g.player.add_passive("might")
    g.player.add_passive("vigor")
g.player.hp = g.player.hp_max
for god, key, rm in (("odin", "ravens_eye", 1.0), ("odin", "sage_blood", 1.7),
                     ("thor", "chain_light", 1.0), ("freya", "life_spring", 2.6),
                     ("freya", "love_ward", 1.7), ("freya", "fragrant_wind", 1.0)):
    g.boons.add(god, key, rm)
for kind in ("draugr", "wolf", "troll", "wraith"):
    for _ in range(9):
        g.spawn_enemy(kind)
for _ in range(6):
    g.gems.append(Gem(g.player.x + 60 - _ * 10, g.player.y - 40, 2))
for _ in range(60):
    g.update(DT, 1, 0)
g.draw_world(screen)
ui.draw_hud(screen, g)
save("shot_battle.png")

# ---- 3) 升级三选一 ----
g.pending_cards = 1
g.open_cards()
g.draw_world(screen)
ui.draw_hud(screen, g)
ui.draw_upgrade(screen, g, g.cards, -1, g.chosen)
save("shot_upgrade.png")

# ---- 4) 赐福选卡 ----
g.state = "play"
g.spawn_shrine()
g.open_boon(g.shrines[0])
g.draw_world(screen)
ui.draw_hud(screen, g)
ui.draw_boon(screen, g)
save("shot_boon.png")

# ---- 5) 命运星图 ----
ui.draw_tree(screen, g)
save("shot_tree.png")

# ---- 6) Boss 战 ----
g.state = "play"
g.enemies.clear()
g.boss = None
g.spawn_boss()
for _ in range(30):
    g.update(DT, 1, 0)
g.draw_world(screen)
ui.draw_hud(screen, g)
save("shot_boss.png")

# ---- 7) 熔岩废土（喷泉 + 黑龙） ----
g2 = M.Game(smoke=True, map_key="lava")
g2.state = "play"
g2.god = True
g2.player.hp = g2.player.hp_max
for _ in range(60 * 75):                 # 模拟 75 秒（哥布林/自爆已解锁）
    g2.update(DT, 1, 0)
orig_ring = M.Spawner.ring_pos
M.Spawner.ring_pos = staticmethod(lambda px, py: (px + 240, py - 80))
g2.spawn_boss()                          # 尼德霍格
M.Spawner.ring_pos = orig_ring
for _ in range(60 * 4):
    g2.update(DT, -1, 0)
g2.draw_world(screen)
ui.draw_hud(screen, g2)
save("shot_lava.png")

# ---- 8) 角色选择 / 9) 地图选择 / 10) 设置 / 11) 最高分 ----
g3 = M.Game(smoke=True)
g3.draw_world(screen)
ui.draw_charsel(screen, g3)
save("shot_charsel.png")
g3.draw_world(screen)
ui.draw_mapsel(screen, g3)
save("shot_mapsel.png")
g3.draw_world(screen)
ui.draw_settings(screen, g3)
save("shot_settings.png")
g3.draw_world(screen)
ui.draw_stats(screen, g3)
save("shot_stats.png")

print("SHOTS_OK")
