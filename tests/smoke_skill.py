"""冒烟测试：技能按等级解锁（T1.6 验收）

覆盖：开局只送 1 级技、升级自动学会、学习提示只出一次、存档往返。
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
from viewmodel import GameViewModel  # noqa: E402


def main():
    tmp_dir = tempfile.mkdtemp(prefix="maga_skilltest_")
    try:
        config_path = os.path.join(tmp_dir, "config.xlsx")
        shutil.copy(os.path.join(REPO_ROOT, "config.xlsx"), config_path)
        config = ConfigLoader(config_path)
        assert config.load_all(), "配置加载失败"

        # 配置解锁等级
        assert config.skills[1].unlock_level == 1
        assert config.skills[2].unlock_level == 2
        assert config.skills[5].unlock_level == 5

        vm = GameViewModel(config)
        vm.command_new_game()
        player = vm.data.player

        # 开局只有 1 级技（普通攻击/防御姿态）
        learned = sorted(s.id for s in player.skills)
        assert learned == [1, 3], f"开局应只有 1 级技: {learned}"

        # 升到 2 级 → 学会蓄力射击
        player.level = 2
        vm._check_skill_unlocks()
        assert 2 in [s.id for s in player.skills], "2 级应学会蓄力射击"

        # 提示只出现一次（幂等）
        logs_before = [m for m in vm.data.log_messages if "学会了新技能" in m]
        vm._check_skill_unlocks()
        vm._check_skill_unlocks()
        logs_after = [m for m in vm.data.log_messages if "学会了新技能" in m]
        assert logs_before == logs_after, "重复调用不应重复提示"

        # 升到 5 级 → 全部学会
        player.level = 5
        vm._check_skill_unlocks()
        assert sorted(s.id for s in player.skills) == [1, 2, 3, 4, 5], "5 级应学会全部技能"

        # 存档往返保留已学技能
        assert vm.command_save(2)
        vm.command_new_game()
        vm.command_load(2)
        assert sorted(s.id for s in vm.data.player.skills) == [1, 2, 3, 4, 5], \
            "读档后已学技能应保留"

        # 旧配置（无解锁等级列）默认 1 级，全部开局可学 —— 向后兼容
        import pandas as pd
        old_path = os.path.join(tmp_dir, "old_config.xlsx")
        with pd.ExcelFile(os.path.join(REPO_ROOT, "config.xlsx")) as xl:
            sheets = {name: pd.read_excel(xl, sheet_name=name) for name in xl.sheet_names}
        sheets["Skills"] = sheets["Skills"].drop(columns=["解锁等级"])
        with pd.ExcelWriter(old_path, engine="openpyxl") as writer:
            for name, df in sheets.items():
                df.to_excel(writer, sheet_name=name, index=False)
        old_config = ConfigLoader(old_path)
        assert old_config.load_all()
        assert all(s.unlock_level == 1 for s in old_config.skills.values()), \
            "旧配置缺列应默认 1 级"
        vm2 = GameViewModel(old_config)
        vm2.command_new_game()
        assert len(vm2.data.player.skills) == 5, "旧配置开局应可学全部技能"

        print("SMOKE OK: 技能解锁全部断言通过")
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


if __name__ == "__main__":
    main()
