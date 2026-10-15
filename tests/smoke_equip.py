"""冒烟测试：装备系统（T1.7 验收）

覆盖：装备加成、换装回包、卸下、消耗品不受影响、存档往返、
物品栏渲染、旧配置无装备槽位列时的兼容。
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
from model import Item  # noqa: E402
from viewmodel import GameViewModel  # noqa: E402


def main():
    tmp_dir = tempfile.mkdtemp(prefix="maga_equipent_")
    try:
        config_path = os.path.join(tmp_dir, "config.xlsx")
        shutil.copy(os.path.join(REPO_ROOT, "config.xlsx"), config_path)
        config = ConfigLoader(config_path)
        assert config.load_all(), "配置加载失败"

        # 装备槽位配置
        assert config.items[4].equip_slot == "武器" and config.items[4].is_equipment
        assert config.items[7].equip_slot == "头"
        assert config.items[1].equip_slot == "" and not config.items[1].is_equipment

        vm = GameViewModel(config)
        vm.command_new_game()
        player = vm.data.player
        # 初始 attack/defense 已含战车加成（吉普车 +25/+15），以此为基线
        base_attack, base_defense = player.attack, player.defense
        assert base_attack == 15 + 25 and base_defense == 8 + 15, "初始应只有战车加成"

        # ── 装备武器与防具 ──
        old = player.equip(Item(config.items[4]))  # 猎枪 +20
        assert old is None
        assert player.attack == base_attack + 20, "武器加成未生效"
        player.equip(Item(config.items[7]))  # 钢盔 +10
        player.equip(Item(config.items[8]))  # 防弹衣 +25
        assert player.defense == base_defense + 35, f"防具加成未生效: {player.defense}"

        # ── 换装：旧装备回包 ──
        old_weapon = player.equip(Item(config.items[5]))  # 激光枪 +35
        assert old_weapon is not None and old_weapon.id == 4, "旧武器应被换下"
        assert player.attack == base_attack + 35, "换枪后加成应更新"

        # ── 卸下 ──
        removed = player.unequip("头")
        assert removed is not None and removed.id == 7
        assert player.defense == base_defense + 25, "卸下钢盔后防御应回落"

        # ── VM 命令：使用=装备，序号续排=卸下 ──
        player.unequip("武器")
        player.unequip("身")
        vm.data.inventory = [Item(config.items[4]), Item(config.items[1])]  # 猎枪, 药草
        vm.command_use_item(0)  # 装备猎枪 → 物品栏剩 [药草]
        assert "武器" in player.equipment and player.equipment["武器"].id == 4
        vm.command_use_item(0)  # 使用药草（此时在物品栏第 1 位）
        assert all(it.id != 1 for it in vm.data.inventory), "药草应被消耗"
        # 物品栏已空，序号 1 续排到装备区 → 卸下武器
        vm.command_use_item(0)
        assert "武器" not in player.equipment, "序号续排应卸下装备"

        # ── 存档往返保留装备 ──
        player.equip(Item(config.items[6]))  # 火箭筒
        player.equip(Item(config.items[9]))  # 动力装甲
        assert vm.command_save(1)
        vm.command_new_game()
        vm.command_load(1)
        p2 = vm.data.player
        assert p2.equipment["武器"].id == 6, "读档后武器应保留"
        assert p2.equipment["身"].id == 9, "读档后防具应保留"

        # ── 物品栏渲染包含装备区 ──
        text = vm._render_inventory()
        assert "已装备" in text and "卸下" in text, "物品栏应展示装备区"

        # ── 旧配置（无装备槽位列）兼容 ──
        import pandas as pd
        old_path = os.path.join(tmp_dir, "old_config.xlsx")
        with pd.ExcelFile(os.path.join(REPO_ROOT, "config.xlsx")) as xl:
            sheets = {name: pd.read_excel(xl, sheet_name=name) for name in xl.sheet_names}
        sheets["Items"] = sheets["Items"].drop(columns=["装备槽位"])
        with pd.ExcelWriter(old_path, engine="openpyxl") as writer:
            for name, df in sheets.items():
                df.to_excel(writer, sheet_name=name, index=False)
        old_config = ConfigLoader(old_path)
        assert old_config.load_all()
        assert all(not it.is_equipment for it in old_config.items.values()), \
            "旧配置所有物品应视为消耗品"

        print("SMOKE OK: 装备系统全部断言通过")
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


if __name__ == "__main__":
    main()
