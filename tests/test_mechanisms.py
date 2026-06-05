"""机关系统集成测试 — 验证 MechanismSystem 的 replace_at / replace_area 操作有效。

这些测试防止历史上反复出现的问题：
- 阁楼门的 replace_at 目标坐标与地图字符不匹配
- 地下室解锁的 replace_area 范围不包含关键格子
- 走廊暗影清除的范围遗漏区域
"""
from pathlib import Path

import pytest

from core.map_data import MapData
from core.event_bus import EventBus
from systems.mechanism_system import MechanismSystem

DATA = Path(__file__).resolve().parent.parent / "data"


# ─── Helper ────────────────────────────────────────────


def _char_before_after(mechanism_key, target_col, target_row, old_char, new_char):
    """验证指定机关触发后目标格子的字符是否从 old 变为 new。"""
    md = MapData(DATA / "mansion_map.txt")
    bus = EventBus()

    # 创建 MechanismSystem（不需要 UI）
    ms = MechanismSystem(md, bus)

    # 确认替换前字符
    assert md.get(target_col, target_row) == old_char, \
        f"Before mechanism: ({target_col},{target_row}) expected '{old_char}', got '{md.get(target_col, target_row)}'"

    # 触发机关
    event_type, trigger_id = mechanism_key
    if event_type == "CARD_COLLECTED":
        bus.emit("CARD_COLLECTED", {"card_id": trigger_id, "name": "test", "glyph": "?"})
    else:
        bus.emit("MEMORY_TRIGGERED", {"id": trigger_id, "name": "test", "sanity_cost": 0, "text": "..."})

    # 确认替换后字符
    assert md.get(target_col, target_row) == new_char, \
        f"After mechanism: ({target_col},{target_row}) expected '{new_char}', got '{md.get(target_col, target_row)}'"


# ─── 阁楼门解锁 ────────────────────────────────────────


class TestAtticUnlock:
    """收集 key_01 → 阁楼门打开。"""

    KEY = ("CARD_COLLECTED", "key_01")

    def test_door_char_replaced(self):
        """col=18,row=3 的"门"变为"░"。"""
        _char_before_after(self.KEY, 18, 3, "门", "░")

    def test_wrong_coord_not_replaced(self):
        """col=19,row=3 的"墙"不应该变化。"""
        key = self.KEY
        md = MapData(DATA / "mansion_map.txt")
        bus = EventBus()
        MechanismSystem(md, bus)
        assert md.get(19, 3) == "墙"
        bus.emit("CARD_COLLECTED", {"card_id": "key_01", "name": "test", "glyph": "?"})
        assert md.get(19, 3) == "墙"


# ─── 地下室解锁 ────────────────────────────────────────


class TestBasementUnlock:
    """收集 suspicious_hole_01 → 地下室入口打开 + 初始照明。"""

    KEY = ("CARD_COLLECTED", "suspicious_hole_01")

    def test_entry_wall_replaced(self):
        """col=19,20 row=20 的"墙"变为"░"。"""
        _char_before_after(self.KEY, 19, 20, "墙", "░")
        md = MapData(DATA / "mansion_map.txt")
        bus = EventBus()
        MechanismSystem(md, bus)
        bus.emit("CARD_COLLECTED", {"card_id": "suspicious_hole_01", "name": "test", "glyph": "?"})
        assert md.get(20, 20) == "░"

    def test_entry_dark_cleared_in_range(self):
        """col 17-22, row 22-29 的"暗"变为"░"。"""
        md = MapData(DATA / "mansion_map.txt")
        bus = EventBus()
        MechanismSystem(md, bus)

        assert md.get(20, 22) == "暗"
        bus.emit("CARD_COLLECTED", {"card_id": "suspicious_hole_01", "name": "test", "glyph": "?"})
        assert md.get(20, 22) == "░"

    def test_basement_entrance_cleared(self):
        """地下室入口行(row=20)打开后，row=21 黑暗区域会被清除。"""
        md = MapData(DATA / "mansion_map.txt")
        bus = EventBus()
        MechanismSystem(md, bus)
        # replace_area(17,22,21,29) 清除 row 21 col 17-22 的"暗"
        assert md.get(18, 21) == "暗"
        bus.emit("CARD_COLLECTED", {"card_id": "suspicious_hole_01", "name": "test", "glyph": "?"})
        assert md.get(18, 21) == "░"


