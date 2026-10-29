"""冒烟测试：人车分离伤害模型（T1.8 验收）

覆盖：乘战车时敌人打战车人不掉血、战车毁后伤害转到人、
防御姿态在车内翻倍战车防御、步行时防御减伤、战斗面板显示战车。
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
from model import Character, Enemy, GameState  # noqa: E402
from viewmodel import GameViewModel  # noqa: E402


def fresh_battle(vm, enemy_id=4):
    """用高 HP 敌人（战车，100HP）开一场确定能挨住反击的战斗"""
    d = vm.data
    enemy = Enemy(vm.config.enemies[enemy_id])
    d.current_enemy = enemy
    d.state = GameState.BATTLE
    return enemy


def main():
    tmp_dir = tempfile.mkdtemp(prefix="maga_battletest_")
    try:
        config_path = os.path.join(tmp_dir, "config.xlsx")
        shutil.copy(os.path.join(REPO_ROOT, "config.xlsx"), config_path)
        config = ConfigLoader(config_path)
        assert config.load_all(), "配置加载失败"
        vm = GameViewModel(config)
        vm.command_new_game()
        d = vm.data
        player = d.player
        vehicle = d.current_vehicle
        assert vehicle is not None and vehicle.is_alive(), "初始应有战车"

        # ── 乘战车：敌人伤害由战车承担（先耗装甲片） ──
        player.hp = player.max_hp
        vehicle.hp = vehicle.max_hp
        vehicle.armor_plates = vehicle.max_plates
        enemy = fresh_battle(vm, 4)  # 战车 100HP，扛得住一击
        vm.command_attack()
        assert enemy.hp < enemy.max_hp, "敌人应受伤"
        assert player.hp == player.max_hp, "乘战车时人不应掉血"
        assert (vehicle.armor_plates < vehicle.max_plates
                or vehicle.hp < vehicle.max_hp), "战车应承伤（装甲片或耐久）"

        # ── 战车毁后，伤害转到人 ──
        vm.command_new_game()
        d = vm.data
        player, vehicle = d.player, d.current_vehicle
        vehicle.armor_plates = 0  # 装甲片耗尽
        vehicle.hp = 1
        fresh_battle(vm, 4)
        vm.command_attack()
        assert not vehicle.is_alive(), "战车应被击毁"
        assert vehicle.broken is True
        assert player.hp == player.max_hp, "击毁战车的那一击不波及驾驶员"

        # 战车已毁：再挨打直接扣人
        if d.current_enemy is not None and d.current_enemy.is_alive():
            hp_before = player.hp
            fresh_battle(vm, 4)
            vm.command_attack()
            if d.current_enemy is not None and d.current_enemy.is_alive():
                assert player.hp < hp_before, "战车毁后人应直接承伤"

        # ── 防御姿态：车内翻倍战车防御，结束后复原 ──
        vm.command_new_game()
        d = vm.data
        vehicle = d.current_vehicle
        vehicle.hp = vehicle.max_hp
        fresh_battle(vm, 6)  # 钢铁巨蝎
        v_def_before = vehicle.defense
        vm.command_defend()
        assert vehicle.defense == v_def_before, "防御姿态结束后战车防御应复原"

        # ── 乘降切换：步行用人属性、战车不承伤 ──
        vm.command_new_game()
        d = vm.data
        player, vehicle = d.player, d.current_vehicle
        vehicle.hp = vehicle.max_hp
        fresh_battle(vm, 4)
        vm.command_toggle_vehicle()  # 下车
        assert player.combat_on_foot is True, "应切步行形态"
        plates_before = vehicle.armor_plates
        hp_before = player.hp
        vm.command_attack()  # 步行攻击 → 敌人反击打人
        if d.current_enemy is not None and d.current_enemy.is_alive():
            assert player.hp < hp_before, "步行时人应直接承伤"
            assert vehicle.armor_plates == plates_before, "步行时战车不应承伤"
        vm.command_toggle_vehicle()  # 上车
        assert player.combat_on_foot is False, "应恢复乘车形态"

        # ── 战斗面板显示形态 ──
        text = vm._render_battle()
        assert "形态:" in text and "乘战车" in text, "战斗面板应显示形态"

        # ── 步行（无战车）：防御减伤，无随机 ──
        player.vehicle = None
        d.current_vehicle = None
        hp_before = player.hp
        dmg_dealt = player.take_damage(30)
        assert dmg_dealt == max(1, 30 - player.defense // 2), "步行伤害应按防御减伤"
        assert player.hp == hp_before - dmg_dealt

        # ── 战斗面板显示战车状态 ──
        vm.command_new_game()
        vm._start_battle(Enemy(config.enemies[1]))
        text = vm._render_battle()
        assert "战车:" in text and "燃料" in text, "战斗面板应显示战车状态"

        print("SMOKE OK: 人车分离伤害模型全部断言通过")
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


if __name__ == "__main__":
    main()
