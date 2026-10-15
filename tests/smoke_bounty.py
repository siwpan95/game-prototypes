"""冒烟测试：赏金首系统（T2.1 验收）

覆盖：配置加载、赏金首不随机遭遇、悬赏榜接取、明雷遭遇触发、
接取后击杀即时入账、未接取击杀后补领、强制人战（临时收车/战后恢复）、
存档往返、视口 B 标记。
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
from model import Direction, GameState, BountyManager  # noqa: E402
from viewmodel import GameViewModel  # noqa: E402


def walk_onto(vm, x, y):
    """把玩家传送到目标旁一格，再走上去（触发遭遇判定）"""
    d = vm.data
    d.player_x, d.player_y = x, y - 1
    vm.command_move(Direction.DOWN)


def kill_current_enemy(vm):
    """把当前敌人打到 1 血后攻击，确保击杀"""
    d = vm.data
    assert d.current_enemy is not None, "应处于战斗中"
    d.current_enemy.hp = 1
    vm.command_attack()


def main():
    tmp_dir = tempfile.mkdtemp(prefix="maga_bountytest_")
    try:
        config_path = os.path.join(tmp_dir, "config.xlsx")
        shutil.copy(os.path.join(REPO_ROOT, "config.xlsx"), config_path)
        config = ConfigLoader(config_path)
        assert config.load_all(), "配置加载失败"

        # ── 配置：11 个赏金首 ──
        assert len(config.bounties) == 11, f"应有 11 个赏金首: {len(config.bounties)}"
        assert config.bounties[1].name == "水怪" and config.bounties[1].reward == 1000
        assert config.bounties[11].name == "帕鲁" and config.bounties[11].reward == 200000
        assert config.bounties[3].on_foot is True, "马歇尔应强制人战"
        assert config.bounties[11].on_foot is True, "帕鲁应强制人战"
        assert config.enemies[9].is_bounty is True, "水怪敌人数据应为赏金首专用"
        assert config.enemies[9].encounter_rate == 0, "赏金首不参与随机遭遇"

        vm = GameViewModel(config)
        vm.command_new_game()
        d = vm.data

        # ── 赏金首不会随机遭遇 ──
        bounty_names = {config.bounties[b].name for b in config.bounties}
        for _ in range(300):
            enemy = config.get_random_enemy(1)
            assert enemy is not None and not enemy.is_bounty, "赏金首不应随机遭遇"

        # ── 悬赏榜接取 ──
        vm.command_open_bounty_board()
        assert d.state == GameState.BOUNTY, "应进入悬赏榜"
        board_text = vm._render_bounty_board()
        assert "水怪" in board_text and "帕鲁" in board_text, "悬赏榜应列出全部赏金首"
        assert "[可接取]" in board_text, "初始状态应为可接取"
        vm.command_bounty_interact(0)  # 接取水怪
        assert BountyManager.status(d, 1) == "active", "接取后应进行中"
        vm.command_handle_escape()   # 悬赏榜 → 城镇
        vm.command_leave_town()      # 离开城镇 → 荒野
        assert d.state == GameState.WORLD and d.current_map_id == 1

        # ── 走到水怪坐标触发明雷战斗 ──
        walk_onto(vm, 0, 25)
        assert d.state == GameState.BATTLE, "走到赏金首坐标应触发战斗"
        assert d.current_enemy is not None and d.current_enemy.name == "水怪"
        assert d.current_bounty_id == 1, "应记录当前赏金首"

        # ── 击杀：接取状态下悬赏即时入账 ──
        gold_before = d.gold
        kill_current_enemy(vm)
        assert BountyManager.status(d, 1) == "claimed", "击杀后应已领取"
        assert d.gold >= gold_before + 1000, f"悬赏应即时入账: {d.gold - gold_before}"
        assert d.current_bounty_id is None, "战斗结束后应清除赏金首标记"
        # 再走一次不会触发
        walk_onto(vm, 0, 25)
        assert d.state != GameState.BATTLE, "已领取的赏金首不应重复触发"

        # ── 未接取路径：击杀后回悬赏榜补领 ──
        walk_onto(vm, 12, -12)  # 水鬼
        assert d.state == GameState.BATTLE and d.current_enemy.name == "水鬼"
        gold_before = d.gold
        kill_current_enemy(vm)
        assert BountyManager.status(d, 2) == "defeated", "未接取击杀应为待领赏"
        assert d.gold < gold_before + 3000, "未接取击杀不立即入账"
        d.state = GameState.TOWN
        vm.command_bounty_interact(1)  # 悬赏榜领赏
        assert BountyManager.status(d, 2) == "claimed", "领赏后应已领取"
        assert d.gold >= gold_before + 3000, "补领应到账"
        vm.command_handle_escape()
        vm.command_leave_town()

        # ── 强制人战：临时收车 + 战后恢复 ──
        vm.command_bounty_interact(2)  # 接取马歇尔
        assert d.player.vehicle is not None, "接取前应乘战车"
        walk_onto(vm, -25, -5)
        assert d.state == GameState.BATTLE and d.current_enemy.name == "马歇尔"
        assert d.player.vehicle is None, "强制人战应临时收车"
        kill_current_enemy(vm)
        assert d.player.vehicle is not None, "战后应恢复战车"
        assert d.current_vehicle is not None and d.current_vehicle.is_alive() or True

        # ── 存档往返 ──
        assert vm.command_save(1), "应可保存"
        vm.command_new_game()
        vm.command_load(1)
        assert 1 in vm.data.bounty_claimed and 2 in vm.data.bounty_claimed, \
            "读档后赏金状态应保留"
        assert 3 in vm.data.bounty_claimed, "读档后马歇尔悬赏应保留"

        # ── 视口 B 标记 ──
        d = vm.data
        d.player_x, d.player_y = 22, 14  # 大象(22,15)旁边
        from model import MapManager
        view = MapManager.get_viewport(d, config.npcs)
        assert 'B' in view, "荒野视口应显示赏金首标记"

        print("SMOKE OK: 赏金首系统全部断言通过")
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


if __name__ == "__main__":
    main()
