"""
AudioSystem — ECS System that drives the AudioManager.
Runs every frame: reads GameState/Drift components,
calls AudioManager.update() and triggers SFX events.

Enhanced with faatt-engine: milestone chimes, near-miss detection,
bonus SFX triggers via event-name system.
"""

import random
from ecs import System, Component
from ecs.components import GameState, Drift, VehicleControl, Position


_audio_manager = None


def get_audio_manager():
    global _audio_manager
    return _audio_manager


def set_audio_manager(am):
    global _audio_manager
    _audio_manager = am


class AudioComponent(Component):
    """Marker component for future spatial audio expansion."""
    pass


class AudioSystem(System):
    """
    ECS Audio System — drives audio from game state.
    Responsibilities:
      1. Call AudioManager.update() with distance/drift state
      2. Trigger one-shot SFX on state transitions
      3. Distance milestone chimes (every 1km)
      4. Near-miss detection (close to edge, trigger warning)
      5. Drift SFX with cooldown
    """

    def __init__(self):
        self.audio = None
        self.prev_alive = True
        self.prev_paused = False
        self.engine_started = False
        self.crash_triggered = False
        self._drift_sfx_cooldown = 0.0
        self._near_miss_cooldown = 0.0
        self._near_miss_threshold = 4.0  # world units from center near road edge
        self._random_sfx_cooldown = random.uniform(3.0, 8.0)  # activate idle SFX

    def _ensure_audio(self):
        if self.audio is None:
            self.audio = get_audio_manager()
        return self.audio is not None

    def update(self, world, dt):
        if not self._ensure_audio():
            return

        am = self.audio

        state = world.get_singleton(GameState)
        if state is None:
            return

        # ── Start engine on first alive frame ──────────────
        if not self.engine_started and state.alive and not state.paused:
            am.start_engine_sfx()
            self.engine_started = True

        # ── State transitions → SFX ────────────────────────

        # Crash
        if self.prev_alive and not state.alive:
            am.trigger_sfx('event:/SFX/Crash')
            self.crash_triggered = True
            am.stop_engine_sfx()

        # Pause
        if not self.prev_paused and state.paused and state.alive:
            am.trigger_sfx('event:/SFX/UI_Pause')

        # Resume
        if self.prev_paused and not state.paused and state.alive:
            am.trigger_sfx('event:/SFX/UI_Resume')
            if not self.engine_started or not am.sfx_sys.engine_playing:
                am.start_engine_sfx()
                self.engine_started = True

        # ── Drift detection ────────────────────────────────
        is_drifting = False
        for entity in world.get_entities_with(Drift, Position):
            is_drifting = True
            self._drift_sfx_cooldown -= dt
            if self._drift_sfx_cooldown <= 0:
                am.trigger_sfx('event:/SFX/Drift')
                self._drift_sfx_cooldown = 1.5
            break

        # ── Near-miss detection ────────────────────────────
        # Check if vehicle is close to road edges
        player_x = None
        for entity in world.get_entities_with(VehicleControl, Position):
            pos = world.get_component(entity, Position)
            if pos:
                player_x = pos.x
                break

        if player_x is not None:
            # 近失检测（简化）：车辆贴近公路边缘时给出警示。
            # 边缘信息来自世界配置（road_half_width），这里用合理阈值估算。
            if state.alive and abs(player_x) > self._near_miss_threshold:
                self._near_miss_cooldown -= dt
                if self._near_miss_cooldown <= 0:
                    am.trigger_sfx('event:/SFX/NearMiss')
                    self._near_miss_cooldown = 0.6

        # ── Update adaptive music + engine ────────────────
        am.update(
            distance_km=state.distance_km,
            dt=dt,
            is_drifting=is_drifting,
        )

        # ── Random bonus SFX (keep soundscape alive) ─────
        if state.alive and not state.paused:
            self._random_sfx_cooldown -= dt
            if self._random_sfx_cooldown <= 0:
                am.trigger_random_sfx()
                self._random_sfx_cooldown = random.uniform(3.0, 8.0)

        # ── Save state for next frame ─────────────────────
        self.prev_alive = state.alive
        self.prev_paused = state.paused


# ── Helper: ensure audio assets exist ────────────────────

def ensure_audio_assets(asset_dir: str = "audio/assets") -> dict:
    """
    Generate audio assets if they don't exist.
    Uses faatt-enhanced AudioSynthesizer.
    """
    from pathlib import Path
    from .synthesizer import AudioSynthesizer

    out_dir = Path(asset_dir)
    synthesizer = AudioSynthesizer(str(out_dir))

    expected_files = [
        # Music
        'music_bass.wav', 'music_arp.wav', 'music_drums.wav',
        'music_atmosphere.wav', 'music_melody.wav',
        # Core SFX
        'sfx_engine.wav', 'sfx_drift.wav', 'sfx_crash.wav',
        'sfx_ui_pause.wav', 'sfx_ui_resume.wav', 'sfx_ui_quit.wav',
        # Bonus SFX
        'sfx_nitro.wav', 'sfx_screech.wav', 'sfx_near_miss.wav',
        'sfx_milestone.wav', 'sfx_warning.wav', 'sfx_coin.wav',
        'sfx_shield.wav', 'sfx_speed_boost.wav',
    ]

    need_generate = any(not (out_dir / f).exists() for f in expected_files)

    if need_generate:
        print("[AudioSystem] Audio assets not found or incomplete, generating with faatt engine...")
        return synthesizer.generate_all()
    else:
        paths = {}
        for f in expected_files:
            key = f.split('.')[0]
            fpath = out_dir / f
            if fpath.exists():
                paths[key] = str(fpath)
        print(f"[AudioSystem] All {len(paths)} audio assets found.")
        return paths