# ─── 走廊暗影消散 ──────────────────────────────────────


class TestHallwayClear:
    """收集 dead_vole_01 → 走廊暗影清除。"""

    KEY = ("CARD_COLLECTED", "dead_vole_01")

    def test_hallway_dark_cleared(self):
        """row 18-19, col 0-39 的"暗"变为"░"。"""
        md = MapData(DATA / "mansion_map.txt")
        bus = EventBus()
        MechanismSystem(md, bus)

        # row 19 col 12 是"暗"（已验证）
        assert md.get(12, 19) == "暗"
        bus.emit("CARD_COLLECTED", {"card_id": "dead_vole_01", "name": "test", "glyph": "?"})
        assert md.get(12, 19) == "░"


# ─── 地下室二次照明（蜡烛记忆）──────────────────────────


class TestBasementLight:
    """触发 candle_01 记忆 → 地下室黑暗扩大清除范围。"""

    KEY = ("MEMORY_TRIGGERED", "candle_01")

    def test_left_side_dark_cleared(self):
        """col 5-36, row 22-29 的"暗"变为"░"。"""
        md = MapData(DATA / "mansion_map.txt")
        bus = EventBus()
        MechanismSystem(md, bus)

        # 先解锁地下室（清除入口附近）
        bus.emit("CARD_COLLECTED", {"card_id": "suspicious_hole_01", "name": "test", "glyph": "?"})
        # 确保 col=5,row=24 区域此时还是暗
        assert md.get(6, 24) == "暗"

        bus.emit("MEMORY_TRIGGERED", {"id": "candle_01", "name": "test", "sanity_cost": 0, "text": "..."})
        assert md.get(6, 24) == "░"


# ─── 地下室完全照明（猫头鹰）────────────────────────────


class TestBasementFullLight:
    """收集 owl_01 → 地下室完全照亮。"""

    KEY = ("CARD_COLLECTED", "owl_01")

    def test_full_dark_cleared(self):
        """col 0-39, row 21-29 的"暗"全部变为"░"。"""
        md = MapData(DATA / "mansion_map.txt")
        bus = EventBus()
        MechanismSystem(md, bus)

        bus.emit("CARD_COLLECTED", {"card_id": "suspicious_hole_01", "name": "test", "glyph": "?"})
        bus.emit("MEMORY_TRIGGERED", {"id": "candle_01", "name": "test", "sanity_cost": 0, "text": "..."})

        # 此时 row 21 的某些 col 还是暗（owl 阶段前未清除）
        has_dark_before = any(md.get(c, 21) == "暗" for c in range(0, 40))
        assert has_dark_before, "Expected some dark cells in row 21 before owl"

        bus.emit("CARD_COLLECTED", {"card_id": "owl_01", "name": "test", "glyph": "?"})
        # 全部变░
        has_dark_after = any(md.get(c, 21) == "暗" for c in range(0, 40))
        assert not has_dark_after, "All dark in row 21 should be cleared after owl"


# ─── 机关不重复触发 ────────────────────────────────────


class TestMechanismIdempotency:
    """同一机关不应重复触发。"""

    def test_attic_unlock_runs_once(self):
        md = MapData(DATA / "mansion_map.txt")
        bus = EventBus()
        ms = MechanismSystem(md, bus)

        bus.emit("CARD_COLLECTED", {"card_id": "key_01", "name": "test", "glyph": "?"})
        assert md.get(18, 3) == "░"
        # 手动改回"门"，再次触发 — 不应再执行
        md.set(18, 3, "门")
        bus.emit("CARD_COLLECTED", {"card_id": "key_01", "name": "test2", "glyph": "?"})
        assert md.get(18, 3) == "门", "Mechanism should not re-trigger"


# ─── 无明显操作的机关 ───────────────────────────────────


class TestPassiveMechanisms:
    """仅有提示、无地图操作的机关。"""

    def test_wooden_statue_only_hint(self):
        """wooden_statue_01 收集应该有机制定义但 actions 为空。"""
        md = MapData(DATA / "mansion_map.txt")
        bus = EventBus()
        ms = MechanismSystem(md, bus)

        key = ("CARD_COLLECTED", "wooden_statue_01")
        assert key in ms.mechanisms, "wooden_statue_01 mechanism not defined"
        assert ms.mechanisms[key]["actions"] == [], \
            "wooden_statue_01 should have no map actions"
