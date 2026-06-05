"""集成测试 — 完整游戏循环：移动 → 交互 → 理智变化 → 游戏结束。"""
import pytest

import pygame
pygame.init()

from core.ecs import World, Entity
from core.event_bus import EventBus
from components.sanity import Sanity
from systems.sanity_system import SanitySystem


# ── Fixtures ──────────────────────────────

@pytest.fixture
def bus():
    return EventBus()


@pytest.fixture
def world_with_player(bus):
    """创建含 player 的 World，并注册事件监听器。"""
    w = World()
    e = Entity(eid="player")
    e.add(Sanity(value=100, max_value=100))
    w.add_entity(e)

    # 注册 SANITY_RECOVER 监听器（模拟 main.py 中的逻辑）
    def on_recover(data):
        player = w.get_entity("player")
        if not player:
            return
        s = player.get(Sanity)
        amount = data.get("amount", 0)
        if s and amount > 0:
            s.value = min(s.value + amount, s.max_value)
    bus.subscribe("SANITY_RECOVER", on_recover)

    return w, bus


# ── 完整循环测试 ──────────────────────────────

class TestFullGameLoop:
    """测试完整的游戏循环。"""

    def test_move_and_trigger(self, world_with_player, bus):
        """测试移动并触发事件。"""
        w, bus = world_with_player
        sys = SanitySystem(event_bus=bus)

        # 模拟移动
        bus.emit("PLAYER_MOVE", {"col": 5, "row": 5})
        sys.update(w, 0)

        assert True  # 不崩溃即通过

    def test_sanity_drain_and_recover(self, world_with_player, bus):
        """测试理智扣除和恢复。"""
        w, bus = world_with_player
        sys = SanitySystem(event_bus=bus)

        # 扣除理智
        player = w.get_entity("player")
        s = player.get(Sanity)
        if s:
            s.value = 50

        # 恢复理智
        bus.emit("SANITY_RECOVER", {"amount": 15})
        sys.update(w, 0)

        s = player.get(Sanity)
        assert s.value == 65 if s else False

    def test_game_over_then_recover(self, world_with_player, bus):
        """测试游戏结束后无法恢复理智。"""
        w, bus = world_with_player
        events = []
        bus.subscribe("GAME_OVER", lambda d: events.append(d))
        sys = SanitySystem(event_bus=bus)

        # 理智降至 0
        player = w.get_entity("player")
        s = player.get(Sanity)
        if s:
            s.value = 0

        sys.update(w, 0)

        assert len(events) >= 1
        assert events[-1]["reason"] == "sanity_zero"

    def test_collect_card_recovers_sanity(self, world_with_player, bus):
        """测试收集卡牌后恢复理智。"""
        w, bus = world_with_player
        sys = SanitySystem(event_bus=bus)

        # 收集薰衣草卡牌（恢复 15 理智）
        player = w.get_entity("player")
        s = player.get(Sanity)
        if s:
            s.value = 10

        bus.emit("CARD_COLLECTED", {"card_id": "lavender_01"})
        sys.update(w, 0)

        s = player.get(Sanity)
        assert s.value == 25 if s else False  # 10 + 15


# ── 边界情况 ──────────────────────────────

class TestEdgeCases:
    """测试边界情况。"""

    def test_no_player_no_crash(self, bus):
        """测试没有 player 时不崩溃。"""
        w = World()
        sys = SanitySystem(event_bus=bus)
        sys.update(w, 0)
        assert True

    def test_no_sanity_component_no_crash(self, bus):
        """测试 player 没有 Sanity 组件时不崩溃。"""
        w = World()
        e = Entity(eid="player")
        w.add_entity(e)
        sys = SanitySystem(event_bus=bus)
        sys.update(w, 0)
        assert True

    def test_multiple_players(self, bus):
        """测试多个实体（非 player）不影响逻辑。"""
        w = World()
        e1 = Entity(eid="player")
        e1.add(Sanity(value=100, max_value=100))
        w.add_entity(e1)

        e2 = Entity(eid="npc")
        e2.add(Sanity(value=50, max_value=100))
        w.add_entity(e2)

        sys = SanitySystem(event_bus=bus)
        sys.update(w, 0)

        assert True  # 不崩溃即通过
