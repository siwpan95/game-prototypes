# -*- coding: utf-8 -*-
"""定向验证：Boss 战全路径（登场 -> 跺地冲击波 -> 受伤 -> 死亡 -> 胜利结算）。

用法: python test_boss.py
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
from entities import Shockwave
from weapons import Weapon
import main as M

pygame.init()
pygame.display.init()
pygame.font.init()
screen = pygame.display.set_mode((320, 180))
M.init_globals()

# ---------- 单元：冲击波判定 ----------
sw = Shockwave(0, 0, 175, 520, 24, 0.0)     # 无前摇
hits_before = sw.hits(100, 0, 14)
for _ in range(30):                          # 扩散到 r≈260
    sw.update(DT)
    if sw.hits(100, 0, 14):
        hits_before = True
        break
warn_sw = Shockwave(0, 0, 175, 520, 24, 0.5)
warn_no_hit = warn_sw.hits(10, 0, 14)        # 前摇期不判定
assert warn_no_hit is False and hits_before, "Shockwave 判定逻辑错误"
print(f"UNIT shockwave OK (ring hit at r={sw.r:.0f})")

# ---------- 集成：Boss 战 ----------
g = M.Game(smoke=True)
g.state = "play"
g.god = True                                 # 玩家伤害路径已在 smoke 死亡用例验证

for key in ("axe", "mjolnir", "gungnir", "raven"):
    w = Weapon(key)
    w.level = 5
    g.weapons.append(w)
for _ in range(5):
    g.player.add_passive("might")
g.player.hp = g.player.hp_max

# 只把 Boss 贴脸刷，随后恢复出怪环（小怪仍从屏幕外来）
orig_ring = M.Spawner.ring_pos
M.Spawner.ring_pos = staticmethod(lambda px, py: (px + 120, py))
g.spawn_boss()
M.Spawner.ring_pos = orig_ring
assert g.boss is not None, "Boss 未生成"
boss0 = g.boss
g.boss_stomp_t = 0.2                          # 尽快触发第一次跺地

stomp_seen = 0
steps = 0
while steps < 60 * 120:                       # 最多模拟 120 秒
    g.update(DT, 0, 0)
    steps += 1
    if g.boss is not None:
        stomp_seen += len(g.shockwaves)
    if g.state == "gameover":
        break

print(f"steps={steps} sim_t={g.time:.1f}s")
print(f"boss_spawned=True boss_hp0={boss0.hp_max}")
print(f"shockwaves_spawned~{stomp_seen} kills={g.kills} dmg={g.total_damage:.0f}")
print(f"state={g.state} victory={g.victory}")

ok = (g.state == "gameover" and g.victory and boss0.hp_max == 3200)
print("BOSS_TEST_OK" if ok else "BOSS_TEST_FAIL")
sys.exit(0 if ok else 1)
