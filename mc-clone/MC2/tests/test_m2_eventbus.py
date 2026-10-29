# -*- coding: utf-8 -*-
"""test_m2_eventbus — M2 事件常量存在 + M1 四事件不破坏（headless，T-M2-09）。"""

from __future__ import annotations

from mcclone.core.event_bus import EventBus, EventTypes


def test_m2_event_constants_present():
    assert EventTypes.PLAYER_DIED == "PLAYER_DIED"
    assert EventTypes.PLAYER_RESPAWN == "PLAYER_RESPAWN"
    assert EventTypes.ITEM_CRAFTED == "ITEM_CRAFTED"


def test_m1_events_still_present():
    for e in (EventTypes.PLAYER_MOVED, EventTypes.BLOCK_BROKEN,
              EventTypes.BLOCK_PLACED, EventTypes.PLAYER_LANDED,
              EventTypes.DEBUG):
        assert e is not None


def test_bus_works_with_all_seven_events():
    bus = EventBus()
    got = []
    all_events = (EventTypes.PLAYER_MOVED, EventTypes.BLOCK_BROKEN,
                  EventTypes.BLOCK_PLACED, EventTypes.PLAYER_LANDED,
                  EventTypes.PLAYER_DIED, EventTypes.PLAYER_RESPAWN,
                  EventTypes.ITEM_CRAFTED)
    for e in all_events:
        bus.subscribe(e, lambda t, d: got.append(t))
    for e in all_events:
        bus.emit(e)
    assert len(got) == 7
