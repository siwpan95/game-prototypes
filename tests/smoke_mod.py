"""冒烟测试：战车改造系统（T2.3 验收）

覆盖：改造店开孔（费用翻倍/上限）、防御强化（步进/上限）、
装甲片扩容、引擎更换（价格/金币不足）、状态存档往返、界面渲染。
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
from model import GameState, ModShop  # noqa: E402
from viewmodel import GameViewModel  # noqa: E402


def main():
    tmp_dir = tempfile.mkdtemp(prefix="maga_modtest_")
    try:
        config_path = os.path.join(tmp_dir, "config.xlsx")
        shutil.copy(os.path.join(REPO_ROOT, "config.xlsx"), config_path)
        config = ConfigLoader(config_path)
        assert config.load_all(), "配置加载失败"

        vm = GameViewModel(config)
        vm.command_new_game()
        d = vm.data
        v = d.current_vehicle

        # ── 打开改造店 ──
        d.state = GameState.TOWN
        vm.command_open_garage()
        assert d.state == GameState.GARAGE, "应进入改造店"
        render = vm._render_garage()
        assert "开主炮孔" in render and "更换引擎" in render, "改造菜单渲染异常"

        # ── 开主炮孔：2000 → 4000 → 已满 ──
        d.gold = 1000
        vm.command_mod_action(1)
        assert v.extra_main_slots == 0, "金币不足不应开孔"
        d.gold = 10000
        vm.command_mod_action(1)
        assert v.extra_main_slots == 1 and d.gold == 8000, "第一个孔 2000G"
        vm.command_mod_action(1)
        assert v.extra_main_slots == 2 and d.gold == 4000, "第二个孔 4000G（翻倍）"
        vm.command_mod_action(1)
        assert v.extra_main_slots == 2, "达到上限不应再开"
        assert v.main_slots == v.chassis.main_slots + 2, "孔位 = 底盘基础 + 改造"

        # ── 底盘防御强化：+10/次，费用 1000 起 ──
        def_before = v.chassis.defense + v.chassis_defense_bonus
        vm.command_mod_action(4)
        assert v.chassis_defense_bonus == 10, "防御应 +10"
        assert v.chassis.defense + v.chassis_defense_bonus == def_before + 10
        assert d.gold == 3000, "防御强化第一次 1000G"

        # ── 装甲片扩容 ──
        vm.command_mod_action(5)
        assert v.max_plates == 30, "装甲片容量应 +10"
        assert d.gold == 2200, "扩容第一次 800G"

        # ── 防御上限 ──
        d.gold = 99999
        v.chassis_defense_bonus = 145  # 野驴上限 200 - 基础 50 = 150 room
        vm.command_mod_action(4)
        assert v.chassis_defense_bonus == 150, "强化不应超过上限"
        assert ModShop.defense_cost(v) is None, "满级后应无费用"

        # ── 引擎更换 ──
        vm.command_mod_action(6)
        assert d.state == GameState.ENGINE_SHOP, "应进入引擎列表"
        render = vm._render_engine_shop()
        assert "V48金刚式" in render and "V100金刚式改" in render, "引擎列表渲染异常"
        d.gold = 9000
        vm.command_engine_interact(3)  # V48（按价格>0 排序第 4 个）
        assert v.engine.name == "V48金刚式", f"引擎应更换: {v.engine.name}"
        assert d.gold == 1000, "V48 应花 8000G"
        assert v.load_capacity() == 52, "载重应变为 52"

        # ── 返回流程 ──
        vm.command_handle_escape()
        assert d.state == GameState.GARAGE, "引擎店应返回改造店"
        vm.command_handle_escape()
        assert d.state == GameState.TOWN, "改造店应返回城镇"

        # ── 存档往返（改造状态持久化） ──
        v.chassis_defense_bonus = 20
        v.plates_capacity_bonus = 10
        assert vm.command_save(2)
        vm.command_new_game()
        vm.command_load(2)
        v2 = vm.data.current_vehicle
        assert v2.extra_main_slots == 2, "读档后开孔应保留"
        assert v2.chassis_defense_bonus == 20, "读档后防御强化应保留"
        assert v2.plates_capacity_bonus == 10, "读档后装甲扩容应保留"
        assert v2.engine.name == "V48金刚式", "读档后引擎应保留"
        assert v2.max_plates == 30, "读档后装甲片容量应保留"

        print("SMOKE OK: 战车改造系统全部断言通过")
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


if __name__ == "__main__":
    main()
