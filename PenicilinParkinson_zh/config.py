"""
PenicilinParkinson_zh — 游戏配置（薄壳层）
含卡牌战斗扩展，无独立 rooms.json。
"""
import os

GAME_NAME = "Penicilin Parkinson (盘尼西林·帕金森)"
GAME_ID = "PenicilinParkinson_zh"
VERSION = "2.0-thinshell"
AUTHOR = "Hell Below CN"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "assets", "data")

STORY_FILE = os.path.join(DATA_DIR, "dialogs.json")
ROOMS_FILE = None   # PenicilinParkinson 无 rooms.json
ITEMS_FILE = os.path.join(DATA_DIR, "items.json")
CHARACTERS_FILE = os.path.join(DATA_DIR, "characters.json")
DIALOGS_FILE = os.path.join(DATA_DIR, "dialogs.json")
PUZZLES_FILE = os.path.join(DATA_DIR, "puzzles.json")
CARDS_FILE = os.path.join(DATA_DIR, "cards.json")
ENEMIES_FILE = os.path.join(DATA_DIR, "enemies.json")
EVENTS_FILE = os.path.join(DATA_DIR, "events.json")

WINDOW_TITLE = f"{GAME_NAME} — 地狱之下"
WINDOW_SIZE = "1100x700"
MIN_SIZE = (900, 550)

HAS_COMBAT = True
HAS_CARDS = True
HAS_MAP = False
HAS_EVENT_BUS = True

STARTING_ROOM = "arena"
INITIAL_HEALTH = 100
INITIAL_INVENTORY = []
THEME_OVERRIDE = {}
