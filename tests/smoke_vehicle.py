"""冒烟测试：战车结构（T2.2 验收）

覆盖：部件表加载、攻防 derived、载重/超重、装甲片吸收、修理、
存档往返、超重拦截移动、旧版扁平配置合成兼容。
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
from model import Direction, GameState, Vehicle  # noqa: E402
from viewmodel import GameViewModel  # noqa: E402


def main():
    tmp_dir = tempfile.mkdtemp(prefix="maga_vehicletest_")
    try:
        config_path = os.path.join(tmp_dir, "config.xlsx")
        shutil.copy(os.path.join(REPO_ROOT, "config.xlsx"), config_path)
        config = ConfigLoader(config_path)
        assert config.load_all(), "配置加载失败"

        # ── 部件表 ──
        assert len(config.chassis) == 8, f"应有 8 个底盘: {len(config.chassis)}"
        assert len(config.engines) == 6, f"应有 6 个引擎: {len(config.engines)}"
        assert len(config.cunits) == 4, f"应有 4 个C装置: {len(config.cunits)}"
        assert len(config.weapons) == 14, f"应有 14 个武器: {len(config.weapons)}"
        assert len(config.vehicles) == 8, f"应有 8 辆战车: {len(config.vehicles)}"

        # ── 起始战车（吉普车 = 野驴底 + MOT1 + 艾米 + 15机关炮） ──
        vm = GameViewModel(config)
        vm.command_new_game()
        v = vm.data.current_vehicle
        assert v is not None and v.name == "吉普车"
        assert v.attack == 40, f"攻击应为武器之和 40: {v.attack}"
        assert v.defense == 150, f"防御应为 50+0+100=150: {v.defense}"
        assert v.max_hp == 280 and v.hp == 280, "耐久应为底盘耐久 280"
        assert v.armor_plates == 20 and v.max_sp == 200
        assert v.total_weight() == 16.31, f"全重计算错误: {v.total_weight()}"
        assert not v.is_overweight(), "起始战车不应超重"

        # ── 装甲片先吃伤害 ──
        dealt = v.take_damage(50)
        assert dealt == 50 and v.armor_plates == 15 and v.hp == 280, \
            "50 伤害应只掉装甲片"
        # SP 耗尽后防御减伤：300 - 150 - 75 = 75
        dealt = v.take_damage(300)
        assert v.armor_plates == 0 and v.hp == 280 - 75, \
            f"SP 耗尽后应扣耐久: hp={v.hp}, dealt={dealt}"

        # ── 修理：耐久 + 装甲片 ──
        vm.data.gold = 9999
        vm.command_repair_vehicle()
        assert v.hp == 280 and v.armor_plates == 20 and not v.broken, "修理应全恢复"

        # ── 超重：挂 220 炮（10t）后 26.31t > 20t ──
        v.main_weapons.append(config.weapons[5])  # 220炮
        assert v.is_overweight(), "挂 220 炮后应超重"
        x_before, y_before = vm.data.player_x, vm.data.player_y
        vm.command_move(Direction.RIGHT)
        assert (vm.data.player_x, vm.data.player_y) == (x_before, y_before), \
            "超重应无法移动"
        v.main_weapons.pop()  # 卸掉恢复
        assert not v.is_overweight()
        vm.command_move(Direction.RIGHT)
        assert vm.data.player_x == x_before + 1, "恢复正常后应可移动"

        # ── 存档往返（部件引用保持） ──
        v.armor_plates = 7
        v.fuel = 30
        assert vm.command_save(1)
        vm.command_new_game()
        vm.command_load(1)
        v2 = vm.data.current_vehicle
        assert v2.chassis.id == v.chassis.id, "读档后底盘应保持"
        assert v2.engine.id == v.engine.id, "读档后引擎应保持"
        assert v2.cunit.id == v.cunit.id, "读档后C装置应保持"
        assert v2.armor_plates == 7 and v2.fuel == 30, "读档后状态应保持"
        assert v2.attack == 40, "读档后攻击应保持"

        # ── 红狼战车（最强中期车） ──
        wolfs = Vehicle(config.vehicles[6], config)  # 红狼战车
        assert wolfs.attack == 300 + 40 + 760, f"红狼车攻击错误: {wolfs.attack}"
        assert wolfs.defense == 150 + 115 + 190, f"红狼车防御错误: {wolfs.defense}"

        # ── 旧版扁平配置兼容（合成部件） ──
        import pandas as pd
        old_path = os.path.join(tmp_dir, "old_config.xlsx")
        with pd.ExcelFile(os.path.join(REPO_ROOT, "config.xlsx")) as xl:
            sheets = {name: pd.read_excel(xl, sheet_name=name) for name in xl.sheet_names}
        legacy_vehicles = pd.DataFrame({
            'ID': [1, 2],
            '名称': ['老吉普', '老坦克'],
            'HP': [200, 500],
            '攻击': [25, 60],
            '防御': [15, 40],
            '速度': [8, 5],
            '燃料容量': [100, 150],
            '燃料消耗': [1.0, 2.0],
            '修理费用': [100, 300],
            '描述': ['旧配置', '旧配置'],
        })
        for name in ('Chassis', 'Engines', 'CUnits', 'Weapons'):
            sheets.pop(name, None)
        sheets['Vehicles'] = legacy_vehicles
        with pd.ExcelWriter(old_path, engine='openpyxl') as writer:
            for name, df in sheets.items():
                df.to_excel(writer, sheet_name=name, index=False)
        old_config = ConfigLoader(old_path)
        assert old_config.load_all()
        old_v = Vehicle(old_config.vehicles[1], old_config)
        assert old_v.attack == 25, f"旧配置攻击应保持: {old_v.attack}"
        assert old_v.max_hp == 200 and old_v.defense == 15, "旧配置 HP/防御应保持"
        assert not old_v.is_overweight(), "旧配置合成车不应超重"

        print("SMOKE OK: 战车结构全部断言通过")
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


if __name__ == "__main__":
    main()
