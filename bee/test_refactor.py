# -*- coding: utf-8 -*-
"""验证 difficulty_service（当前版本：DDA 纯等级驱动 + 词缀注入）

重构后的核心语义：
    D(level) = M * [max(0, level - L_safe)] ** P   （无界幂函数，纯等级驱动）
    scale_enemy_template：敌人等级 = 玩家等级，DDA 负责属性缩放
    词缀池：由外部数据源注入（set_affix_pool），不再由服务自行做文件 I/O
旧版 _delta 微调 API 已删除，本脚本按现行 API 断言。
"""
import os
import random
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from src.sim_core.services.difficulty_service import DifficultyService


class FakeMember:
    """模拟队员（只需 level）"""
    def __init__(self, level):
        self.level = level
        self.hp = 100


class FakeParty:
    """模拟队伍（只需 members）"""
    def __init__(self, level):
        self.members = [FakeMember(level)]

    def get_alive(self):
        return [m for m in self.members if m.hp > 0]


def main():
    random.seed(42)
    ds = DifficultyService()

    # 测试1: 新手保护区内 D=0
    D1 = ds._difficulty(1)
    print(f"[测试1] Lv.1 时 D={D1:.3f}（应=0，L_safe={ds.L_SAFE} 以下无缩放）")
    assert D1 == 0.0, f"新手保护区 D 应为 0，实际 {D1}"

    # 测试2: D 随等级单调递增（幂函数无界）
    D10, D50, D100 = ds._difficulty(10), ds._difficulty(50), ds._difficulty(100)
    print(f"[测试2] D(10)={D10:.3f}, D(50)={D50:.3f}, D(100)={D100:.3f}（应单调递增）")
    assert 0 < D10 < D50 < D100, "D 应随等级单调递增"

    # 测试3/4: 敌人等级 = 玩家等级（DDA 纯等级驱动）
    tpl = {"name": "哥布林", "hp": 30, "damage": 5, "defense": 0,
           "exp": 10, "gold": 5, "loot_table": "normal", "race": "哥布林",
           "description": ""}
    scaled = ds.scale_enemy_template(tpl, FakeParty(1))
    print(f"[测试3] Lv.1 玩家 → 敌人等级={scaled['level']}, HP={scaled['hp']}, 伤害={scaled['damage']}")
    assert scaled["level"] == 1, f"敌人等级应为1，实际{scaled['level']}"

    scaled10 = ds.scale_enemy_template(tpl, FakeParty(10))
    print(f"[测试4] Lv.10 玩家 → 敌人等级={scaled10['level']}, HP={scaled10['hp']}, 伤害={scaled10['damage']}")
    assert scaled10["level"] == 10, f"敌人等级应为10，实际{scaled10['level']}"

    # 测试5: 攻击间隔随等级递减
    interval_low = ds.get_monster_attack_interval(1)
    interval_high = ds.get_monster_attack_interval(50)
    print(f"[测试5] 攻击间隔 Lv.1={interval_low:.2f}s, Lv.50={interval_high:.2f}s（高等级应更短）")
    assert interval_high < interval_low, "高等级攻击间隔应更短"

    # 测试6: 词缀池注入 → 探针可见
    ds.set_affix_pool(["锋利的", "铁壁的", "回生的"])
    print(f"[测试6] 注入词缀池后 enemy_affixes_loaded={ds.enemy_affixes_loaded}（应=3）")
    assert ds.enemy_affixes_loaded == 3, "注入的词缀池应可被探针读取"

    # 测试7: 存档/读档（反馈回路抑制状态往返一致）
    ds.on_combat_end(10.0, True, total_damage=100, enemy_max_hp=50, enemy_regen=5)
    saved = ds.to_dict()
    ds2 = DifficultyService()
    ds2.load_dict(saved)
    print(f"[测试7] 存档/读档 regen_suppression={ds2.regen_suppression:.3f}（应={saved['regen_suppression']:.3f}）")
    assert abs(ds2.regen_suppression - saved["regen_suppression"]) < 0.001, "存档/读档 regen_suppression 应一致"

    print("\n✅ 所有测试通过！当前 DDA 语义正确。")


if __name__ == "__main__":
    main()
