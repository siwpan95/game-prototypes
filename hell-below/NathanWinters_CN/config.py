"""
NathanWinters_CN — 游戏配置（薄壳层）
"""
import os

GAME_NAME = " Nathan Winters (内森·温特斯)"
GAME_ID = "NathanWinters_CN"
VERSION = "2.0-thinshell"
AUTHOR = "Hell Below CN"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "assets", "data")

STORY_FILE = None
ROOMS_FILE = os.path.join(DATA_DIR, "rooms.json")
ITEMS_FILE = os.path.join(DATA_DIR, "items.json")
CHARACTERS_FILE = os.path.join(DATA_DIR, "characters.json")
DIALOGS_FILE = None
PUZZLES_FILE = os.path.join(DATA_DIR, "puzzles.json")

WINDOW_TITLE = f"{GAME_NAME} — 地狱之下"
WINDOW_SIZE = "1100x700"
MIN_SIZE = (900, 550)

HAS_COMBAT = False
HAS_CARDS = False
HAS_MAP = False
HAS_EVENT_BUS = True

STARTING_ROOM = "start"
INITIAL_HEALTH = 100
INITIAL_INVENTORY = []
THEME_OVERRIDE = {}
