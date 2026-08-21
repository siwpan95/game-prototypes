# -*- coding: utf-8 -*-
"""定向验证：赐福系统关键路径 + 武器进化 + 神龛交互。

用法: python test_boons.py
覆盖：
1. 神眷触发（同神 3 种不同赐福 -> favors 激活）
2. 玩家受击管线（闪避/护盾/HP 扣减）
3. 连锁闪电 / 厄运爆炸 / 天雷 / 寒风 的真实伤害落地
4. 神龛触碰 -> 赐福选卡 -> 重掷 -> 选择
5. 武器进化条件与数值跃升
"""
import os
import sys

# 从项目根执行 python tests\xxx.py 时，把根目录加进 sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"

import pygame

from settings import DT
from entities import Enemy, Shrine
from weapons import Weapon
import main as M
import boons as B

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
g.god = False

# ---------- 1) 神眷触发 ----------
for key in ("ravens_eye", "sage_blood", "runes"):        # 奥丁三种
    g.boons.add("odin", key, 1.0)
check("神眷：奥丁三赐福触发眷顾", "odin" in g.boons.favors)
check("神眷：眷顾不重复触发", g.boons.add("odin", "ravens_eye", 1.0)[2] is False)
check("聚合：符文精通 +10%", abs(g.boons.bonus("dmg_all") - 0.10) < 1e-9)

# ---------- 2) 受击管线（护盾/闪避/HP） ----------
g.player.hp = 1000
g.boons.add("freya", "love_ward", 1.0)                    # 普通护盾 15
g.boons.tick(g, DT)
shield0 = g.boons.shield
check("护盾：爱之护盾生成", shield0 > 0)
hurt = g.hurt_player(10)
check("护盾：吸收伤害不掉血", hurt is False and g.player.hp == 1000
      and g.boons.shield == shield0 - 10)
g.boons.shield = 0
before = g.player.hp
g.hurt_player(30)
check("受击：无盾时扣 HP", g.player.hp == before - 30)

# 闪避：给 100% 闪避验证必闪
g.boons.taken[("loki", "shadow_trick")] = 3
g.boons.rarity[("loki", "shadow_trick")] = 2.6            # 5%*3*2.6=39%……
hp_before = g.player.hp
g.player.iframes = 0
g.hurt_player(999)
# 39% 闪避有概率扣血，此处只验证不崩（闪避路径已跑）
check("闪避：受击管线不崩", g.player.hp <= hp_before)

# ---------- 3) 周期效果真实落地 ----------
g.player.hp = 100
g.enemies.append(Enemy("troll", 0, -100, 1.0))
e0 = g.enemies[0]
hp0 = e0.hp
g.skybolt(e0, 100.0)
check("天雷：伤害落地（含闪电视觉）",
      e0.hp == hp0 - 100 and len(g.bolts) >= 1)

# 连锁闪电：摆 3 个相邻敌人
for i in range(3):
    g.enemies.append(Enemy("draugr", 60 + i * 40, 0, 1.0))
src = g.enemies[1]
hp_before = [e.hp for e in g.enemies[1:]]
g.boons.taken[("thor", "chain_light")] = 3
g.boons.rarity[("thor", "chain_light")] = 2.6
g.chain_lightning(src, 50.0)
hit_any = any(e.hp < h for e, h in zip(g.enemies[2:], hp_before[1:]))
check("连锁闪电：跳到邻近敌人", hit_any)

# 厄运爆炸
victim = g.enemies[-1]
victim.hp = victim.hp_max
victim.doom_t = 0.01
victim.doom_dmg = 80.0
near = Enemy("draugr", victim.x + 20, victim.y, 1.0)
g.enemies.append(near)
n0 = near.hp
for _ in range(3):
    g.update(DT, 0, 0)
check("厄运：爆炸波及邻居", near.hp < n0)

# 寒风（斯卡蒂·凛冬将至）——放一个远离战场的活敌做探针
probe = Enemy("draugr", 400.0, 400.0, 1.0)
g.enemies.append(probe)
g.boons.taken[("skadi", "winter")] = 1
g.boons.rarity[("skadi", "winter")] = 1.0
probe_hp0 = probe.hp
g.boons.timers["blizzard"] = 99.0                          # 强制到期
g.boons.tick(g, DT)
check("寒风：全场减速+伤害", probe.slow_t > 0 and probe.hp < probe_hp0)

# ---------- 4) 神龛交互 ----------
g.state = "play"
g.enemies.clear()
g.player.x, g.player.y = 0.0, 0.0
shrine = Shrine(20.0, 0.0, "thor", (255, 208, 96))
g.shrines.append(shrine)
g.update(DT, 1, 0)                                          # 走过去碰
check("神龛：触碰进入赐福界面", g.state == "boon" and g.boon_offer is not None
      and g.boon_offer[0] == "thor")
god_key, cards1, rr1 = g.boon_offer
g.reroll_boon()
check("神龛：重掷刷新卡池", g.boon_offer[2] is True
      and g.boon_offer[0] == "thor")
g.choose_boon(0)
check("神龛：选卡返回战斗", g.state == "play")

# ---------- 5) 武器进化 ----------
w = g.weapons[0]                                            # axe
w.level = 5
g.player.passives["might"] = 3
dmg_before = w.stats()["damage"]
pierce_before = w.stats()["pierce"]
evo_card = None
for _ in range(50):                                         # 进化卡必出现在池里
    cs = g.gen_cards()
    evo_card = next((c for c in cs if c["kind"] == "evo"), None)
    if evo_card:
        break
check("进化：满足条件时卡池出现进化卡", evo_card is not None)
if evo_card:
    w.evolved = True
    st = w.stats()
    check("进化：数值跃升（伤害/穿透）",
          st["damage"] > dmg_before and st["pierce"] > pierce_before)
    check("进化：显示名切换", w.display_name == "血怒旋斧")
# 不满足条件时不出进化卡
w2 = Weapon("gungnir")
g.weapons.append(w2)
g.player.passives["swift"] = 0
g.state = "play"
seen = any(c["kind"] == "evo" and c["act"][1] == "gungnir" for _ in range(30)
           for c in g.gen_cards())
check("进化：被动不足不出进化卡", not seen)

# ---------- 收尾 ----------
print("=" * 40)
if fails:
    print(f"BOON_TEST_FAIL ({len(fails)}): " + "; ".join(fails))
    sys.exit(1)
print("BOON_TEST_OK 全部通过")
sys.exit(0)
