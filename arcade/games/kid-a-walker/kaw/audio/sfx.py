# -*- coding: utf-8 -*-
"""短促音效播放器（拾取 / 预警 / 护盾）。"""
import time

import numpy as np
import pygame

from ..config import SR

# ─────────────────────── 音效播放器（SFX） ─────────────────────────
class SFXPlayer:
    """简易音效播放器，不影响 ZoneSynth BGM"""
    def __init__(self, enabled: bool = True):
        self.enabled = enabled
        self._last_warning_t = 0.0  # 防止预警音效过于频繁

    def play_collect(self, deco_type: int):
        """拾取音效：根据碎片类型变化音高"""
        if not self.enabled:
            return
        try:
            freq = 400 + deco_type * 50
            snd = self._synth_beep(freq, 0.08)
            snd.play()
        except Exception:
            pass

    def play_warning(self):
        """危险预警蜂鸣"""
        if not self.enabled:
            return
        now = time.monotonic()
        if now - self._last_warning_t < 1.0:
            return  # 每秒最多一次
        self._last_warning_t = now
        try:
            snd = self._synth_beep(200, 0.15)
            snd.play()
        except Exception:
            pass

    def play_shield(self):
        """护盾激活音效"""
        if not self.enabled:
            return
        try:
            snd = self._synth_beep(800, 0.2)
            snd.play()
        except Exception:
            pass

    def _synth_beep(self, freq: float, duration: float) -> pygame.mixer.Sound:
        """合成短促蜂鸣音"""
        n_samples = int(SR * duration)
        t = np.linspace(0, duration, n_samples, dtype=np.float32)
        wave = np.sin(2 * np.pi * freq * t).astype(np.float32)
        # 简单包络
        env = np.ones(n_samples, dtype=np.float32)
        fade = min(n_samples // 4, 200)
        if fade > 0:
            env[:fade] = np.linspace(0, 1, fade)
            env[-fade:] = np.linspace(1, 0, fade)
        pcm = (wave * env * 0.3).astype(np.float32)
        i16 = np.clip(pcm * 32767, -32768, 32767).astype(np.int16)
        stereo = np.ascontiguousarray(np.column_stack([i16, i16]))
        return pygame.sndarray.make_sound(stereo)
