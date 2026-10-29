"""
可逆装配内核（Context）行为测试
===============================

覆盖 P1（注册即回滚）的验收项：
    - provide/get/effect/dispose 基本语义与逆序回滚
    - 子作用域（child）：查找向上、销毁只回滚自身
    - 插件协议（name/inject/apply）与装配期依赖校验
    - GameEngine 兼容层：add_* 幂等、mount/unload/shutdown 可重启
    - EventBus 分派模式：waterfall（中间件链）与 serial（顺序投票）
"""

from __future__ import annotations

from allin_engine.core.context import (
    Context,
    DuplicateServiceError,
    MissingDependencyError,
)
from allin_engine import GameEngine
from allin_engine.core import EventBus


# ── Context 基础 ─────────────────────────────────────

def test_context_provide_get():
    ctx = Context()
    marker = object()
    ctx.provide("svc", marker)
    assert ctx.get("svc") is marker
    assert ctx.has("svc")
    assert "svc" in ctx.keys()


def test_context_get_missing_raises():
    ctx = Context()
    try:
        ctx.get("nope")
        raise AssertionError("应当抛 MissingDependencyError")
    except MissingDependencyError:
        pass


def test_context_get_default():
    ctx = Context()
    assert ctx.get("nope", default=42) == 42
    assert ctx.get("nope", default=None) is None


def test_context_duplicate_provide_raises():
    ctx = Context()
    ctx.provide("svc", 1)
    try:
        ctx.provide("svc", 2)
        raise AssertionError("应当抛 DuplicateServiceError")
    except DuplicateServiceError:
        pass


def test_context_replace_provides_new():
    ctx = Context()
    ctx.provide("svc", 1)
    ctx.provide("svc", 2, replace=True)
    assert ctx.get("svc") == 2


def test_context_effect_dispose_reverse_order():
    ctx = Context()
    order: list = []
    ctx.effect(lambda: order.append(1))
    ctx.effect(lambda: order.append(2))
    ctx.provide("svc", None, dispose=lambda: order.append(3))
    ctx.dispose()
    assert order == [3, 2, 1]  # 逆序回滚：后注册先销毁


def test_context_dispose_idempotent():
    ctx = Context()
    calls = []
    ctx.effect(lambda: calls.append("x"))
    ctx.dispose()
    ctx.dispose()
    assert calls == ["x"]


def test_context_child_lookup_parent():
    parent = Context()
    parent.provide("svc", "p")
    child = parent.child()
    assert child.get("svc") == "p"
    assert child.has("svc")


def test_context_child_own_service_shadows_parent():
    parent = Context()
    parent.provide("svc", "p")
    child = parent.child()
    child.provide("svc", "c")
    assert child.get("svc") == "c"
    assert parent.get("svc") == "p"


def test_context_child_dispose_keeps_parent():
    parent = Context()
    parent.provide("svc", "p")
    child = parent.child()
    child.effect(lambda: None)
    child.provide("child_only", 1)
    child.dispose()
    assert parent.get("svc") == "p"


def test_context_unload_runs_disposer_and_removes():
    ctx = Context()
    flag = []
    ctx.provide("svc", 1, dispose=lambda: flag.append("undone"))
    assert ctx.unload("svc") is True
    assert flag == ["undone"]
    assert not ctx.has("svc")


def test_context_unload_missing_returns_false():
    ctx = Context()
    assert ctx.unload("ghost") is False


# ── 插件协议 ─────────────────────────────────────────

class _HelloPlugin:
    name = "hello"
    inject = ["world"]

    def apply(self, ctx, config):
        ctx.provide("hello", f"hi:{config.get('name', 'world')}")
        return None


def test_context_install_plugin():
    ctx = Context()
    ctx.provide("world", object())
    ctx.install(_HelloPlugin(), {"name": "allin"})
    assert ctx.get("hello") == "hi:allin"


