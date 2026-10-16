"""冒烟测试：道具体系扩充（T2.5 验收）

覆盖：新道具配置、夺命三宝（军号/烟幕弹/雷达）、系别克制
（药液/铁弹/钢弹）、再生丸、探索道具（迷彩条/地图）、
战斗中使用道具的回合流程、存档往返。
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
from model import Direction, Enemy, GameState, Item  # noqa: E402
from viewmodel import GameViewModel  # noqa: E402


def main():
    tmp_dir = tempfile.mkdtemp(prefix="maga_itemtest_")
    try:
        config_path = os.path.join(tmp_dir, "config.xlsx")
        shutil.copy(os.path.join(REPO_ROOT, "config.xlsx"), config_path)
        config = ConfigLoader(config_path)
        assert config.load_all(), "配置加载失败"

        # ── 新道具配置 ──
        assert len(config.items) == 27, f"应有 27 个物品: {len(config.items)}"
        assert config.items[11].name == "军号" and config.items[11].effect_type == "buff_atkdef"
        assert config.items[12].name == "烟幕弹" and config.items[12].use_scene == "车"
        assert config.items[13].name == "雷达" and config.items[13].use_scene == "车"
        assert config.items[14].name == "药液" and config.items[14].effect_type == "damage_bio"
        assert config.items[17].use_scene == "探索"  # 迷彩条
        assert config.enemies[4].category == "机械", "战车敌人应系机械"
        assert config.enemies[1].category == "生物"

        vm = GameViewModel(config)
        vm.command_new_game()
        d = vm.data

        # ── 军号：攻防倍率 ──
        d.state = GameState.BATTLE
        d.current_enemy = Enemy(config.enemies[1])
        d.inventory = [Item(config.items[11])]
        atk_before, def_before = d.player.attack, d.player.defense
        vm.command_use_item(0)
        assert d.player.battle_atk_mult == 1.5, "军号应攻 +50%"
        assert d.player.battle_def_mult == 1.5, "军号应防 +50%"
        assert d.player.attack > atk_before
        assert d.current_enemy is not None, "敌人应存活（未秒杀）"

        # ── 烟幕弹：敌人下回合伤害减半（一次性） ──
        vm.command_new_game()
        d = vm.data
        d.state = GameState.BATTLE
        enemy = Enemy(config.enemies[6])  # 钢铁巨蝎
        d.current_enemy = enemy
        d.inventory = [Item(config.items[12])]
        vm.command_use_item(0)
        assert "烟幕" in vm.battle_text.get(), "应有烟幕提示"
        # 倍率直接验证：0.5 时伤害显著低于常态，且一次性消耗
        import model.battle as battle_mod
        player = d.player
        player.vehicle = None
        player.combat_on_foot = True  # 步行态，防御=8，差异可观测
        enemy.next_attack_mult = 0.5
        dmg_halved = battle_mod.BattleEngine.calculate_enemy_damage(enemy, player)
        assert enemy.next_attack_mult == 1.0, "减伤应一次性消耗"
        enemy.next_attack_mult = 1.0
        dmg_full = battle_mod.BattleEngine.calculate_enemy_damage(enemy, player)
        assert dmg_halved < dmg_full, f"减伤应生效: {dmg_halved} vs {dmg_full}"

        # ── 雷达：战车攻击倍率 ──
        vm.command_new_game()
        d = vm.data
        d.state = GameState.BATTLE
        d.current_enemy = Enemy(config.enemies[1])
        d.inventory = [Item(config.items[13])]
        veh_atk_before = d.current_vehicle.attack
        vm.command_use_item(0)
        assert d.current_vehicle.battle_atk_mult == 1.2, "雷达应战车攻 +20%"
        assert d.current_vehicle.attack > veh_atk_before

        # ── 药液：生物特效 / 机械低效 ──
        vm.command_new_game()
        d = vm.data
        d.state = GameState.BATTLE
        bio = Enemy(config.enemies[1])  # 野犬 30HP
        d.current_enemy = bio
        d.inventory = [Item(config.items[14])]
        vm.command_use_item(0)
        assert not bio.is_alive(), "药液 80 伤应秒杀野犬"

        vm.command_new_game()
        d = vm.data
        d.state = GameState.BATTLE
        mech = Enemy(config.enemies[4])  # 战车 100HP 机械系
        d.current_enemy = mech
        d.inventory = [Item(config.items[14])]
        vm.command_use_item(0)
        # 20 点保底伤害同样过敌人防御减伤
        expected = 100 - max(1, 20 - mech.defense // 2)
        assert mech.hp == expected, f"药液对机械仅保底 20 伤: {mech.hp}"

        # ── 铁弹：机械特效 ──
        vm.command_new_game()
        d = vm.data
        d.state = GameState.BATTLE
        mech = Enemy(config.enemies[7])  # 钢铁巨蝎 120HP
        d.current_enemy = mech
        d.inventory = [Item(config.items[18])]
        vm.command_use_item(0)
        assert not mech.is_alive(), "铁弹 150 应秒杀钢铁巨蝎"

        # ── 场景校验：战车道具步行时不可用 ──
        vm.command_new_game()
        d = vm.data
        d.state = GameState.BATTLE
        d.player.combat_on_foot = True
        d.current_enemy = Enemy(config.enemies[1])
        d.inventory = [Item(config.items[12])]
        vm.command_use_item(0)
        assert len(d.inventory) == 1, "步行时烟幕弹不应被消耗"

        # ── 探索道具：迷彩条 / 地图 ──
        vm.command_new_game()
        d = vm.data
        d.state = GameState.WORLD
        d.inventory = [Item(config.items[17]), Item(config.items[16])]
        vm.command_use_item(0)  # 迷彩条
        assert d.camouflage_steps == 30, "迷彩条应持续 30 步"
        assert len(d.inventory) == 1
        vm.command_use_item(0)  # 地图
        assert any("查看" in m or "地图" in m for m in d.log_messages), "地图应给出提示"

        # ── 迷彩条逐步递减 ──
        before = d.camouflage_steps
        vm.command_move(Direction.RIGHT)
        assert d.camouflage_steps == before - 1, "移动应消耗隐身步数"

        # ── 存档往返 ──
        assert vm.command_save(1)
        vm.command_new_game()
        vm.command_load(1)
        assert vm.data.camouflage_steps == before - 1, "迷彩条步数应持久化"

        print("SMOKE OK: 道具体系全部断言通过")
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


if __name__ == "__main__":
    main()
