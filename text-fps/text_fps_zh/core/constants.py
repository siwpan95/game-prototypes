# Window
SCREEN_WIDTH = 1024
SCREEN_HEIGHT = 768
FPS = 60

# Layout
TOP_BAR_HEIGHT = 40
MAIN_TEXT_WIDTH = 700
SIDE_PANEL_WIDTH = SCREEN_WIDTH - MAIN_TEXT_WIDTH
BOTTOM_BAR_HEIGHT = 200

# Font sizes
FONT_SIZE_BODY = 16
FONT_SIZE_TITLE = 24
FONT_SIZE_HUD = 14
FONT_SIZE_BUTTON = 14

# Game
MAX_HEALTH = 100
MAX_ARMOR = 100
MAX_INVENTORY = 10
NOISE_THRESHOLD = 5
NOISE_DECAY = 1
AIM_BONUS = 0.25
COVER_ACCURACY_PENALTY = 0.20

# Flank / exposure bonus (F3): shooting an enemy that is exposed (popped out
# of cover to shoot you, or a rusher closing in) rewards accuracy + damage.
EXPOSED_ACCURACY_BONUS = 0.15
EXPOSED_DAMAGE_BONUS = 6

# Suppression (F2): firing pins enemies; suppressive weapons (LMG) pin harder.
SUPPRESSION_ACCURACY_PENALTY = 0.25  # accuracy lost per point of suppressed
SUPPRESSION_SCALE = 2                # suppressed-turns added per unit weapon.suppression
SUPPRESSION_MAX = 3                  # cap on stacked suppressed turns

# Game phases
PHASE_PLAYER_TURN = "player_turn"
PHASE_ENEMY_TURN = "enemy_turn"
PHASE_GAME_OVER = "game_over"
PHASE_VICTORY = "victory"

# Direction display names (single source of truth for ZH labels)
DIR_DISPLAY = {"north": "北", "south": "南", "east": "东", "west": "西"}

# Save
SAVE_DIR = "saves"
MAX_SAVE_SLOTS = 3
SAVE_VERSION = 1  # Current supported save schema version
