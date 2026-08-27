"""Tests for the (headless-safe) audio subsystem.

Covers three requirements:
  * ``DISABLE_AUDIO=1`` forces the system to stay disabled and ``start()`` safe.
  * Sonar physics: stationary -> silent, moving -> audible (non-zero signal).
  * Degradation path: ``start()`` / ``stop()`` never raise, enabled may be True
    (sounddevice present) or gracefully False (no device) without crashing.
"""
import importlib

import pytest

from doom_game.audio.audio_system import DynamicAudioSystem
from doom_game.audio.sonar import PhysicsRaySonar


@pytest.fixture
def disabled_audio(monkeypatch):
    """Force DISABLE_AUDIO=1 and reload the affected modules in-place."""
    import doom_game.config as cfg
    import doom_game.audio.audio_system as asys

    monkeypatch.setenv("DISABLE_AUDIO", "1")
    importlib.reload(cfg)
    importlib.reload(asys)
    yield
    monkeypatch.delenv("DISABLE_AUDIO", raising=False)
    importlib.reload(cfg)
    importlib.reload(asys)


class TestDisabledAudio:
    def test_disabled_when_env_set(self, disabled_audio):
        audio = DynamicAudioSystem()
        assert audio.enabled is False

    def test_start_is_safe_noop_when_disabled(self, disabled_audio):
        audio = DynamicAudioSystem()
        # Must never raise, and must remain disabled.
        audio.start(2.5, 2.5, 0.0, None)
        assert audio.enabled is False
        audio.stop()


class TestSonarPhysics:
    def test_stationary_is_silent(self, small_map):
        sonar = PhysicsRaySonar(2.5, 2.5, 0.0, 44100)
        sig, vel, _ = sonar.update(2.5, 2.5, 0.0, small_map)
        assert abs(sig) < 1e-6
        assert vel == 0.0

    def test_moving_produces_audible_signal(self, small_map):
        sonar = PhysicsRaySonar(2.5, 2.5, 0.0, 44100)
        # Prime the motion tracker, then move a clearly perceptible distance.
        sonar.update(2.5, 2.5, 0.0, small_map)
        max_abs = 0.0
        for dx in (0.3, 0.6, 0.9, 1.2):
            sig, vel, _ = sonar.update(2.5 + dx, 2.5, 0.0, small_map)
            assert vel > sonar.min_velocity_threshold
            max_abs = max(max_abs, abs(sig))
        # Moving must yield a non-zero (audible) signal at least once.
        assert max_abs > 1e-6


class TestDegradation:
    def test_start_stop_never_raise(self, small_map):
        audio = DynamicAudioSystem()
        # enabled may be True (sounddevice present) or gracefully False.
        try:
            audio.start(2.5, 2.5, 0.0, small_map)
        except Exception as exc:  # pragma: no cover - robustness guarantee
            pytest.fail(f"start() raised unexpectedly: {exc}")
        assert isinstance(audio.enabled, bool)
        try:
            audio.stop()
        except Exception as exc:  # pragma: no cover - robustness guarantee
            pytest.fail(f"stop() raised unexpectedly: {exc}")
