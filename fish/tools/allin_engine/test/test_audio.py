"""
test/test_audio.py — audio 层单元测试

测试 note_to_freq (音符转频率)、SynthVoice 数据类、
振荡器与包络 (需 numpy)。

运行：
    cd <fish仓>/tools && python -m allin_engine.test.test_audio
"""

import sys
import os
import math

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))

from allin_engine.audio.synth import (
    SynthVoice, note_to_freq, SR, HAS_NUMPY,
    OscType, EnvShape, ADSRParams,
    oscillator, make_envelope, synthesize_voice,
)
from allin_engine.audio.music_gen import MusicPattern, generate_music_wav


# ══════════════════════════════════════════════════════════
# note_to_freq 测试 (纯 Python)
# ══════════════════════════════════════════════════════════

def test_note_to_freq_a4():
    """A4 = 440 Hz"""
    freq = note_to_freq("A4")
    assert abs(freq - 440.0) < 0.01


def test_note_to_freq_a5():
    """A5 = 880 Hz (A4 高八度)"""
    freq = note_to_freq("A5")
    assert abs(freq - 880.0) < 0.5


def test_note_to_freq_a3():
    """A3 = 220 Hz (A4 低八度)"""
    freq = note_to_freq("A3")
    assert abs(freq - 220.0) < 0.3


def test_note_to_freq_c4():
    """C4 ≈ 261.63 Hz"""
    freq = note_to_freq("C4")
    assert abs(freq - 261.63) < 0.1


def test_note_to_freq_c5():
    """C5 ≈ 523.25 Hz"""
    freq = note_to_freq("C5")
    assert abs(freq - 523.25) < 0.5


def test_note_to_freq_sharp():
    """升号 C#4"""
    freq = note_to_freq("C#4")
    assert freq > note_to_freq("C4")
    assert freq < note_to_freq("D4")


def test_note_to_freq_flat():
    """降号 Eb4"""
    freq = note_to_freq("Eb4")
    # Eb4 应该等于 D#4
    assert abs(freq - note_to_freq("D#4")) < 0.01


def test_note_to_freq_underscore():
    """下划线分隔 Eb_4"""
    freq = note_to_freq("Eb_4")
    assert abs(freq - note_to_freq("Eb4")) < 0.01


def test_note_to_freq_with_spaces():
    """含空格"""
    freq = note_to_freq("  A4  ")
    assert abs(freq - 440.0) < 0.01


def test_note_to_freq_custom_a4():
    """自定义 A4 基准"""
    freq = note_to_freq("A4", a4_freq=442.0)
    assert abs(freq - 442.0) < 0.01


def test_note_to_freq_invalid():
    """无效音符抛出 ValueError"""
    try:
        note_to_freq("INVALID")
        assert False, "应该抛出 ValueError"
    except ValueError:
        pass


def test_note_to_freq_invalid_no_octave():
    """无八度数"""
    try:
        note_to_freq("C")
        assert False, "应该抛出 ValueError"
    except ValueError:
        pass


def test_note_to_freq_octave_range():
    """不同八度递增"""
    f3 = note_to_freq("C3")
    f4 = note_to_freq("C4")
    f5 = note_to_freq("C5")
    assert f3 < f4 < f5
    # C5 约是 C4 的 2 倍
    assert abs(f5 / f4 - 2.0) < 0.01


# ══════════════════════════════════════════════════════════
# SynthVoice 数据类测试
# ══════════════════════════════════════════════════════════

def test_synth_voice_default():
    """测试默认 SynthVoice"""
    v = SynthVoice()
    assert v.freq == 440.0
    assert v.osc_type == OscType.SINE
    assert v.duration == 0.15
    assert v.volume == 1.0
    assert v.env_shape == EnvShape.PERCUSSIVE
    assert v.harmonics == []


def test_synth_voice_custom():
    """测试自定义 SynthVoice"""
    v = SynthVoice(
        freq=220.0,
        osc_type=OscType.SAW,
        duration=0.3,
        volume=0.7,
        env_shape=EnvShape.PAD,
        pitch_mod=2.0,
        vibrato_rate=5.0,
        vibrato_depth=0.5,
        detune=0.1,
        harmonics=[(2, 0.3)],
    )
    assert v.freq == 220.0
    assert v.osc_type == OscType.SAW
    assert v.pitch_mod == 2.0
    assert v.vibrato_depth == 0.5
    assert len(v.harmonics) == 1


