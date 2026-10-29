"""
smoke_test.py — 冒烟测试：真实战斗模拟（DDA 纯等级驱动）
用法：python smoke_test.py [对局数=100]
"""
import sys
import os
import random
import math

# Windows 默认 GBK 控制台无法编码 ✓/✗/★ 等字符，先做输出容错（不改变内容语义）
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        try:
            _stream.reconfigure(errors="replace")
        except Exception:
            pass

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

try:
    from app.services.difficulty_service import DifficultyService
except ImportError:
    print("无法导入 DifficultyService，检查路径")
    sys.exit(1)


# ────────────────────────────────────────
# 真实战斗模拟器
# ────────────────────────────────────────

class MockPlayer:
    """模拟玩家角色（基于等级生成属性）"""
    def __init__(self, level: float):
        self.level = level
        self.hp = int(80 + 30 * max(0, level - 1) ** 0.9)
        self.max_hp = self.hp
        self.damage = int(8 + 4 * max(0, level - 1) ** 0.8)
        self.defense = int(3 + 2 * max(0, level - 1) ** 0.7)
        self.crit_chance = min(0.3, 0.05 + level * 0.002)
        self.attack_interval = 2.0
        self.evasion = 0.02
        self.thorns = 0.0
        self.regen = 0.0
        self.life_steal = 0.0
        self.stun_chance = 0.0
        self.cdr = 0.0

    def effective_dps(self) -> float:
        base = self.damage / self.attack_interval
        crit_bonus = 1.0 + self.crit_chance * 1.5
        return base * crit_bonus * 0.95


class CombatSimulator:
    """时间步战斗模拟器"""

    def __init__(self, player: MockPlayer, enemy: dict):
        self.p = player
        self.e = enemy
        self.log: list = []

    def run(self, max_time: float = 120.0, dt: float = 0.5) -> dict:
        p_hp = self.p.max_hp
        e_hp = self.e.get("hp", 50)
        e_max_hp = e_hp

        p_timer = 0.0
        e_timer = 0.0
        t = 0.0

        e_damage = self.e.get("damage", 5)
        e_defense = self.e.get("defense", 0)
        e_evasion = self.e.get("evasion", 0.0)
        e_thorns = self.e.get("thorns", 0.0)
        e_regen = self.e.get("regen", 0.0)
        e_life_steal = self.e.get("life_steal", 0.0)
        e_stun = self.e.get("stun_chance", 0.0)
        e_atk_interval = self.e.get("attack_interval", 3.0)

        p_stunned = False
        p_stun_timer = 0.0

        while t < max_time:
            p_timer += dt
            if p_timer >= self.p.attack_interval and not p_stunned:
                p_timer = 0.0
                if random.random() < e_evasion:
                    pass  # 闪避
                else:
                    crit = random.random() < self.p.crit_chance
                    dmg = self.p.damage * (2.5 if crit else 1.0)
                    reduction = 1.0 / (1.0 + e_defense / 50.0)
                    actual_dmg = max(1, int(dmg * reduction))
                    e_hp -= actual_dmg
                    if e_thorns > 0:
                        thorns_dmg = int(actual_dmg * e_thorns)
                        p_hp -= thorns_dmg
                    if e_life_steal > 0:
                        heal = int(actual_dmg * e_life_steal)
                        e_hp = min(e_max_hp, e_hp + heal)

            e_timer += dt
            if e_timer >= e_atk_interval:
                e_timer = 0.0
                if random.random() < self.p.evasion:
                    pass  # 闪避
                else:
                    crit = random.random() < 0.05
                    dmg = e_damage * (2.0 if crit else 1.0)
                    reduction = 1.0 / (1.0 + self.p.defense / 50.0)
                    actual_dmg = max(1, int(dmg * reduction))
                    p_hp -= actual_dmg
                    if e_stun > 0 and random.random() < e_stun:
                        p_stunned = True
                        p_stun_timer = 1.5

            if e_regen > 0 and e_hp < e_max_hp:
                e_hp = min(e_max_hp, e_hp + e_regen * dt * 10)

            if p_stunned:
                p_stun_timer -= dt
                if p_stun_timer <= 0:
                    p_stunned = False

            if e_hp <= 0:
                return {"win": True, "duration": round(t, 1), "t": t}
            if p_hp <= 0:
                return {"win": False, "duration": round(t, 1), "t": t}

            t += dt

        # 超时
        return {"win": p_hp > e_hp, "duration": round(t, 1), "t": t}


