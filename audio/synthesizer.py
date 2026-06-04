"""
AudioSynthesizer — Enhanced WAV synthesizer for Endless Highway.
Powered by faatt synthesis engine: numpy oscillators, 6 envelope shapes,
complete effects chain (LP/HP filter, distortion, bit crush, reverb, stereo).
Style: High-energy synthwave driving music + rich cinematic SFX.

Dependencies: numpy, scipy (for wavfile output)
"""

import numpy as np
from scipy.io import wavfile
import math
import os
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, List, Tuple, Dict
from enum import Enum

SR = 44100
BPM = 130
BEAT_DURATION = 60.0 / BPM
SIXTEENTH = BEAT_DURATION / 4
EIGHTH = BEAT_DURATION / 2


# ============================================================
#  Oscillators (from faatt engine)
# ============================================================
class OscType(Enum):
    SAW = "saw"
    SQUARE = "square"
    SINE = "sine"
    TRIANGLE = "triangle"
    NOISE_WHITE = "noise_white"
    NOISE_PINK = "noise_pink"
    NOISE_BROWN = "noise_brown"


def _osc_saw(t: np.ndarray, freq: float) -> np.ndarray:
    return 2.0 * ((t * freq) % 1.0) - 1.0


def _osc_square(t: np.ndarray, freq: float, duty: float = 0.5) -> np.ndarray:
    return np.where(((t * freq) % 1.0) < duty, 1.0, -1.0)


def _osc_sine(t: np.ndarray, freq: float) -> np.ndarray:
    return np.sin(2.0 * np.pi * t * freq)


def _osc_triangle(t: np.ndarray, freq: float) -> np.ndarray:
    phase = (t * freq) % 1.0
    return 4.0 * np.abs(phase - 0.5) - 1.0


def _pink_noise_kernel(n: int) -> np.ndarray:
    out = np.zeros(n)
    states = np.zeros(12)
    rng = np.random.default_rng()
    for i in range(n):
        inc = rng.standard_normal()
        idx = i & 11
        states[idx] = 0.998 * states[idx] + inc
        out[i] = states.mean() + inc * 0.05
    return out * 3.0


def _osc_noise_white(n: int, rng: np.random.Generator = None) -> np.ndarray:
    if rng is None:
        rng = np.random.default_rng()
    return 2.0 * rng.random(n, dtype=np.float64) - 1.0


def _osc_noise_pink(n: int) -> np.ndarray:
    return _pink_noise_kernel(n)


def _osc_noise_brown(n: int) -> np.ndarray:
    out = np.cumsum(2.0 * np.random.random(n).astype(np.float64) - 1.0)
    peak = np.max(np.abs(out)) + 1e-8
    return out / peak


def oscillator(t: np.ndarray, freq: float, osc_type: OscType = OscType.SAW,
               duty: float = 0.5) -> np.ndarray:
    if osc_type == OscType.SAW:
        return _osc_saw(t, freq)
    elif osc_type == OscType.SQUARE:
        return _osc_square(t, freq, duty)
    elif osc_type == OscType.SINE:
        return _osc_sine(t, freq)
    elif osc_type == OscType.TRIANGLE:
        return _osc_triangle(t, freq)
    elif osc_type == OscType.NOISE_WHITE:
        return _osc_noise_white(len(t))
    elif osc_type == OscType.NOISE_PINK:
        return _osc_noise_pink(len(t))
    elif osc_type == OscType.NOISE_BROWN:
        return _osc_noise_brown(len(t))
    return _osc_saw(t, freq)


# ============================================================
#  Envelopes (from faatt engine)
# ============================================================
class EnvShape(Enum):
    PERCUSSIVE = "percussive"
    PAD = "pad"
    PLUCK = "pluck"
    SWELL = "swell"
    REVERSE = "reverse"
    ADSR_CUSTOM = "adsr_custom"


@dataclass
class ADSRParams:
    attack: float = 0.01
    decay: float = 0.1
    sustain: float = 0.7
    release: float = 0.15


