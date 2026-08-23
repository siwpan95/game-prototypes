# -*- coding: utf-8 -*-
"""test_m1_eventbus — 事件总线 + Player 发射（headless）。

覆盖：
  - EventBus 发布/订阅同步调用
  - Player 破坏/放置时经 event_bus 发射对应事件
"""

from __future__ import annotations

from mcclone.core.block_registry import BlockRegistry, STONE, AIR
from mcclone.core.block_world import BlockWorld
from mcclone.core.event_bus import EventBus, EventTypes
from mcclone.player.player import Player


def _reg():
    reg = BlockRegistry()
    reg.load_defaults()
    return reg


def test_event_bus_emit_and_subscribe():
    bus = EventBus()
    received = []
    bus.subscribe(EventTypes.BLOCK_BROKEN, lambda t, d: received.append((t, d)))
    bus.emit(EventTypes.BLOCK_BROKEN, x=1, y=2, id=3)
    assert len(received) == 1
    assert received[0][0] == EventTypes.BLOCK_BROKEN
    assert received[0][1]["x"] == 1


def test_event_bus_multiple_subscribers():
    bus = EventBus()
    a, b = [], []
    bus.subscribe(EventTypes.PLAYER_MOVED, lambda t, d: a.append(d))
    bus.subscribe(EventTypes.PLAYER_MOVED, lambda t, d: b.append(d))
    bus.emit(EventTypes.PLAYER_MOVED, x=5, y=6)
    assert len(a) == 1 and len(b) == 1


def test_player_emits_on_break():
    reg = _reg()
    world = BlockWorld(10, 10)
    world.set(3, 3, 0, STONE)
    p = Player(5.0, 3.0, reg)
    bus = EventBus()
    events = []
    bus.subscribe(EventTypes.BLOCK_BROKEN, lambda t, d: events.append(d))
    p.event_bus = bus
    ok = p.try_break(world, 3, 3)
    assert ok is True
    assert any(e.get("x") == 3 and e.get("y") == 3 for e in events)


def test_player_emits_on_place():
    reg = _reg()
    world = BlockWorld(10, 10)
    p = Player(5.0, 3.0, reg)
    bus = EventBus()
    events = []
    bus.subscribe(EventTypes.BLOCK_PLACED, lambda t, d: events.append(d))
    p.event_bus = bus
    ok = p.try_place(world, 4, 3)
    assert ok is True
    assert any(e.get("x") == 4 and e.get("y") == 3 and e.get("id") == p.held_id
               for e in events)


def test_player_emits_on_land():
    reg = _reg()
    world = BlockWorld(10, 20)
    for x in range(10):
        for y in range(0, 5):
            world.set(x, y, 0, STONE)
    p = Player(5.0, 12.0, reg)
    bus = EventBus()
    landed = []
    bus.subscribe(EventTypes.PLAYER_LANDED, lambda t, d: landed.append(d))
    p.event_bus = bus
    # 简单桩输入
    class _FI:
        def left(self): return False
        def right(self): return False
        def jump_pressed(self): return False
    for _ in range(600):
        p.update(1 / 60, world, _FI())
    assert any(True for _ in landed), "落地应发射 PLAYER_LANDED"
