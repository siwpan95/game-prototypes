"""EventBus 单元测试 — 发布/订阅事件总线。"""
import pytest
from core.event_bus import EventBus


class TestEventBusSubscribe:
    def test_callback_subscribe(self, event_bus):
        calls = []
        event_bus.subscribe("TEST", lambda d: calls.append(d))
        event_bus.emit("TEST", {"x": 1})
        assert calls == [{"x": 1}]

    def test_decorator_subscribe(self, event_bus):
        calls = []
        @event_bus.subscribe("DECO")
        def handler(data):
            calls.append(data)
        event_bus.emit("DECO", {"y": 2})
        assert calls == [{"y": 2}]

    def test_multiple_listeners_same_event(self, event_bus):
        result = []
        event_bus.subscribe("MULTI", lambda d: result.append("A"))
        event_bus.subscribe("MULTI", lambda d: result.append("B"))
        event_bus.emit("MULTI", {})
        assert result == ["A", "B"]

    def test_no_listener_no_crash(self, event_bus):
        """emit 到无监听者的事件不应崩溃。"""
        event_bus.emit("NOBODY_LISTENS", {})


class TestEventBusEmit:
    def test_data_passed_correctly(self, event_bus):
        received = None
        event_bus.subscribe("DATA", lambda d: setattr(event_bus, "_captured", d))
        event_bus.emit("DATA", {"card_id": "key_01", "name": "铜钥匙"})
        assert event_bus._captured == {"card_id": "key_01", "name": "铜钥匙"}

    def test_none_data(self, event_bus):
        received = object()
        event_bus.subscribe("NIL", lambda d: setattr(event_bus, "_nil_cap", d))
        event_bus.emit("NIL", None)
        assert event_bus._nil_cap is None

    def test_emit_isolated_between_events(self, event_bus):
        hits = []
        event_bus.subscribe("E1", lambda d: hits.append("E1"))
        event_bus.subscribe("E2", lambda d: hits.append("E2"))
        event_bus.emit("E1", {})
        assert hits == ["E1"]


class TestEventBusGameEvents:
    """验证项目实际使用的事件名称和数据结构。"""

    def test_card_collected_event(self, event_bus):
        captured = None
        event_bus.subscribe("CARD_COLLECTED", lambda d: setattr(event_bus, "_cc", d))
        event_bus.emit("CARD_COLLECTED", {
            "card_id": "key_01",
            "name": "铜钥匙",
            "glyph": "Ω",
        })
        assert event_bus._cc["card_id"] == "key_01"
        assert event_bus._cc["name"] == "铜钥匙"

    def test_memory_triggered_event(self, event_bus):
        captured = None
        event_bus.subscribe("MEMORY_TRIGGERED", lambda d: setattr(event_bus, "_mem", d))
        event_bus.emit("MEMORY_TRIGGERED", {
            "id": "candle_01",
            "name": "祭烛的记忆",
            "sanity_cost": 5,
            "text": "火焰在黑暗中摇曳……",
        })
        assert event_bus._mem["id"] == "candle_01"

    def test_mechanism_triggered_event(self, event_bus):
        captured = None
        event_bus.subscribe("MECHANISM_TRIGGERED", lambda d: setattr(event_bus, "_mech", d))
        event_bus.emit("MECHANISM_TRIGGERED", {
            "id": "attic_unlock",
            "desc": "阁楼的门打开了。",
        })
        assert event_bus._mech["id"] == "attic_unlock"
