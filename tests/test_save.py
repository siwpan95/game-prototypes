# -*- coding: utf-8 -*-
"""定向验证：Phase 6 存档 + 金币（save.py roundtrip / 掉落 / 结算落档）。"""
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
from save import SaveData, BestRun, Stats
from entities import Enemy
import main as M

pygame.init()
pygame.display.init()
pygame.font.init()
screen = pygame.display.set_mode((320, 180))
M.init_globals()

# ---------- 1. 默认档与 schema ----------
sd = SaveData()
assert sd.gold == 0 and sd.settings["sfx_vol"] == 0.8
assert isinstance(sd.best_run, BestRun) and isinstance(sd.stats, Stats)
print("PASS 默认档 schema（gold/settings/best_run/stats）")

# ---------- 2. roundtrip（隔离临时目录） ----------
d = tempfile.mkdtemp()
save._mgr = None
_orig_dir = save.save_dir
save.save_dir = lambda: d
try:
    sd2 = SaveData(gold=1234, best_run=BestRun(level=9, kills=321, time=88.5),
                   stats=Stats(runs=7, wins=2, total_kills=900, total_damage=12345),
                   settings={"sfx_vol": 0.3, "music_vol": 0.9})
    assert save.save_data(sd2)
    got = save.load_data()
    assert got.gold == 1234 and got.best_run.level == 9
    assert got.stats.total_kills == 900
    assert got.settings["music_vol"] == 0.9
    # 缺字段旧档迁移：直接写一个少 settings 的档
    raw = os.path.join(d, "save_00.json")
    import json, time
    with open(raw, "w", encoding="utf-8") as f:
        json.dump({"version": 1, "timestamp": time.time(), "time_str": "",
                   "state_data": {"gold": 5}}, f)
    got2 = save.load_data()
    assert got2.gold == 5 and got2.settings["sfx_vol"] == 0.8  # 补默认设置
    print("PASS 存档 roundtrip + 旧档缺字段迁移")
finally:
    save.save_dir = _orig_dir
    save._mgr = None

# ---------- 3. 金币掉落 + 结算落档 ----------
d3 = tempfile.mkdtemp()
save._mgr = None
save.save_dir = lambda: d3
try:
    g = M.Game(smoke=True)
    g.state = "play"
    # 普通敌：金币 = 经验等量（draugr xp=1）
    g._kill_rewards(Enemy("draugr", 0, 0, 1.0))
    assert g.run_gold == 1 and g.kills == 1
    # 精英：+50
    g._kill_rewards(Enemy("draugr", 0, 0, 1.0, elite=True))
    assert g.run_gold == 51
    # Boss：+200（会置 victory/gameover，结算前把状态拨回 play 继续测）
    g._kill_rewards(Enemy("jotunn", 0, 0, 1.0, is_boss=True, boss_key="jotunn"))
    assert g.run_gold == 251
    # 事件总线金币事件
    seen = []
    g.bus.subscribe("gold_gain", lambda d: seen.append(d["amount"]))
    g._kill_rewards(Enemy("troll", 0, 0, 1.0))    # troll xp=5
    assert seen == [5]
    # 结算（victory 已被 Boss 置 True）
    g.settle_run()
    sd3 = save.load_data()
    assert sd3.gold == 256 and sd3.stats.runs == 1 and sd3.stats.wins == 1
    assert sd3.best_run.kills == 4
    # 幂等：第二次 settle 不再写
    g.settle_run()
    assert save.load_data().stats.runs == 1
    print("PASS 金币掉落（普通/精英/Boss）+ 结算落档 + 幂等")
finally:
    save.save_dir = _orig_dir
    save._mgr = None

print("SAVE_TEST_OK")
