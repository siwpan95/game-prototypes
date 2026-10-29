"""pytest fixtures — 为所有测试模块共享的游戏数据。"""
import json
from pathlib import Path

import pytest

from core.event_bus import EventBus
from core.map_data import MapData
from core.ecs import World, Entity, System
from components.grid_position import GridPosition
from components.memory import Memory
from components.interactable import Interactable
from components.card_collectible import CardCollectible
from components.sanity import Sanity

DATA = Path(__file__).resolve().parent.parent / "data"


# ─── 底层的纯逻辑 fixture ──────────────────────────────


@pytest.fixture
def event_bus():
    """空 EventBus，不连接任何系统。"""
    return EventBus()


@pytest.fixture
def map_data():
    """从 mansion_map.txt 加载的共享 MapData。"""
    return MapData(DATA / "mansion_map.txt")


@pytest.fixture
def map_data_empty():
    """直接构造一个 3×3 的自定义 MapData 用于边界测试。"""
    class MiniMap:
        def __init__(self):
            self.grid = [
                ["A", "B", "C"],
                ["D", "E", "F"],
                ["G", "H", "I"],
            ]
        def get(self, c, r):
            if 0 <= c < 3 and 0 <= r < 3:
                return self.grid[r][c]
            return "X"
        def set(self, c, r, v):
            if 0 <= c < 3 and 0 <= r < 3:
                self.grid[r][c] = v
        def replace_at(self, c, r, old, new):
            if self.get(c, r) == old:
                self.set(c, r, new)
        def replace_region(self, cs, ce, rs, re, old, new):
            for r in range(rs, re + 1):
                for c in range(cs, ce + 1):
                    self.replace_at(c, r, old, new)
        def replace_area(self, cs, ce, rs, re, target, replacement):
            for r in range(rs, re + 1):
                for c in range(cs, ce + 1):
                    if self.get(c, r) in target:
                        self.set(c, r, replacement)

    return MiniMap()


# ─── 数据文件 fixture ──────────────────────────────────


@pytest.fixture(scope="session")
def objects_json():
    with open(DATA / "mansion_objects.json", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="session")
def map_lines():
    with open(DATA / "mansion_map.txt", encoding="utf-8") as f:
        return f.read().strip("\n").split("\n")


@pytest.fixture(scope="session")
def card_definitions():
    """返回 {card_id: card_data} 的字典。"""
    cards = {}
    for cf in sorted((DATA / "cards").glob("*.json")):
        with open(cf, encoding="utf-8") as f:
            card = json.load(f)
        cards[card["id"]] = card
    return cards


# ─── World 与 Entity fixture ───────────────────────────


@pytest.fixture
def world():
    """空的 World，无 Entity 无 System。"""
    return World()


@pytest.fixture
def player_entity():
    """标准玩家 Entity。"""
    e = Entity("player")
    e.add(GridPosition(col=19, row=13))
    e.add(Sanity(120, max_value=120))
    return e


@pytest.fixture
def card_entity():
    """一个未收集的卡牌 Entity。"""
    e = Entity("card_test")
    e.add(GridPosition(col=10, row=10))
    e.add(CardCollectible(card_id="test_card", collected=False))
    e.add(Interactable(hitbox_width=20, hitbox_height=20))
    return e


@pytest.fixture
def memory_entity():
    """一个未发现的记忆 Entity（单格 hitbox）。"""
    e = Entity("memory_test")
    e.add(GridPosition(col=5, row=5))
    e.add(Memory(memory_id="test_memory"))
    e.add(Interactable(hitbox_width=20, hitbox_height=20))
    return e


@pytest.fixture
def multi_hitbox_entity():
    """多格物件 Entity（模拟"枯手" hitbox_w=2）。"""
    e = Entity("withered_hand_test")
    e.add(GridPosition(col=4, row=23))
    e.add(Memory(memory_id="withered_hand_01"))
    e.add(Interactable(hitbox_width=2 * 20, hitbox_height=20))
    return e
