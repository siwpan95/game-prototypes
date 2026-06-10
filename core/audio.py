"""
音频管理器
- 表情音效和风扇音效走不同 mixer 通道，保持层次感
- 表情音效：Channel 0-3（前景，音量较高）
- 风扇音效：Channel 4-7（背景，音量较低，恶搞风格）
"""
import os
import pygame


class AudioManager:
    """统一管理表情音效和风扇音效，确保层次分离"""

    # 通道分配
    EXPR_CHANNELS = 4       # 表情音效通道数
    FAN_CHANNELS = 4        # 风扇音效通道数
    FAN_BASE_CHANNEL = 4    # 风扇通道起始编号

    def __init__(self, base_dir):
        self.base_dir = base_dir
        self._sound_cache = {}           # path -> Sound
        self._fan_sounds = {}            # name -> Sound
        self._expr_channel_idx = 0       # 轮询指针
        self._fan_channels = []          # 风扇 Channel 对象
        self._initialized = False

    def init(self):
        """在 pygame.mixer.init() 之后调用，分配通道"""
        total = self.EXPR_CHANNELS + self.FAN_CHANNELS
        pygame.mixer.set_num_channels(total)
        # 预留风扇通道
        self._fan_channels = [
            pygame.mixer.Channel(self.FAN_BASE_CHANNEL + i)
            for i in range(self.FAN_CHANNELS)
        ]
        self._initialized = True

    # ── 表情音效（前景） ────────────────────────────────────────

    def play_expression(self, sound_path):
        """播放表情音效，走前景通道，音量 0.7"""
        if not sound_path:
            return
        full = os.path.join(self.base_dir, sound_path)
        if not os.path.exists(full):
            return
        snd = self._get_or_load(full)
        if snd is None:
            return
        ch = pygame.mixer.Channel(self._expr_channel_idx % self.EXPR_CHANNELS)
        self._expr_channel_idx += 1
        ch.set_volume(0.7)
        ch.play(snd)

    # ── 风扇音效（背景） ────────────────────────────────────────

    def load_fan_sound(self, name, path):
        """预加载一个风扇音效"""
        if not os.path.exists(path):
            return
        snd = self._get_or_load(path)
        if snd:
            self._fan_sounds[name] = snd

    def play_fan_loop(self, name, volume=0.15, channel_idx=0):
        """在指定风扇通道上循环播放音效，音量较低"""
        if name not in self._fan_sounds:
            return
        if channel_idx >= len(self._fan_channels):
            return
        ch = self._fan_channels[channel_idx]
        snd = self._fan_sounds[name]
        ch.set_volume(volume)
        ch.play(snd, loops=-1)

    def stop_fan(self, channel_idx=0):
        """停止指定风扇通道"""
        if channel_idx < len(self._fan_channels):
            self._fan_channels[channel_idx].stop()

    def set_fan_volume(self, volume, channel_idx=0):
        """调整风扇通道音量"""
        if channel_idx < len(self._fan_channels):
            self._fan_channels[channel_idx].set_volume(volume)

    def play_fan_once(self, name, volume=0.3, channel_idx=1):
        """播放一次性风扇音效（如启动/停止），走备用通道"""
        if name not in self._fan_sounds:
            return
        if channel_idx >= len(self._fan_channels):
            return
        ch = self._fan_channels[channel_idx]
        snd = self._fan_sounds[name]
        ch.set_volume(volume)
        ch.play(snd)

    # ── 内部 ────────────────────────────────────────────────────

    def _get_or_load(self, path):
        if path in self._sound_cache:
            return self._sound_cache[path]
        try:
            snd = pygame.mixer.Sound(path)
            self._sound_cache[path] = snd
            return snd
        except pygame.error:
            return None
