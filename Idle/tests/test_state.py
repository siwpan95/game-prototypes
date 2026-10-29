"""
GameState 序列化/反序列化 单元测试。
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.state import GameState


class TestGameState:
    """GameState dataclass 基础测试。"""

    def test_default_state(self):
        s = GameState()
        assert s.gold == 0.0
        assert s.total_gold == 0.0
        assert s.dps == 0.0
        assert s.click_power == 1.0
        assert s.upgrades == {}
        assert s.prestige_points == 0
        assert s.active_challenge is None
        assert s.challenge_completed is False
        assert s.heroes == {}
        assert s.equipment_inventory == []

    def test_to_dict_contains_all_fields(self):
        s = GameState(gold=100, total_gold=500, dps=10.5)
        d = s.to_dict()
        assert d["gold"] == 100
        assert d["total_gold"] == 500
        assert d["dps"] == 10.5
        assert d["click_power"] == 1.0
        assert "upgrades" in d
        assert "prestige_points" in d
        assert "ts" in d  # timestamp

    def test_from_dict_restores_state(self):
        original = GameState(
            gold=999, total_gold=10000, dps=50.0, click_power=25,
            upgrades={"clicker": 3, "cursor": 1},
            prestige_points=5,
            heroes={"mage": {"level": 3, "equipped": {}}},
        )
        d = original.to_dict()
        restored = GameState.from_dict(d)
        assert restored.gold == 999
        assert restored.total_gold == 10000
        assert restored.dps == 50.0
        assert restored.click_power == 25
        assert restored.upgrades == {"clicker": 3, "cursor": 1}
        assert restored.prestige_points == 5
        assert restored.heroes == {"mage": {"level": 3, "equipped": {}}}

    def test_from_dict_handles_missing_fields(self):
        """旧存档缺字段时自动补齐。"""
        old_save = {"gold": 500, "total_gold": 5000}
        s = GameState.from_dict(old_save)
        assert s.gold == 500
        assert s.total_gold == 5000
        assert s.dps == 0       # 默认值
        assert s.click_power == 1  # 默认值
        assert s.upgrades == {}
        assert s.prestige_points == 0
        assert s.heroes == {}
        assert s.equipment_inventory == []

    def test_from_dict_empty(self):
        s = GameState.from_dict({})
        assert s.gold == 0
        assert s.total_gold == 0
        assert s.dps == 0
        assert s.click_power == 1

    def test_to_dict_roundtrip(self):
        """序列化 → 反序列化 一致性。"""
        s = GameState(
            gold=1234, total_gold=567890, dps=42.0, click_power=99,
            upgrades={"clicker": 5, "cursor": 2, "gremlin": 1},
            empowered={"noob_clicker": 2},
            prestige_points=12,
            prestige_upgrades={"p_dps": 3},
            active_challenge="speedrun",
            challenge_start_time=1000.0,
            challenge_completed=True,
            heroes={"mage": {"level": 10, "equipped": {"weapon": {"name": "火焰法杖", "bonus": 15}}}},
            equipment_inventory=[
                {"name": "铁剑", "rarity": "common", "bonus": 3, "color": "#aaa"},
            ],
        )
        d = s.to_dict()
        restored = GameState.from_dict(d)
        # 时间戳会不同，跳过
        assert restored.gold == 1234
        assert restored.total_gold == 567890
        assert restored.dps == 42.0
        assert restored.click_power == 99
        assert restored.upgrades == {"clicker": 5, "cursor": 2, "gremlin": 1}
        assert restored.prestige_points == 12
        assert restored.prestige_upgrades == {"p_dps": 3}
        assert restored.active_challenge == "speedrun"
        assert restored.challenge_completed is True
        assert restored.heroes["mage"]["level"] == 10
        assert restored.heroes["mage"]["equipped"]["weapon"]["name"] == "火焰法杖"
        assert len(restored.equipment_inventory) == 1
