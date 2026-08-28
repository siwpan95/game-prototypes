"""Game constants for KARD - Vampire Survivors meets Slay the Spire meets Hearthstone."""

# ── Window ──────────────────────────────────────────────────────────────────
SCREEN_WIDTH = 1280
SCREEN_HEIGHT = 720
FPS = 60
TITLE = "KARD — Endless Card Survival"

# ── Colors ──────────────────────────────────────────────────────────────────
BG_COLOR = (22, 22, 40)
BG_BOARD = (30, 30, 55)
BG_ENEMY_ZONE = (25, 25, 48)

CARD_ATTACK_BG = (160, 44, 38)
CARD_SKILL_BG = (35, 110, 170)
CARD_MINION_BG = (32, 150, 80)
CARD_FRAME = (60, 60, 80)
CARD_HOVER_GLOW = (255, 220, 80)
CARD_SELECTED_GLOW = (80, 200, 255)
CARD_TARGET_GLOW = (255, 80, 80)

ENERGY_COLOR = (241, 196, 15)
ENERGY_BG = (30, 30, 30)
HP_COLOR = (220, 50, 50)
HP_BG = (80, 20, 20)
SHIELD_COLOR = (180, 200, 220)
SHIELD_BG = (50, 60, 80)
TEXT_COLOR = (230, 235, 240)
TEXT_DIM = (160, 165, 175)
TEXT_DARK = (40, 40, 60)

BUTTON_COLOR = (45, 130, 200)
BUTTON_HOVER = (55, 155, 230)
BUTTON_DISABLED = (70, 70, 90)
BUTTON_TEXT = (240, 245, 250)

RARITY_COMMON = (140, 150, 160)
RARITY_RARE = (40, 120, 200)
RARITY_EPIC = (160, 60, 200)
RARITY_LEGENDARY = (255, 150, 0)

KEYWORD_COLORS = {
    "taunt": (241, 196, 15),
    "charge": (220, 60, 50),
    "rush": (230, 120, 40),
    "divine_shield": (200, 215, 230),
    "poisonous": (50, 200, 100),
    "lifesteal": (160, 70, 200),
    "windfury": (50, 160, 230),
    "battlecry": (255, 180, 50),
    "deathrattle": (150, 50, 50),
}

ENEMY_NORMAL_BG = (180, 100, 40)
ENEMY_BOSS_BG = (140, 50, 160)
ENEMY_INTENT_ATTACK = (220, 60, 60)
ENEMY_INTENT_DEFEND = (60, 150, 220)
ENEMY_INTENT_BUFF = (60, 200, 100)

MINION_BG = (45, 75, 55)
MINION_ATTACK_COLOR = (255, 220, 80)
MINION_HEALTH_COLOR = (220, 60, 60)

OVERLAY_COLOR = (10, 10, 25, 180)
FLOAT_DAMAGE = (255, 60, 60)
FLOAT_HEAL = (60, 220, 100)
FLOAT_SHIELD = (150, 200, 255)

DIVIDER_COLOR = (60, 60, 90)

# ── Layout ──────────────────────────────────────────────────────────────────
# Enemy zone
ENEMY_ZONE_TOP = 60
ENEMY_ZONE_HEIGHT = 200

# Board zone (player minions)
BOARD_ZONE_TOP = 310
BOARD_ZONE_HEIGHT = 160

# Hand zone
HAND_ZONE_TOP = 530
HAND_ZONE_HEIGHT = 190

# Card dimensions
CARD_WIDTH = 120
CARD_HEIGHT = 170
CARD_RADIUS = 8

# Minion dimensions
MINION_WIDTH = 100
MINION_HEIGHT = 100
MINION_RADIUS = 6

# Enemy dimensions
ENEMY_WIDTH = 130
ENEMY_HEIGHT = 130
ENEMY_RADIUS = 8

# Hand layout
HAND_CARD_SPACING = 5
HAND_MAX_CARDS = 10
HAND_Y = 555
HAND_HOVER_LIFT = 30

# Board layout
BOARD_MINION_SPACING = 15
BOARD_MAX_MINIONS = 7
BOARD_Y = 345

# Enemy layout
ENEMY_SPACING = 25
ENEMY_Y = 110

# ── Game Balance ────────────────────────────────────────────────────────────
STARTING_HP = 50
STARTING_ENERGY = 3
MAX_ENERGY = 10
DRAW_PER_TURN = 1
INITIAL_HAND_SIZE = 5
MAX_HAND_SIZE = 10

WAVE_ENEMY_BASE_HP = 12
WAVE_ENEMY_HP_SCALE = 5
WAVE_ENEMY_BASE_ATK = 4
WAVE_ENEMY_ATK_SCALE = 1
WAVE_BOSS_HP_MULTI = 4
WAVE_BOSS_ATK_MULTI = 2

# Reward
REWARD_CARD_COUNT = 3
RARITY_WEIGHTS = {"common": 65, "rare": 28, "epic": 7}

# ── Animation ───────────────────────────────────────────────────────────────
CARD_PLAY_SPEED = 400      # pixels/sec for card fly animation
FLOAT_TEXT_SPEED = 60       # pixels/sec upward
FLOAT_TEXT_DURATION = 1.2   # seconds
FLASH_DURATION = 0.15       # seconds
SHAKE_DURATION = 0.2        # seconds
SHAKE_MAGNITUDE = 5         # pixels

# ── Fonts ───────────────────────────────────────────────────────────────────
FONT_NAME = None  # Use pygame default
FONT_TITLE_SIZE = 48
FONT_LARGE_SIZE = 28
FONT_MEDIUM_SIZE = 20
FONT_SMALL_SIZE = 16
FONT_TINY_SIZE = 13
