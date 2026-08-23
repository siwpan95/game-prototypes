# -*- coding: utf-8 -*-
"""audio_fx — M6 音效系统（可插拔后端，事件驱动）。

订阅现有游戏事件，映射到具体音效（dig/place/hit/death/hurt），用 pygame.mixer 程序合成短音
（无素材依赖）。headless / 无音频设备时自动回退 NullBackend（静音），play() 永不抛。

设计要点：
  - 后端抽象：PygameMixerBackend（真机有声）/ NullBackend（静音容错）。
  - 事件解耦：subscribe(bus) 自动接线，不新增事件。
  - headless 全兼容：init() 失败 → NullBackend；play() try/except 包裹。
"""
from __future__ import annotations

import math
import os
import struct
from typing import Dict, Optional

# 音频参数（与 pygame.mixer 初始化一致）。
_RATE = 22050

# 音效规格：(时长秒, 频率Hz 或 (起,止)扫频, 波形)。
_SPEC: Dict[str, tuple] = {
    "dig":   (0.08, 140.0, "square"),
    "place": (0.07, 260.0, "tri"),
    "hit":   (0.05, 620.0, "square"),
    "death": (0.40, (420.0, 70.0), "sweep"),
    "hurt":  (0.12, 300.0, "tri"),
}


def _pygame():
    """延迟导入 pygame；不可用时抛出清晰错误。"""
    import pygame
    if pygame is None:
        raise RuntimeError("需要 pygame 才能播放音效")
    return pygame


def _render_wave(name: str) -> bytes:
    """合成单条 16-bit 小端 PCM 波形（22050Hz 单声道）。"""
    dur, freq, kind = _SPEC[name]
    n = max(1, int(_RATE * dur))
    buf = bytearray()
    for i in range(n):
        t = i / _RATE
        if kind == "sweep":
            f = freq[0] + (freq[1] - freq[0]) * (t / dur)
        else:
            f = freq
        phase = 2.0 * math.pi * f * t
        if kind == "square":
            v = 1.0 if math.sin(phase) >= 0 else -1.0
        elif kind == "tri":
            v = 2.0 * abs(2.0 * (t * f - math.floor(t * f + 0.5))) - 1.0
        else:
            v = math.sin(phase)
        env = max(0.0, 1.0 - t / dur)          # 指数式衰减包络
        samp = int(v * env * 0.5 * 32767)
        buf += struct.pack("<h", samp)
    return bytes(buf)


class NullBackend:
    """静音后端（headless / 无音频设备）。"""

    def init(self) -> bool:
        return True

    def play(self, name: str) -> None:
        pass


class PygameMixerBackend:
    """pygame.mixer 后端（真机有声）。"""

    def __init__(self) -> None:
        self._ready = False
        self._sounds: Dict[str, object] = {}

    def init(self) -> bool:
        try:
            pg = _pygame()
            if pg.mixer.get_init() is None:
                pg.mixer.init(frequency=_RATE, size=-16, channels=1, buffer=512)
            self._ready = True
            return True
        except Exception:
            return False

    def play(self, name: str) -> None:
        if not self._ready:
            return
        pg = _pygame()
        if name not in self._sounds:
            self._sounds[name] = pg.mixer.Sound(buffer=_render_wave(name))
        self._sounds[name].play()


try:
    from alloy.audio import AudioSystem as _EngineAudioSystem
    _HAS_ENGINE_AUDIO = True
except Exception:  # noqa: BLE001 — 引擎音频不可用时静默降级
    _EngineAudioSystem = None
    _HAS_ENGINE_AUDIO = False


class EngineAudioBackend:
    """后端：复用 alloy.audio.AudioSystem 播放（统一引擎音频管线）。

    MC2 程序合成的 16-bit PCM 波形转为 float32 数组后交给引擎 AudioSystem 播放，
    实现「MC2 音效接入统一引擎」的整合目标。headless / 无 numpy 时静默降级，
    play() 永不抛。

    整合增强：可注入一个已存在的 AudioSystem（如统一产品内核的共享音频系统），
    使 MC1 / MC2 共用同一音频引擎；不注入时自建。
    """

    def __init__(self, audio_system: Optional[object] = None) -> None:
        self._audio = audio_system
        self._ready = audio_system is not None

    def init(self) -> bool:
        # 已注入共享音频系统：直接复用
        if self._audio is not None:
            self._ready = True
            return True
        if not _HAS_ENGINE_AUDIO:
            return False
        try:
            self._audio = _EngineAudioSystem()
            self._ready = True
            return True
        except Exception:  # noqa: BLE001
            self._ready = False
            return False

    def play(self, name: str) -> None:
        if not self._ready or self._audio is None:
            return
        try:
            import numpy as np
            pcm = _render_wave(name)                       # bytes, int16 小端
            arr = np.frombuffer(pcm, dtype="<i2").astype(np.float32) / 32768.0
            self._audio.play_sfx_from_array(arr, volume=0.5, sample_rate=_RATE)
        except Exception:  # noqa: BLE001 — 任何异常静默吞掉（headless 安全）
            pass


class SoundEngine:
    """音效引擎：管理后端 + 事件订阅映射。

    整合增强：可传入 audio_system（统一产品内核的共享 AudioSystem），
    使 MC2 音效接入与 MC1 同一套引擎音频管线。
    """

    def __init__(self, backend: Optional[object] = None,
                 audio_system: Optional[object] = None) -> None:
        self.backend = backend
        self._shared_audio = audio_system

    def init(self) -> bool:
        """选定后端：优先 alloy.audio.AudioSystem（可复用共享实例），
        失败回退 PygameMixer，再回退 Null（静音容错，headless 安全）。"""
        if self.backend is None:
            for BackendCls in (EngineAudioBackend, PygameMixerBackend):
                try:
                    b = BackendCls(audio_system=self._shared_audio) \
                        if BackendCls is EngineAudioBackend \
                        else BackendCls()
                    if b.init():
                        self.backend = b
                        break
                except Exception:  # noqa: BLE001
                    continue
            if self.backend is None:
                self.backend = NullBackend()
        return self.backend is not None

    def subscribe(self, bus) -> None:
        """订阅现有事件 → 音效映射（不新增事件）。"""
        if bus is None:
            return
        from mcclone.core.event_bus import EventTypes
        mapping = {
            EventTypes.BLOCK_BROKEN: "dig",
            EventTypes.BLOCK_PLACED: "place",
            EventTypes.CREATURE_HIT: "hit",
            EventTypes.CREATURE_DIED: "death",
            EventTypes.PLAYER_HIT: "hurt",
        }
        for ev, sname in mapping.items():
            bus.subscribe(ev, lambda _et, _d, _n=sname: self.play(_n))

    def play(self, name: str) -> None:
        """播放音效；任何异常静默吞掉（永不抛，headless 安全）。"""
        if self.backend is None:
            self.init()
        try:
            self.backend.play(name)
        except Exception:
            pass
