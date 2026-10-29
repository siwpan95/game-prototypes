"""
SFXSystem — Sound effects system for Endless Highway.
Manages one-shot + looping SFX with faatt-engine generated assets.
Channel allocation: 0-3 SFX, 4+ Music.
Playback backend: sounddevice (sd_mixer).
"""

import os
import random

from . import sd_mixer as mixer  # 同名表面 API，零改动接入

# Channel allocation
SFX_CHANNEL_ENGINE = 0
SFX_CHANNEL_DRIFT = 1
SFX_CHANNEL_CRASH = 2
SFX_CHANNEL_UI_A = 3
SFX_CHANNEL_UI_B = 4
SFX_CHANNEL_UI_C = 5
SFX_CHANNEL_BONUS = 6  # Rotates for bonus SFX
SFX_CHANNEL_LOOP = 7   # Looping SFX channel


class SFXSystem:
    """
    Manages all sound effects with faatt-engine enhanced audio.
    - Core SFX: engine, drift, crash, ui_pause/resume/quit
    - Bonus SFX: nitro, screech, near_miss, milestone, warning, coin, shield, speed_boost
    """

    def __init__(self, asset_paths: dict):
        self.asset_paths = asset_paths
        self.sounds = {}
        self.engine_playing = False
        self._initialized = False
        self._bonus_channel_round = 0

    def initialize(self) -> bool:
        if self._initialized:
            return True

        mixer.set_num_channels(max(24, 16))

        sfx_keys = [
            'sfx_engine', 'sfx_drift', 'sfx_crash',
            'sfx_ui_pause', 'sfx_ui_resume', 'sfx_ui_quit',
            # Bonus SFX
            'sfx_nitro', 'sfx_screech', 'sfx_near_miss',
            'sfx_milestone', 'sfx_warning', 'sfx_coin',
            'sfx_shield', 'sfx_speed_boost',
        ]
        loaded = 0
        for key in sfx_keys:
            path = self.asset_paths.get(key)
            if not path or not os.path.isfile(path):
                continue
            try:
                sound = mixer.Sound(path)
                self.sounds[key] = sound
                loaded += 1
            except Exception as e:
                print(f"[SFXSystem] Failed to load {key}: {e}")

        self._initialized = True
        print(f"[SFXSystem] Loaded {loaded}/{len(sfx_keys)} SFX assets.")
        return loaded > 0

    # ── Core SFX ────────────────────────────────────────────

    def start_engine(self):
        if not self._initialized:
            self.initialize()
        if 'sfx_engine' in self.sounds and not self.engine_playing:
            ch = mixer.Channel(SFX_CHANNEL_ENGINE)
            ch.play(self.sounds['sfx_engine'], loops=-1)
            ch.set_volume(0.12)
            self.engine_playing = True

    def stop_engine(self):
        if self.engine_playing:
            mixer.Channel(SFX_CHANNEL_ENGINE).stop()
            self.engine_playing = False

    def play_drift(self):
        if 'sfx_drift' in self.sounds:
            ch = mixer.Channel(SFX_CHANNEL_DRIFT)
            ch.play(self.sounds['sfx_drift'])
            ch.set_volume(0.45)

    def play_crash(self):
        if 'sfx_crash' in self.sounds:
            ch = mixer.Channel(SFX_CHANNEL_CRASH)
            ch.play(self.sounds['sfx_crash'])
            ch.set_volume(0.70)
            if self.engine_playing:
                mixer.Channel(SFX_CHANNEL_ENGINE).fadeout(500)

    def play_ui_pause(self):
        if 'sfx_ui_pause' in self.sounds:
            ch = mixer.Channel(SFX_CHANNEL_UI_A)
            ch.play(self.sounds['sfx_ui_pause'])
            ch.set_volume(0.4)

    def play_ui_resume(self):
        if 'sfx_ui_resume' in self.sounds:
            ch = mixer.Channel(SFX_CHANNEL_UI_B)
            ch.play(self.sounds['sfx_ui_resume'])
            ch.set_volume(0.4)

    def play_ui_quit(self):
        if 'sfx_ui_quit' in self.sounds:
            ch = mixer.Channel(SFX_CHANNEL_UI_C)
            ch.play(self.sounds['sfx_ui_quit'])
            ch.set_volume(0.4)

    # ── Bonus SFX (round-robin channels) ────────────────────

    def _play_bonus(self, key: str, volume: float = 0.4):
        """Play a bonus SFX on a rotating channel."""
        if key in self.sounds:
            ch_id = SFX_CHANNEL_BONUS + (self._bonus_channel_round % 3)
            self._bonus_channel_round += 1
            ch = mixer.Channel(ch_id)
            ch.play(self.sounds[key])
            ch.set_volume(volume)

    def play_nitro(self):
        self._play_bonus('sfx_nitro', volume=0.50)

    def play_screech(self):
        self._play_bonus('sfx_screech', volume=0.45)

    def play_near_miss(self):
        self._play_bonus('sfx_near_miss', volume=0.35)

    def play_milestone(self):
        self._play_bonus('sfx_milestone', volume=0.50)

    def play_warning(self):
        self._play_bonus('sfx_warning', volume=0.40)

    def play_coin(self):
        self._play_bonus('sfx_coin', volume=0.35)

    def play_shield(self):
        self._play_bonus('sfx_shield', volume=0.45)

    def play_speed_boost(self):
        self._play_bonus('sfx_speed_boost', volume=0.50)

    # ── Random bonus SFX (idle assets activated) ────────────

    # Bonus SFX pool for random playback (excluding milestone which fires on distance)
    RANDOM_BONUS_POOL = [
        'sfx_nitro', 'sfx_screech', 'sfx_near_miss',
        'sfx_warning', 'sfx_coin', 'sfx_shield', 'sfx_speed_boost',
    ]

    def play_random_bonus(self):
        """Play a random idle bonus SFX to keep the soundscape alive."""
        available = [k for k in self.RANDOM_BONUS_POOL if k in self.sounds]
        if not available:
            return
        key = random.choice(available)
        self._play_bonus(key, volume=0.55)

    # ── Engine pitch simulation ─────────────────────────────

    def update_engine_pitch(self, speed: float):
        """Simulate engine load via volume modulation."""
        if self.engine_playing:
            ch = mixer.Channel(SFX_CHANNEL_ENGINE)
            vol = 0.08 + min(0.12, speed * 0.02)
            ch.set_volume(vol)

    # ── Shutdown ───────────────────────────────────────────

    def shutdown(self):
        for i in range(SFX_CHANNEL_LOOP + 4):
            try:
                mixer.Channel(i).stop()
            except Exception:
                pass
        self.engine_playing = False
        print("[SFXSystem] All SFX stopped.")
