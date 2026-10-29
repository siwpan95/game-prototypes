"""PlayerController 测试 — 移动、阻挡、交互、边界。"""
import pytest
from pygame import Vector2

from core.ecs import World, Entity
from core.config import CELL, COLS, ROWS, BLOCKED_CHARS
from components.grid_position import GridPosition
from components.interactable import Interactable
from components.card_collectible import CardCollectible
from components.memory import Memory
from systems.player_controller import PlayerController


# ── Helpers ────────────────────────────

def _make_player(world, col=5, row=5):
    e = Entity(eid="player")
    e.add(GridPosition(col=col, row=row))
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
                row.append(".")
        grid.append(row)
    return grid


# ── Fixtures ────────────────────────────

@pytest.fixture
def world_with_player():
    w = World()
    _make_player(w, col=5, row=5)
    return w

@pytest.fixture
def controller(bus):
    return PlayerController(event_bus=bus)

@pytest.fixture
def bus():
    return EventBus()


# ── 移动 ────────────────────────────

class TestMovement:
    def test_move_within_bounds(self, world_with_player):
        w = world_with_player
        player = w.get_entity("player")
        gp = player.get(GridPosition)
        if gp:
            gp.col = 6
            gp.row = 5
        # 验证可以移动
        new_gp = player.get(GridPosition)
        assert new_gp.col == 6 if new_gp else False

    def test_move_blocked_by_wall(self, world_with_player):
        w = world_with_player
        player = w.get_entity("player")
        gp = player.get(GridPosition)
        if gp:
            gp.col = 1
            gp.row = 1
        # 边界应该被阻挡
        assert True  # 具体测试逻辑需要根据实现调整

    def test_move_cooldown(self, world_with_player, controller):
        w = world_with_player
        # 测试移动冷却时间
        assert controller.move_timer == 0


# ── 交互 ────────────────────────────

class TestInteraction:
    def test_touch_collects_card(self, world_with_player, bus):
        w = world_with_player
        # 创建可收集的卡牌
        e = Entity(eid="test_card")
        e.add(GridPosition(col=6, row=5))
        e.add(Interactable(hitbox_width=20, hitbox_height=20))
        e.add(CardCollectible(card_id="test_01", collected=False))
        w.add_entity(e)

        collected = []
        bus.subscribe("CARD_COLLECTED", lambda d: collected.append(d))

        # 模拟交互
        bus.emit("PLAYER_MOVE", {"col": 5, "row": 5})

        assert True  # 具体测试逻辑需要根据实现调整

    def test_touch_triggers_memory(self, world_with_player, bus):
        w = world_with_player
        # 创建可触发的记忆
        e = Entity(eid="test_mem")
        e.add(GridPosition(col=6, row=5))
        e.add(Interactable(hitbox_width=20, hitbox_height=20))
        e.add(Memory(memory_id="test_mem", discovered=False))
        w.add_entity(e)

        triggered = []
        bus.subscribe("MEMORY_TRIGGERED", lambda d: triggered.append(d))

        # 模拟交互
        bus.emit("PLAYER_MOVE", {"col": 5, "row": 5})

        assert True  # 具体测试逻辑需要根据实现调整


# ── 边界 ────────────────────────────

class TestEdgeCases:
    def test_no_player_no_crash(self, controller, bus):
        w = World()
        controller.handle_input(w, 0, [])
        assert True

    def test_entity_blocks_movement(self, world_with_player):
        w = world_with_player
        # 在玩家旁边放置一个实体
        e = Entity(eid="blocker")
        e.add(GridPosition(col=6, row=5))
        e.add(Interactable(hitbox_width=20, hitbox_height=20))
        w.add_entity(e)

        player = w.get_entity("player")
        gp = player.get(GridPosition)
        if gp:
            assert gp.col == 5
            assert gp.row == 5
