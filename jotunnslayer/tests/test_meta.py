# -*- coding: utf-8 -*-
"""定向验证：跨局技能树（购买/存档/开局生效）。"""
import os
import sys

# 从项目根执行 python tests\xxx.py 时，把根目录加进 sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import tempfile

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import pygame

import save
import meta
from save import SaveData
import main as M

pygame.init()
pygame.display.init()
pygame.font.init()
screen = pygame.display.set_mode((320, 180))
M.init_globals()

# ---------- 1. 购买：扣款 + 升级 + 上限 ----------
d = tempfile.mkdtemp()
save._mgr = None
_orig = save.save_dir
save.save_dir = lambda: d
try:
    sd = SaveData(gold=3000)
    assert meta.cost(0) == 400
    assert meta.buy(sd, "char", "berserker", 0)         # 生命强化 Lv0->1
    assert sd.gold == 2600 and meta.level_of(sd, "char", "berserker", 0) == 1
    assert meta.buy(sd, "char", "berserker", 0)
    assert meta.buy(sd, "char", "berserker", 0)         # Lv2->3（满级）
    assert not meta.buy(sd, "char", "berserker", 0)     # 满级拒绝
    assert meta.level_of(sd, "char", "berserker", 0) == 3
    # 金币不足拒绝
    sd2 = SaveData(gold=100)
    assert not meta.buy(sd2, "char", "berserker", 1)
    # 众神树
    assert meta.buy(sd, "god", "odin", 1)               # 智慧 xp
    assert meta.level_of(sd, "god", "odin", 1) == 1
    print("PASS 购买：扣款/升级/满级与金币门槛")

    # ---------- 2. 存档 roundtrip ----------
    assert save.save_data(sd)
    got = save.load_data()
    assert got.char_levels["berserker"][0] == 3
    assert got.god_levels["odin"][1] == 1
    print("PASS 技能树存档 roundtrip")

    # ---------- 3. bonus_of 聚合 ----------
    b = meta.bonus_of(got)
    assert b["hp"] == 25 * 3 and b["xp"] == 0.12
    print("PASS bonus 聚合（hp75 / xp12%）")

    # ---------- 4. 开局生效 ----------
    g = M.Game(smoke=True, char_key="berserker")
    # g.meta 读的是隔离目录里的档（上面刚写的）
    assert g.player.hp_max == 110 + 75
    assert abs(g.player.dmg_mult() - 1.0) < 1e-9      # 未点伤害
    assert g.player.xp_bonus == 0.12
    print("PASS 开局生效（HP+75 / 经验+12%）")

    # ---------- 5. 旧档缺字段迁移 ----------
    import json, time
    raw = os.path.join(d, "save_00.json")
    with open(raw, "w", encoding="utf-8") as f:
        json.dump({"version": 1, "timestamp": time.time(), "time_str": "",
                   "state_data": {"gold": 5}}, f)
    got2 = save.load_data()
    assert got2.char_levels == {} and got2.god_levels == {}
    print("PASS 旧档缺技能树字段迁移")
finally:
    save.save_dir = _orig
    save._mgr = None

print("META_TEST_OK")
