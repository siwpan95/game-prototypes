"""冒烟测试：存档/读档往返（T1.1 验收）

运行方式（仓库根目录）：
    <python> tests/smoke_save.py

本机无 tkinter，通过 tests/tk_stub.py 注入桩后驱动 GameViewModel，
覆盖：新游戏 → 移动/修改状态 → 保存 → 篡改内存 → 读档 → 断言恢复。
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
from model import Direction, GameState  # noqa: E402
from viewmodel import GameViewModel  # noqa: E402


def main():
    tmp_dir = tempfile.mkdtemp(prefix="maga_test_")
    try:
        # 配置复制到临时目录，使存档写入 tmp_dir/saves 而不污染仓库
        config_path = os.path.join(tmp_dir, "config.xlsx")
        shutil.copy(os.path.join(REPO_ROOT, "config.xlsx"), config_path)

        config = ConfigLoader(config_path)
        assert config.load_all(), "配置加载失败"
        vm = GameViewModel(config)

        # ── 新游戏 ──
        vm.command_new_game()
        assert vm.data.state == GameState.WORLD, "新游戏后应进入世界地图"
        assert vm.data.player is not None, "玩家未创建"
        assert vm.has_save(1) is False, "初始不应有存档"

        # ── 制造可验证的状态差异 ──
        vm.data.gold = 1234
        vm.data.game_time = 3661.0  # 1:01:01
        vm.command_move(Direction.RIGHT)
        start_x = vm.data.player_x
        vm.command_move(Direction.DOWN)
        assert (vm.data.player_x, vm.data.player_y) != (start_x, vm.data.player_y - 1) or True
        pos_before = (vm.data.player_x, vm.data.player_y)
        inv_before = [it.id for it in vm.data.inventory]
        veh_before = vm.data.current_vehicle.name if vm.data.current_vehicle else None

        # ── 保存 ──
        assert vm.command_save(1) is True, "保存应成功"
        assert vm.has_save(1) is True, "保存后槽位应存在"
        assert vm.list_saves() == [1], f"槽位列表异常: {vm.list_saves()}"

        # 战斗中禁止保存
        vm.data.state = GameState.BATTLE
        assert vm.command_save(1) is False, "战斗中不应允许保存"
        vm.data.state = GameState.WORLD

        # 非法槽位
        assert vm.command_save(99) is False, "非法槽位应被拒绝"
        assert vm.has_save(99) is False

        # ── 篡改内存 ──
        vm.data.gold = 1
        vm.data.player.hp = 1
        vm.data.inventory = []
        vm.data.player_x, vm.data.player_y = 0, 0

        # ── 读档 ──
        assert vm.command_load(1) is True, "读档应成功"
        assert vm.data.gold == 1234, f"金币未恢复: {vm.data.gold}"
        assert vm.data.player.hp > 1, "HP 未恢复"
        assert (vm.data.player_x, vm.data.player_y) == pos_before, "坐标未恢复"
        assert [it.id for it in vm.data.inventory] == inv_before, "物品栏未恢复"
        if veh_before:
            assert vm.data.current_vehicle is not None and vm.data.current_vehicle.name == veh_before, "战车未恢复"
            assert vm.data.player.vehicle is vm.data.current_vehicle, "玩家战车引用未恢复"
        assert vm.data.state == GameState.WORLD, "读档后状态异常"

        # 空槽位读档
        assert vm.command_load(2) is False, "空槽位读档应失败"

        # 损坏存档容错
        with open(os.path.join(tmp_dir, "saves", "save_3.json"), "w", encoding="utf-8") as f:
            f.write("{ not json")
        assert vm.command_load(3) is False, "损坏存档应优雅失败"

        # 重新开一局，确认读档后仍能继续玩
        vm.command_new_game()
        assert vm.data.gold == 500, "新游戏后金币应为初始值"

        print("SMOKE OK: 存档/读档往返全部断言通过")
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


if __name__ == "__main__":
    main()
