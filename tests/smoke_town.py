"""冒烟测试：城镇设施——战车武器店与出租车站（T2.7 验收）"""
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
from model import GameState, MapManager  # noqa: E402
from viewmodel import GameViewModel  # noqa: E402


def main():
    tmp_dir = tempfile.mkdtemp(prefix="maga_towntest_")
    try:
        config_path = os.path.join(tmp_dir, "config.xlsx")
        shutil.copy(os.path.join(REPO_ROOT, "config.xlsx"), config_path)
        config = ConfigLoader(config_path)
        assert config.load_all(), "配置加载失败"

        vm = GameViewModel(config)
        vm.command_new_game()
        d = vm.data
        v = d.current_vehicle

        # ── 战车武器店：孔位已满时拒绝购买 ──
        d.state = GameState.TOWN
        vm.command_open_garage()
        vm.command_open_weapon_shop()
        assert d.state == GameState.WEAPON_SHOP, "应进入武器店"
        render = vm._render_weapon_shop()
        assert "格林炮" in render, "武器店应列出格林炮"
        assert "托卢" not in render, "专有武器（价格 0）不应出售"
        # 野驴副炮孔 1 已装 15机关炮 → 满
        idx = [i for i, w in enumerate(sorted(
            (w for w in config.weapons.values() if w.price > 0),
            key=lambda w: w.id)) if w.id == 7][0]
        d.gold = 99999
        vm.command_weapon_interact(idx)  # 格林炮
        assert len(v.sub_weapons) == 1, "孔位已满不应安装"
        assert d.gold == 99999, "未安装不应扣款"

        # 开副炮孔后可买
        d.state = GameState.GARAGE
        vm.command_mod_action(2)  # 开副炮孔 2000G
        assert v.extra_sub_slots == 1
        d.state = GameState.WEAPON_SHOP
        vm.command_weapon_interact(idx)
        assert len(v.sub_weapons) == 2, "开孔后应能安装"
        assert any(w.id == 7 for w in v.sub_weapons), "格林炮应已装备"
        assert v.attack == 40 + 90, f"攻击应为 15机关炮+格林炮: {v.attack}"

        # ── 出租车站 ──
        vm.command_handle_escape()  # 武器店 → 改造店
        assert d.state == GameState.GARAGE
        vm.command_handle_escape()  # 改造店 → 城镇
        assert d.state == GameState.TOWN
        vm.command_open_taxi()
        assert d.state == GameState.TAXI, "应进入出租车站"
        render = vm._render_taxi()
        assert "伊尔镇" in render, "出租车应列出伊尔镇"
        assert "罗克镇" not in render or d.current_map_id != 3, "不列当前所在城镇"

        gold_before = d.gold
        vm.command_taxi_interact(0)  # 第一个城镇
        assert d.current_map_id == 2, f"应瞬移到伊尔镇: {d.current_map_id}"
        assert d.gold == gold_before - vm.TAXI_PRICE, "应扣车费"
        assert d.state == GameState.TOWN, "到达后应处于城镇状态"
        entrance = MapManager.entrance_cell(config.maps[2])
        assert (d.player_x, d.player_y) == entrance, "应落在城镇入口格"

        # ── 金币不足 ──
        d.gold = 0
        vm.command_open_taxi()
        vm.command_taxi_interact(0)
        assert d.current_map_id == 2, "金币不足不应瞬移"

        print("SMOKE OK: 城镇设施全部断言通过")
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


if __name__ == "__main__":
    main()
