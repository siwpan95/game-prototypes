"""冒烟测试：八辆战车全收集（T2.8 验收）

覆盖：default 初始车、site 荒野发现（免费/付费/金币不足）、
bounty 剧情车（击败戈麦斯继承红狼战车）、V 标记、车库切换、
重复获取防护、车库存档往返。
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
from model import Direction, GameState, MapManager  # noqa: E402
from viewmodel import GameViewModel  # noqa: E402


def main():
    tmp_dir = tempfile.mkdtemp(prefix="maga_collecttest_")
    try:
        config_path = os.path.join(tmp_dir, "config.xlsx")
        shutil.copy(os.path.join(REPO_ROOT, "config.xlsx"), config_path)
        config = ConfigLoader(config_path)
        assert config.load_all(), "配置加载失败"

        # ── 获取方式配置 ──
        assert config.vehicles[1].acquire_type == "default"
        assert config.vehicles[2].acquire_type == "site"
        assert config.vehicles[6].acquire_type == "bounty" and config.vehicles[6].acquire_bounty_id == 7
        assert config.vehicles[8].acquire_price == 30000, "警车应为帕特港购买"

        vm = GameViewModel(config)
        vm.command_new_game()
        d = vm.data

        # 初始只有吉普车
        assert d.owned_vehicle_ids == {1}, f"初始应只有 1 号车: {d.owned_vehicle_ids}"
        assert d.current_vehicle.name == "吉普车"

        # ── site 免费：摩托车 (5,18) ──
        d.player_x, d.player_y = 5, 17
        vm.command_move(Direction.DOWN)
        vm.command_interact()
        assert 2 in d.owned_vehicle_ids, "应获得摩托车"
        assert d.current_vehicle.name == "摩托车", "获得后应自动换乘"
        # 重复交互不重复获得
        vm.command_interact()
        assert sum(1 for v in d.vehicles if v.id == 2) == 1, "不应重复获得"

        # ── site 付费：警车 (28,12) 金币不足 ──
        d.player_x, d.player_y = 28, 11
        vm.command_move(Direction.DOWN)
        vm.command_interact()
        assert 8 not in d.owned_vehicle_ids, "金币不足不应获得"
        d.gold = 50000
        vm.command_interact()
        assert 8 in d.owned_vehicle_ids, "付得起应获得警车"
        assert d.gold == 50000 - 30000, "应扣购买价"

        # ── 视口 V 标记（未获得的获取点） ──
        d.player_x, d.player_y = -25, 1  # 装甲车(-25,2)旁边
        view = MapManager.get_viewport(d, config.npcs)
        assert 'V' in view, "荒野视口应显示战车获取点标记"

        # ── 车库切换 ──
        vm.command_switch_vehicle(0)  # 吉普车
        assert d.current_vehicle.name == "吉普车"
        vm.command_switch_vehicle(1)  # 摩托车
        assert d.current_vehicle.name == "摩托车"
        assert d.player.vehicle is d.current_vehicle

        # ── bounty 剧情车：击败戈麦斯 → 红狼战车 ──
        # 模拟赏金首战斗流程：接受/遭遇/击杀
        d.player_x, d.player_y = 8, 27
        vm.command_move(Direction.DOWN)  # 走到戈麦斯(8,28)触发战斗
        assert d.state == GameState.BATTLE and d.current_enemy.name == "戈麦斯"
        d.current_enemy.hp = 1
        vm.command_attack()
        assert 6 in d.owned_vehicle_ids, "击败戈麦斯应获得红狼战车"
        wolf = [v for v in d.vehicles if v.id == 6][0]
        assert wolf.attack == 300 + 40 + 760, "红狼战车武装应为 165T+15机关炮+托卢"
        assert any("红狼的意志" in m for m in d.log_messages), "应有继承台词"

        # ── 车库存档往返 ──
        d.state = GameState.WORLD
        assert vm.command_save(1)
        vm.command_new_game()
        vm.command_load(1)
        assert vm.data.owned_vehicle_ids == {1, 2, 6, 8}, \
            f"读档后车库应保留: {vm.data.owned_vehicle_ids}"
        assert len(vm.data.vehicles) == 4, "读档后战车实例应重建"

        print("SMOKE OK: 八辆战车全收集全部断言通过")
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


if __name__ == "__main__":
    main()
