"""PlayerController 测试 — 移动、阻挡、交互、边界。"""
import json
from pathlib import Path

import pygame
pygame.init()

from core.ecs import World, Entity
from core.config import CELL, COLS, ROWS, BLOCKED_CHARS
from components.grid_position import GridPosition
from components.interactable import Interactable
from components.card_collectible import CardCollectible
from components.memory import Memory
from systems.player_controller import PlayerController, LAST_DIR


ROOT = Path(__file__).resolve().parent.parent


# ── Helpers ────────────────────────────────────

def _make_player(world, col=5, row=5):
    e = Entity(eid="player")
    e.add(GridPosition(col=col, row=row)
    world.add_entity(e)
    return e


def _make_map_grid():
    """创建一个最小地图：全是地板，边界是墙。"""
    grid = []
    for r in range(ROWS):
        row = []
        for c in range(COLS):
            if r == 0 or r == ROWS - 1 or c == 0 or c == COLS - 1:
                row.append("墙")
            else:
                row.append("　")
        grid.append(row)
    return grid


def _make_controller(world, grid=None):
    bus = __import__("core.event_bus", fromlist=["EventBus"]).EventBus()
    ctrl = PlayerController(event_bus=bus, map_data=None)
    if grid:
        ctrl.map_grid = grid
    else:
        ctrl.map_grid = _make_map_grid()
    return ctrl, bus


# ── is_walkable ────────────────────────────────

class TestIsWalkable:
    def _grid(self, chars):
        g = [["　"] * COLS for _ in range(ROWS)]
        for (c, r), ch in chars.items():
            if 0 <= r < ROWS and 0 <= c < COLS:
                g[r][c] = ch
        return g

    def test_walkable_floor(self):
        ctrl, _ = _make_controller(None)
        ctrl.map_grid = self._grid({(5, 5): "　"})
        assert ctrl.is_walkable(5, 5) is True

    def test_blocked_by_wall(self):
        ctrl, _ = _make_controller(None)
        ctrl.map_grid = self._grid({(5, 5): "墙"})
        assert ctrl.is_walkable(5, 5) is False

    def test_blocked_by_dark(self):
        ctrl, _ = _make_controller(None)
        ctrl.map_grid = self._grid({(5, 5): "暗"})
        assert ctrl.is_walkable(5, 5) is False

    def test_blocked_by_door(self):
        ctrl, _ = _make_controller(None)
        ctrl.map_grid = self._grid({(5, 5): "门"})
        assert ctrl.is_walkable(5, 5) is False

    def test_out_of_bounds_negative(self):
        ctrl, _ = _make_controller(None)
        assert ctrl.is_walkable(-1, 5) is False
        assert ctrl.is_walkable(5, -1) is False

    def test_out_of_bounds_too_large(self):
        ctrl, _ = _make_controller(None)
        assert ctrl.is_walkable(COLS, 5) is False
        assert ctrl.is_walkable(5, ROWS) is False

    def test_door_open_passable(self):
        ctrl, _ = _make_controller(None)
        ctrl.map_grid = self._grid({(5, 5): "░"})
        assert ctrl.is_walkable(5, 5) is True


# ── _entity_blocks ──────────────────────────────

class TestEntityBlocks:
    def test_no_entities_not_blocked(self):
        ctrl, _ = _make_controller(None)
        w = World()
        _make_player(w)
        assert ctrl._entity_blocks(w, 5, 5) is False

    def test_interactable_blocks(self):
        ctrl, _ = _make_controller(None)
        w = World()
        _make_player(w)
        e = Entity(eid="obj")
        e.add(GridPosition(col=6, row=5)
        e.add(Interactable(hitbox_width=20, hitbox_height=20)
        w.add_entity(e)
        assert ctrl._entity_blocks(w, 6, 5) is True

    def test_collected_card_not_blocked(self):
        ctrl, _ = _make_controller(None)
        w = World()
        _make_player(w)
        e = Entity(eid="obj")
        e.add(GridPosition(col=6, row=5)
        e.add(Interactable(hitbox_width=20, hitbox_height=20)
        e.add(CardCollectible(card_id="test_01", collected=True)
        w.add_entity(e)
        assert ctrl._entity_blocks(w, 6, 5) is False

    def test_discovered_memory_not_blocked(self):
        ctrl, _ = _make_controller(None)
        w = World()
        _make_player(w)
        e = Entity(eid="obj")
        e.add(GridPosition(col=6, row=5)
        e.add(Interactable(hitbox_width=20, hitbox_height=20)
        e.add(Memory(memory_id="test_mem")
        e.get(Memory).discovered = True
        w.add_entity(e)
        assert ctrl._entity_blocks(w, 6, 5) is False

    def test_multicell_hitbox_blocks(self):
        ctrl, _ = _make_controller(None)
        w = World()
        _make_player(w)
        e = Entity(eid="big_obj")
        e.add(GridPosition(col=6, row=5)
        e.add(Interactable(hitbox_width=40, hitbox_height=20)
        w.add_entity(e)
        assert ctrl._entity_blocks(w, 7, 5) is True


# ── _try_interact_at ──────────────────────────

class TestTryInteractAt:
    def test_touch_collects_card(self):
        events = []
        ctrl, bus = _make_controller(None)
        bus.subscribe("CARD_COLLECTED", lambda d: events.append(d))
        w = World()
        _make_player(w, col=5, row=5)
        e = Entity(eid="card_ent")
        e.add(GridPosition(col=6, row=5)
        e.add(Interactable(hitbox_width=20, hitbox_height=20)
        e.add(CardCollectible(card_id="key_01", collected=False)
        w.add_entity(e)

        ctrl._try_interact_at(w, 6, 5)
        assert len(events) == 1
        assert events[0]["card_id"] == "key_01"
        assert e.get(CardCollectible).collected is True

    def test_touch_triggers_memory(self):
        events = []
        ctrl, bus = _make_controller(None)
        bus.subscribe("MEMORY_TRIGGERED", lambda d: events.append(d))
        w = World()
        _make_player(w, col=5, row=5)
        e = Entity(eid="mem_ent")
        e.add(GridPosition(col=5, row=4)
        e.add(Interactable(hitbox_width=20, hitbox_height=20)
        e.add(Memory(memory_id="candle_01")
        w.add_entity(e)

        ctrl._try_interact_at(w, 5, 4)
        assert len(events) == 1
        assert events[0]["id"] == "candle_01"

    def test_priority_card_over_memory(self):
        events_card = []
        events_mem = []
        ctrl, bus = _make_controller(None)
        bus.subscribe("CARD_COLLECTED", lambda d: events_card.append(d))
        bus.subscribe("MEMORY_TRIGGERED", lambda d: events_mem.append(d))
        w = World()
        _make_player(w, col=5, row=5)
        e = Entity(eid="both")
        e.add(GridPosition(col=6, row=5)
        e.add(Interactable(hitbox_width=20, hitbox_height=20)
        e.add(CardCollectible(card_id="owl_01", collected=False)
        e.add(Memory(memory_id="owl_mem")
        w.add_entity(e)

        ctrl._try_interact_at(w, 6, 5)
        assert len(events_card) == 1
        assert len(events_mem) == 0

    def test_no_adjacent_nothing_happens(self):
        events = []
        ctrl, bus = _make_controller(None)
        bus.subscribe("CARD_COLLECTED", lambda d: events.append(d))
        bus.subscribe("MEMORY_TRIGGERED", lambda d: events.append(d))
        w = World()
        _make_player(w, col=5, row=5)
        ctrl._try_interact_at(w, 6, 5)
        assert len(events) == 0


# ── get_adjacent_interactables ────────────────────

class TestGetAdjacentInteractables:
    def test_returns_adjacent(self):
        ctrl, bus = _make_controller(None)
        w = World()
        _make_player(w, col=5, row=5)
        e = Entity(eid="adj")
        e.add(GridPosition(col=6, row=5)
        e.add(Interactable(hitbox_width=20, hitbox_height=20)
        e.add(CardCollectible(card_id="test", collected=False)
        w.add_entity(e)

        result = ctrl.get_adjacent_interactables(w)
        assert len(result) == 1
        ac, ar, ent = result[0]
        assert (ac, ar) == (6, 5)

    def test_discovered_memory_not_returned(self):
        ctrl, bus = _make_controller(None)
        w = World()
        _make_player(w, col=5, row=5)
        e = Entity(eid="mem")
        e.add(GridPosition(col=5, row=4)
        e.add(Interactable(hitbox_width=20, hitbox_height=20)
        e.add(Memory(memory_id="test_mem")
        e.get(Memory).discovered = True
        w.add_entity(e)

        result = ctrl.get_adjacent_interactables(w)
        assert len(result) == 0

    def test_collected_card_not_returned(self):
        ctrl, bus = _make_controller(None)
        w = World()
        _make_player(w, col=5, row=5)
        e = Entity(eid="card")
        e.add(GridPosition(col=6, row=5)
        e.add(Interactable(hitbox_width=20, hitbox_height=20)
        e.add(CardCollectible(card_id="test", collected=True)
        w.add_entity(e)

        result = ctrl.get_adjacent_interactables(w)
        assert len(result) == 0


# ── 边界 & 异常 ──────────────────────────────

class TestEdgeCases:
    def test_no_player_no_crash(self):
        ctrl, bus = _make_controller(None)
        w = World()
        ctrl.handle_input(w, 0, [])

    def test_no_grid_position_no_crash(self):
        ctrl, bus = _make_controller(None)
        w = World()
        e = Entity(eid="player")
        w.add_entity(e)
        ctrl.handle_input(w, 0, [])

    def test_load_map_no_crash(self):
        ctrl = PlayerController(event_bus=None, map_data=None)
        assert ctrl.map_grid is not None
        assert len(ctrl.map_grid) == ROWS
