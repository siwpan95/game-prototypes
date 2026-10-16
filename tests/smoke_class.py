"""冒烟测试：职业与特技（T2.6 验收）

覆盖：职业配置、成长率按职业、职业限定技能解锁、特技效果
（紧急修理/电光石火连击）、技能冷却、职业存档往返。
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
from model import Enemy, GameState  # noqa: E402
from viewmodel import GameViewModel  # noqa: E402


def start_battle(vm, enemy_id):
    vm.data.state = GameState.BATTLE
    vm.data.current_enemy = Enemy(vm.config.enemies[enemy_id])


def main():
    tmp_dir = tempfile.mkdtemp(prefix="maga_classtest_")
    try:
        config_path = os.path.join(tmp_dir, "config.xlsx")
        shutil.copy(os.path.join(REPO_ROOT, "config.xlsx"), config_path)
        config = ConfigLoader(config_path)
        assert config.load_all(), "配置加载失败"

        # ── 职业配置 ──
        assert len(config.classes) == 3, f"应有 3 个职业: {len(config.classes)}"
        assert config.classes[1].name == "猎人"
        assert config.classes[2].attack_growth == 2 and config.classes[3].attack_growth == 4
        assert len(config.skills) == 8, f"应有 8 个技能: {len(config.skills)}"
        assert config.skills[6].class_id == 1 and config.skills[6].effect_type == "double_strike"
        assert config.skills[7].class_id == 2 and config.skills[7].cooldown == 4

        # ── 职业成长率 ──
        vm = GameViewModel(config)
        vm.command_new_game(2)  # 机械师
        player = vm.data.player
        assert player.class_data is not None and player.class_data.name == "机械师"
        hp0, atk0 = player.max_hp, player._base_attack
        player.gain_exp(player.exp_to_next + 1)  # 升级
        assert player.max_hp == hp0 + 10, f"机械师 HP 成长应为 10: {player.max_hp}"
        assert player._base_attack == atk0 + 2, "机械师攻击成长应为 2"

        vm.command_new_game(3)  # 战士
        player = vm.data.player
        hp0 = player.max_hp
        player.gain_exp(player.exp_to_next + 1)
        assert player.max_hp == hp0 + 14, "战士 HP 成长应为 14"

        # ── 职业限定技能解锁 ──
        vm.command_new_game(2)  # 机械师
        player = vm.data.player
        player.level = 5
        vm._check_skill_unlocks()
        learned = [s.id for s in player.skills]
        assert 7 in learned, "机械师 5 级应学会紧急修理"
        assert 6 not in learned, "机械师不应学会猎人的电光石火"
        assert 8 not in learned, "机械师不应学会战士的肉搏精通"

        # ── 紧急修理效果 ──
        start_battle(vm, 4)  # 战车敌人
        v = vm.data.current_vehicle
        v.hp = int(v.max_hp * 0.5)
        v.armor_plates = 5
        skill_idx = [i for i, s in enumerate(player.skills) if s.id == 7][0]
        vm.command_use_skill(skill_idx)
        assert v.hp == int(v.max_hp * 0.5) + int(v.max_hp * 0.3), "紧急修理应恢复 30% HP"
        assert v.armor_plates == 15, "紧急修理应补 10 装甲片"

        # ── 技能冷却 ──
        vm.command_new_game(1)  # 猎人
        player = vm.data.player
        player.skills.clear()
        from model import Skill
        player.learn_skill(Skill(config.skills[2]))  # 蓄力射击 冷却2
        start_battle(vm, 18)  # 千血敌人（沙漠之舟，扛得住多轮行动）
        vm.command_use_skill(0)
        assert player.cooldowns.get(2) == 2, "使用后应进入 2 回合冷却"
        vm.command_use_skill(0)
        assert "冷却中" in vm.battle_text.get(), "冷却中应被拒绝"
        vm.command_attack()  # 普攻行动一次 → 冷却 -1
        assert player.cooldowns.get(2) == 1, "普攻应递减冷却"
        vm.command_attack()
        assert player.cooldowns.get(2, 0) == 0, "第二次普攻后冷却应结束"
        vm.command_use_skill(0)
        last_line = vm.battle_text.get().rstrip().splitlines()[-1]
        assert "冷却中" not in last_line, "冷却结束后应可再用"

        # ── 职业存档往返 ──
        vm.data.state = GameState.WORLD  # 退出战斗才能存档
        vm.command_save(1)
        vm.command_new_game(3)
        vm.command_load(1)
        assert vm.data.player.class_id == 1, "读档后职业应保留"
        assert vm.data.player.class_data.name == "猎人"

        print("SMOKE OK: 职业与特技全部断言通过")
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


if __name__ == "__main__":
    main()