def make_envelope(length: int, shape: EnvShape = EnvShape.PERCUSSIVE,
                  adsr: Optional[ADSRParams] = None,
                  custom_peak: float = 1.0) -> np.ndarray:
    if length <= 0:
        return np.array([0.0])
    e = np.ones(length, dtype=np.float64)

    if shape == EnvShape.PERCUSSIVE:
        att = max(1, int(0.003 * length))
        dec = max(1, int(0.15 * length))
        rel = max(1, int(0.20 * length))
        e[:att] = np.linspace(0, 1, att)
        e[att:att + dec] = np.linspace(1, 0.15, dec)
        e[-rel:] = np.linspace(e[-rel] if rel < length else 0.15, 0, rel)
    elif shape == EnvShape.PAD:
        att = max(1, int(0.20 * length))
        rel = max(1, int(0.30 * length))
        sus_val = 0.85
        e[:att] = np.linspace(0, sus_val, att)
        e[-rel:] = np.linspace(sus_val, 0, rel)
    elif shape == EnvShape.PLUCK:
        att = max(1, int(0.002 * length))
        dec = max(int(1), int(0.40 * length))
        e[:att] = np.linspace(0, 1, att)
        dec_curve = np.exp(-np.linspace(0, 5, dec))
        end_idx = min(att + dec, length)
        e[att:end_idx] *= dec_curve[:end_idx - att]
        if end_idx < length:
            e[end_idx:] *= 0.001
    elif shape == EnvShape.SWELL:
        half = length // 2
        e[:half] = np.linspace(0, 1, half)
        e[half:] = np.linspace(1, 0, length - half)
    elif shape == EnvShape.REVERSE:
        rel = max(1, int(0.70 * length))
        e[:length - rel] = 1.0
        e[length - rel:] = np.linspace(1, 0, rel)
    elif shape == EnvShape.ADSR_CUSTOM and adsr is not None:
        att_samp = min(int(adsr.attack * SR), length // 4)
        dec_samp = min(int(adsr.decay * SR), length // 4)
        rel_samp = min(int(adsr.release * SR), length // 4)
        pos = 0
        if att_samp > 0:
            e[pos:pos + att_samp] = np.linspace(0, 1, att_samp)
            pos += att_samp
        if dec_samp > 0:
            end_d = min(pos + dec_samp, length - rel_samp)
            e[pos:end_d] = np.linspace(1, adsr.sustain, end_d - pos)
            pos = end_d
        if pos < length - rel_samp:
            e[pos:length - rel_samp] = adsr.sustain
        if rel_samp > 0:
            e[length - rel_samp:] = np.linspace(
                e[length - rel_samp] if rel_samp < length else adsr.sustain,
                0, rel_samp)
    return e * custom_peak


# ============================================================
#  Effects Chain (from faatt engine)
# ============================================================
@dataclass
class EffectChain:
    lp_filter_hz: Optional[float] = None
    hp_filter_hz: Optional[float] = None
    distortion: float = 0.0
    bit_crush: int = 16
    reverb_mix: float = 0.0
    reverb_decay: float = 0.3
    stereo_width: float = 0.0


def apply_lowpass(sig: np.ndarray, cutoff_hz: float, sr: int = SR) -> np.ndarray:
    rc = 1.0 / (2.0 * np.pi * cutoff_hz)
    dt = 1.0 / sr
    alpha = dt / (rc + dt)
    output = np.zeros_like(sig)
    output[0] = sig[0]
    for i in range(1, len(sig)):
        output[i] = alpha * sig[i] + (1 - alpha) * output[i - 1]
    return output


def apply_highpass(sig: np.ndarray, cutoff_hz: float, sr: int = SR) -> np.ndarray:
    lp = apply_lowpass(sig, cutoff_hz, sr)
    return sig - lp


def apply_distortion(sig: np.ndarray, amount: float = 0.5) -> np.ndarray:
    if amount <= 0:
        return sig
    drive = 1.0 + amount * 10.0
    return np.tanh(sig * drive) / np.tanh(drive)


def apply_bit_crush(sig: np.ndarray, depth: int = 8) -> np.ndarray:
    if depth >= 16:
        return sig
    steps = 2 ** depth
    quantized = np.round(sig * (steps / 2)) / (steps / 2)
    return np.clip(quantized, -1, 1)


def apply_simple_reverb(sig: np.ndarray, mix: float = 0.2,
                        decay: float = 0.3, sr: int = SR) -> np.ndarray:
    if mix <= 0 or len(sig) < sr:
        return sig
    delay_samples = [
        int(sr * 0.047), int(sr * 0.071),
        int(sr * 0.113), int(sr * 0.173),
    ]
    gains = [0.55, 0.43, 0.32, 0.21]
    wet = np.zeros_like(sig)
    for dly, gain in zip(delay_samples, gains):
        if dly >= len(sig):
            continue
        delayed = np.zeros_like(sig)
        delayed[dly:] = sig[:-dly] * gain * np.exp(
            -np.arange(len(sig) - dly) * (1.0 / (decay * sr)))
        wet += delayed
    wet_norm = wet / (np.max(np.abs(wet)) + 1e-8)
    wet_lp = apply_lowpass(wet_norm, 4000)
    return sig * (1 - mix) + wet_lp * mix


def apply_stereo(sig: np.ndarray, width: float = 0.5) -> np.ndarray:
    if width <= 0 or (sig.ndim > 1 and sig.shape[1] >= 2):
        return sig
    rng = np.random.RandomState(seed=42)
    n = len(sig)
    chunk_size = max(n // 64, 8)
    n_chunks = max((n + chunk_size - 1) // chunk_size, 2)
    lowres_noise = rng.randn(n_chunks)
    xp = np.linspace(0, n, len(lowres_noise))
    side = np.interp(np.arange(n), xp, lowres_noise)
    side = side / (np.max(np.abs(side)) + 1e-8) * width * np.abs(sig) * 0.3
    kernel_size = min(256, max(n // 20, 4))
    if kernel_size >= 2:
        kernel = np.ones(kernel_size) / kernel_size
        side = np.convolve(side, kernel, mode='same')
    left = sig + side
    right = sig - side
    return np.column_stack([left, right])


def process_effects(sig: np.ndarray, chain: EffectChain) -> np.ndarray:
    result = sig.copy()
    if chain.lp_filter_hz is not None:
        result = apply_lowpass(result, chain.lp_filter_hz)
    if chain.hp_filter_hz is not None:
        result = apply_highpass(result, chain.hp_filter_hz)
    if chain.distortion > 0:
        result = apply_distortion(result, chain.distortion)
    if chain.bit_crush < 16:
        result = apply_bit_crush(result, chain.bit_crush)
    if chain.reverb_mix > 0:
        result = apply_simple_reverb(result, chain.reverb_mix, chain.reverb_decay)
    if chain.stereo_width > 0:
        result = apply_stereo(result, chain.stereo_width)
    return result


# ============================================================
#  SynthVoice — Parameterized voice (from faatt)
# ============================================================
@dataclass
class SynthVoice:
    freq: float = 440.0
    osc_type: OscType = OscType.SINE
    duration: float = 0.15
    volume: float = 1.0
    env_shape: EnvShape = EnvShape.PERCUSSIVE
    adsr: Optional[ADSRParams] = None
    effect_chain: Optional[EffectChain] = None
    pitch_mod: float = 0.0
    vibrato_rate: float = 0.0
    vibrato_depth: float = 0.0
    detune: float = 0.0
    harmonics: List[Tuple[float, float]] = field(default_factory=list)


def synthesize_voice(voice: SynthVoice) -> np.ndarray:
    """Synthesize a single voice into a numpy array."""
    n_samples = int(voice.duration * SR)
    if n_samples <= 0:
        n_samples = 1
    t = np.linspace(0, voice.duration, n_samples, dtype=np.float64)

    base_freq = voice.freq * (2 ** (voice.pitch_mod / 12))

    # Vibrato
    if voice.vibrato_depth > 0 and voice.vibrato_rate > 0:
        vib_env = make_envelope(n_samples, EnvShape.PAD)
        vib = 1.0 + (voice.vibrato_depth / 12) * np.sin(
            2 * np.pi * voice.vibrato_rate * t) * vib_env
        mod_freq = base_freq * vib
    else:
        mod_freq = base_freq

    # Main oscillator
    main_sig = oscillator(t, mod_freq, voice.osc_type)

    # Harmonics
    for harmonic_mult, harmonic_amp in voice.harmonics:
        h_sig = oscillator(t, mod_freq * harmonic_mult, voice.osc_type) * harmonic_amp
        main_sig += h_sig

    # Detune (unison)
    if abs(voice.detune) > 0.001:
        detune_sig = oscillator(
            t, mod_freq * (2 ** (voice.detune / 12)), voice.osc_type) * 0.6
        main_sig += detune_sig

    # Envelope
    env = make_envelope(n_samples, voice.env_shape, voice.adsr)
    sig = main_sig * env * voice.volume

    # Effects
    if voice.effect_chain is not None:
        sig = process_effects(sig, voice.effect_chain)

    # Safe limiter
    peak = np.max(np.abs(sig))
    if peak > 1.0:
        sig = sig / peak * 0.98

    return sig.astype(np.float32)


# ============================================================
#  ROADDD Driving SFX Presets
# ============================================================
DRIVING_SFX_PRESETS: Dict[str, SynthVoice] = {
    # ── Core driving SFX ──
    "sfx_engine": SynthVoice(
        freq=40.0, osc_type=OscType.NOISE_BROWN, duration=4.0,
        volume=0.55, env_shape=EnvShape.PAD,
        harmonics=[(2.0, 0.25)],
        vibrato_rate=3.0, vibrato_depth=2.0,
        effect_chain=EffectChain(
            lp_filter_hz=300, distortion=0.12, stereo_width=0.2,
        ),
    ),
    "sfx_drift": SynthVoice(
        freq=200.0, osc_type=OscType.SAW, duration=1.5,
        volume=0.45, env_shape=EnvShape.SWELL,
        pitch_mod=24,
        harmonics=[(0.5, 0.2), (1.5, 0.15)],
        effect_chain=EffectChain(
            hp_filter_hz=150, reverb_mix=0.15, reverb_decay=0.5,
            distortion=0.08, stereo_width=0.35,
        ),
    ),
    "sfx_crash": SynthVoice(
        freq=120.0, osc_type=OscType.NOISE_BROWN, duration=2.5,
        volume=0.75, env_shape=EnvShape.PERCUSSIVE,
        pitch_mod=-18,
        harmonics=[(2.0, 0.3), (4.0, 0.15), (0.5, 0.25)],
        effect_chain=EffectChain(
            lp_filter_hz=4000, distortion=0.35, bit_crush=8,
            reverb_mix=0.25, reverb_decay=1.2, stereo_width=0.5,
        ),
    ),

    # ── UI SFX ──
    "sfx_ui_pause": SynthVoice(
        freq=600.0, osc_type=OscType.SINE, duration=0.12,
        volume=0.4, env_shape=EnvShape.PERCUSSIVE,
        harmonics=[(1.5, 0.15)],
        effect_chain=EffectChain(reverb_mix=0.08),
    ),
    "sfx_ui_resume": SynthVoice(
        freq=800.0, osc_type=OscType.SINE, duration=0.12,
        volume=0.4, env_shape=EnvShape.PERCUSSIVE,
        harmonics=[(1.5, 0.15)],
        effect_chain=EffectChain(reverb_mix=0.08),
    ),
    "sfx_ui_quit": SynthVoice(
        freq=440.0, osc_type=OscType.SINE, duration=0.2,
        volume=0.35, env_shape=EnvShape.REVERSE,
        pitch_mod=-7,
        effect_chain=EffectChain(reverb_mix=0.12, reverb_decay=0.4),
    ),

    # ── New: Nitro boost ──
    "sfx_nitro": SynthVoice(
        freq=300.0, osc_type=OscType.NOISE_WHITE, duration=0.8,
        volume=0.55, env_shape=EnvShape.SWELL,
        pitch_mod=18,
        harmonics=[(0.5, 0.3)],
        effect_chain=EffectChain(
            hp_filter_hz=200, lp_filter_hz=8000,
            reverb_mix=0.1, distortion=0.15,
        ),
    ),

    # ── New: Tire screech ──
    "sfx_screech": SynthVoice(
        freq=800.0, osc_type=OscType.SAW, duration=0.6,
        volume=0.5, env_shape=EnvShape.SWELL,
        pitch_mod=12,
        harmonics=[(2.0, 0.2)],
        effect_chain=EffectChain(
            distortion=0.25, bit_crush=10,
            hp_filter_hz=400, reverb_mix=0.08,
        ),
    ),

    # ── New: Near miss (close call) ──
    "sfx_near_miss": SynthVoice(
        freq=1200.0, osc_type=OscType.SINE, duration=0.25,
        volume=0.35, env_shape=EnvShape.PERCUSSIVE,
        pitch_mod=-5,
        vibrato_rate=8, vibrato_depth=1.5,
        effect_chain=EffectChain(reverb_mix=0.12),
    ),

    # ── New: Distance milestone ──
    "sfx_milestone": SynthVoice(
        freq=523.25, osc_type=OscType.TRIANGLE, duration=0.5,
        volume=0.45, env_shape=EnvShape.SWELL,
        pitch_mod=7,
        harmonics=[(2.0, 0.2), (3.0, 0.1)],
        effect_chain=EffectChain(reverb_mix=0.15, reverb_decay=0.5, stereo_width=0.3),
    ),

    # ── New: Warning beep ──
    "sfx_warning": SynthVoice(
        freq=880.0, osc_type=OscType.SQUARE, duration=0.15,
        volume=0.4, env_shape=EnvShape.PERCUSSIVE,
        effect_chain=EffectChain(bit_crush=8),
    ),

    # ── New: Coin/pickup ──
    "sfx_coin": SynthVoice(
        freq=988.0, osc_type=OscType.SINE, duration=0.12,
        volume=0.4, env_shape=EnvShape.PERCUSSIVE,
        pitch_mod=4,
        effect_chain=EffectChain(reverb_mix=0.06),
    ),

    # ── New: Shield power-up ──
    "sfx_shield": SynthVoice(
        freq=450.0, osc_type=OscType.TRIANGLE, duration=0.6,
        volume=0.5, env_shape=EnvShape.SWELL,
        harmonics=[(2.0, 0.2), (3.0, 0.1)],
        vibrato_rate=4, vibrato_depth=2,
        effect_chain=EffectChain(
            reverb_mix=0.2, reverb_decay=0.7, stereo_width=0.4,
        ),
    ),

    # ── New: Speed burst ──
    "sfx_speed_boost": SynthVoice(
        freq=150.0, osc_type=OscType.SAW, duration=0.5,
        volume=0.5, env_shape=EnvShape.SWELL,
        pitch_mod=24,
        harmonics=[(2.0, 0.2), (3.0, 0.1)],
        effect_chain=EffectChain(
            reverb_mix=0.1, distortion=0.1,
        ),
    ),
}


# ============================================================
#  Music Pattern System (from faatt)
# ============================================================
@dataclass
class MusicPattern:
    name: str
    notes: List[Optional[str]]
    durations: List[float]
    octave_shifts: List[int] = None
    bpm: int = 130
    loop: bool = True
    osc_type: OscType = OscType.SINE
    volume: float = 0.18
    env_shape: EnvShape = EnvShape.PAD
    harmonics: List[Tuple[float, float]] = field(default_factory=list)
    vibrato_rate: float = 0
    vibrato_depth: float = 0
    reverb_mix: float = 0.15
    reverb_decay: float = 0.8
    stereo_width: float = 0.3
    lp_filter_hz: Optional[float] = None


# Note frequency table
NOTES: Dict[str, float] = {
    "C2": 65.41, "D2": 73.42, "Eb2": 77.78, "E2": 82.41,
    "F2": 87.31, "Gb2": 92.50, "G2": 98.00, "Ab2": 103.83,
    "A2": 110.00, "Bb2": 116.54, "B2": 123.47,
    "C3": 130.81, "D3": 146.83, "Eb3": 155.56, "E3": 164.81,
    "F3": 174.61, "Gb3": 185.00, "G3": 196.00, "Ab3": 207.65,
    "A3": 220.00, "Bb3": 233.08, "B3": 246.94,
    "C4": 261.63, "Db4": 277.18, "D4": 293.66, "Eb4": 311.13,
    "E4": 329.63, "F4": 349.23, "Gb4": 369.99, "G4": 392.00,
    "Ab4": 415.30, "A4": 440.00, "Bb4": 466.16, "B4": 493.88,
    "C5": 523.25, "Db5": 554.37, "D5": 587.33, "Eb5": 622.25,
    "E5": 659.26, "F5": 698.46, "Gb5": 739.99, "G5": 783.99,
    "Ab5": 830.61, "A5": 880.00, "Bb5": 932.33, "B5": 987.77,
}


def note_to_freq(note: str) -> float:
    return NOTES.get(note, 440.0)


def generate_music_wav(pattern: MusicPattern, duration_sec: float,
                       sr: int = SR) -> np.ndarray:
    """Generate a music pattern as a numpy array (mono float32)."""
    beat_dur = 60.0 / pattern.bpm
    total_beats = sum(pattern.durations)
    loops = max(1, int(duration_sec / (total_beats * beat_dur)))

    octaves = pattern.octave_shifts or [0] * len(pattern.notes)

    samples_list = []
    for loop_idx in range(loops):
        for i, note in enumerate(pattern.notes):
            dur = pattern.durations[i] * beat_dur
            oct_v = octaves[i] if i < len(octaves) else 0
            n_samp = int(dur * sr)
            t = np.linspace(0, dur, n_samp, dtype=np.float64)

            if note is None:
                sig = np.zeros(n_samp, dtype=np.float64)
            else:
                f = note_to_freq(note) * (2 ** oct_v)
                sig = oscillator(t, f, pattern.osc_type)

                for h_mult, h_amp in pattern.harmonics:
                    sig += oscillator(t, f * h_mult, pattern.osc_type) * h_amp

                if pattern.vibrato_depth > 0:
                    vib_env = make_envelope(n_samp, EnvShape.PAD)
                    vib = 1.0 + (pattern.vibrato_depth / 12) * np.sin(
                        2 * np.pi * pattern.vibrato_rate * t) * vib_env
                    mod_f = f * vib
                    sig = oscillator(t, mod_f, pattern.osc_type)
                    for h_mult, h_amp in pattern.harmonics:
                        sig += oscillator(t, mod_f * h_mult, pattern.osc_type) * h_amp

                env = make_envelope(n_samp, pattern.env_shape)
                sig = sig * env * pattern.volume

            samples_list.append(sig)

    full = np.concatenate(samples_list) if samples_list else np.zeros(sr)

    chain = EffectChain(
        reverb_mix=pattern.reverb_mix, reverb_decay=pattern.reverb_decay,
        stereo_width=pattern.stereo_width, lp_filter_hz=pattern.lp_filter_hz,
    )
    processed = process_effects(full, chain)

    # Ensure mono
    if processed.ndim > 1 and processed.shape[1] >= 2:
        processed = processed.mean(axis=1)

    return processed.astype(np.float32)


# ════════════════════════════════════════════════════════════
#  Highway Driving Music Patterns (synthwave / outrun style)
# ════════════════════════════════════════════════════════════

# ── Bass: driving, syncopated, E minor pentatonic ──
HIGHWAY_BASS = MusicPattern(
    name="highway_bass",
    notes=[
        "E2", "E2", None, "E2",  "E2", "G2", None, None,
        "E2", "E2", None, "G2",  "A2", "G2", "E2", None,
    ],
    durations=[
        0.75, 0.5, 0.25, 0.5,  0.5, 0.5, 0.25, 0.25,
        0.75, 0.5, 0.25, 0.5,  0.5, 0.5, 0.75, 0.25,
    ],
    bpm=130, loop=True,
    osc_type=OscType.SQUARE, volume=0.22,
    env_shape=EnvShape.PLUCK,
    harmonics=[(0.5, 0.3), (2.0, 0.1)],
    lp_filter_hz=2500,
)

# ── Arp: bright 16th note pattern, trance-gated ──
HIGHWAY_ARP = MusicPattern(
    name="highway_arp",
    notes=[
        "E3", "G3", "B3", "D4", "E4", "D4", "B3", "G3",
        "E3", "G3", "A3", "C4", "E4", "C4", "A3", "G3",
    ],
    durations=[0.25] * 16,
    bpm=130, loop=True,
    osc_type=OscType.SAW, volume=0.12,
    env_shape=EnvShape.PERCUSSIVE,
    harmonics=[(2.0, 0.15)],
    lp_filter_hz=6000,
)

# ── Drums: complex rhythm with fills ──
HIGHWAY_DRUMS = MusicPattern(
    name="highway_drums",
    notes=[
        "C2", None, None, None,  "C2", None, "C2", None,
        "C2", None, None, None,  "C2", "C2", "C2", "C2",
    ],
    durations=[0.25] * 16,
    bpm=130, loop=True,
    osc_type=OscType.NOISE_PINK, volume=0.08,
    env_shape=EnvShape.PERCUSSIVE,
    lp_filter_hz=8000,
)

# ── Atmosphere: lush pad, E minor 9 chord ──
HIGHWAY_ATMOSPHERE = MusicPattern(
    name="highway_atmosphere",
    notes=[
        "E3", None, None, None,
        "G3", None, None, None,
        "B3", None, None, None,
        "D4", None, None, None,
    ],
    durations=[1.0, 1.0, 1.0, 1.0] * 4,
    bpm=130, loop=True,
    osc_type=OscType.SAW, volume=0.10,
    env_shape=EnvShape.PAD,
    harmonics=[(1.5, 0.2), (2.0, 0.15)],
    vibrato_rate=0.3, vibrato_depth=1.5,
    reverb_mix=0.25, reverb_decay=1.0,
    stereo_width=0.5, lp_filter_hz=3500,
)

# ── Melody: catchy synthwave lead ──
HIGHWAY_MELODY = MusicPattern(
    name="highway_melody",
    notes=[
        "E4", "G4", "B4", "D5",  "B4", "G4", "E4", None,
        "D4", "E4", "G4", "E4",  "D4", "B3", "E4", None,
    ],
    durations=[
        0.5, 0.5, 0.5, 1.0,  0.5, 0.5, 1.0, 0.5,
        0.5, 0.5, 0.5, 0.5,  0.75, 0.25, 1.0, 0.5,
    ],
    bpm=130, loop=True,
    osc_type=OscType.SAW, volume=0.14,
    env_shape=EnvShape.PLUCK,
    harmonics=[(2.0, 0.15), (3.0, 0.05)],
    vibrato_rate=5.5, vibrato_depth=2.0,
    reverb_mix=0.18, reverb_decay=0.6,
    stereo_width=0.4, lp_filter_hz=5000,
)


# ============================================================
#  AudioSynthesizer — Main Class
# ============================================================
class AudioSynthesizer:
    """
    Enhanced WAV synthesizer for Endless Highway.
    Uses faatt engine: numpy oscillators, 6 envelopes, effects chain.
    Generates all audio assets at startup for pygame.mixer playback.
    """

    def __init__(self, output_dir: str):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.sr = SR

    def _synthesize_to_wav(self, voice: SynthVoice, filename: str) -> str:
        """Synthesize a SynthVoice and save to WAV file."""
        sig = synthesize_voice(voice)

        # Handle stereo/mono
        if sig.ndim == 1:
            final = sig.reshape(-1, 1)
        elif sig.ndim == 2 and sig.shape[1] >= 2:
            final = sig
        else:
            final = sig.reshape(-1, 1)

        wav_int = np.clip(final * 32767, -32768, 32767).astype(np.int16)
        filepath = self.output_dir / filename
        wavfile.write(str(filepath), self.sr, wav_int)

        dur = len(sig) / self.sr
        print(f"  [Synthesizer] {filename} ({dur:.2f}s)")
        return str(filepath)

    def _synthesize_music_to_wav(self, pattern: MusicPattern,
                                  filename: str, duration: float = 30.0) -> str:
        """Synthesize a music pattern and save to WAV file."""
        sig = generate_music_wav(pattern, duration, self.sr)

        final = sig.reshape(-1, 1)
        wav_int = np.clip(final * 32767, -32768, 32767).astype(np.int16)
        filepath = self.output_dir / filename
        wavfile.write(str(filepath), self.sr, wav_int)

        print(f"  [Synthesizer] {filename} ({duration:.0f}s)")
        return str(filepath)

    # ════════════════════════════════════════════════════════════
    #  SFX Generators
    # ════════════════════════════════════════════════════════════

    def generate_engine(self) -> str:
        """Engine loop — brown noise + sub bass, modulated."""
        return self._synthesize_to_wav(
            DRIVING_SFX_PRESETS["sfx_engine"], "sfx_engine.wav")

    def generate_drift(self) -> str:
        """Drift whoosh — saw sweep + noise + reverb."""
        return self._synthesize_to_wav(
            DRIVING_SFX_PRESETS["sfx_drift"], "sfx_drift.wav")

    def generate_crash(self) -> str:
        """Crash — brown noise impact + distortion + stereo reverb."""
        return self._synthesize_to_wav(
            DRIVING_SFX_PRESETS["sfx_crash"], "sfx_crash.wav")

    def generate_ui_pause(self) -> str:
        """UI pause — dual sine blip."""
        # Two-tone: 600Hz then 800Hz
        v1 = SynthVoice(freq=600, osc_type=OscType.SINE, duration=0.1,
                        volume=0.35, env_shape=EnvShape.PERCUSSIVE)
        v2 = SynthVoice(freq=800, osc_type=OscType.SINE, duration=0.1,
                        volume=0.35, env_shape=EnvShape.PERCUSSIVE)
        s1 = synthesize_voice(v1)
        s2 = synthesize_voice(v2)
        gap = np.zeros(int(0.04 * self.sr), dtype=np.float32)
        sig = np.concatenate([s1, gap, s2])
        return self._save_raw_wav(sig, "sfx_ui_pause.wav")

    def generate_ui_resume(self) -> str:
        """UI resume — rising dual sine blip."""
        v1 = SynthVoice(freq=800, osc_type=OscType.SINE, duration=0.1,
                        volume=0.35, env_shape=EnvShape.PERCUSSIVE)
        v2 = SynthVoice(freq=600, osc_type=OscType.SINE, duration=0.1,
                        volume=0.35, env_shape=EnvShape.PERCUSSIVE)
        s1 = synthesize_voice(v1)
        s2 = synthesize_voice(v2)
        gap = np.zeros(int(0.04 * self.sr), dtype=np.float32)
        sig = np.concatenate([s1, gap, s2])
        return self._save_raw_wav(sig, "sfx_ui_resume.wav")

    def generate_ui_quit(self) -> str:
        """UI quit — descending three-tone."""
        sigs = []
        for freq in [900, 600, 300]:
            v = SynthVoice(freq=freq, osc_type=OscType.SINE, duration=0.1,
                           volume=0.3, env_shape=EnvShape.PERCUSSIVE)
            s = synthesize_voice(v)
            sigs.append(s)
        gap = np.zeros(int(0.03 * self.sr), dtype=np.float32)
        combined = np.concatenate([sigs[0], gap, sigs[1], gap, sigs[2]])
        return self._save_raw_wav(combined, "sfx_ui_quit.wav")

    # ── New SFX ──
    def generate_nitro(self) -> str:
        return self._synthesize_to_wav(
            DRIVING_SFX_PRESETS["sfx_nitro"], "sfx_nitro.wav")

    def generate_screech(self) -> str:
        return self._synthesize_to_wav(
            DRIVING_SFX_PRESETS["sfx_screech"], "sfx_screech.wav")

    def generate_near_miss(self) -> str:
        return self._synthesize_to_wav(
            DRIVING_SFX_PRESETS["sfx_near_miss"], "sfx_near_miss.wav")

    def generate_milestone(self) -> str:
        return self._synthesize_to_wav(
            DRIVING_SFX_PRESETS["sfx_milestone"], "sfx_milestone.wav")

    def generate_warning(self) -> str:
        return self._synthesize_to_wav(
            DRIVING_SFX_PRESETS["sfx_warning"], "sfx_warning.wav")

    def generate_coin(self) -> str:
        return self._synthesize_to_wav(
            DRIVING_SFX_PRESETS["sfx_coin"], "sfx_coin.wav")

    def generate_shield(self) -> str:
        return self._synthesize_to_wav(
            DRIVING_SFX_PRESETS["sfx_shield"], "sfx_shield.wav")

    def generate_speed_boost(self) -> str:
        return self._synthesize_to_wav(
            DRIVING_SFX_PRESETS["sfx_speed_boost"], "sfx_speed_boost.wav")

    # ════════════════════════════════════════════════════════════
    #  Music Generators (5-layer progressive system)
    # ════════════════════════════════════════════════════════════

    def generate_bass(self) -> str:
        """Bass layer — driving square+sub synthwave bass."""
        return self._synthesize_music_to_wav(
            HIGHWAY_BASS, "music_bass.wav", duration=30.0)

    def generate_arp(self) -> str:
        """Arp layer — bright saw arpeggios."""
        return self._synthesize_music_to_wav(
            HIGHWAY_ARP, "music_arp.wav", duration=30.0)

    def generate_drums(self) -> str:
        """Drums layer — complex electronic rhythm."""
        # Use custom drum synthesis (music pattern for rhythm, synth for sounds)
        pattern = HIGHWAY_DRUMS
        beat_dur = 60.0 / pattern.bpm
        total_beats = sum(pattern.durations)
        loop_dur = total_beats * beat_dur
        loops = max(1, int(30.0 / loop_dur) + 1)

        wave_data = np.array([], dtype=np.float64)

        for _ in range(loops):
            bar_data = np.zeros(int(self.sr * loop_dur), dtype=np.float64)
            pos = 0
            for i, (note, dur_beats) in enumerate(zip(pattern.notes, pattern.durations)):
                dur_s = dur_beats * beat_dur
                n_samp = int(dur_s * self.sr)

                if note is not None:
                    if i % 4 == 0:
                        # Kick — 4-on-the-floor
                        t_kick = np.linspace(0, 0.15, int(0.15 * self.sr), dtype=np.float64)
                        sweep_f = 180 - 135 * np.minimum(1.0, t_kick / 0.15)
                        kick = 0.55 * np.exp(-t_kick * 10) * np.sin(2 * np.pi * sweep_f * t_kick)
                        kick += 0.12 * np.exp(-t_kick * 50) * np.sin(2 * np.pi * sweep_f * 2 * t_kick)
                        end_idx = min(pos + len(kick), len(bar_data))
                        if pos < len(bar_data):
                            bar_data[pos:end_idx] += kick[:end_idx - pos]
                    elif i % 8 in [4, 12]:
                        # Snare — noise + tone
                        t_sn = np.linspace(0, 0.1, int(0.1 * self.sr), dtype=np.float64)
                        sn_noise = _osc_noise_white(len(t_sn)) * 0.28
                        env_sn = make_envelope(len(t_sn), EnvShape.PERCUSSIVE)
                        sn = sn_noise * env_sn
                        sn_tone = 0.15 * np.sin(2 * np.pi * 200 * t_sn)
                        sn += sn_tone * env_sn * 0.6
                        end_idx = min(pos + len(sn), len(bar_data))
                        if pos < len(bar_data):
                            bar_data[pos:end_idx] += sn[:end_idx - pos]
                    else:
                        # Hi-hat — short noise
                        t_hh = np.linspace(0, 0.03, int(0.03 * self.sr), dtype=np.float64)
                        hh = _osc_noise_white(len(t_hh)) * 0.08
                        env_hh = make_envelope(len(t_hh), EnvShape.PERCUSSIVE)
                        hh = hh * env_hh
                        end_idx = min(pos + len(hh), len(bar_data))
                        if pos < len(bar_data):
                            bar_data[pos:end_idx] += hh[:end_idx - pos]

                pos += n_samp

            wave_data = np.concatenate([wave_data, bar_data])

        # Apply light processing
        chain = EffectChain(lp_filter_hz=12000, stereo_width=0.15)
        processed = process_effects(wave_data.astype(np.float64), chain)
        return self._save_raw_wav(processed.astype(np.float32), "music_drums.wav")

    def generate_atmosphere(self) -> str:
        """Atmosphere — lush pad with LFO breathing."""
        return self._synthesize_music_to_wav(
            HIGHWAY_ATMOSPHERE, "music_atmosphere.wav", duration=30.0)

    def generate_melody(self) -> str:
        """Melody — catchy synthwave lead with vibrato."""
        return self._synthesize_music_to_wav(
            HIGHWAY_MELODY, "music_melody.wav", duration=30.0)

    # ════════════════════════════════════════════════════════════
    #  Utility
    # ════════════════════════════════════════════════════════════

    def _save_raw_wav(self, sig: np.ndarray, filename: str) -> str:
        """Save a raw numpy array as WAV."""
        if sig.ndim == 1:
            final = sig.reshape(-1, 1)
        else:
            final = sig
        peak = np.max(np.abs(final))
        if peak > 1.0:
            final = final / peak * 0.98
        wav_int = np.clip(final * 32767, -32768, 32767).astype(np.int16)
        filepath = self.output_dir / filename
        wavfile.write(str(filepath), self.sr, wav_int)
        dur = len(sig) / self.sr
        print(f"  [Synthesizer] {filename} ({dur:.2f}s)")
        return str(filepath)

    def generate_all(self) -> dict:
        """
        Generate ALL audio assets and return a path map.
        Includes core assets + new bonus SFX.
        """
        print("=" * 55)
        print("  [AudioSynthesizer] faatt engine — synthwave driving audio")
        print("=" * 55)

        paths = {}

        # ── Music layers (5 layers) ──
        print("\n  Music layers:")
        paths['music_bass'] = self.generate_bass()
        paths['music_arp'] = self.generate_arp()
        paths['music_drums'] = self.generate_drums()
        paths['music_atmosphere'] = self.generate_atmosphere()
        paths['music_melody'] = self.generate_melody()

        # ── Core SFX (6 SFX) ──
        print("\n  Core SFX:")
        paths['sfx_engine'] = self.generate_engine()
        paths['sfx_drift'] = self.generate_drift()
        paths['sfx_crash'] = self.generate_crash()
        paths['sfx_ui_pause'] = self.generate_ui_pause()
        paths['sfx_ui_resume'] = self.generate_ui_resume()
        paths['sfx_ui_quit'] = self.generate_ui_quit()

        # ── New bonus SFX (8 SFX) ──
        print("\n  Bonus driving SFX:")
        paths['sfx_nitro'] = self.generate_nitro()
        paths['sfx_screech'] = self.generate_screech()
        paths['sfx_near_miss'] = self.generate_near_miss()
        paths['sfx_milestone'] = self.generate_milestone()
        paths['sfx_warning'] = self.generate_warning()
        paths['sfx_coin'] = self.generate_coin()
        paths['sfx_shield'] = self.generate_shield()
        paths['sfx_speed_boost'] = self.generate_speed_boost()

        print(f"\n{'=' * 55}")
        print(f"  Done! {len(paths)} audio files generated.")
        print(f"  Output: {self.output_dir}")
        print(f"{'=' * 55}")

        return paths
