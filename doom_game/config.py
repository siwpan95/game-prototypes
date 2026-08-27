"""Global configuration constants.

All screen / gameplay / audio tunables live here so that individual modules
never hard-code resolutions or magic numbers (architecture rule #5).
"""
import math
import os

# ---------------------------------------------------------------------------
# Screen resolution (logical resolution)
# ---------------------------------------------------------------------------
SCREEN_WIDTH = 1024
SCREEN_HEIGHT = 768
HALF_HEIGHT = SCREEN_HEIGHT // 2

# ---------------------------------------------------------------------------
# Field of view and camera plane (classic Lodev raycasting formulation)
# ---------------------------------------------------------------------------
FOV = math.pi / 2                      # 90 degrees
CAMERA_PLANE_LEN = 1.0                # tan(FOV / 2) = 1.0
NUM_RAYS = SCREEN_WIDTH               # one ray per pixel column

# ---------------------------------------------------------------------------
# Textures
# ---------------------------------------------------------------------------
TEXTURE_SIZE = 64                     # wall texture is 64 x 64

# ---------------------------------------------------------------------------
# Rendering / collision limits
# ---------------------------------------------------------------------------
MAX_RENDER_DIST = 20.0                # max ray cast distance (grid units)

# ---------------------------------------------------------------------------
# Movement / rotation (grid units per frame)
# ---------------------------------------------------------------------------
MOVE_SPEED = 0.1
ROTATE_SPEED = 0.05

# ---------------------------------------------------------------------------
# Map generation defaults
# ---------------------------------------------------------------------------
DEFAULT_MAP_WIDTH = 24
DEFAULT_MAP_HEIGHT = 24
WORLD_SEED = 42

# ---------------------------------------------------------------------------
# Audio
# ---------------------------------------------------------------------------
MIN_AUDIO_VELOCITY = 0.05             # below this speed -> silent (physical constraint)
SAMPLE_RATE = 44100
AUDIO_BUFFER_SIZE = 512

# ---------------------------------------------------------------------------
# Headless / audio flags (read once at import time from the environment)
# ---------------------------------------------------------------------------
HEADLESS_TEST = os.environ.get("HEADLESS_TEST", "0") == "1"
DISABLE_AUDIO = os.environ.get("DISABLE_AUDIO", "0") == "1"

# Doppler mixing ratio used in DOOM_STYLE rendering (architecture rule #4).
DOPPLER_MIX = 0.7

# ---------------------------------------------------------------------------
# Entities (enemies / pickups) - incremental feature tunables
# ---------------------------------------------------------------------------
# Enemy combat / movement model.
ENEMY_HP = 30                          # base enemy health
ENEMY_DAMAGE = 10                      # contact damage dealt to the player
ENEMY_SPEED = 0.06                     # chase speed (grid units per frame)
ENEMY_PERCEPTION_RANGE = 6.0           # LOS + distance threshold to start chasing
ENEMY_CONTACT_DIST = 0.5               # distance at which an enemy hits the player
ENEMY_CONTACT_COOLDOWN = 1.0           # seconds between two contact hits

# Player health / score model.
PLAYER_MAX_HP = 100                    # maximum player health
HEALTH_PICKUP_AMOUNT = 25              # hp restored by a health pickup
SCORE_PICKUP_AMOUNT = 100              # score granted by a score pickup
PICKUP_CONTACT_DIST = 0.5              # distance at which a pickup is collected

# ---------------------------------------------------------------------------
# Frame timing (used by entity update loops)
# ---------------------------------------------------------------------------
FRAME_DT = 1.0 / 60.0                  # nominal per-frame delta time (seconds)

# ---------------------------------------------------------------------------
# Default level storage paths
# ---------------------------------------------------------------------------
DEFAULT_MAP_DIR = "G:/loly/maps"       # default directory holding level files
DEFAULT_MAP_PATH = "G:/loly/maps/level_01.json"  # default playable level

# ---------------------------------------------------------------------------
# Enemy ranged attack + projectiles (incremental V2 tunables)
# ---------------------------------------------------------------------------
ENEMY_ATTACK_RANGE = 5.0               # max firing distance (<= perception)
ENEMY_ATTACK_COOLDOWN = 1.5            # seconds between two shots
PROJECTILE_SPEED = 0.15                # grid units per frame (> ENEMY_SPEED)
PROJECTILE_DAMAGE = 8                  # hp removed on player hit
PROJECTILE_HIT_DIST = 0.4              # hit radius against the player
PROJECTILE_MAX_DIST = 8.0              # max flight distance (grid units)
PROJECTILE_COLOR = (255, 150, 40)      # bright orange (3D block + minimap dot)

# ---------------------------------------------------------------------------
# Player hitscan attack (SPACE key)
# ---------------------------------------------------------------------------
PLAYER_ATTACK_DAMAGE = 15              # hp removed from a struck enemy
PLAYER_ATTACK_RANGE = 6.0              # max hitscan distance (grid units)
PLAYER_ATTACK_COOLDOWN = 0.4           # seconds between two attacks
PLAYER_ATTACK_HIT_DIST = 0.4           # hit radius against an enemy

# ---------------------------------------------------------------------------
# Level editor
# ---------------------------------------------------------------------------
EDITOR_UNDO_DEPTH = 50                 # max undo snapshots kept on the stack

# ---------------------------------------------------------------------------
# Multi-level progression
# ---------------------------------------------------------------------------
LEVEL_SEQUENCE = [
    os.path.join(DEFAULT_MAP_DIR, "level_01.json"),
    os.path.join(DEFAULT_MAP_DIR, "level_02.json"),
    os.path.join(DEFAULT_MAP_DIR, "level_03.json"),
]
LEVEL_CLEAR_DURATION = 1.5             # seconds the LEVEL CLEAR card is shown
NEW_LEVEL_HP_FLOOR = 0.5               # hp floor ratio when entering a level
