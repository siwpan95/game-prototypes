"""冒烟测试：敌人掉落表（T1.9 验收）

覆盖：按敌人配置掉落/不掉落、掉落率边界、旧配置无掉落列兼容。
用桩替换 battle 模块的 random 实现确定性判定。
"""
import os
import shutil
import sys
import tempfile
import types

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)
sys.path.insert(0, os.path.join(REPO_ROOT, "tests"))

import tk_stub  # noqa: E402

tk_stub.install()

import model.battle as battle_mod  # noqa: E402
from data import ConfigLoader  # noqa: E402
from model import Enemy, GameState  # noqa: E402


class _RandomStub:
    """固定返回值的 random 替身"""

    def __init__(self, value):
        self._value = value

    def random(self):
        return self._value

    def randint(self, a, b):
        return a

    def choice(self, seq):
        return seq[0]


def main():
    tmp_dir = tempfile.mkdtemp(prefix="maga_droptest_")
    original_random = battle_mod.random
    try:
        config_path = os.path.join(tmp_dir, "config.xlsx")
        shutil.copy(os.path.join(REPO_ROOT, "config.xlsx"), config_path)
        config = ConfigLoader(config_path)
        assert config.load_all(), "配置加载失败"

        # 掉落配置
        assert config.enemies[1].drop_item_id == 1 and config.enemies[1].drop_rate == 0.25
        assert config.enemies[3].drop_item_id == 0, "装甲虫应不掉落"

        class _Data:
            pass

        # ── 必掉（random=0 < 0.25） ──
        battle_mod.random = _RandomStub(0.0)
        data = _Data()
        data.player = types.SimpleNamespace(gain_exp=lambda exp: False)
        data.gold = 0
        data.inventory = []
        data.quest_progress = []
        data.current_enemy = Enemy(config.enemies[1])  # 野犬 → 药草
        data.add_log = lambda msg: None
        result = battle_mod.BattleEngine.resolve_victory(data, config.items)
        assert result.item_dropped is not None and result.item_dropped.id == 1, \
            "野犬应掉落药草"
        assert len(data.inventory) == 1

        # ── 不掉（random=0.99 > 0.25） ──
        battle_mod.random = _RandomStub(0.99)
        data = _Data()
        data.player = types.SimpleNamespace(gain_exp=lambda exp: False)
        data.gold = 0
        data.inventory = []
        data.quest_progress = []
        data.current_enemy = Enemy(config.enemies[1])
        data.add_log = lambda msg: None
        result = battle_mod.BattleEngine.resolve_victory(data, config.items)
        assert result.item_dropped is None, "0.99 摇不出 0.25 的掉落"
        assert len(data.inventory) == 0

        # ── 配置不掉落的敌人，摇 0 也不掉 ──
        battle_mod.random = _RandomStub(0.0)
        data = _Data()
        data.player = types.SimpleNamespace(gain_exp=lambda exp: False)
        data.gold = 0
        data.inventory = []
        data.quest_progress = []
        data.current_enemy = Enemy(config.enemies[3])  # 装甲虫 drop=0
        data.add_log = lambda msg: None
        result = battle_mod.BattleEngine.resolve_victory(data, config.items)
        assert result.item_dropped is None, "不掉落配置应生效"

        # ── 高价值敌人（诺亚碎片 → 万能药 0.5） ──
        data = _Data()
        data.player = types.SimpleNamespace(gain_exp=lambda exp: False)
        data.gold = 0
        data.inventory = []
        data.quest_progress = []
        data.current_enemy = Enemy(config.enemies[8])
        data.add_log = lambda msg: None
        result = battle_mod.BattleEngine.resolve_victory(data, config.items)
        assert result.item_dropped is not None and result.item_dropped.id == 2, \
            "诺亚碎片应掉落万能药"

        # ── 旧配置（无掉落列）兼容 ──
        import pandas as pd
        old_path = os.path.join(tmp_dir, "old_config.xlsx")
        with pd.ExcelFile(os.path.join(REPO_ROOT, "config.xlsx")) as xl:
            sheets = {name: pd.read_excel(xl, sheet_name=name) for name in xl.sheet_names}
        sheets["Enemies"] = sheets["Enemies"].drop(columns=["掉落物品ID", "掉落率"])
        with pd.ExcelWriter(old_path, engine="openpyxl") as writer:
            for name, df in sheets.items():
                df.to_excel(writer, sheet_name=name, index=False)
        old_config = ConfigLoader(old_path)
        assert old_config.load_all()
        assert all(e.drop_item_id == 0 and e.drop_rate == 0.0
                   for e in old_config.enemies.values()), "旧配置应无掉落"
        data = _Data()
        data.player = types.SimpleNamespace(gain_exp=lambda exp: False)
        data.gold = 0
        data.inventory = []
        data.quest_progress = []
        data.current_enemy = Enemy(old_config.enemies[1])
        data.add_log = lambda msg: None
        result = battle_mod.BattleEngine.resolve_victory(data, old_config.items)
        assert result.item_dropped is None, "旧配置不应掉落"

        print("SMOKE OK: 敌人掉落表全部断言通过")
    finally:
        battle_mod.random = original_random
        shutil.rmtree(tmp_dir, ignore_errors=True)


if __name__ == "__main__":
    main()
