# -*- coding: utf-8 -*-
"""test_m6_particles — M6 粒子系统（particles，T-M6-07/08/09）。

纯逻辑 update / 事件订阅生成；draw 在 screen=None 时 no-op（headless 安全）。不依赖 pygame。
"""
from __future__ import annotations

from mcclone.core.geometry import AABB2D
from mcclone.core.event_bus import EventBus, EventTypes
from mcclone.render.particles import ParticleSystem


class _Cam:
    """最小相机桩：提供 viewport。"""

    def __init__(self) -> None:
        self.viewport = AABB2D(0, 0, 15, 15)


class _Renderer:
    """最小渲染器桩：screen=None（headless）。"""

    screen = None


def test_spawn_break_count():
    ps = ParticleSystem()
    ps.spawn_break(1.0, 1.0, (200, 0, 0))
    assert len(ps._ps) == 8


def test_update_removes_dead():
    ps = ParticleSystem()
    ps.spawn_break(1.0, 1.0, (200, 0, 0))
    n0 = len(ps._ps)
    for _ in range(200):
        ps.update(0.02)                   # 累计 4s，远超粒子生命
    assert n0 > 0 and len(ps._ps) == 0


def test_max_cap_enforced():
    ps = ParticleSystem(max_particles=50)
    for _ in range(200):
        ps.spawn_step(1, 1)
    assert len(ps._ps) <= 50


def test_draw_headless_noop():
    ps = ParticleSystem()
    ps.spawn_break(1, 1, (200, 0, 0))
    ps.draw(_Cam(), _Renderer())         # screen=None → 不抛


def test_subscribe_block_broken_generates():
    bus = EventBus()
    ps = ParticleSystem()
    ps.subscribe(bus, None)
    bus.emit(EventTypes.BLOCK_BROKEN, x=2, y=3, id=1)
    assert len(ps._ps) >= 1


def test_subscribe_step_event_generates():
    bus = EventBus()
    ps = ParticleSystem()
    ps.subscribe(bus, None)
    bus.emit(EventTypes.PLAYER_STEP, x=1, y=1)
    assert len(ps._ps) >= 1


def test_creature_died_generates_with_kind_color():
    bus = EventBus()
    ps = ParticleSystem()
    ps.subscribe(bus, None)
    bus.emit(EventTypes.CREATURE_DIED, kind="ZOMBIE", x=2.0, y=3.0, drops=[])
    assert len(ps._ps) >= 1
