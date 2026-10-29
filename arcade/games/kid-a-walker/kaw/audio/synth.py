# -*- coding: utf-8 -*-
"""区域环境音效合成器：后台线程生成 PCM，区域间渐变过渡。"""
import math
import threading
import time

import numpy as np
import pygame

from ..config import BEAT, SEMITONES_DOWN, SR, VOL

# ─────────────────────── 区域音效系统 ─────────────────────────
PITCH_RATIO = 2.0 ** (SEMITONES_DOWN / 12.0)
# 不同装饰物类型对应不同的音效风格
# 2: 青绿发光 - 空灵神秘  |  3: 红色警示 - 紧张警告  |  4: 金色宝库 - 庄严神圣
# 5: 绿色植被 - 自然平和  |  6: 紫色能量 - 科幻能量  |  7: 橙色出口 - 温暖引导
# 8: 灰色碎石 - 废墟沉默  |  9: 科技装饰 - 电子数字  |  A: 蓝色水晶 - 冰冷空灵
# B: 紫水晶 - 神秘魔法

# ── 音符频率表 ──
NOTE_FREQS = {
    "C3":130.81,"D3":146.83,"E3":164.81,"F3":174.61,"G3":196.00,"A3":220.00,"B3":246.94,
    "C4":261.63,"D4":293.66,"E4":329.63,"F4":349.23,"G4":392.00,"A4":440.00,"B4":493.88,
    "C5":523.25,"D5":587.33,"E5":659.26,"F5":698.46,"G5":783.99,"A5":880.00,"B5":987.77,
    "C6":1046.50,
}

# ── 区域音效配置 ──
class ZoneSound:
    """每个区域的音效配置"""
    def __init__(self, notes, bpm, waveform, scale_mode, reverb_dense, pitch_shift):
        self.notes = notes          # 音符列表
        self.bpm = bpm              # 节拍速度
        self.waveform = waveform    # 波形类型
        self.scale_mode = scale_mode # 音阶模式
        self.reverb_dense = reverb_dense  # 混响浓度
        self.pitch_shift = pitch_shift    # 音高偏移


ZONE_CONFIGS = {
    2: ZoneSound(["C4","E4","G4","C5","G4","E4","C4","E4"], 90, "sine", "minor", 0.5, 0),    # 空灵神秘
    3: ZoneSound(["Eb4","Eb4","Bb3","Eb4","Eb4","Bb3","F4","Eb4"], 130, "sawtooth", "blues", 0.2, 2),  # 紧张警告
    4: ZoneSound(["C4","G4","C5","E5","G4","C5","A4","G4"], 70, "organ", "major", 0.6, -1),  # 庄严神圣
    5: ZoneSound(["A3","C4","E4","G4","E4","C4","A3","D4"], 85, "sine", "pentatonic_minor", 0.4, -2),  # 自然平和
    6: ZoneSound(["F4","F#4","G4","A4","C5","A4","G4","F#4"], 140, "square", "phrygian", 0.3, 3),  # 科幻能量
    7: ZoneSound(["C4","E4","G4","C5","E5","G4","C5","E4"], 100, "triangle", "major", 0.35, 0),  # 温暖引导
    8: ZoneSound(["D3","D3","A3","D3","D3","A3","G3","D3"], 60, "sine", "minor", 0.15, -3),   # 废墟沉默
    9: ZoneSound(["G4","A4","C5","D5","C5","A4","G4","F4"], 160, "square", "chromatic", 0.25, 4),  # 电子数字
    10: ZoneSound(["C5","F5","C5","A4","F4","C4","G4","C5"], 75, "sine", "crystal", 0.7, 1),  # 冰冷空灵
    11: ZoneSound(["Bb3","Eb4","G4","C5","G4","Eb4","Bb3","D4"], 95, "sine", "mystic", 0.55, 2),  # 神秘魔法
    12: ZoneSound(["C5","E5","G5","C6","G5","E5","C5","E5"], 110, "triangle", "major", 0.6, 5),  # 传送门
}

# ── 基础波形合成 ──
def _wave(freq, phase, waveform, duration):
    """生成单周期波形"""
    samples = []
    for i in range(int(SR * duration)):
        t = (phase + i) / SR
        if waveform == "sine":
            val = math.sin(2 * math.pi * freq * t)
        elif waveform == "sawtooth":
            val = 2.0 * ((freq * t) % 1.0) - 1.0
        elif waveform == "square":
            val = 1.0 if (freq * t) % 1.0 < 0.5 else -1.0
        elif waveform == "triangle":
            p = (freq * t) % 1.0
            val = 4.0 * p - 1.0 if p < 0.5 else 3.0 - 4.0 * p
        elif waveform == "organ":
            # 管风琴多谐波
            val = (math.sin(2*math.pi*freq*t)*0.5 +
                   math.sin(4*math.pi*freq*t)*0.3 +
                   math.sin(6*math.pi*freq*t)*0.15 +
                   math.sin(8*math.pi*freq*t)*0.05)
        else:
            val = math.sin(2 * math.pi * freq * t)
        samples.append(val)
    return samples

