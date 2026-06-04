"""
MusicSystem - Adaptive music system for Endless Highway.
Implements Deja Vu style layered music with distance-based intensity control.
Uses pygame.mixer for playback (no FMOD/Wwise dependency for this Pygame project).
"""

import pygame
import os
from pathlib import Path

# ── Music layer configuration ──────────────────────────────────────
# Each layer has: file key, fade-in distance (km), target volume
MUSIC_LAYERS = [
    {
        'key': 'music_bass',
        'name': 'Bass',
        'fade_in_start': 0.0,    # Always playing
        'fade_in_end': 0.5,      # Fuly audible by 0.5km
        'base_volume': 0.55,
    },
    {
        'key': 'music_arp',
        'name': 'Arpeggio',
        'fade_in_start': 1.0,
        'fade_in_end': 3.0,
        'base_volume': 0.35,
    },
    {
        'key': 'music_drums',
        'name': 'Drums',
        'fade_in_start': 2.0,
        'fade_in_end': 5.0,
        'base_volume': 0.50,
    },
    {
        'key': 'music_atmosphere',
        'name': 'Atmosphere',
        'fade_in_start': 5.0,
        'fade_in_end': 10.0,
        'base_volume': 0.30,
    },
    {
        'key': 'music_melody',
        'name': 'Melody',
        'fade_in_start': 10.0,
        'fade_in_end': 18.0,
        'base_volume': 0.28,
    },
]


class MusicSystem:
    """
    Manages adaptive music layers.
    Each layer is a pygame.mixer.Sound played on its own channel.
    Volume is controlled by DistanceIntensity (driven by state.distance_km).
    """

    def __init__(self, asset_paths: dict, num_channels: int = 8):
        self.asset_paths = asset_paths
        self.num_channels = num_channels
        self.channels = {}       # layer_key -> channel_id
        self.sounds = {}         # layer_key -> pygame.mixer.Sound
        self.current_intensity = 0.0
        self._initialized = False

    def initialize(self) -> bool:
        """Load all music assets and allocate channels."""
        if self._initialized:
            return True

        # Ensure enough channels
        pygame.mixer.set_num_channels(max(16, self.num_channels + 8))

        for layer in MUSIC_LAYERS:
            key = layer['key']
            path = self.asset_paths.get(key)
            if not path or not os.path.isfile(path):
                print(f"[MusicSystem] WARNING: Asset not found for {key}: {path}")
                continue

            try:
                sound = pygame.mixer.Sound(path)
                # Allocate a dedicated channel for this layer
                ch_id = len(self.channels) + 1  # channel 0 reserved for SFX
                channel = pygame.mixer.Channel(ch_id)
                channel.set_volume(0.0)  # start silent
                self.sounds[key] = sound
                self.channels[key] = ch_id
                print(f"[MusicSystem] Loaded layer '{layer['name']}' -> channel {ch_id}")
            except Exception as e:
                print(f"[MusicSystem] Failed to load {key}: {e}")

        self._initialized = True
        return len(self.sounds) > 0

    def start(self):
        """Start all music layers (silent, will fade in via update)."""
        if not self._initialized:
            self.initialize()

        for key, ch_id in self.channels.items():
            channel = pygame.mixer.Channel(ch_id)
            # Play looping, at volume=0 (silent start)
            channel.play(self.sounds[key], loops=-1)
            channel.set_volume(0.0)
        print("[MusicSystem] Music started (all layers silent, awaiting distance intensity).")

    def stop(self, fade_ms: int = 1000):
        """Fade out and stop all music layers."""
        for key, ch_id in self.channels.items():
            channel = pygame.mixer.Channel(ch_id)
            channel.fadeout(fade_ms)
        print("[MusicSystem] Music stopped.")

    def _calc_layer_volume(self, layer: dict, intensity: float) -> float:
        """
        Calculate the volume for a layer given current distance intensity.
        Uses smooth S-curve interpolation for musical feel.
        """
        start = layer['fade_in_start']
        end = layer['fade_in_end']
        base = layer['base_volume']

        if intensity <= start:
            return 0.0
        elif intensity >= end:
            return base
        else:
            # Normalize progress [0, 1] within the fade range
            progress = (intensity - start) / (end - start)
            # Apply smooth S-curve (smoothstep) for musical feel
            smooth = progress * progress * (3.0 - 2.0 * progress)
            return base * smooth

    def update(self, distance_km: float, dt: float):
        """
        Call每一个 frame. Update music layer volumes based on distance.
        Also handles drift filter effect (simulated via volume oscillation).
        """
        if not self._initialized:
            return

        # Map distance to intensity [0.0, 1.0]
        # Full intensity reached at 20km
        intensity = min(1.0, distance_km / 20.0)
        self.current_intensity = intensity

        for layer in MUSIC_LAYERS:
            key = layer['key']
            if key not in self.channels:
                continue

            ch_id = self.channels[key]
            channel = pygame.mixer.Channel(ch_id)
            target_vol = self._calc_layer_volume(layer, intensity)

            # Smooth volume interpolation (avoid clicks)
            current_vol = channel.get_volume()
            lerp_speed = 2.0  # ~0.5 sec to reach target
            new_vol = current_vol + (target_vol - current_vol) * min(1.0, lerp_speed * dt)
            channel.set_volume(max(0.0, min(1.0, new_vol)))

    def set_drift_filter_open(self, is_drifting: bool):
        """
        Deja Vu style: open a low-pass filter simulation on music
        by temporarily boosting bass+atmosphere layers.
        (pygame.mixer has no real filter; we simulate via volume boost)
        """
        for key in ['music_bass', 'music_atmosphere']:
            if key in self.channels:
                ch = pygame.mixer.Channel(self.channels[key])
                boost = 1.30 if is_drifting else 1.0
                current = ch.get_volume()
                # Apply boost to max volume (not beyond base)
                layer = next(l for l in MUSIC_LAYERS if l['key'] == key)
                max_v = layer['base_volume'] * boost
                ch.set_volume(min(max_v, ch.get_volume() * (1.1 if is_drifting else 0.99)))

    def get_status(self) -> dict:
        """Return current music system status for debugging."""
        status = {'intensity': round(self.current_intensity, 3), 'layers': {}}
        for layer in MUSIC_LAYERS:
            key = layer['key']
            if key in self.channels:
                vol = pygame.mixer.Channel(self.channels[key]).get_volume()
                status['layers'][layer['name']] = round(vol, 3)
        return status