def test_context_install_plugin_missing_dep_raises():
    ctx = Context()  # 无 world
    try:
        ctx.install(_HelloPlugin())
        raise AssertionError("应当报缺少依赖")
    except MissingDependencyError:
        pass


def test_context_install_apply_returns_disposer():
    class P:
        name = "p"

        def apply(self, ctx, config):
            ctx.provide("p_svc", 1)
            return lambda: None
    ctx = Context()
    ctx.install(P())
    assert ctx.get("p_svc") == 1


# ── GameEngine 兼容层 ────────────────────────────────

def test_engine_add_core_provides_services():
    engine = GameEngine()
    engine.add_core()
    assert engine.world is not None
    assert engine.bus is not None
    assert engine.loop is not None
    assert engine.ctx.get("world") is engine.world
    assert engine.ctx.get("bus") is engine.bus


def test_engine_add_systems_get():
    engine = GameEngine()
    engine.add_core().add_world().add_systems()
    assert engine.get("inventory") is not None
    assert engine.get("puzzles") is not None
    assert engine.get("commands") is not None
    assert engine.get("saves") is not None
    assert engine.get("no_such") is None
    assert engine.has("inventory")
    assert not engine.has("no_such")


def test_engine_add_idempotent():
    engine = GameEngine()
    engine.add_core()
    world = engine.world
    engine.add_core()
    assert engine.world is world  # 复用，不重建


def test_engine_mount_plugin_provides_service():
    engine = GameEngine()
    engine.add_core()
    engine.mount(_HelloPlugin(), {"name": "game"})
    assert engine.get("hello") == "hi:game"
    assert engine.ctx.get("hello") == "hi:game"


def test_engine_unload_runs_disposer():
    engine = GameEngine()
    engine.add_core()

    class Track:
        def __init__(self):
            self.flag = []
            self.name = "track"

        def apply(self, ctx, config):
            ctx.provide("track_svc", self, dispose=lambda: self.flag.append("off"))
            return None

    t = Track()
    engine.mount(t)
    assert engine.has("track_svc")
    assert engine.unload("track_svc") is True
    assert t.flag == ["off"]
    assert not engine.has("track_svc")


def test_engine_shutdown_then_readd():
    engine = GameEngine()
    engine.add_core().add_world().add_systems()
    engine.shutdown()
    assert engine.world is None
    # 可重新装配
    engine.add_core().add_world()
    assert engine.world is not None
    assert engine.state is not None


# ── EventBus 分派模式 ────────────────────────────────

def test_eventbus_waterfall_transform():
    bus = EventBus()

    @bus.subscribe("damage")
    def double(value, next):
        return next(value * 2)

    @bus.subscribe("damage")
    def plus_one(value, next):
        return next(value + 1)

    assert bus.waterfall("damage", 10) == 21


def test_eventbus_waterfall_short_circuit():
    bus = EventBus()
    calls = []

    @bus.subscribe("stop")
    def blocker(value, next):
        calls.append("blocker")
        return "blocked"  # 不调用 next → 短路

    @bus.subscribe("stop")
    def late(value, next):
        calls.append("late")
        return next(value)

    assert bus.waterfall("stop", 1) == "blocked"
    assert calls == ["blocker"]


def test_eventbus_waterfall_no_listeners_passthrough():
    bus = EventBus()
    assert bus.waterfall("nobody", 7) == 7


def test_eventbus_serial_short_circuit():
    bus = EventBus()

    @bus.subscribe("vote")
    def first(value):
        return None  # 弃权

    @bus.subscribe("vote")
    def second(value):
        return "locked"

    @bus.subscribe("vote")
    def third(value):
        return "never"

    assert bus.serial("vote", {}) == "locked"


def test_eventbus_serial_all_none_returns_none():
    bus = EventBus()

    @bus.subscribe("vote2")
    def nop(value):
        return None

    assert bus.serial("vote2", {}) is None
