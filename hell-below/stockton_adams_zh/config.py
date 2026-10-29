"""
stockton_adams_zh — 游戏配置（薄壳层）
使用 nodes.json + world.json 结构（节点式叙事）。
"""
import os

GAME_NAME = "Stockton Adams (斯托克顿·亚当斯)"
GAME_ID = "stockton_adams_zh"
VERSION = "2.0-thinshell"
AUTHOR = "Hell Below CN"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "assets", "data")

STORY_FILE = os.path.join(DATA_DIR, "nodes.json")
ROOMS_FILE = os.path.join(DATA_DIR, "world.json")
ITEMS_FILE = os.path.join(DATA_DIR, "items.json")
CHARACTERS_FILE = os.path.join(DATA_DIR, "characters.json")
DIALOGS_FILE = os.path.join(DATA_DIR, "nodes.json")
PUZZLES_FILE = os.path.join(DATA_DIR, "puzzles.json")

WINDOW_TITLE = f"{GAME_NAME} — 地狱之下"
WINDOW_SIZE = "1100x700"
MIN_SIZE = (900, 550)

HAS_COMBAT = False
HAS_CARDS = False
HAS_MAP = False
HAS_EVENT_BUS = True

STARTING_ROOM = "node_001"
INITIAL_HEALTH = 100
INITIAL_INVENTORY = []
THEME_OVERRIDE = {}
