"""数值平衡锚点测试（T4.1 验收）：锁定调参后的关键曲线

锚点（依据 tests/balance_sim.py 的模拟数据）：
- 到 8 级 ≤ 60 场战斗（原 119 场过陡，调后 32 场）
- 8 级时裸刷怪金币 ≥ 2500G（不含悬赏/任务收入）
- 红狼战车对终局 BOSS 帕鲁需 3~5 击（不许一击秒）
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

import random  # noqa: E402

from data import ConfigLoader  # noqa: E402
from model import Enemy, Vehicle  # noqa: E402
from viewmodel import GameViewModel  # noqa: E402


def main():
    tmp_dir = tempfile.mkdtemp(prefix="maga_balancetest_")
    try:
        config_path = os.path.join(tmp_dir, "config.xlsx")
        shutil.copy(os.path.join(REPO_ROOT, "config.xlsx"), config_path)
        config = ConfigLoader(config_path)
        assert config.load_all(), "配置加载失败"

        vm = GameViewModel(config)
        vm.command_new_game(1)
        d = vm.data
        d.active_quests = []
        d.quest_progress = []

        random.seed(42)
        enemy_pool = [e for e in config.enemies.values()
                      if e.region_id == 1 and e.encounter_rate > 0]
        weights = [e.encounter_rate for e in enemy_pool]
        battle_to_8 = None
        for i in range(120):
            roll = random.uniform(0, sum(weights))
            acc, ed = 0.0, enemy_pool[-1]
            for e in enemy_pool:
                acc += e.encounter_rate
                if roll <= acc:
                    ed = e
                    break
            enemy = Enemy(ed)
            guard = 0
            while enemy.is_alive() and d.player.is_alive() and guard < 50:
                enemy.take_damage(max(1, d.player.attack + random.randint(-5, 5)))
                guard += 1
                if enemy.is_alive():
                    d.player.take_damage(max(1, enemy.attack + random.randint(-3, 3)))
            if not enemy.is_alive():
                d.player.gain_exp(ed.exp_reward)
                d.gold += ed.gold_reward
                d.gold = max(0, d.gold - 15)
            if d.player.level >= 8 and battle_to_8 is None:
                battle_to_8 = i + 1
                break

        assert battle_to_8 is not None and battle_to_8 <= 60, \
            f"到 8 级应 ≤ 60 场战斗: {battle_to_8}"
        assert d.gold >= 2500, f"8 级时裸刷怪金币应 ≥ 2500: {d.gold}"

        # 终局火力：红狼战车 vs 帕鲁（2500HP/防45）需 3~5 击
        wolf = Vehicle(config.vehicles[6], config)
        paru = Enemy(config.enemies[19])
        hits = 0
        while paru.is_alive():
            paru.take_damage(wolf.attack)
            hits += 1
            assert hits <= 8, "红狼战车不应需要 8 击以上"
        assert 3 <= hits <= 5, f"帕鲁应需 3~5 击: {hits}"

        print("SMOKE OK: 数值平衡锚点全部通过"
              f"（8级={battle_to_8}场, 金币={d.gold}, 帕鲁={hits}击）")
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


if __name__ == "__main__":
    main()
