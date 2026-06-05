#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
============================================
  卡瑞玛拉：枯肢之下 — 音频制作引擎
  Carimara: Beneath the Forlorn Limbs
  程序化音频合成 + WAV 批量导出
  Version: 1.0.0
============================================

音色风格：阴暗小调 · 宅邸低语 · 记忆残响
用法:
  python faatt.py --batch       # 导出全部
  python faatt.py --sfx         # 仅 SFX
  python faatt.py --music       # 仅音乐
  python faatt.py --duration 60 # 音乐时长
"""

import numpy as np
from scipy.io import wavfile
import argparse
from dataclasses import dataclass, field
from typing import List, Tuple, Optional
from enum import Enum
from pathlib import Path

SR = 44100
ROOT = Path(__file__).resolve().parent
OUTPUT_DIR = ROOT / "assets" / "audio"

NOTES = {
    "C2": 65.41,  "D2": 73.42,  "Eb2": 77.78,  "F2": 87.31,
    "G2": 98.00,  "Ab2": 103.83, "Bb2": 116.54,
    "C3": 130.81, "D3": 146.83, "Eb3": 155.56, "F3": 174.61,
    "G3": 196.00, "Ab3": 207.65, "Bb3": 233.08,
    "C4": 261.63, "D4": 293.66, "Eb4": 311.13, "F4": 349.23,
    "G4": 392.00, "Ab4": 415.30, "Bb4": 466.16,
    "C5": 523.25, "D5": 587.33, "Eb5": 622.25, "F5": 698.46,
    "G5": 783.99, "Ab5": 830.61, "Bb5": 932.33,
}

def note_to_freq(note: str) -> float:
    return NOTES.get(note, 261.63)

def freq_mod(base_freq: float, semitones: float) -> float:
    return base_freq * (2.0 ** (semitones / 12.0))

# ---- Enums ----
class OscType(Enum):
    SINE = "sine"; TRIANGLE = "triangle"; SAW = "saw"
    SQUARE = "square"; NOISE_PINK = "noise_pink"
    NOISE_BROWN = "noise_brown"; NOISE_WHITE = "noise_white"

class EnvShape(Enum):
    PERCUSSIVE = "percussive"; PAD = "pad"; PLUCK = "pluck"
    SWELL = "swell"; REVERSE = "reverse"

# ---- Dataclasses ----
@dataclass
class EffectChain:
    lp_filter_hz: float = 0.0
    hp_filter_hz: float = 0.0
    distortion: float = 0.0
    reverb_mix: float = 0.0
    reverb_decay: float = 0.0
    stereo_width: float = 0.0

@dataclass
class SynthVoice:
    freq: float
    osc_type: OscType
    duration: float
    volume: float
    env_shape: EnvShape
    effect_chain: EffectChain = field(default_factory=EffectChain)
    pitch_mod: float = 0.0
    vibrato_rate: float = 0.0
    vibrato_depth: float = 0.0
    harmonics: List[Tuple[float, float]] = field(default_factory=list)

@dataclass
class MusicPattern:
    name: str
    notes: List[str]
    durations: List[float]
    bpm: float
    loop: bool
    osc_type: OscType
    volume: float
    env_shape: EnvShape
    harmonics: List[Tuple[float, float]] = field(default_factory=list)
    vibrato_rate: float = 0.0
    vibrato_depth: float = 0.0
    reverb_mix: float = 0.0
    reverb_decay: float = 0.0
    stereo_width: float = 0.0
    lp_filter_hz: float = 0.0
    distortion: float = 0.0
    pitch_mod: float = 0.0

# ---- Oscillators ----
def _osc_sine(phase):
    return np.sin(2.0 * np.pi * phase)

def _osc_triangle(phase):
    return 4.0 * np.abs(phase - 0.5) - 1.0

def _osc_saw(phase):
    return 2.0 * phase - 1.0

def _osc_square(phase):
    return np.where(phase < 0.5, 1.0, -1.0)

def _noise_white(n_samples):
    return np.random.uniform(-1.0, 1.0, n_samples).astype(np.float32)

def _noise_pink(n_samples):
    octaves = 8
    out = np.zeros(n_samples, dtype=np.float32)
    for o in range(octaves):
        step = 1 << o
        n_segs = (n_samples + step - 1) // step
        vals = np.random.uniform(-1.0, 1.0, n_segs).astype(np.float32)
        for i in range(n_segs):
            s = i * step; e = min((i + 1) * step, n_samples)
            out[s:e] += vals[i]
    pk = np.max(np.abs(out))
    return (out / pk) if pk > 0 else out

def _noise_brown(n_samples):
    w = np.random.uniform(-0.3, 0.3, n_samples).astype(np.float32)
    b = np.cumsum(w)
    pk = np.max(np.abs(b))
    return (b / pk) if pk > 0 else b

def generate_oscillator(osc_type: OscType, freq: float, duration: float,
                        vibrato_rate: float = 0.0, vibrato_depth: float = 0.0) -> np.ndarray:
    n = int(SR * duration); n = max(1, n)
    t = np.arange(n, dtype=np.float32) / SR
    # vibrato: modulate frequency
    if vibrato_rate > 0 and vibrato_depth > 0:
        mod = np.sin(2.0 * np.pi * vibrato_rate * t)
        freq_inst = freq * (1.0 + (vibrato_depth / 12.0) * mod)
        phase = np.cumsum(freq_inst) / SR
        phase -= np.floor(phase)
    else:
        phase = (t * freq) % 1.0
    if osc_type == OscType.SINE: return _osc_sine(phase).astype(np.float32)
    if osc_type == OscType.TRIANGLE: return _osc_triangle(phase).astype(np.float32)
    if osc_type == OscType.SAW: return _osc_saw(phase).astype(np.float32)
    if osc_type == OscType.SQUARE: return _osc_square(phase).astype(np.float32)
    if osc_type == OscType.NOISE_WHITE: return _noise_white(n).astype(np.float32)
    if osc_type == OscType.NOISE_PINK: return _noise_pink(n).astype(np.float32)
    if osc_type == OscType.NOISE_BROWN: return _noise_brown(n).astype(np.float32)
    return np.zeros(n, dtype=np.float32)

# ---- Envelopes ----
def generate_envelope(env_shape: EnvShape, n_samples: int) -> np.ndarray:
    if n_samples <= 0: return np.array([0.0], dtype=np.float32)
    env = np.ones(n_samples, dtype=np.float32)
    if env_shape == EnvShape.PERCUSSIVE:
        a = max(1, int(0.005 * SR))
        d_end = min(n_samples, max(a + 1, int(0.1 * SR)))
        env[:a] = np.linspace(0, 1, a)
        env[a:d_end] = np.exp(-np.linspace(0, 4, d_end - a))
        if d_end < n_samples: env[d_end:] = 0.0
    elif env_shape == EnvShape.PAD:
        a = max(1, int(0.15 * SR))
        r_start = max(a, int(n_samples * 0.85))
        env[:a] = np.linspace(0, 1, a)
        if r_start < n_samples:
            env[r_start:] = np.exp(-np.linspace(0, 3, n_samples - r_start))
    elif env_shape == EnvShape.PLUCK:
        a = max(1, int(0.001 * SR))
        env[:a] = np.linspace(0, 1, a)
        env[a:] = np.exp(-np.linspace(0, 6, n_samples - a))
    elif env_shape == EnvShape.SWELL:
        half = n_samples // 2
        env[:half] = np.linspace(0, 1, half)
        env[half:] = np.exp(-np.linspace(0, 2, n_samples - half))
    elif env_shape == EnvShape.REVERSE:
        env = np.exp(-np.linspace(0, 4, n_samples))
    return env.astype(np.float32)

# ---- Effects ----
def apply_lowpass(sig: np.ndarray, cutoff_hz: float) -> np.ndarray:
    if cutoff_hz <= 0 or cutoff_hz >= SR / 2: return sig.astype(np.float32)
    dt = 1.0 / SR; rc = 1.0 / (2.0 * np.pi * cutoff_hz)
    alpha = dt / (rc + dt)
    y = np.zeros_like(sig, dtype=np.float32); y[0] = sig[0]
    for i in range(1, len(sig)):
        y[i] = y[i-1] + alpha * (sig[i] - y[i-1])
    return y

def apply_highpass(sig: np.ndarray, cutoff_hz: float) -> np.ndarray:
    if cutoff_hz <= 0: return sig.astype(np.float32)
    lp = apply_lowpass(sig, cutoff_hz)
    return (sig - lp).astype(np.float32)

def apply_distortion(sig: np.ndarray, amount: float) -> np.ndarray:
    if amount <= 0: return sig.astype(np.float32)
    gain = 1.0 + amount * 8.0
    return np.tanh(sig * gain).astype(np.float32)

def apply_reverb(sig: np.ndarray, mix: float, decay: float) -> np.ndarray:
    if mix <= 0: return sig.astype(np.float32)
    n = len(sig)
    out = sig.copy().astype(np.float32)
    delays = [int(SR * d) for d in [0.0297, 0.0371, 0.0413, 0.0437]]
    fb = decay * 0.5
    for dly in delays:
        if dly >= n: continue
        wet = np.zeros(n, dtype=np.float32)
        for i in range(dly, n):
            wet[i] = out[i] + fb * wet[i - dly]
        out += wet * (decay * 0.2)
    pk = np.max(np.abs(out))
    if pk > 1.0: out /= pk
    return (sig * (1.0 - mix) + out * mix).astype(np.float32)

def apply_stereo(sig: np.ndarray, width: float) -> np.ndarray:
    if width <= 0: return np.array([sig, sig])
    n = len(sig)
    shift = min(n, int(SR * 0.005))
    side = np.roll(sig, shift); side[:shift] = 0
    left = sig + side * width
    right = sig - side * width
    pk = max(np.max(np.abs(left)), np.max(np.abs(right)))
    if pk > 1.0: left /= pk; right /= pk
    return np.array([left.astype(np.float32), right.astype(np.float32)])

def _safe_clip(sig: np.ndarray) -> np.ndarray:
    pk = np.max(np.abs(sig))
    if pk > 1.0: sig = sig / pk
    return np.clip(sig, -1.0, 1.0).astype(np.float32)

def process_effects(sig: np.ndarray, chain: EffectChain) -> np.ndarray:
    if chain.hp_filter_hz > 0: sig = apply_highpass(sig, chain.hp_filter_hz)
    if chain.lp_filter_hz > 0: sig = apply_lowpass(sig, chain.lp_filter_hz)
    if chain.distortion > 0: sig = apply_distortion(sig, chain.distortion)
    if chain.reverb_mix > 0: sig = apply_reverb(sig, chain.reverb_mix, chain.reverb_decay)
    if chain.stereo_width > 0: sig = apply_stereo(sig, chain.stereo_width)
    return _safe_clip(sig)

# ---- Voice synthesis ----
def synthesize_voice(voice: SynthVoice) -> np.ndarray:
    n = max(1, int(voice.duration * SR))
    t = np.arange(n, dtype=np.float32) / SR
    f = freq_mod(voice.freq, voice.pitch_mod)
    sig = generate_oscillator(voice.osc_type, f, voice.duration,
                              voice.vibrato_rate, voice.vibrato_depth)
    total = sig.astype(np.float64)
    for mult, amp in voice.harmonics:
        hf = f * mult
        if hf < SR / 2:
            h_sig = generate_oscillator(OscType.SINE, hf, voice.duration, 0, 0)
            total += h_sig.astype(np.float64) * amp
    sig = total.astype(np.float32)
    pk = np.max(np.abs(sig))
    if pk > 1.0: sig /= pk
    env = generate_envelope(voice.env_shape, n)
    sig = sig * env * voice.volume
    return process_effects(sig, voice.effect_chain)

def _sig_to_int16(sig: np.ndarray) -> np.ndarray:
    s = _safe_clip(sig)
    return np.clip(s * 32767, -32768, 32767).astype(np.int16)

def write_wav(path: Path, sig: np.ndarray):
    path.parent.mkdir(parents=True, exist_ok=True)
    if sig.ndim == 2:
        data = np.column_stack([_sig_to_int16(sig[0]), _sig_to_int16(sig[1])])
    else:
        data = _sig_to_int16(sig)
    wavfile.write(str(path), SR, data)

# ---- Music generation ----
def generate_music_wav(pattern: MusicPattern, out_path: Path, dur_sec: float) -> str:
    """Generate music WAV from pattern, repeat to fill dur_sec, write to out_path."""
    beat_dur = 60.0 / pattern.bpm
    note_freqs = [freq_mod(note_to_freq(n), pattern.pitch_mod) for n in pattern.notes]
    # Build one cycle
    cycle_samples = []
    for freq, dur in zip(note_freqs, pattern.durations):
        note_dur = dur * beat_dur
        note_n = max(1, int(note_dur * SR))
        if freq > 0:
            note_sig = generate_oscillator(pattern.osc_type, freq, note_dur,
                                           pattern.vibrato_rate, pattern.vibrato_depth)
            n64 = note_sig.astype(np.float64)
            for mult, amp in pattern.harmonics:
                hf = freq * mult
                if hf < SR / 2:
                    n64 += generate_oscillator(OscType.SINE, hf, note_dur, 0, 0).astype(np.float64) * amp
            note_sig = n64.astype(np.float32)
            pk = np.max(np.abs(note_sig))
            if pk > 1.0: note_sig /= pk
        else:
            note_sig = np.zeros(note_n, dtype=np.float32)
        env = generate_envelope(pattern.env_shape, note_n)
        note_sig = note_sig * env * pattern.volume
        cycle_samples.append(note_sig)
    one_cycle = np.concatenate(cycle_samples) if cycle_samples else np.zeros(SR, dtype=np.float32)
    total_dur = sum(max(d, 0.05) for d in pattern.durations) * beat_dur
    n_cycles = max(1, int(np.ceil(dur_sec / total_dur)))
    full = np.tile(one_cycle, n_cycles)
    full = full[:int(dur_sec * SR)]
    # Apply effects
    chain = EffectChain(
        lp_filter_hz=pattern.lp_filter_hz,
        distortion=pattern.distortion,
        reverb_mix=pattern.reverb_mix,
        reverb_decay=pattern.reverb_decay,
        stereo_width=pattern.stereo_width,
    )
    full = process_effects(full, chain)
    if pattern.stereo_width > 0 and full.ndim == 1:
        full = apply_stereo(full, pattern.stereo_width)
    write_wav(out_path, full)
    return str(out_path)

# ---- Special SFX methods with sweeps / layered sounds ----
def _sfx_dark_clear(out_dir: Path):
    dur = 0.6; n = int(SR * dur)
    noise = _noise_pink(n)
    env = np.ones(n, dtype=np.float32)
    env[:int(n*0.3)] = np.linspace(0, 1, int(n*0.3))
    env[int(n*0.8):] = np.exp(-np.linspace(0, 3, n-int(n*0.8)))
    sig = noise * env * 0.35
    sig = apply_reverb(sig, 0.2, 0.4)
    write_wav(out_dir / "explore" / "dark_clear.wav", sig)

def _sfx_sanity_low(out_dir: Path):
    dur = 1.0; n = int(SR * dur)
    t = np.arange(n, dtype=np.float32) / SR
    saw = _osc_saw((t * 80) % 1.0) * 0.3
    noise = _noise_brown(n) * 0.4
    sig = (saw + noise).astype(np.float32)
    pk = np.max(np.abs(sig))
    if pk > 0: sig /= pk
    env = np.ones(n, dtype=np.float32)
    env[:int(n*0.4)] = np.linspace(0, 1, int(n*0.4))
    env[int(n*0.8):] = np.exp(-np.linspace(0, 3, n-int(n*0.8)))
    sig = sig * env * 0.35
    sig = process_effects(sig, EffectChain(
        lp_filter_hz=1200, distortion=0.15,
        reverb_mix=0.25, reverb_decay=0.5))
    write_wav(out_dir / "sanity" / "sanity_low.wav", sig)

def _sfx_mech_trigger(out_dir: Path):
    dur = 0.5; n = int(SR * dur)
    f = freq_mod(note_to_freq("C3"), 12)
    t = np.arange(n, dtype=np.float32) / SR
    saw = _osc_saw((t * f) % 1.0)
    env = np.ones(n, dtype=np.float32)
    env[:int(n*0.3)] = np.linspace(0, 1, int(n*0.3))
    env[int(n*0.8):] = np.exp(-np.linspace(0, 2, n-int(n*0.8)))
    sig_low = apply_lowpass(saw, 500)
    sig_high = apply_lowpass(saw, 3000)
    fade = np.linspace(0, 1, n)
    sig = (sig_low * (1-fade) + sig_high * fade) * env * 0.35
    sig = apply_reverb(sig, 0.2, 0.4)
    write_wav(out_dir / "mechanism" / "mech_trigger.wav", sig)

def _sfx_wall_open(out_dir: Path):
    dur = 0.7; n = int(SR * dur)
    t = np.arange(n, dtype=np.float32) / SR
    saw = _osc_saw((t * 100) % 1.0) * 0.3
    noise = _noise_brown(n) * 0.4
    sig = (saw + noise).astype(np.float32)
    pk = np.max(np.abs(sig))
    if pk > 0: sig /= pk
    env = np.exp(-np.linspace(0, 3, n))
    sig = sig * env * 0.35
    sig = process_effects(sig, EffectChain(
        lp_filter_hz=2000, reverb_mix=0.15, reverb_decay=0.3))
    write_wav(out_dir / "mechanism" / "wall_open.wav", sig)

def _sfx_basement_reveal(out_dir: Path):
    dur = 1.0; n = int(SR * dur)
    t = np.arange(n, dtype=np.float32) / SR
    saw = _osc_saw((t * note_to_freq("C3")) % 1.0) * 0.4
    noise = _noise_pink(n) * 0.1
    sig = (saw + noise).astype(np.float32)
    pk = np.max(np.abs(sig))
    if pk > 0: sig /= pk
    env = np.ones(n, dtype=np.float32)
    env[:int(n*0.2)] = np.linspace(0, 1, int(n*0.2))
    env[int(n*0.8):] = np.exp(-np.linspace(0, 3, n-int(n*0.8)))
    sig = sig * env * 0.35
    sig = process_effects(sig, EffectChain(
        lp_filter_hz=2500, reverb_mix=0.3, reverb_decay=0.6, stereo_width=0.4))
    write_wav(out_dir / "mechanism" / "basement_reveal.wav", sig)

# ---- Batch exporter ----
class AudioBatchExporter:
    def __init__(self):
        self.sfx_dir = OUTPUT_DIR / "sfx"
        self.music_dir = OUTPUT_DIR / "music"

    def ensure_dirs(self):
        for d in ["explore", "memory", "sanity", "card", "mechanism"]:
            (self.sfx_dir / d).mkdir(parents=True, exist_ok=True)
        self.music_dir.mkdir(parents=True, exist_ok=True)

    def _export_one(self, name: str, voice: SynthVoice, category: str):
        sig = synthesize_voice(voice)
        path = self.sfx_dir / category / f"{name}.wav"
        write_wav(path, sig)
        print(f"  -> {path}")

    def export_all_sfx(self):
        print("\n[SFX] 导出音效...")

        print("\n  [探索]")
        self._export_one("step", SynthVoice(
            freq=200, osc_type=OscType.NOISE_BROWN, duration=0.08, volume=0.35,
            env_shape=EnvShape.PERCUSSIVE,
            effect_chain=EffectChain(lp_filter_hz=800)), "explore")
        self._export_one("door_open", SynthVoice(
            freq=400, osc_type=OscType.SAW, duration=0.5, volume=0.35,
            env_shape=EnvShape.REVERSE, pitch_mod=-7,
            effect_chain=EffectChain(lp_filter_hz=1500, reverb_mix=0.15, reverb_decay=0.3)), "explore")
        _sfx_dark_clear(self.sfx_dir)

        print("\n  [记忆]")
        C4 = note_to_freq("C4")
        self._export_one("memory_touch", SynthVoice(
            freq=C4, osc_type=OscType.SINE, duration=0.4, volume=0.35,
            env_shape=EnvShape.PAD, harmonics=[(2,0.3),(3,0.15),(5,0.05)],
            effect_chain=EffectChain(reverb_mix=0.3, reverb_decay=0.6, stereo_width=0.4)), "memory")
        self._export_one("memory_whisper", SynthVoice(
            freq=C4, osc_type=OscType.TRIANGLE, duration=0.8, volume=0.35,
            env_shape=EnvShape.PAD, vibrato_rate=4.5, vibrato_depth=2,
            harmonics=[(2,0.2),(4,0.1)],
            effect_chain=EffectChain(lp_filter_hz=5000, reverb_mix=0.35, reverb_decay=0.7)), "memory")
        self._export_one("sanity_cost", SynthVoice(
            freq=note_to_freq("C3"), osc_type=OscType.SAW, duration=0.3, volume=0.35,
            env_shape=EnvShape.REVERSE, pitch_mod=-7,
            effect_chain=EffectChain(lp_filter_hz=2000, distortion=0.2)), "memory")

        print("\n  [理智]")
        _sfx_sanity_low(self.sfx_dir)
        self._export_one("sanity_recover", SynthVoice(
            freq=C4, osc_type=OscType.SINE, duration=0.5, volume=0.35,
            env_shape=EnvShape.SWELL, pitch_mod=7,
            harmonics=[(2,0.2),(3,0.1)],
            effect_chain=EffectChain(reverb_mix=0.2, reverb_decay=0.4)), "sanity")
        self._export_one("sanity_zero", SynthVoice(
            freq=note_to_freq("C2"), osc_type=OscType.SAW, duration=1.5, volume=0.35,
            env_shape=EnvShape.REVERSE, pitch_mod=-12,
            effect_chain=EffectChain(
                lp_filter_hz=1500, distortion=0.3,
                reverb_mix=0.3, reverb_decay=0.6, stereo_width=0.5)), "sanity")

        print("\n  [卡牌]")
        self._export_one("card_collect", SynthVoice(
            freq=C4, osc_type=OscType.TRIANGLE, duration=0.2, volume=0.35,
            env_shape=EnvShape.PLUCK, pitch_mod=5,
            harmonics=[(2,0.15),(3,0.08)],
            effect_chain=EffectChain(reverb_mix=0.12, reverb_decay=0.25)), "card")
        self._export_one("card_reveal", SynthVoice(
            freq=C4, osc_type=OscType.SINE, duration=0.4, volume=0.35,
            env_shape=EnvShape.SWELL, pitch_mod=12,
            harmonics=[(2,0.2),(3,0.08)],
            effect_chain=EffectChain(reverb_mix=0.18, reverb_decay=0.35)), "card")
        self._export_one("card_answer", SynthVoice(
            freq=C4, osc_type=OscType.TRIANGLE, duration=0.6, volume=0.35,
            env_shape=EnvShape.SWELL, vibrato_rate=5, vibrato_depth=2,
            harmonics=[(1.5,0.2),(2,0.15)],
            effect_chain=EffectChain(reverb_mix=0.25, reverb_decay=0.5, stereo_width=0.3)), "card")
        self._export_one("card_all", SynthVoice(
            freq=note_to_freq("C5"), osc_type=OscType.SINE, duration=1.0, volume=0.35,
            env_shape=EnvShape.SWELL, vibrato_rate=4, vibrato_depth=1.5,
            harmonics=[(2,0.3),(3,0.15),(4,0.08),(5,0.03)],
            effect_chain=EffectChain(reverb_mix=0.25, reverb_decay=0.5, stereo_width=0.4)), "card")

        print("\n  [机关]")
        _sfx_mech_trigger(self.sfx_dir)
        _sfx_wall_open(self.sfx_dir)
        _sfx_basement_reveal(self.sfx_dir)
        print("\n  SFX 导出完成!")

    def export_all_music(self, dur_sec: float = 30.0):
        print(f"\n[Music] 导出音乐 (时长: {dur_sec}s)...")
        NOTES["B1"] = 61.74; NOTES["Bb1"] = 58.27; NOTES["Ab1"] = 51.91

        print("\n  [探索 BGM]")
        generate_music_wav(MusicPattern(
            "mansion_explore",
            ["C3","Eb3","G3","Ab3","G3","F3","Eb3","Bb3","Ab3","G3","F3","G3","Eb3","C3"],
            [2,2,2,2,2,2,2, 2,2,2,2,2,2,2],
            60, True, OscType.TRIANGLE, 0.13, EnvShape.PAD,
            [(2,0.15),(3,0.05)], 3.5, 1, 0.25, 0.5, 0.3, 4000
        ), self.music_dir / "mansion_explore.wav", dur_sec)
        print(f"  -> {self.music_dir / 'mansion_explore.wav'}")

        print("\n  [记忆氛围]")
        generate_music_wav(MusicPattern(
            "memory_ambience",
            ["C4","Eb4","G4","C5","Bb3","Ab3","G3","C4"],
            [3,3,3,3, 2.5,2.5,2.5,2],
            50, True, OscType.SINE, 0.10, EnvShape.PAD,
            [(2,0.2),(3,0.1),(5,0.03)], 5, 2, 0.35, 0.7, 0.5, 5000
        ), self.music_dir / "memory_ambience.wav", dur_sec)
        print(f"  -> {self.music_dir / 'memory_ambience.wav'}")

        print("\n  [理智流失]")
        generate_music_wav(MusicPattern(
            "sanity_drain",
            ["C2","G2","Ab2","Bb2","C3","Ab2"],
            [4,4,4,4,4,4],
            40, True, OscType.SAW, 0.12, EnvShape.PAD,
            [(0.5,0.2),(2,0.1)], 0, 0, 0.2, 0.4, 0.0, 2000, 0.15
        ), self.music_dir / "sanity_drain.wav", dur_sec)
        print(f"  -> {self.music_dir / 'sanity_drain.wav'}")

        print("\n  [游戏结束]")
        generate_music_wav(MusicPattern(
            "game_over", ["C2","B1","Bb1","Ab1"], [2,2,2,2],
            40, False, OscType.SAW, 0.18, EnvShape.REVERSE,
            [], 0, 0, 0.3, 0.6, 0.4, 1500, 0.2, -12
        ), self.music_dir / "game_over.wav", 8.0)
        print(f"  -> {self.music_dir / 'game_over.wav'}")

        print("\n  [胜利]")
        generate_music_wav(MusicPattern(
            "victory",
            ["C4","Eb4","G4","C5","F4","Ab4","Bb4","C5"],
            [1.5,1.5,1.5,1.5, 1.5,1.5,1.5,1.5],
            80, False, OscType.TRIANGLE, 0.16, EnvShape.SWELL,
            [(2,0.25),(3,0.1)], 4, 1.5, 0.3, 0.6, 0.5
        ), self.music_dir / "victory.wav", 12.0)
        print(f"  -> {self.music_dir / 'victory.wav'}")
        print("\n  Music 导出完成!")

    def export_everything(self, dur_sec: float = 30.0):
        self.ensure_dirs()
        self.export_all_sfx()
        self.export_all_music(dur_sec)
        print(f"\n{'='*48}")
        print(f"  全部音频导出完成!")
        print(f"  输出目录: {OUTPUT_DIR}")
        print(f"{'='*48}")

# ---- CLI ----
def main():
    parser = argparse.ArgumentParser(description="卡瑞玛拉：枯肢之下 — 音频制作引擎")
    parser.add_argument("--batch", action="store_true", help="导出全部音频")
    parser.add_argument("--sfx", action="store_true", help="仅导出 SFX")
    parser.add_argument("--music", action="store_true", help="仅导出音乐")
    parser.add_argument("--duration", type=float, default=30.0, help="音乐时长(秒)")
    args = parser.parse_args()
    if not any([args.batch, args.sfx, args.music]):
        parser.print_help()
        print("\n示例: python faatt.py --batch")
        return
    print("=" * 48)
    print("  卡瑞玛拉：枯肢之下 — 音频制作引擎")
    print("=" * 48)
    exp = AudioBatchExporter()
    exp.ensure_dirs()
    if args.batch:
        exp.export_everything(args.duration)
    else:
        if args.sfx: exp.export_all_sfx()
        if args.music: exp.export_all_music(args.duration)

if __name__ == "__main__":
    main()
