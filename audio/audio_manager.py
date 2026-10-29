"""
AudioManager — High-level audio facade for Endless Highway.
Combines MusicSystem + SFXSystem with faatt-enhanced synthesis.
Event-name driven SFX triggering, distance-based adaptive music.
Playback backend: sounddevice (via sd_mixer).
"""

import os
from . import sd_mixer as mixer  # 同名表面 API，零改动接入
from .music_system import MusicSystem
from .sfx_system import SFXSystem


class AudioManager:
    """
    Top-level audio manager.
    Usage:
        am = AudioManager()
        am.initialize(asset_paths)
        am.start_music()
        am.update(distance_km, dt)
        am.trigger_sfx('crash')
        am.shutdown()
    """

    def __init__(self):
        self.music_sys = None
        self.sfx_sys = None
        self.asset_paths = {}
        self._initialized = False
        self._music_started = False
        self._last_milestone = 0  # Track last milestone distance

    def initialize(self, asset_paths: dict) -> bool:
        self.asset_paths = asset_paths

        if not mixer.get_init():
            mixer.init(frequency=44100, size=-16, channels=2, buffer=512)
            print("[AudioManager] sd_mixer (sounddevice) initialized.")

        self.music_sys = MusicSystem(asset_paths)
        self.sfx_sys = SFXSystem(asset_paths)

        music_ok = self.music_sys.initialize()
        sfx_ok = self.sfx_sys.initialize()

        self._initialized = music_ok or sfx_ok
        print(f"[AudioManager] Init: music={'OK' if music_ok else 'FAIL'}, "
              f"SFX={'OK' if sfx_ok else 'FAIL'}")
        return self._initialized

    # ── Music control ──────────────────────────────────────

    def start_music(self):
        if self.music_sys:
            self.music_sys.start()
            self._music_started = True

    def stop_music(self, fade_ms: int = 1000):
        if self.music_sys:
            self.music_sys.stop(fade_ms)
            self._music_started = False

    # ── Engine control ─────────────────────────────────────

    def start_engine_sfx(self):
        if self.sfx_sys:
            self.sfx_sys.start_engine()

    def stop_engine_sfx(self):
        if self.sfx_sys:
            self.sfx_sys.stop_engine()

    # ── Frame update (parameter-driven) ────────────────────

    def update(self, distance_km: float, dt: float, is_drifting: bool = False):
        if not self._initialized:
            return

        if self.music_sys:
            self.music_sys.update(distance_km, dt)
            self.music_sys.set_drift_filter_open(is_drifting)

        if self.sfx_sys:
            speed_proxy = 5.0 + distance_km * 0.1
            self.sfx_sys.update_engine_pitch(speed_proxy)

        # ── Distance milestone triggers ──
        milestone = int(distance_km)
        if milestone > self._last_milestone and milestone > 0:
            self._last_milestone = milestone
            self.trigger_sfx('event:/SFX/Milestone')

    # ── SFX triggers (event-name driven) ───────────────────

    def trigger_sfx(self, event_name: str):
        if not self.sfx_sys:
            return

        mapping = {
            # Core SFX
            'event:/SFX/Drift':      self.sfx_sys.play_drift,
            'event:/SFX/Crash':      self.sfx_sys.play_crash,
            'event:/SFX/UI_Pause':   self.sfx_sys.play_ui_pause,
            'event:/SFX/UI_Resume':  self.sfx_sys.play_ui_resume,
            'event:/SFX/UI_Quit':    self.sfx_sys.play_ui_quit,
            # Short aliases (core)
            'drift':     self.sfx_sys.play_drift,
            'crash':     self.sfx_sys.play_crash,
            'ui_pause':  self.sfx_sys.play_ui_pause,
            'ui_resume': self.sfx_sys.play_ui_resume,
            'ui_quit':   self.sfx_sys.play_ui_quit,
            # Bonus SFX
            'event:/SFX/Nitro':       self.sfx_sys.play_nitro,
            'event:/SFX/Screech':     self.sfx_sys.play_screech,
            'event:/SFX/NearMiss':    self.sfx_sys.play_near_miss,
            'event:/SFX/Milestone':   self.sfx_sys.play_milestone,
            'event:/SFX/Warning':     self.sfx_sys.play_warning,
            'event:/SFX/Coin':        self.sfx_sys.play_coin,
            'event:/SFX/Shield':      self.sfx_sys.play_shield,
            'event:/SFX/SpeedBoost':  self.sfx_sys.play_speed_boost,
            # Short aliases (bonus)
            'nitro':       self.sfx_sys.play_nitro,
            'screech':     self.sfx_sys.play_screech,
            'near_miss':   self.sfx_sys.play_near_miss,
            'milestone':   self.sfx_sys.play_milestone,
            'warning':     self.sfx_sys.play_warning,
            'coin':        self.sfx_sys.play_coin,
            'shield':      self.sfx_sys.play_shield,
            'speed_boost': self.sfx_sys.play_speed_boost,
        }

        func = mapping.get(event_name)
        if func:
            func()
        else:
            print(f"[AudioManager] Unknown SFX event: {event_name}")

    def trigger_random_sfx(self):
        """Play a random bonus SFX from the idle pool."""
        if self.sfx_sys:
            self.sfx_sys.play_random_bonus()

    # ── Shutdown ──────────────────────────────────────────

    def shutdown(self):
        if self.music_sys:
            self.music_sys.stop(fade_ms=500)
        if self.sfx_sys:
            self.sfx_sys.shutdown()
        self._initialized = False
        print("[AudioManager] AudioManager shut down.")

    # ── Diagnostics ───────────────────────────────────────

    def get_status(self) -> dict:
        status = {'music': {}, 'sfx': {}}
        if self.music_sys:
            status['music'] = self.music_sys.get_status()
        status['engine_playing'] = self.sfx_sys.engine_playing if self.sfx_sys else False
        return status
