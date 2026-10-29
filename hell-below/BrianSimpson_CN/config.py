"""
BrianSimpson_CN — 游戏配置（薄壳层）
使用 narratives.json 作为主剧情文件。
"""
import os

GAME_NAME = "Brian Simpson (布莱恩·辛普森)"
GAME_ID = "BrianSimpson_CN"
VERSION = "2.0-thinshell"
AUTHOR = "Hell Below CN"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "assets", "data")

STORY_FILE = os.path.join(DATA_DIR, "narratives.json")
ROOMS_FILE = os.path.join(DATA_DIR, "rooms.json")
ITEMS_FILE = os.path.join(DATA_DIR, "items.json")
CHARACTERS_FILE = None   # BrianSimpson 无独立角色文件
DIALOGS_FILE = os.path.join(DATA_DIR, "narratives.json")
PUZZLES_FILE = os.path.join(DATA_DIR, "puzzles.json")

WINDOW_TITLE = f"{GAME_NAME} — 地狱之下"
WINDOW_SIZE = "1100x700"
MIN_SIZE = (900, 550)

HAS_COMBAT = False
HAS_CARDS = False
HAS_MAP = False
HAS_EVENT_BUS = True

STARTING_ROOM = "cell"
INITIAL_HEALTH = 100
INITIAL_INVENTORY = []
THEME_OVERRIDE = {}
