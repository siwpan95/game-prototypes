"""数值平衡模拟（T4.1）：离线跑成长/经济曲线，输出报告

非断言式诊断脚本，直接驱动 model 层模拟真实玩法：
  场景A：徒步/驾车在荒野刷区域1敌人到 8 级，统计战斗数与耗时
  场景B：8 级时的战车火力 vs 戈麦斯（红狼战车获取门槛）
  场景C：经济——刷怪+悬赏收入 vs 关键装备价格

用法：python tests/balance_sim.py
"""
import os
import shutil
import sys
import tempfile

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)
sys.path.insert(0, os.path.join(REPO_ROOT, "tests"))

import tk_stub  # noqa: E402

tk_stub.install()

from data import ConfigLoader  # noqa: E402
from model import Character, Enemy, Vehicle, QuestManager, BountyManager  # noqa: E402

import random  # noqa: E402


def sim_grind(config, battles=200, seed=42):
    """模拟荒野刷怪：区域1随机敌人， victory 流程等价于 resolve_victory"""
    random.seed(seed)
    vm_tmp_gold = 0
    # 新游戏状态（复用 VM 初始化，但不启动 UI tick）
    from viewmodel import GameViewModel
    tmp_dir = tempfile.mkdtemp()
    try:
        cfg_path = os.path.join(tmp_dir, "config.xlsx")
        shutil.copy(os.path.join(REPO_ROOT, "config.xlsx"), cfg_path)
        cfg = ConfigLoader(cfg_path)
        cfg.load_all()
        vm = GameViewModel(cfg)
        vm.command_new_game(1)
        d = vm.data
        # 清掉初始任务，只看刷怪曲线
        d.active_quests = []
        d.quest_progress = []

        enemy_pool = [e for e in cfg.enemies.values()
                      if e.region_id == 1 and e.encounter_rate > 0]
        weights = [e.encounter_rate for e in enemy_pool]
        history = []  # (level, battle_no, gold)
        fights_per_level = {}
        for i in range(battles):
            roll = random.uniform(0, sum(weights))
            acc, ed = 0.0, enemy_pool[-1]
            for e in enemy_pool:
                acc += e.encounter_rate
                if roll <= acc:
                    ed = e
                    break
            enemy = Enemy(ed)
            # 玩家自动攻击直到分出胜负（战车火力）
            guard = 0
            while enemy.is_alive() and d.player.is_alive() and guard < 50:
                dmg = max(1, d.player.attack + random.randint(-5, 5))
                enemy.take_damage(dmg)
                guard += 1
                if enemy.is_alive():
                    back = enemy.attack + random.randint(-3, 3)
                    d.player.take_damage(max(1, back))
            if not enemy.is_alive():
                d.player.gain_exp(ed.exp_reward)
                d.gold += ed.gold_reward
                # 修理/燃料开销粗算：每场 15G
                d.gold = max(0, d.gold - 15)
            fights_per_level[d.player.level] = fights_per_level.get(d.player.level, 0) + 1
            history.append((d.player.level, i + 1, d.gold))
            if d.player.level >= 12:
                break
        return d, fights_per_level, history
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def main():
    config = ConfigLoader(os.path.join(REPO_ROOT, "config.xlsx"))
    config.load_all()

    print("=" * 64)
    print("场景A：荒野刷怪到 8 级（战车火力，每场扣 15G 维护）")
    print("=" * 64)
    d, fights_per_level, history = sim_grind(config)
    total_battles = history[-1][1]
    lvl8_battle = next((n for lvl, n, _ in history if lvl >= 8), None)
    gold_at_8 = next((g for lvl, n, g in history if lvl >= 8), None)
    print(f"总场次: {total_battles}, 到 8 级: {lvl8_battle} 场, 8 级时金币: {gold_at_8}")
    for lvl in sorted(fights_per_level):
        print(f"  Lv{lvl}: {fights_per_level[lvl]} 场")
    print(f"终局: Lv{d.player.level} 金币 {d.gold} HP {d.player.hp}")

    print()
    print("=" * 64)
    print("场景B：8 级战车火力 vs 戈麦斯(500HP/防24) 与 赏金首梯队")
    print("=" * 64)
    player = Character("雷班纳", 100, 100, 15, 8, 12)
    player.class_data = config.get_class_by_id(1)
    player.level = 8
    player.exp = player.exp_to_next
    jeep = Vehicle(config.vehicles[1], config)
    player.vehicle = jeep
    print(f"8级 吉普车(40攻) 攻击: {player.attack} → 戈麦斯(防24)每击 "
          f"{max(1, player.attack - 24 // 2)} → 需 {500 // max(1, player.attack - 24 // 2) + 1} 击")
    # 改造后（+105加农 3t、副炮孔1已用）：换 105加农
    jeep2 = Vehicle(config.vehicles[1], config)
    jeep2.main_weapons.append(config.weapons[2])  # 105加农炮
    player.vehicle = jeep2
    print(f"8级 吉普车+105加农 攻击: {player.attack} → 需 "
          f"{500 // max(1, player.attack - 12) + 1} 击")
    wolf = Vehicle(config.vehicles[6], config)
    print(f"红狼战车攻击: {wolf.attack}（对防38的沙漠之舟每击 "
          f"{max(1, wolf.attack - 19)}）")

    print()
    print("=" * 64)
    print("场景C：经济（8级时购买力）")
    print("=" * 64)
    prices = {"105加农炮": 3000, "V48引擎": 8000, "开主炮孔(第1)": 2000,
              "军号": 2000, "警车": 30000}
    for name, p in prices.items():
        afford = "买得起" if (gold_at_8 or 0) >= p else "买不起"
        print(f"  {name} {p}G: {afford}（8级金币 {gold_at_8}）")
    bounty_total = sum(b.reward for b in config.bounties.values())
    print(f"  全部悬赏总额: {bounty_total}G（帕鲁 200000）")
    print(f"  沙漠之舟单笔: {config.bounties[10].reward}G + 战斗金 {config.enemies[18].gold_reward}G")


if __name__ == "__main__":
    main()