def _apply_envelope(samples, attack=0.01, decay=0.05, sustain=0.7, release=0.1):
    """ADSR包络"""
    n = len(samples)
    a = int(attack * n)
    d = int(decay * n)
    r = int(release * n)
    for i in range(n):
        t = i / n
        if i < a:
            samples[i] *= i / a if a > 0 else 1
        elif i < a + d:
            samples[i] *= 1.0 - (1.0 - sustain) * (i - a) / d if d > 0 else sustain
        elif i < n - r:
            samples[i] *= sustain
        else:
            samples[i] *= sustain * (n - i) / r if r > 0 else 0
    return samples

def _apply_reverb(samples, delay_ms=80, decay=0.3):
    """简单混响"""
    delay = int(delay_ms * SR / 1000)
    out = list(samples)
    for i in range(delay, len(out)):
        out[i] += out[i - delay] * decay
    return out


class ZoneSynth:
    """区域环境音效合成器，支持区域间渐变过渡"""
    def __init__(self):
        self._lock = threading.Lock()
        self._current_zone = 2  # 当前区域
        self._prev_zone = 2     # 前一区域
        self._fade = 1.0        # 渐变进度：0.0=纯旧区，1.0=纯新区
        self._fade_rate = 0.08  # 每拍渐变步进（~12拍≈6秒完成过渡）
        self._cur_beat = 0
        self._prev_beat = 0
        self._queue = []
        self._q_lock = threading.Lock()
        self.running = True
        self._frames = int(SR * BEAT * 0.5)
        self._thread = threading.Thread(target=self._worker, daemon=True)
        self._thread.start()

    def set_zone(self, zone_type):
        """切换到指定区域（触发渐变）"""
        with self._lock:
            if self._current_zone != zone_type:
                self._prev_zone = self._current_zone
                self._prev_beat = self._cur_beat  # 继承旧区节拍
                self._current_zone = zone_type
                self._cur_beat = 0
                self._fade = 0.0  # 开始渐变

    def _get_zone_config(self, zone=None):
        """获取指定区域的音效配置"""
        z = zone if zone is not None else self._current_zone
        return ZONE_CONFIGS.get(z, ZONE_CONFIGS[2])

    def _get_freq(self, note_name, pitch_shift=0):
        """获取音符频率"""
        base = NOTE_FREQS.get(note_name, 440.0)
        return base * (2.0 ** (pitch_shift / 12.0)) * PITCH_RATIO

    def _gen_zone_pcm(self, zone, beat):
        """生成指定区域、指定节拍的PCM"""
        cfg = self._get_zone_config(zone)
        beat_dur = 60.0 / cfg.bpm
        note_dur = beat_dur * 0.8
        note_name = cfg.notes[int(beat) % len(cfg.notes)]
        if note_name is None:
            return np.zeros(self._frames, dtype=np.float32)
        freq = self._get_freq(note_name, cfg.pitch_shift)
        samples = _wave(freq, 0.0, cfg.waveform, note_dur)
        samples = _apply_envelope(samples, attack=0.02, decay=0.1, sustain=0.6, release=0.15)
        samples = _apply_reverb(samples, delay_ms=int(50 + cfg.reverb_dense * 80),
                               decay=0.2 + cfg.reverb_dense * 0.3)
        raw = np.array(samples[:self._frames], dtype=np.float32)
        if len(raw) < self._frames:
            raw = np.pad(raw, (0, self._frames - len(raw)))
        raw = np.tanh(raw * 1.2).astype(np.float32)
        return (raw * VOL).astype(np.float32)

    def _gen_pcm(self):
        """生成一拍PCM，渐变期间混合新旧区域"""
        with self._lock:
            cur_zone = self._current_zone
            prev_zone = self._prev_zone
            fade = self._fade
            cur_beat = self._cur_beat
            self._cur_beat += 0.5
            if fade < 1.0:
                prev_beat = self._prev_beat
                self._prev_beat += 0.5
                self._fade = min(1.0, fade + self._fade_rate)

        cur_pcm = self._gen_zone_pcm(cur_zone, cur_beat)

        if fade < 1.0:
            prev_pcm = self._gen_zone_pcm(prev_zone, prev_beat)
            # 渐变混合：fade从0→1，旧区权重递减，新区权重递增
            mixed = (cur_pcm * fade + prev_pcm * (1.0 - fade))
            return mixed.astype(np.float32)

        return cur_pcm

    def _make_sound(self, pcm):
        i16 = np.clip(pcm * 32767.0, -32768, 32767).astype(np.int16)
        stereo = np.ascontiguousarray(np.column_stack([i16, i16]))
        return pygame.sndarray.make_sound(stereo)

    def _worker(self):
        while self.running:
            with self._q_lock:
                qlen = len(self._queue)
            if qlen < 6:
                pcm = self._gen_pcm()
                snd = self._make_sound(pcm)
                with self._q_lock:
                    self._queue.append(snd)
            else:
                time.sleep(0.005)

    def pop_sound(self):
        with self._q_lock:
            return self._queue.pop(0) if self._queue else None


# ── 保持向后兼容的 WalkerSynth 别名 ──
WalkerSynth = ZoneSynth
