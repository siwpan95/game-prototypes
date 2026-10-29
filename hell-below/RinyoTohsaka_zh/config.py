"""
RinyoTohsaka_zh — 游戏配置（薄壳层）
含卡牌战斗 + 地图扩展。
"""
import os

GAME_NAME = "Rinyo Tohsaka (远坂凛世)"
GAME_ID = "RinyoTohsaka_zh"
VERSION = "2.0-thinshell"
AUTHOR = "Hell Below CN"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "assets", "data")

STORY_FILE = os.path.join(DATA_DIR, "dialogs.json")
ROOMS_FILE = os.path.join(DATA_DIR, "rooms.json")
ITEMS_FILE = os.path.join(DATA_DIR, "items.json")
CHARACTERS_FILE = os.path.join(DATA_DIR, "characters.json")
DIALOGS_FILE = os.path.join(DATA_DIR, "dialogs.json")
PUZZLES_FILE = os.path.join(DATA_DIR, "puzzles.json")
CARDS_FILE = os.path.join(DATA_DIR, "cards.json")
ENEMIES_FILE = os.path.join(DATA_DIR, "enemies.json")
MAP_LAYOUT_FILE = os.path.join(DATA_DIR, "map_layout.json")

WINDOW_TITLE = f"{GAME_NAME} — 地狱之下"
WINDOW_SIZE = "1100x700"
MIN_SIZE = (900, 550)

HAS_COMBAT = True
HAS_CARDS = True
HAS_MAP = True
HAS_EVENT_BUS = True

STARTING_ROOM = "shrine"
INITIAL_HEALTH = 100
INITIAL_INVENTORY = []
THEME_OVERRIDE = {}
