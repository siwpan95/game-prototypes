"""实时音频合成器（基于 sounddevice）"""

import math
import threading
import numpy as np
import sounddevice as sd

from config import SAMPLE_RATE, BUFFER_SIZE, AUDIO_GAIN


class AudioSynthesizer:
    """实时合成音频，基于 Rider 的物理参数驱动。"""

    def __init__(self):
        self.stream = None
        self.lock = threading.Lock()
        self.current_freq = 440.0
        self.current_harmonics = [1.0]
        self.current_volume = 0.0
        self.current_chaos = 0.0
        self.on_ground = True
        self.phase = 0.0
        self.chaos_phase = 0.0

    def start(self):
        self.stream = sd.OutputStream(
            samplerate=SAMPLE_RATE, channels=1, dtype='float32',
            blocksize=BUFFER_SIZE, callback=self._callback)
        self.stream.start()

    def stop(self):
        if self.stream:
            self.stream.stop()
            self.stream.close()

    def update_params(self, params: dict):
        with self.lock:
            self.current_freq = params['freq']
            self.current_harmonics = params['harmonics']
            self.current_volume = params['volume']
            self.current_chaos = params['chaos']
            self.on_ground = params['on_ground']

    def _callback(self, outdata, frames, time_info, status):
        with self.lock:
            freq = self.current_freq
            harmonics = self.current_harmonics
            volume = self.current_volume
            chaos = self.current_chaos
            on_ground = self.on_ground

        buffer = np.zeros(frames, dtype=np.float32)
        phase_inc = 2 * np.pi * freq / SAMPLE_RATE
        chaos_inc = 2 * np.pi * chaos * 10 / SAMPLE_RATE

        for i in range(frames):
            self.chaos_phase += chaos_inc
            chaos_mod = 1.0 + math.sin(self.chaos_phase) * chaos * 0.5

            sample = 0.0
            for j, amp in enumerate(harmonics[:4]):
                hf = freq * (j + 1) * chaos_mod
                if on_ground:
                    wave = math.sin(self.phase * (j + 1))
                else:
                    # 空中用锯齿波
                    wave = 2 * (self.phase * (j + 1) % (2 * np.pi) / (2 * np.pi)) - 1
                sample += wave * amp * volume

            buffer[i] = sample * AUDIO_GAIN
            self.phase += phase_inc

        outdata[:] = buffer.reshape(-1, 1)