# ────────────────────────────────────────
# 主测试逻辑
# ────────────────────────────────────────

def run_smoke(rounds: int = 100):
    ds = DifficultyService()

    # 注入敌人词缀池（与引擎启动路径一致：来自物品模板的前缀配置），
    # 让词缀/稀有度/Boss 分支在独立冒烟测试中也被真实覆盖。
    try:
        from sim_core.services.data_service import DataService
        templates = DataService().get_item_templates()
        prefixes = templates.get("prefixes", [])
        if prefixes:
            ds.set_affix_pool(prefixes)
    except Exception as exc:  # 词缀池不可用不阻塞主流程
        print(f"[警告] 词缀池注入失败（将退化为无词缀模拟）: {exc}")

    print(f"\n{'='*65}")
    print(f"冒烟测试（DDA 纯等级驱动）开始：{rounds} 场 | 词缀库：{ds.enemy_affixes_loaded}")
    print(f"{'='*65}\n")

    templates = [
        {"name": "史莱姆", "hp": 47, "damage": 5,  "defense": 3,  "exp": 17, "gold": 8,  "loot_table": None, "race": "魔法"},
        {"name": "九头蛇", "hp": 65, "damage": 12, "defense": 5,  "exp": 50, "gold": 30, "loot_table": None, "race": "野兽"},
        {"name": "魔龙",   "hp": 70, "damage": 15, "defense": 8,  "exp": 80, "gold": 50, "loot_table": None, "race": "龙类"},
    ]

    results = []

    for i in range(1, rounds + 1):
        lv = random.uniform(1.0, 100.0)
        player = MockPlayer(lv)
        party = type("P", (), {"members": [player]})()

        tpl = random.choice(templates)
        enemy = ds.scale_enemy_template(tpl, party)

        sim = CombatSimulator(player, enemy)
        result = sim.run(max_time=90.0)

        affix_cnt = len(enemy.get("affixes", []))
        boss_tag = "★BOSS★" if affix_cnt >= 3 else ""
        results.append((lv, enemy["name"], affix_cnt, result["win"], result["duration"]))

        if i <= 5 or affix_cnt >= 4:
            outcome = "✓胜" if result["win"] else "✗负"
            print(f"  [{i:03d}] Lv.{lv:5.1f} | {enemy['name']:22s} | {outcome} {result['duration']:5.1f}s | 词缀={affix_cnt} {boss_tag}")

    # ── 统计 ──
    wins = sum(1 for r in results if r[3])
    losses = rounds - wins
    win_rate = wins * 100.0 / rounds

    affix_stats = {}
    for (lv, name, acnt, win, dur) in results:
        k = f"词缀={acnt}"
        if k not in affix_stats:
            affix_stats[k] = {"total": 0, "wins": 0}
        affix_stats[k]["total"] += 1
        if win:
            affix_stats[k]["wins"] += 1

    avg_dur = sum(r[4] for r in results) / rounds
    boss_cnt = sum(1 for r in results if r[2] >= 3)

    print(f"\n{'='*65}")
    print(f"  总对局：{rounds}")
    print(f"  胜率：  {wins}/{rounds} ({win_rate:.0f}%)")
    print(f"  平均耗时：{avg_dur:.1f}s")
    print(f"  Boss 战（词缀≥3）：{boss_cnt} ({boss_cnt*100//rounds}%)")
    print(f"\n  ── 按词缀数统计胜率 ──")
    for k in sorted(affix_stats.keys()):
        s = affix_stats[k]
        wr = s["wins"] * 100 // s["total"]
        print(f"    {k}: {s['wins']}/{s['total']} ({wr}%)")
    print(f"\n  DDA 快照：{ds.probe_snapshot()}")
    print(f"{'='*65}\n")


if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 100
    run_smoke(n)
