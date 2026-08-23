# -*- coding: utf-8 -*-
"""test_m6_audio — M6 音效系统（audio_fx，T-M6-04/05/06）。

事件→音效映射用记录型后端断言；SoundEngine.init 在 headless（无 pygame）下回退 NullBackend，
play() 永不抛。无需真实音频设备。
"""
from __future__ import annotations

from mcclone.core.event_bus import EventBus, EventTypes
from mcclone.audio.audio_fx import SoundEngine, NullBackend


class _RecBackend(NullBackend):
    """记录 play 调用的后端（不依赖音频设备）。"""

    def __init__(self) -> None:
        super().__init__()
        self.calls: list = []

    def play(self, name: str) -> None:
        self.calls.append(name)


def test_event_to_sound_mapping():
    bus = EventBus()
    eng = SoundEngine(backend=_RecBackend())
    eng.subscribe(bus)
    bus.emit(EventTypes.BLOCK_BROKEN)
    bus.emit(EventTypes.BLOCK_PLACED)
    bus.emit(EventTypes.CREATURE_HIT)
    bus.emit(EventTypes.CREATURE_DIED)
    bus.emit(EventTypes.PLAYER_HIT)
    assert eng.backend.calls == ["dig", "place", "hit", "death", "hurt"]


def test_play_never_raises():
    eng = SoundEngine(backend=NullBackend())
    for n in ("dig", "place", "hit", "death", "hurt"):
        eng.play(n)                       # 静音后端，绝不抛


def test_init_falls_back_when_no_backend():
    # headless（conftest 屏蔽 pygame）→ PygameMixerBackend.init 失败 → NullBackend
    eng = SoundEngine()
    ok = eng.init()
    assert ok is True
    assert eng.backend is not None


def test_subscribe_is_idempotent_and_safe():
    bus = EventBus()
    eng = SoundEngine(backend=_RecBackend())
    eng.subscribe(bus)
    eng.subscribe(bus)                    # 重复订阅不崩
    bus.emit(EventTypes.BLOCK_BROKEN)
    assert eng.backend.calls.count("dig") == 2
