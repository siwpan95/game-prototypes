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
_master = 0.7                # 主音量：5 个音乐分层 + 引擎音叠加，留足不削波
_rec = None            # 录音落盘用：(wave handle, 已写帧数)
_cb_calls = 0          # 音频回调被调用次数（心跳）
_cb_errors = 0         # 回调内异常次数


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


class _Channel:
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
        if nf == 0:                      # 空音频：直接停掉，别做取模
            ch.playing = False
            continue
        start = ch.pos
        end = start + frames
        if end <= nf:
            seg = d[int(start):int(end)]
            ch.pos = end
            if ch.loops != -1 and ch.pos >= nf:
                ch.playing = False
        elif ch.loops == -1:
            # 循环拼接
            idx = np.arange(int(start), int(end)) % nf
            seg = d[idx]
            ch.pos = end % nf
        else:
            # 一次性音效：剩余数据比一个块还长时，**只取本块能装下的部分**。
            # ⚠️ 早期写法是 seg[:take] = d[start:]，当 take > frames 会因形状
            # 不匹配抛广播异常 → 整个 _mix 中断 → 该通道此后每帧都抛 →
            # 混音链彻底哑掉（表现为撞毁后声音消失、录像音轨被截断）。
            seg = np.zeros((frames, 2), dtype=np.float32)
            start_i = int(start)
            take = min(nf - start_i, frames)
            if take > 0:
                seg[:take] = d[start_i:start_i + take]
            ch.pos = start_i + take
            if ch.pos >= nf:
                ch.playing = False
        # 淡出处理：斜坡按"已播样本数"线性下降。
        # ⚠️ 不能写成 ramp[fade_idx : fade_idx + n] 的切片形式：fade_idx 超过
        # fade_steps 时切片为空 → 广播异常 → 整个 _mix 中断 → 音频哑掉，
        # 而且 playing=False 位于异常之后，永远设不上（每帧都抛）。
        if ch.fade_steps > 0:
            n = seg.shape[0]
            idx = np.arange(ch.fade_idx, ch.fade_idx + n, dtype=np.float32)
            ramp = np.clip(1.0 - idx / ch.fade_steps, 0.0, 1.0) * ch.fade_from
            # ramp 是 (n,)，seg 是 (n,2)：必须沿声道轴展开，否则广播失败
            seg = seg * ramp[:, np.newaxis]
            ch.fade_idx += n
            if ch.fade_idx >= ch.fade_steps:
                ch.playing = False
        # 兜底：切片长度异常时补齐/截断，避免广播异常拖垮整条混音链
        if seg.shape[0] != frames:
            if seg.shape[0] > frames:
                seg = seg[:frames]
            else:
                pad = np.zeros((frames - seg.shape[0], 2), dtype=np.float32)
                seg = np.concatenate([seg, pad], axis=0)
        out += seg * ch.volume
    np.clip(out * _master, -1.0, 1.0, out=out)
    outdata[:] = out
    _write_recording(out)


# ── 录音（把混音输出落盘，供录像配音用）──────────────────────────
def enable_recording(path):
    """开始把混音输出写成 WAV（16bit 立体声）。返回路径。"""
    global _rec
    with _lock:
        disable_recording()
        w = wave.open(str(path), 'wb')
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(_sr)
        _rec = w
    return str(path)


def disable_recording():
    """停止并关闭录音文件。"""
    global _rec
    with _lock:
        if _rec is not None:
            try:
                _rec.close()
            except Exception:
                pass
            _rec = None


def _write_recording(out):
    """在音频回调线程里把混合结果写进 WAV（float32 → int16）。"""
    if _rec is None:
        return
    try:
        pcm = (np.clip(out, -1.0, 1.0) * 32767.0).astype('<i2')
        _rec.writeframes(pcm.tobytes())
    except Exception:
        pass


def _callback(outdata, frames, time_info, status):
    global _cb_calls, _cb_errors
    _cb_calls += 1
    try:
        _mix(outdata, frames)
    except Exception as e:
        _cb_errors += 1
        outdata[:] = 0.0
        if _cb_errors <= 3:              # 只报前几次，避免刷屏
            import traceback
            print(f'[sd_mixer] callback error #{_cb_errors}: {e!r}\n'
                  f'{traceback.format_exc()[-900:]}')


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
            _channels[i] = _Channel(i)


def get_channel(idx):
    """取（或惰性创建）编号为 idx 的**已注册**通道。"""
    if idx not in _channels:
        set_num_channels(idx + 8)
    return _channels[idx]


def Channel(idx):
    """与 ``pygame.mixer.Channel(idx)`` 同义：按编号取通道。

    ⚠️ 必须返回**注册表里那一条**——混音器只遍历 ``_channels`` 里的通道。
    若这里每次都 new 一个，播放指令（play/set_volume）就落在没人混音的
    孤立对象上，结果是"日志显示加载成功、实际一点声音都没有"。
    """
    return get_channel(idx)


def quit():
    global _stream, _enabled
    disable_recording()
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
