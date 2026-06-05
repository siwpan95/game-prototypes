"""集成测试 — 全链路：卡牌收集 → 机关触发 → 地图变化 → 胜利/失败。"""
import json
from pathlib import Path

import pytest

import pygame
pygame.init()

from core.ecs import World, Entity
from core.event_bus import EventBus
from core.map_data import MapData
from core.config import COLS, ROWS
from core.text_world import create_text_world

from components.grid_position import GridPosition
from components.card_collectible import CardCollectible
from components.interactable import Interactable
from components.sanity import Sanity

from systems.player_controller import PlayerController, LAST_DIR
from systems.card_system import CardSystem
from systems.sanity_system import SanitySystem
from systems.mechanism_system import MechanismSystem
from systems.audio_system import AudioSystem

from unittest.mock import MagicMock, patch


ROOT = Path(__file__).resolve().parent.parent


# ── Helpers ────────────────────────────────────

def _install_recover_handler(bus, world):
    """复现 main.py 中 SANITY_RECOVER → 修改理智值的监听器。"""
    def on_recover(data):
        player = world.entities.get("player")
        if not player:
            return
        s = player.get(Sanity)
        amount = data.get("amount", 0)
        if s and amount > 0:
            s.value = min(s.value + amount, s.max_value)
    bus.subscribe("SANITY_RECOVER", on_recover)


def _collect_card(bus, card_id, name="测试", glyph="?"):
    bus.emit("CARD_COLLECTED", {"card_id": card_id, "name": name, "glyph": glyph})


# ── 卡牌全收集 → 胜利 ────────────────────────────

class TestWinCondition:
    """收集所有卡牌 → 触发 GAME_WIN。"""

    def test_win_on_last_card(self):
        bus = EventBus()
        screen = pygame.Surface((960, 640))
        world = create_text_world(bus, screen)

        # 给 player 加 Sanity（create_text_world 可能已加）
        player = world.entities.get("player")
        if player and not player.get(Sanity):
            player.add(Sanity(value=100, max_value=100)

        _install_recover_handler(bus, world)

        cs = CardSystem(screen, bus)
        cs.init_collection(world)

        events = []
        bus.subscribe("GAME_WIN", lambda d: events.append(d))

        # 收集所有未收集的卡牌
        for cid in list(cs.cards_def.keys()):
            if not cs.has_card(cid):
                _collect_card(bus, cid)

        assert len(events) >= 1

    def test_no_win_before_all_collected(self):
        bus = EventBus()
        events = []
        bus.subscribe("GAME_WIN", lambda d: events.append(d))

        screen = pygame.Surface((960, 640))
        world = create_text_world(bus, screen)
        cs = CardSystem(screen, bus)
        # 不收集任何卡牌
        assert len(events) == 0


# ── 理智归零 → 游戏结束 ────────────────────────────

class TestGameOver:
    def test_sanity_zero_emits_game_over(self):
        bus = EventBus()
        events = []
        bus.subscribe("GAME_OVER", lambda d: events.append(d))

        world = World()
        e = Entity(eid="player")
        e.add(Sanity(value=0, max_value=100)
        world.add_entity(e)

        sys = SanitySystem(event_bus=bus)
        sys.update(world, 0)
        assert len(events) == 1

    def test_sanity_drain_game_over(self):
        bus = EventBus()
        events = []
        bus.subscribe("GAME_OVER", lambda d: events.append(d))

        world = World()
        e = Entity(eid="player")
        e.add(Sanity(value=10, max_value=100)
        world.add_entity(e)

        # 模拟记忆触发，扣 20 理智
        def on_mem(data):
            s = world.entities["player"].components.get(Sanity)
            if s:
                s.value -= data.get("sanity_cost", 0)
        bus.subscribe("MEMORY_TRIGGERED", on_mem)

        bus.emit("MEMORY_TRIGGERED", {
            "id": "test", "name": "t",
            "sanity_cost": 20, "text": "..."
        })

        sys = SanitySystem(event_bus=bus)
        sys.update(world, 0)
        assert len(events) == 1


# ── 卡牌收集 → 机关触发 → 地图变化 ───────────

class TestMechanismChain:
    def test_key_01_unlocks_attic_door(self):
        bus = EventBus()
        md = MapData(ROOT / "data" / "mansion_map.txt")
        ms = MechanismSystem(md, bus)

        assert md.get(18, 3) == "门"
        _collect_card(bus, "key_01", "钥匙")
        assert md.get(18, 3) == "░"

    def test_suspicious_hole_unlocks_basement(self):
        bus = EventBus()
        md = MapData(ROOT / "data" / "mansion_map.txt")
        ms = MechanismSystem(md, bus)

        # 先触发 key_01
        _collect_card(bus, "key_01", "钥匙")
        assert md.get(19, 20) == "墙"

        _collect_card(bus, "suspicious_hole_01", "洞")
        assert md.get(19, 20) == "░"

    def test_mechanism_idempotent(self):
        bus = EventBus()
        md = MapData(ROOT / "data" / "mansion_map.txt")
        ms = MechanismSystem(md, bus)

        before = md.get(18, 3)
        _collect_card(bus, "key_01", "钥匙")
        after1 = md.get(18, 3)
        _collect_card(bus, "key_01", "钥匙2")
        after2 = md.get(18, 3)
        assert after1 == after2, "机关重复触发"


# ── 事件链路完整性 ────────────────────────────

class TestEventChain:
    def test_card_collected_emits_event(self):
        bus = EventBus()
        received = []
        bus.subscribe("CARD_COLLECTED", lambda d: received.append(("card", d)))

        md = MapData(ROOT / "data" / "mansion_map.txt")
        ms = MechanismSystem(md, bus)

        _collect_card(bus, "key_01", "钥匙")
        assert len(received) == 1
        assert received[0][0] == "card"

    def test_memory_triggered_emits_event(self):
        bus = EventBus()
        received = []
        bus.subscribe("MEMORY_TRIGGERED", lambda d: received.append(d))

        bus.emit("MEMORY_TRIGGERED", {
            "id": "candle_01", "name": "蜡烛",
            "sanity_cost": 10, "text": "..."
        })
        assert len(received) == 1


# ── 系统 update 不崩溃 ────────────────────────────

class TestSystemUpdates:
    def test_all_systems_update_no_crash(self):
        bus = EventBus()
        screen = pygame.Surface((960, 640))
        world = create_text_world(bus, screen)

        # 给 player 加 Sanity
        player = world.entities.get("player")
        if player and not player.get(Sanity):
            player.add(Sanity(value=100, max_value=100)

        _install_recover_handler(bus, world)

        ss = SanitySystem(event_bus=bus)
        cs = CardSystem(screen, bus)
        md = MapData(ROOT / "data" / "mansion_map.txt")
        ms = MechanismSystem(md, bus)

        for sys in [ss, cs, ms]:
            sys.update(world, 16.7)

    def test_full_game_loop_tick(self):
        bus = EventBus()
        screen = pygame.Surface((960, 640))
        world = create_text_world(bus, screen)

        player = world.entities.get("player")
        if player and not player.get(Sanity):
            player.add(Sanity(value=100, max_value=100)

        _install_recover_handler(bus, world)

        ss = SanitySystem(event_bus=bus)
        cs = CardSystem(screen, bus)
        md = MapData(ROOT / "data" / "mansion_map.txt")
        ms = MechanismSystem(md, bus)

        for sys in [ss, cs, ms]:
            sys.update(world, 16.7)
