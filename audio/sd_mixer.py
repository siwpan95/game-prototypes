# -*- coding: utf-8 -*-
"""
sd_mixer —— sounddevice 版的轻量混音器后端，替换 pygame.mixer。

提供与 pygame.mixer 同名的表面 API（Sound / Channel / set_num_channels /
get_init / init / quit），让 music_system / sfx_system / audio_manager 在不依赖
pygame（pyglet 同进程会与 SDL 抢事件循环，不能用）的前提下，完整保留
Endless Highway 的 synthwave 分层音乐 + 引擎音 + 一次性音效。

实现要点：
- 输出：单条 ``sd.OutputStream`` 回调，按帧把各活跃声道混成双声道 float32。
- ``Sound``：读 WAV → numpy float32（自动 upmix 单声道 → 立体声），支持 16/24/32bit。
- ``Channel.play(sound, loops)``：loops=-1 循环；``set_volume`` 实时调音量；
  ``fadeout(ms)`` 在剩余采样内线性淡出后停止（避免爆音）。
- 无音频设备 / PortAudio 不可用时自动降级为静音（游戏照常运行，不崩溃）。
"""

from __future__ import annotations

import threading
import wave
from pathlib import Path

import numpy as np

try:
    import sounddevice as sd
except Exception:                       # 没有 PortAudio / sounddevice 装不上
    sd = None

_lock = threading.RLock()
_sr = 44100
_channels: dict = {}
_stream = None
_enabled = False
_master = 0.9


def _load_wav(path: str):
    with wave.open(str(path), 'rb') as w:
        sr = w.getframerate()
        n = w.getnframes()
        nch = w.getnchannels()
        sw = w.getsampwidth()
        raw = w.readframes(n)
    if sw == 2:
        data = np.frombuffer(raw, dtype='<i2').astype(np.float32) / 32768.0
    elif sw == 1:
        data = (np.frombuffer(raw, dtype=np.uint8).astype(np.float32) - 128.0) / 128.0
    elif sw == 4:
        data = np.frombuffer(raw, dtype='<i4').astype(np.float32) / 2147483648.0
    elif sw == 3:
        # 24bit：每 3 字节一个小端样本
        arr = np.frombuffer(raw, dtype=np.uint8).reshape(-1, 3).astype(np.float32)
        val = (arr[:, 0] | (arr[:, 1] << 8) | (arr[:, 2] << 16)).astype(np.int32)
        val = np.where(val & 0x800000, val - 0x1000000, val)
        data = val / 8388608.0
    else:
        data = np.zeros(0, dtype=np.float32)
    if nch == 1:
        data = np.repeat(data.reshape(-1, 1), 2, axis=1)
    else:
        data = data.reshape(-1, nch)[:, :2]
    return data, sr


class Sound:
    """一次加载的音频样本（双声道 float32）。"""

    def __init__(self, path):
        data, sr = _load_wav(path)
        self.path = path
        self.data = data
        self.sr = sr
        self.frames = data.shape[0]


class Channel:
    """单条播放声道（复用 pygame.mixer.Channel 的语义）。"""

    def __init__(self, idx):
        self.idx = idx
        self.sound: Sound | None = None
        self.pos = 0.0
        self.loops = 0
        self.volume = 0.0
        self.playing = False
        self.fade_steps = 0
        self.fade_idx = 0
        self.fade_from = 0.0

    def play(self, sound, loops=0, volume=1.0):
        with _lock:
            self.sound = sound
            self.pos = 0.0
            self.loops = loops
            self.volume = volume
            self.playing = True
            self.fade_steps = 0
            self.fade_idx = 0

    def stop(self):
        with _lock:
            self.playing = False

    def set_volume(self, v):
        with _lock:
            self.volume = v

    def get_volume(self):
        return self.volume

    def fadeout(self, ms):
        with _lock:
            if not self.playing or self.sound is None:
                return
            self.fade_steps = max(1, int(ms / 1000.0 * _sr))
            self.fade_idx = 0
            self.fade_from = self.volume


def _mix(outdata, frames):
    out = np.zeros((frames, 2), dtype=np.float32)
    for ch in _channels.values():
        if not ch.playing or ch.sound is None:
            continue
        d = ch.sound.data
        nf = d.shape[0]
        start = ch.pos
        end = start + frames
        if end <= nf:
            seg = d[int(start):int(end)]
            ch.pos = end
            if ch.loops != -1 and ch.pos >= nf:
                ch.playing = False
        else:
            if ch.loops == -1:
                # 循环拼接
                idx = np.arange(int(start), int(end)) % nf
                seg = d[idx]
                ch.pos = end % nf
            else:
                seg = np.zeros((frames, 2), dtype=np.float32)
                take = nf - int(start)
                if take > 0:
                    seg[:take] = d[int(start):]
                ch.pos = nf
                ch.playing = False
        # 淡出处理
        if ch.fade_steps > 0:
            if ch.fade_idx + frames >= ch.fade_steps:
                rem = ch.fade_steps - ch.fade_idx
                fade = np.linspace(ch.fade_from, 0.0, ch.fade_steps)
                seg = seg * fade[ch.fade_idx:ch.fade_idx + frames][: seg.shape[0]]
                ch.playing = False
            else:
                fade = ch.fade_from * (1.0 - (ch.fade_idx + np.arange(frames)) / ch.fade_steps)
                seg = seg * fade[:seg.shape[0]]
                ch.fade_idx += frames
        out += seg * ch.volume
    np.clip(out * _master, -1.0, 1.0, out=out)
    outdata[:] = out


def _callback(outdata, frames, time_info, status):
    try:
        _mix(outdata, frames)
    except Exception:
        outdata[:] = 0.0


def init(frequency=44100, size=-16, channels=2, buffer=512):
    """初始化后端并启动输出流。失败则降级为静音（不抛异常）。"""
    global _sr, _stream, _enabled, _channels
    _sr = frequency
    if sd is None:
        _enabled = False
        return None
    try:
        _stream = sd.OutputStream(
            samplerate=_sr, channels=channels, blocksize=buffer, callback=_callback)
        _stream.start()
        _enabled = True
    except Exception as e:            # 无音频设备 / 设备被占用
        print(f"[sd_mixer] audio device unavailable ({e}); running silent.")
        _stream = None
        _enabled = False
    return get_init()


def get_init():
    if _stream is not None and _enabled:
        return (_sr, -16, 2)
    return None


def set_num_channels(n):
    for i in range(n):
        if i not in _channels:
            _channels[i] = Channel(i)


def get_channel(idx):
    if idx not in _channels:
        set_num_channels(idx + 8)
    return _channels[idx]


def quit():
    global _stream, _enabled
    if _stream is not None:
        try:
            _stream.stop()
            _stream.close()
        except Exception:
            pass
        _stream = None
    _enabled = False


# ── 兼容层：让使用者可以 ``from . import sd_mixer as mixer`` 后
#    直接 ``mixer.Sound(...) / mixer.Channel(...) / mixer.init(...)`` ──
def Sound_compat(path):
    return Sound(path)