# ══════════════════════════════════════════════════════════
# ADSRParams 测试
# ══════════════════════════════════════════════════════════

def test_adsr_params_default():
    """测试默认 ADSR"""
    adsr = ADSRParams()
    assert adsr.attack == 0.01
    assert adsr.decay == 0.1
    assert adsr.sustain == 0.7
    assert adsr.release == 0.3


def test_adsr_params_custom():
    """测试自定义 ADSR"""
    adsr = ADSRParams(attack=0.05, decay=0.2, sustain=0.5, release=0.5)
    assert adsr.sustain == 0.5
    assert adsr.release == 0.5


# ══════════════════════════════════════════════════════════
# 振荡器测试 (需 numpy)
# ══════════════════════════════════════════════════════════

def _skip_if_no_numpy():
    if not HAS_NUMPY:
        import pytest
        pytest.skip("numpy 不可用")


def test_oscillator_sine():
    """测试正弦波振荡器"""
    if not HAS_NUMPY:
        return
    import numpy as np

    t = np.linspace(0, 0.01, 441, dtype=np.float64)
    sig = oscillator(t, 440.0, OscType.SINE)
    assert len(sig) == 441
    assert sig.dtype == np.float64
    assert -1.0 <= np.max(sig) <= 1.0


def test_oscillator_saw():
    """测试锯齿波"""
    if not HAS_NUMPY:
        return
    import numpy as np

    t = np.linspace(0, 0.01, 441, dtype=np.float64)
    sig = oscillator(t, 440.0, OscType.SAW)
    assert len(sig) == 441


def test_oscillator_square():
    """测试方波"""
    if not HAS_NUMPY:
        return
    import numpy as np

    t = np.linspace(0, 0.01, 441, dtype=np.float64)
    sig = oscillator(t, 440.0, OscType.SQUARE, duty=0.3)
    assert len(sig) == 441


def test_oscillator_triangle():
    """测试三角波"""
    if not HAS_NUMPY:
        return
    import numpy as np

    t = np.linspace(0, 0.01, 441, dtype=np.float64)
    sig = oscillator(t, 440.0, OscType.TRIANGLE)
    assert len(sig) == 441


def test_oscillator_noise_white():
    """测试白噪声"""
    if not HAS_NUMPY:
        return
    import numpy as np

    sig = oscillator(np.array([]), 440.0, OscType.NOISE_WHITE)
    assert len(sig) == 0  # 空 t → 空输出


def test_oscillator_noise_pink():
    """测试粉红噪声"""
    if not HAS_NUMPY:
        return
    import numpy as np

    t = np.linspace(0, 0.1, 4410, dtype=np.float64)
    sig = oscillator(t, 440.0, OscType.NOISE_PINK)
    assert len(sig) == 4410


def test_oscillator_noise_brown():
    """测试棕噪声"""
    if not HAS_NUMPY:
        return
    import numpy as np

    t = np.linspace(0, 0.1, 4410, dtype=np.float64)
    sig = oscillator(t, 440.0, OscType.NOISE_BROWN)
    assert len(sig) == 4410


# ══════════════════════════════════════════════════════════
# 包络测试 (需 numpy)
# ══════════════════════════════════════════════════════════

def test_make_envelope_percussive():
    """测试打击乐包络"""
    if not HAS_NUMPY:
        return
    import numpy as np

    env = make_envelope(1000, EnvShape.PERCUSSIVE)
    assert len(env) == 1000
    assert 0.0 <= np.max(env) <= 1.0
    assert env[-1] < env[0] or env[0] < env[-1]  # 有衰减


def test_make_envelope_pad():
    """测试铺底包络"""
    if not HAS_NUMPY:
        return
    import numpy as np

    env = make_envelope(1000, EnvShape.PAD)
    assert len(env) == 1000


