"""
allin_engine.audio — 音频层子包

提供:
  - SynthVoice / ADSR: 合成音色参数 + 包络
  - synthesize_voice: 单音合成引擎
  - 振荡器: saw/square/sine/triangle/noise
  - MusicPattern / generate_music_wav: 音乐模式 + WAV 导出
  - 预设音乐: MENU/BATTLE/BOSS/DUNGEON/AMBIENT/VICTORY
  - AudioSystem: 统一音频播放接口（pygame mixer 后端）
"""

from allin_engine.audio.synth import (
    OscType, EnvShape, ADSRParams,
    SynthVoice, synthesize_voice,
    oscillator, make_envelope,
)
from allin_engine.audio.music_gen import (
    MusicPattern, generate_music_wav,
    MENU, BATTLE, BOSS, DUNGEON, AMBIENT, VICTORY,
)
from allin_engine.audio.audio_system import AudioSystem

__all__ = [
    "OscType",
    "EnvShape",
    "ADSRParams",
    "SynthVoice",
    "synthesize_voice",
    "oscillator",
    "make_envelope",
    "MusicPattern",
    "generate_music_wav",
    "MENU", "BATTLE", "BOSS", "DUNGEON", "AMBIENT", "VICTORY",
    "AudioSystem",
]
