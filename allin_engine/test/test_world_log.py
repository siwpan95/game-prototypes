"""
世界事件日志（WorldLog）行为测试
================================

覆盖 P3（日志即事实源）验收项：
    - 追加式事件流与快照点
    - 投影折叠（状态由日志推导，三方不矛盾）
    - 事件总线桥（track / disposer）
    - JSON 持久化往返
    - 确定性（同 seed 事件流一致 / 异 seed 不同）
    - 快照 + 日志增量重建 == 直接运行结果
    - GameEngine 提供 log 服务
    - SaveLoadManager 快照+日志模式
"""

from __future__ import annotations

import json
import os
import random
import tempfile

from allin_engine import GameEngine
from allin_engine.core import EventBus, WorldLog
from allin_engine.systems import SaveLoadManager


# ── 追加 / 快照点 ────────────────────────────────────

def test_worldlog_append_increments_seq():
    log = WorldLog()
    e1 = log.append("move", {"x": 1})
    e2 = log.append("move", {"x": 2})
    assert e1["seq"] == 1
    assert e2["seq"] == 2
    assert log.seq == 2


def test_worldlog_entries_in_order():
    log = WorldLog()
    for i in range(5):
        log.append("tick", i)
    assert [e["seq"] for e in log.entries()] == [1, 2, 3, 4, 5]


def test_worldlog_entries_since():
    log = WorldLog()
    for i in range(5):
        log.append("tick", i)
    assert log.checkpoint() == 5
    log.append("tick", 5)
    after = log.entries_since(5)
    assert len(after) == 1 and after[0]["payload"] == 5


def test_worldlog_len():
    log = WorldLog()
    log.append("a")
    log.append("b")
    assert len(log) == 2


# ── 投影 ─────────────────────────────────────────────

def test_worldlog_projection_folds_events():
    log = WorldLog()
    log.register_projection("hp", 100, lambda s, e: s + e["payload"] if e["type"] == "heal" else s)
    log.append("heal", 10)
    log.append("heal", 5)
    assert log.get_projection("hp") == 115


def test_worldlog_projection_unknown_key_raises():
    log = WorldLog()
    try:
        log.get_projection("nope")
        raise AssertionError("应当 KeyError")
    except KeyError:
        pass


def test_worldlog_rebuild_projection():
    log = WorldLog()
    log.register_projection("sum", 0, lambda s, e: s + e["payload"])
    log.append("n", 1)
    log.append("n", 2)
    log._entries.clear()  # 模拟加载时绕过 append 后投影失同步
    assert log.rebuild_projection("sum") == 0  # 日志已被清空 → 0
    log.append("n", 7)
    assert log.get_projection("sum") == 7


# ── 事件总线桥 ──────────────────────────────────────

def test_worldlog_track_bridges_bus_events():
    bus = EventBus()
    log = WorldLog()
    dispose = log.track(bus, ["item_take", "combat_end"])
    bus.emit("item_take", {"name": "钥匙"})
    bus.emit("combat_end", {"won": True})
    bus.emit("room_enter", None)  # 未跟踪的类型不入日志
    assert len(log) == 2
    assert [e["type"] for e in log.entries()] == ["item_take", "combat_end"]
    dispose()
    bus.emit("item_take", {"name": "钥匙2"})
    assert len(log) == 2  # 解除桥接后不再追加


# ── 持久化 ──────────────────────────────────────────

def test_worldlog_save_load_roundtrip():
    log = WorldLog(source="test")
    log.append("a", 1)
    log.append("b", {"x": [1, 2]})
    with tempfile.TemporaryDirectory() as tmp:
        p = os.path.join(tmp, "log.json")
        log.save_to(p)
        loaded = WorldLog.load_from(p)
    assert loaded.source == "test"
    assert loaded.seq == 2
    assert loaded.entries() == log.entries()


# ── 确定性 ──────────────────────────────────────────

def _seeded_run(seed: int) -> str:
    rng = random.Random(seed)
    log = WorldLog()
    for _ in range(200):
        log.append("dice", rng.randint(1, 6))
        log.append("loot", rng.choice(["sword", "potion", "coin"]))
    return log.deterministic_dump()


def test_worldlog_deterministic_same_seed():
    assert _seeded_run(7) == _seeded_run(7)


def test_worldlog_deterministic_diff_seed():
    assert _seeded_run(7) != _seeded_run(1)


# ── 快照 + 投影重建 == 直接运行 ─────────────────────

def test_worldlog_snapshot_rebuild_equals_direct():
    """存档=快照+日志增量；重建（快照 + 折叠增量）== 直接运行终态。"""
    rng = random.Random(42)
    log = WorldLog()
    log.register_projection("state", {"hp": 100}, lambda s, e: (
        {"hp": s["hp"] + e["payload"]["delta"]} if e["type"] == "damage" else s
    ))

    # 直接运行 60 步
    for _ in range(60):
        log.append("damage", {"delta": -rng.randint(1, 5)})
    direct = log.get_projection("state")

    # 模拟：第 30 步存快照，第 31-60 步继续，崩溃后重建
    snapshot = {"hp": 100}
    for e in log.entries()[:30]:
        snapshot = {"hp": snapshot["hp"] + e["payload"]["delta"]}
    offset = log.entries()[29]["seq"]  # 快照点 30

    # 直接用 entries_since 模拟 load_with_log 的增量
    events_after = log.entries_since(offset)
    rebuilt = dict(snapshot)
    for e in events_after:
        rebuilt = {"hp": rebuilt["hp"] + e["payload"]["delta"]}
    assert rebuilt == direct


# ── GameEngine 集成 ─────────────────────────────────

def test_engine_provides_log_service():
    engine = GameEngine()
    engine.add_core()
    assert engine.log is not None
    assert engine.ctx.get("log") is engine.log
    engine.log.append("boot", {"seed": 1})
    assert engine.log.seq == 1


def test_engine_unload_log():
    engine = GameEngine()
    engine.add_core()
    assert engine.unload("log") is True
    assert engine.log is None
    assert not engine.has("log")


# ── SaveLoadManager 快照+日志模式 ───────────────────

def test_saveload_snapshot_log_roundtrip():
    from allin_engine.world import GameState
    with tempfile.TemporaryDirectory() as tmp:
        mgr = SaveLoadManager(tmp)
        log = WorldLog()
        state = GameState()
        state.set_flag("boss_down", True)
        assert mgr.save_with_log(state, slot=0, log=log) is True  # 快照 + 空日志落盘(offset=0)
        log.append("after_save", 1)
        log.append("after_save", 2)
        # 真实游戏在自动存档/退出时刷新日志文件
        log.save_to(mgr._slot_path(0) + ".log")
        out = mgr.load_with_log(slot=0, log=log)
    assert out is not None
    assert out["snapshot"]["player"]["flags"]["boss_down"] is True
    assert out["log_offset"] == 0
    assert [e["type"] for e in out["events_after"]] == ["after_save", "after_save"]


# ── 审计摘要（CLI 同款） ────────────────────────────

def test_worldlog_audit_summary():
    log = WorldLog()
    log.append("move", 1)
    log.append("move", 2)
    log.append("combat", "win")
    from allin_engine.cli import _summarize_entries
    summary = _summarize_entries(log.entries())
    assert summary["by_type"] == {"combat": 1, "move": 2}
    assert len(summary["sample"]) == 3