def test_make_envelope_pluck():
    """测试拨弦包络"""
    if not HAS_NUMPY:
        return
    import numpy as np

    env = make_envelope(1000, EnvShape.PLUCK)
    assert len(env) == 1000
    assert env[-1] < 0.1  # 拨弦衰减很快


def test_make_envelope_swell():
    """测试渐强包络"""
    if not HAS_NUMPY:
        return
    import numpy as np

    env = make_envelope(1000, EnvShape.SWELL)
    assert len(env) == 1000
    # swell 先渐强
    assert env[100] < env[500]


def test_make_envelope_reverse():
    """测试反转包络"""
    if not HAS_NUMPY:
        return
    import numpy as np

    env = make_envelope(1000, EnvShape.REVERSE)
    assert len(env) == 1000


def test_make_envelope_with_adsr():
    """测试自定义 ADSR"""
    if not HAS_NUMPY:
        return
    import numpy as np

    adsr = ADSRParams(attack=0.05, decay=0.15, sustain=0.5, release=0.3)
    env = make_envelope(1000, EnvShape.PERCUSSIVE, adsr=adsr)
    assert len(env) == 1000
    assert 0.0 <= np.max(env) <= 1.0


# ══════════════════════════════════════════════════════════
# synthesize_voice 测试 (需 numpy)
# ══════════════════════════════════════════════════════════

def test_synthesize_voice_basic():
    """测试基础合成"""
    if not HAS_NUMPY:
        return
    import numpy as np

    voice = SynthVoice(freq=440.0, duration=0.01, osc_type=OscType.SINE)
    sig = synthesize_voice(voice, sample_rate=22050)
    assert len(sig) == max(int(0.01 * 22050), 1)
    assert sig.dtype == np.float32
    assert -1.0 <= float(np.max(sig)) <= 1.0


def test_synthesize_voice_with_harmonics():
    """测试泛音合成"""
    if not HAS_NUMPY:
        return
    import numpy as np

    voice = SynthVoice(
        freq=440.0, duration=0.01, osc_type=OscType.SAW,
        harmonics=[(2, 0.3), (3, 0.15)],
    )
    sig = synthesize_voice(voice, sample_rate=22050)
    assert len(sig) == max(int(0.01 * 22050), 1)


def test_synthesize_voice_with_vibrato():
    """测试颤音"""
    if not HAS_NUMPY:
        return
    import numpy as np

    voice = SynthVoice(
        freq=440.0, duration=0.02,
        vibrato_rate=5.0, vibrato_depth=0.5,
    )
    sig = synthesize_voice(voice, sample_rate=22050)
    assert len(sig) == max(int(0.02 * 22050), 1)


def test_synthesize_voice_with_detune():
    """测试 Unison detune"""
    if not HAS_NUMPY:
        return
    import numpy as np

    voice = SynthVoice(freq=440.0, duration=0.01, detune=0.2)
    sig = synthesize_voice(voice, sample_rate=22050)
    assert len(sig) == max(int(0.01 * 22050), 1)


# ══════════════════════════════════════════════════════════
# MusicPattern 测试
# ══════════════════════════════════════════════════════════

def test_music_pattern_create():
    """测试 MusicPattern 创建"""
    pattern = MusicPattern(
        name="test",
        notes=["C4", "D4", "E4"],
        durations=[0.25, 0.25, 0.5],
        bpm=120,
    )
    assert len(pattern.notes) == 3
    assert len(pattern.durations) == 3
    assert pattern.bpm == 120


def test_music_pattern_defaults():
    """测试 MusicPattern 默认属性"""
    pattern = MusicPattern(name="default", notes=["A4"], durations=[0.5])
    assert pattern.bpm == 120
    assert pattern.loop is True
    assert pattern.volume == 0.18


def test_generate_music_wav_no_numpy():
    """测试 generate_music_wav 无 numpy 时行为"""
    if HAS_NUMPY:
        return  # 有 numpy 时不测试降级路径
    try:
        result = generate_music_wav(MusicPattern(name="t", notes=["A4"], durations=[0.5]))
        assert result is None or isinstance(result, bytes)
    except ImportError:
        pass  # 预期: 无numpy时raise ImportError
