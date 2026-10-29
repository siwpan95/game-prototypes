"""Dynamic audio system: integrates sonar + adaptive synthesizer.

Designed to be fully headless-safe: every ``sounddevice`` import and stream
open is guarded; if anything is unavailable the system degrades to
``enabled = False`` and never raises. ``DISABLE_AUDIO=1`` forces it off.
The audio callback runs on a daemon thread and is stopped via ``stop()``.
"""
import os
import threading
import time
from collections import deque

try:
    import numpy as np
except ImportError:  # pragma: no cover
    np = None

from doom_game.config import DISABLE_AUDIO, SAMPLE_RATE, AUDIO_BUFFER_SIZE
from doom_game.audio.sonar import PhysicsRaySonar
from doom_game.audio.karplus_strong import AdaptiveKarplusStrong


class DynamicAudioSystem:
    """Motion-triggered, environment-aware audio engine (headless-safe)."""

    def __init__(self, sample_rate: int = SAMPLE_RATE,
                 buffer_size: int = AUDIO_BUFFER_SIZE):
        self.sample_rate = sample_rate
        self.buffer_size = buffer_size

        # Core state.
        self.enabled = False
        self.sonar = None
        self.synth = None
        self.audio_thread = None
        self.running = False
        self.audio_module = None

        # Diagnostics used by the HUD visualiser.
        self.visualization_data = {
            "motion_signal": deque(maxlen=200),
            "synthesis_signal": deque(maxlen=200),
            "velocity": deque(maxlen=100),
            "density": deque(maxlen=100),
            "feedback": deque(maxlen=100),
            "frequency": deque(maxlen=100),
        }
        self.stats = {
            "total_samples": 0,
            "silent_frames": 0,
            "active_frames": 0,
            "max_velocity": 0.0,
            "avg_density": 0.0,
        }

        if not DISABLE_AUDIO:
            self._try_load_sounddevice()

    # ------------------------------------------------------------------ #
    # Lifecycle
    # ------------------------------------------------------------------ #
    def _try_load_sounddevice(self) -> None:
        """Try to import sounddevice; on any failure remain disabled."""
        try:
            import sounddevice as sd  # noqa: F401
            self.audio_module = sd
            self.enabled = True
        except Exception:
            self.audio_module = None
            self.enabled = False

    def start(self, x: float, y: float, angle: float, world) -> None:
        """Begin audio. No-op / safe if disabled or on any failure."""
        if DISABLE_AUDIO or not self.enabled:
            self.enabled = False
            return
        try:
            self.sonar = PhysicsRaySonar(x, y, angle, self.sample_rate)
            self.synth = AdaptiveKarplusStrong(self.sample_rate)
            self.running = True
            self.audio_thread = threading.Thread(
                target=self._audio_loop, args=(world,), daemon=True)
            self.audio_thread.start()
        except Exception:
            self.enabled = False
            self.running = False

    def stop(self) -> None:
        """Stop the audio thread (called from GameWorld.cleanup)."""
        self.running = False
        if self.audio_thread is not None:
            try:
                self.audio_thread.join(timeout=1.0)
            except Exception:
                pass
        self.audio_thread = None

    def update_position(self, x: float, y: float, angle: float) -> None:
        """Sync the player position/angle; only when enabled."""
        if self.enabled and self.sonar is not None:
            self.sonar.x = x
            self.sonar.y = y
            self.sonar.base_angle = angle

    # ------------------------------------------------------------------ #
    # Audio processing thread
    # ------------------------------------------------------------------ #
    def _audio_loop(self, world) -> None:
        try:
            sd = self.audio_module
            if sd is None:
                return

            def callback(outdata, frames, _time_info, status):
                if status:
                    pass
                samples = []
                for i in range(frames):
                    if i % 44 == 0 and self.sonar is not None:
                        signal, velocity, density = self.sonar.update(
                            self.sonar.x, self.sonar.y,
                            self.sonar.base_angle, world)
                        self.synth.adapt_parameters(velocity, density, signal)
                        self.synth.fill_with_signal(signal, density)

                        self.visualization_data["motion_signal"].append(signal)
                        self.visualization_data["velocity"].append(velocity)
                        self.visualization_data["density"].append(density)

                        self.stats["total_samples"] += 1
                        if abs(signal) < 0.001:
                            self.stats["silent_frames"] += 1
                        else:
                            self.stats["active_frames"] += 1
                        self.stats["max_velocity"] = max(
                            self.stats["max_velocity"], velocity)
                        if self.visualization_data["density"]:
                            self.stats["avg_density"] = (
                                sum(self.visualization_data["density"])
                                / len(self.visualization_data["density"]))

                    ks = self.synth.process() if self.synth else 0.0
                    self.visualization_data["synthesis_signal"].append(ks)
                    info = self.synth.get_info() if self.synth else {}
                    self.visualization_data["feedback"].append(
                        info.get("feedback", 0.0))
                    self.visualization_data["frequency"].append(
                        info.get("frequency", 0.0))

                    final = ks * 0.7
                    samples.append([final, final])

                if np is not None:
                    outdata[:] = np.array(samples, dtype=np.float32)
                else:  # pragma: no cover - numpy always present w/ sounddevice
                    outdata[:] = samples

            with sd.OutputStream(
                    samplerate=self.sample_rate,
                    blocksize=self.buffer_size,
                    channels=2,
                    callback=callback,
                    dtype="float32"):
                while self.running:
                    time.sleep(0.05)
        except Exception:
            # Any audio failure silently disables the system.
            self.enabled = False
            self.running = False

    # ------------------------------------------------------------------ #
    # Visualisation (only used while rendering, so pygame is available)
    # ------------------------------------------------------------------ #
    def visualize(self, surface, x: int, y: int, w: int, h: int) -> None:
        """Lightweight HUD panel showing velocity / density levels."""
        try:
            import pygame
        except ImportError:  # pragma: no cover
            return
        if surface is None:
            return
        pygame.draw.rect(surface, (15, 15, 25), (x, y, w, h))
        pygame.draw.rect(surface, (40, 40, 60), (x, y, w, h), 2)

        vel = self.stats.get("max_velocity", 0.0)
        density = self.stats.get("avg_density", 0.0)

        vw = int(min(1.0, vel / 5.0) * (w - 20))
        pygame.draw.rect(surface, (100, 200, 100), (x + 10, y + 22, vw, 12))

        dw = int(min(1.0, density) * (w - 20))
        pygame.draw.rect(surface, (100, 150, 255), (x + 10, y + 46, dw, 12))
