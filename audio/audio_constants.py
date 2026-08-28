"""Audio Constants for KARD — 音频预算、路径、参数规范。

遵循游戏音频工程师规范：
- 平台音频预算（语音数、内存、CPU）
- 音频文件路径根目录
- pygame.mixer 配置
- 默认音量
"""

import sys
import os

# ── 项目根目录 ─────────────────────────────────────
_PROJECT_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))

# ── 音频文件路径 ────────────────────────────────────
SFX_ROOT: str = os.path.join(_PROJECT_ROOT, "assets", "audio")
MUSIC_ROOT: str = os.path.join(_PROJECT_ROOT, "assets", "audio", "music")

# ── pygame.mixer 配置 ──────────────────────────────
PYGAME_MIXER_CONFIG: dict = {
    "frequency": 44100,
    "size": -16,        # 16-bit signed
    "channels": 2,       # 立体声
    "buffer": 1024,    # 低延迟
    "allowedchanges": 0,
}

# ── 平台音频预算（音频工程师规范）─────────────────
# Voice count
VOICE_BUDGET: dict[str, int] = {
    "PC": 64,
    "CONSOLE": 48,
    "MOBILE": 24,
}

# Virtual voices（虚拟语音，超出真实语音数时使用）
VIRTUAL_VOICE_BUDGET: dict[str, int] = {
    "PC": 256,
    "CONSOLE": 128,
    "MOBILE": 64,
}

# 根据当前平台返回语音预算
def get_current_voice_count() -> int:
    """返回当前平台的真实语音数上限。"""
    # 简化：默认 PC
    return VOICE_BUDGET["PC"]

def get_current_virtual_voices() -> int:
    """返回当前平台的虚拟语音数上限。"""
    return VIRTUAL_VOICE_BUDGET["PC"]


# ── 内存预算 ──────────────────────────────────────
MEMORY_BUDGET: dict[str, dict] = {
    "SFX":    {"budget_mb": 32,  "format": "ADPCM", "policy": "decompress_to_ram"},
    "MUSIC":  {"budget_mb": 8,  "format": "Vorbis", "policy": "stream"},
    "AMBIENCE": {"budget_mb": 12, "format": "Vorbis", "policy": "stream"},
    "VO":     {"budget_mb": 4,  "format": "Vorbis", "policy": "stream"},
}

# ── CPU 预算 ──────────────────────────────────────
AUDIO_CPU_BUDGET_MS: float = 1.5   # 每帧最大 DSP 耗时（毫秒）
MAX_RAYCASTS_PER_FRAME: int = 4     # 空间音频射线检测上限

# ── 默认音量 ──────────────────────────────────────
DEFAULT_VOLUMES: dict[str, float] = {
    "master": 1.0,
    "sfx": 0.8,
    "music": 0.6,
    "ui": 0.9,
    "ambience": 0.5,
}

# ── 音频事件类型导出 ─────────────────────────────
# 从 audio_components 导入事件类型常量
try:
    from .audio_components import AudioEventType
    AUDIO_EVENT_TYPES = AudioEventType()
except Exception:
    AUDIO_EVENT_TYPES = None

# ── 音乐过渡时间 ─────────────────────────────────
MUSIC_FADE_MS: int = 1000      # 普通过渡淡入淡出
MUSIC_BEAT_SYNC: bool = True    # 是否节拍同步过渡
MUSIC_TEMPO_DEFAULT: float = 120.0  # BPM

# ── 3D 音频默认参数 ───────────────────────────
SPATIAL_DEFAULTS: dict = {
    "min_distance": 1.0,
    "max_distance": 50.0,
    "rolloff": "logarithmic",   # 衰减曲线
    "occlusion_lowpass_hz": 800.0,
}

# ── 混响区预设 ──────────────────────────────────
REVERB_PRESETS: dict[str, dict] = {
    "outdoor":    {"pre_delay": 20,  "decay": 0.8,  "wet": 0.15},
    "indoor":     {"pre_delay": 30,  "decay": 1.5,  "wet": 0.35},
    "cave":       {"pre_delay": 50,  "decay": 3.5,  "wet": 0.60},
    "metal_room": {"pre_delay": 15,  "decay": 1.0,  "wet": 0.45},
}
