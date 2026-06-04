"""
Audio package — Game Audio System for Endless Highway.
faatt-enhanced synthesis engine: numpy oscillators, 6 envelope shapes,
complete effects chain (LP/HP filter, distortion, reverb, stereo).
Style: High-energy synthwave driving music + cinematic SFX.
"""

# Lazy imports — pygame may not be available at import time
def __getattr__(name):
    if name in ('MusicSystem', 'SFXSystem', 'AudioManager'):
        if name == 'MusicSystem':
            from .music_system import MusicSystem
            return MusicSystem
        elif name == 'SFXSystem':
            from .sfx_system import SFXSystem
            return SFXSystem
        elif name == 'AudioManager':
            from .audio_manager import AudioManager
            return AudioManager
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

__all__ = ['AudioSynthesizer', 'MusicSystem', 'SFXSystem', 'AudioManager']
