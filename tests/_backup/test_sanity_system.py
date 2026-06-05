"""SanitySystem 测试 — 理智钳制、恢复、游戏结束。"""
import pytest

import pygame
pygame.init()

from core.ecs import World, Entity
from core.event_bus import EventBus
from components.sanity import Sanity
from systems.sanity_system import SanitySystem


# ── Helpers ──────────────────────────────────────

def _make_world_with_player(sanity_value=50, max_value=100):
    """创建含 player 的 World，并注册 SANITY_RECOVER 监听器。"""
    w = World()
    e = Entity(eid="player")
    e.add(Sanity(value=sanity_value, max_value=max_value)
    w.add_entity(e)

    # 在 main.py 中，SANITY_RECOVER 的监听器负责实际修改理智值
    # 在测试里复现这段逻辑
    bus = None  # 由 fixture 注入
    return w


def _install_recover_handler(bus, world):
    """安装 SANITY_RECOVER → 实际修改理智值的监听器。"""
    def on_recover(data):
        player = world.entities.get("player")
        if not player:
            return
        s = player.get(Sanity)
        amount = data.get("amount", 0)
        if s and amount > 0:
            s.value = min(s.value + amount, s.max_value)
    bus.subscribe("SANITY_RECOVER", on_recover)


# ── Fixtures ──────────────────────────────────────

@pytest.fixture
def bus():
    return EventBus()


@pytest.fixture
def world_with_player(bus):
    w = World()
    e = Entity(eid="player")
    e.add(Sanity(value=50, max_value=100)
    w.add_entity(e)
    _install_recover_handler(bus, w)
    return w, bus


# ── 理智钳制 ──────────────────────────────────────

class TestSanityClamp:
    def test_clamp_upper(self, world_with_player):
        w, _ = world_with_player
        p = w.entities["player"]
        p.get(Sanity).value = 200
        sys = SanitySystem(event_bus=None)
        sys.update(w, 0)
        assert p.get(Sanity).value == 100

    def test_clamp_lower(self, world_with_player):
        w, _ = world_with_player
        p = w.entities["player"]
        p.get(Sanity).value = -10
        sys = SanitySystem(event_bus=None)
        sys.update(w, 0)
        assert p.get(Sanity).value == 0

    def test_clamp_normal(self, world_with_player):
        w, _ = world_with_player
        p = w.entities["player"]
        p.get(Sanity).value = 42
        sys = SanitySystem(event_bus=None)
        sys.update(w, 0)
        assert p.get(Sanity).value == 42


# ── 游戏结束 ──────────────────────────────────────

class TestGameOver:
    def test_zero_emits_game_over(self, world_with_player, bus):
        w, bus = world_with_player
        events = []
        bus.subscribe("GAME_OVER", lambda d: events.append(d))
        sys = SanitySystem(event_bus=bus)
        p = w.entities["player"]
        p.get(Sanity).value = 0
        sys.update(w, 0)
        assert len(events) == 1
        assert events[0]["reason"] == "sanity_zero"

    def test_game_over_only_once(self, world_with_player, bus):
        w, bus = world_with_player
        events = []
        bus.subscribe("GAME_OVER", lambda d: events.append(d))
        sys = SanitySystem(event_bus=bus)
        p = w.entities["player"]
        p.get(Sanity).value = 0
        sys.update(w, 0)
        sys.update(w, 0)
        assert len(events) == 1

    def test_recover_then_drain_again(self, world_with_player, bus):
        w, bus = world_with_player
        events = []
        bus.subscribe("GAME_OVER", lambda d: events.append(d))
        sys = SanitySystem(event_bus=bus)
        p = w.entities["player"]

        p.get(Sanity).value = 0
        sys.update(w, 0)
        assert len(events) == 1

        # 恢复理智
        p.get(Sanity).value = 30
        sys._game_over_emitted = False
        p.get(Sanity).value = 0
        sys.update(w, 0)
        assert len(events) == 2


# ── 卡牌恢复理智 ──────────────────────────────────────

class TestSanityRecover:
    def test_recover_lavender(self, world_with_player, bus):
        w, bus = world_with_player
        sys = SanitySystem(event_bus=bus)
        p = w.entities["player"]
        p.get(Sanity).value = 10
        bus.emit("CARD_COLLECTED", {"card_id": "lavender_01"})
        assert p.get(Sanity).value == 25  # 10 + 15

    def test_recover_owl(self, world_with_player, bus):
        w, bus = world_with_player
        sys = SanitySystem(event_bus=bus)
        p = w.entities["player"]
        p.get(Sanity).value = 5
        bus.emit("CARD_COLLECTED", {"card_id": "owl_01"})
        assert p.get(Sanity).value == 13  # 5 + 8

    def test_no_recover_unknown_card(self, world_with_player, bus):
        w, bus = world_with_player
        sys = SanitySystem(event_bus=bus)
        p = w.entities["player"]
        p.get(Sanity).value = 50
        bus.emit("CARD_COLLECTED", {"card_id": "key_01"})
        # key_01 不在 SANITY_RECOVERY 中，理智不变
        assert p.get(Sanity).value == 50

    def test_recover_clamped_to_max(self, world_with_player, bus):
        w, bus = world_with_player
        sys = SanitySystem(event_bus=bus)
        p = w.entities["player"]
        p.get(Sanity).value = 95
        bus.emit("CARD_COLLECTED", {"card_id": "lavender_01"})
        assert p.get(Sanity).value == 100  # 95 + 15 → 100


# ── 边界 ──────────────────────────────────────

class TestSanityEdgeCases:
    def test_no_player_no_crash(self, bus):
        sys = SanitySystem(event_bus=bus)
        w = World()
        sys.update(w, 0)

    def test_no_sanity_component_no_crash(self, bus):
        sys = SanitySystem(event_bus=bus)
        w = World()
        e = Entity(eid="player")
        w.add_entity(e)
        sys.update(w, 0)

    def test_no_event_bus(self, world_with_player):
        w, _ = world_with_player
        sys = SanitySystem(event_bus=None)
        p = w.entities["player"]
        p.get(Sanity).value = 0
        sys.update(w, 0)  # 不发射事件，不崩溃
