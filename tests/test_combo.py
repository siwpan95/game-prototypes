# -*- coding: utf-8 -*-
"""定向验证：暗黑式连杀系统。

用法: python test_combo.py
覆盖：
1. 击杀累计连杀、刷新 4s 窗口、10 档浮动文字
2. 窗口关闭按档位结算经验（spy 记录 gain_xp 精确入参）
3. 25 档移速 buff 生效
4. 100 档金色冲击波真实伤害（近敌受伤、远敌无伤）
5. 超时断链归零
"""
import os
import sys

# 从项目根执行 python tests\xxx.py 时，把根目录加进 sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"

import pygame

from settings import DT
from entities import Enemy
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


g = M.Game(smoke=True)
g.state = "play"


def iso():
    """节间隔离：清场、复位连杀、满血。"""
    g.enemies.clear()
    g.gems.clear()
    g.floaters.clear()
    g.weapons.clear()                  # 拆掉武器：避免斧头自己杀人污染计数
    g.player.hp = g.player.hp_max
    g.player.x = g.player.y = 0.0
    g.combo = 0
    g.combo_t = 0.0
    g.speed_buff_t = 0.0
    g.state = "play"


def kill(n, hp=1):
    for _ in range(n):
        g._kill_rewards(Enemy("draugr", 0, 0, 1.0))


def spy_xp():
    """替换 gain_xp 为记录器，返回 (log, restore)。"""
    log = []
    orig = g.gain_xp

    def _spy(n):
        log.append(n)
    g.gain_xp = _spy
    return log, orig


# ---------- 1) 连杀累计 + 窗口刷新 + 档位文字 ----------
kill(12)
check("连杀：12 杀累计", g.combo == 12 and g.combo_best == 12)
check("连杀：10 档浮动文字", any("×10" in f[0] for f in g.floaters))

# ---------- 2) 结算：12 杀 = 18 经验（×1.0 档） ----------
iso()
kill(12)
g.gems.clear()                            # 隔离：只测结算路径，排除宝石拾取
log, orig = spy_xp()
g.combo_t = 0.0001
g.update(DT, 0, 0)
g.gain_xp = orig
check("连杀：结算给经验 18（≥10 档 ×1.0）", log == [18] and g.combo == 0)
check("连杀：结算浮动文字", any("结算" in f[0] for f in g.floaters))

# ---------- 3) 25 档移速 buff ----------
iso()
kill(25)
check("连杀：25 档疾行 buff", g.speed_buff_t > 0)
p0x = g.player.x
g.speed_buff_t = 1.0
g.update(DT, 1, 0)
dx_buff = g.player.x - p0x
g.player.x = 0.0
g.speed_buff_t = 0.0
g.update(DT, 1, 0)
dx_norm = g.player.x
check("连杀：疾行移速 +20%", dx_buff > dx_norm * 1.15)

# ---------- 4) 100 档冲击波 ----------
iso()
victim = Enemy("troll", 120.0, 0.0, 1.0)      # 玩家附近
far = Enemy("troll", 900.0, 0.0, 1.0)         # 冲击波范围外
g.enemies.extend([victim, far])
g.hash.clear()
g.hash.insert_many(g.enemies)
vh, fh = victim.hp, far.hp
kill(100)
check("连杀：100 档冲击波伤及近敌", victim.hp < vh)
check("连杀：冲击波不打远敌", far.hp == fh)
check("连杀：最佳连杀记录", g.combo_best == 100)

# ---------- 5) 结算档位倍率：100 杀 = 300 经验（×2.0） ----------
iso()
g.combo = 100
log, orig = spy_xp()
g._settle_combo()
g.gain_xp = orig
check("连杀：100 档 ×2 倍率（300 经验）", log == [300])
g.combo = 0

# ---------- 6) 超时断链归零 ----------
iso()
g.combo = 5
g.combo_t = 4.0
for _ in range(300):                       # 5 秒无击杀
    g.update(DT, 0, 0)
check("连杀：超时归零", g.combo == 0)

print("=" * 40)
if fails:
    print(f"COMBO_TEST_FAIL ({len(fails)}): " + "; ".join(fails))
    sys.exit(1)
print("COMBO_TEST_OK 全部通过")
sys.exit(0)
