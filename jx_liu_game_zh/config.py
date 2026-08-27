"""
jx_liu_game_zh — 游戏配置（薄壳层）
刘敬宣游戏 — 含卡牌战斗、地图、遭遇战、多字符串文件。
最复杂的数据结构。
"""
import os

GAME_NAME = "JX Liu (刘敬宣)"
GAME_ID = "jx_liu_game_zh"
VERSION = "2.0-thinshell"
AUTHOR = "Hell Below CN"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "assets", "data")

STORY_FILE = os.path.join(DATA_DIR, "dialogs.json")
ROOMS_FILE = os.path.join(DATA_DIR, "rooms.json")
ITEMS_FILE = os.path.join(DATA_DIR, "items.json")
CHARACTERS_FILE = None
DIALOGS_FILE = os.path.join(DATA_DIR, "dialogs.json")
PUZZLES_FILE = os.path.join(DATA_DIR, "puzzles.json")
CARDS_FILE = os.path.join(DATA_DIR, "cards.json")
ENEMIES_FILE = os.path.join(DATA_DIR, "enemies.json")
ENCOUNTERS_FILE = os.path.join(DATA_DIR, "encounters.json")
MAP_LAYOUT_FILE = os.path.join(DATA_DIR, "map_layouts.json")
STRINGS_FILE = os.path.join(DATA_DIR, "strings.json")

WINDOW_TITLE = f"{GAME_NAME} — 地狱之下"
WINDOW_SIZE = "1100x700"
MIN_SIZE = (900, 550)

HAS_COMBAT = True
HAS_CARDS = True
HAS_MAP = True
HAS_EVENT_BUS = True

# jx_liu 特有：术语映射（中英对照）
TERMINOLOGY_MAP = {
    "暗纹": "Dark Vein",
    "灵视": "Spirit Sight",
    "心象": "Mental Projection",
}

STARTING_ROOM = "courtyard"
INITIAL_HEALTH = 100
INITIAL_INVENTORY = []
THEME_OVERRIDE = {}
