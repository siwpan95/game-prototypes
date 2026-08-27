"""Adaptive Karplus-Strong string synthesizer.

A delay-line resonator whose feedback / low-pass / pitch adapt to the player's
motion and environment density. Used by ``DynamicAudioSystem`` to turn the
sonar signal into a plucked-string-like tone.
"""
import random
from collections import deque

from doom_game.config import MIN_AUDIO_VELOCITY


class AdaptiveKarplusStrong:
    """Delay-line based plucked-string synthesis with adaptive parameters."""

    def __init__(self, sample_rate: int = 44100):
        self.sample_rate = sample_rate
        # Base delay length -> ~220 Hz fundamental at rest.
        self.base_delay_size = max(2, sample_rate // 220)
        self.delay_line = deque(maxlen=self.base_delay_size * 2)
        self.feedback = 0.995
        self.lowpass_factor = 0.5
        self.read_ptr = 0
        self.is_active = False
        self.activation_threshold = 0.01
        for _ in range(self.base_delay_size):
            self.delay_line.append(0.0)

    def adapt_parameters(self, velocity, density, signal) -> None:
        """Re-tune the resonator from motion (velocity) and environment."""
        self.is_active = abs(signal) > self.activation_threshold
        if not self.is_active:
            return

        v = min(1.0, velocity / 5.0)
        self.feedback = 0.99 + v * 0.009            # faster motion -> longer decay

        d = min(1.0, density)
        self.lowpass_factor = 0.3 + d * 0.4         # open spaces -> brighter

        intensity = min(1.0, velocity * density * 2.0)
        delay_scale = 0.8 + intensity * 0.4         # motion+proximity -> pitch shift
        new_size = int(self.base_delay_size * delay_scale)
        if new_size != len(self.delay_line):
            while len(self.delay_line) < new_size:
                self.delay_line.append(0.0)
            while len(self.delay_line) > new_size:
                self.delay_line.pop()

    def fill_with_signal(self, signal, density) -> None:
        """Inject the sonar signal into a few random delay-line positions."""
        if not self.is_active:
            return
        d = min(1.0, density)
        adjusted = signal * (0.5 + d * 0.5)         # open spaces attenuate
        if len(self.delay_line) > 0:
            n = max(1, int(d * 5))
            for _ in range(n):
                idx = random.randint(0, len(self.delay_line) - 1)
                self.delay_line[idx] = (
                    self.delay_line[idx] * 0.3 + adjusted * 0.7)

    def process(self) -> float:
        """Advance the resonator by one sample and return it."""
        if not self.is_active or len(self.delay_line) < 2:
            return 0.0
        size = len(self.delay_line)
        s1 = self.delay_line[self.read_ptr]
        nxt = (self.read_ptr + 1) % size
        s2 = self.delay_line[nxt]
        filtered = (s1 * self.lowpass_factor
                    + s2 * (1.0 - self.lowpass_factor)) * self.feedback
        self.delay_line[self.read_ptr] = filtered
        self.read_ptr = (self.read_ptr + 1) % size
        return filtered

    def get_info(self) -> dict:
        """Return current synth parameters for visualisation / debugging."""
        freq = self.sample_rate / len(self.delay_line) if self.delay_line else 0.0
        return {
            "active": self.is_active,
            "frequency": freq,
            "feedback": self.feedback,
            "lowpass": self.lowpass_factor,
            "delay_size": len(self.delay_line),
        }
