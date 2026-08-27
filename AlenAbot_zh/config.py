"""
AlenAbot_zh — 游戏配置（薄壳层）
原始数据零改动，仅定义游戏专属参数。
"""
import os

# ── 游戏元信息 ──
GAME_NAME = "AlenAbot (艾伦·阿博特)"
GAME_ID = "AlenAbot_zh"
VERSION = "2.0-thinshell"
AUTHOR = "Hell Below CN"

# ── 数据路径 ──
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "assets", "data")

STORY_FILE = os.path.join(DATA_DIR, "story.json")
ROOMS_FILE = os.path.join(DATA_DIR, "rooms.json")
ITEMS_FILE = os.path.join(DATA_DIR, "items.json")
CHARACTERS_FILE = os.path.join(DATA_DIR, "characters.json")
DIALOGS_FILE = os.path.join(DATA_DIR, "dialogs.json")
PUZZLES_FILE = os.path.join(DATA_DIR, "puzzles.json") if os.path.exists(os.path.join(DATA_DIR, "puzzles.json")) else None
CHAPTERS_FILE = os.path.join(DATA_DIR, "chapters.json") if os.path.exists(os.path.join(DATA_DIR, "chapters.json")) else None
ENDINGS_FILE = os.path.join(DATA_DIR, "endings.json") if os.path.exists(os.path.join(DATA_DIR, "endings.json")) else None
IMAGERY_FILE = os.path.join(DATA_DIR, "imagery.json") if os.path.exists(os.path.join(DATA_DIR, "imagery.json")) else None

# ── 窗口配置 ──
WINDOW_TITLE = f"{GAME_NAME} — 地狱之下"
WINDOW_SIZE = "1100x700"
MIN_SIZE = (900, 550)

# ── 游戏特性开关 ──
HAS_COMBAT = False
HAS_CARDS = False
HAS_MAP = False
HAS_EVENT_BUS = True

# ── 起始房间 / 初始状态 ──
STARTING_ROOM = "intro"
INITIAL_HEALTH = 100
INITIAL_INVENTORY = []

# ── 主题配色覆写（可选，留空则用 shared 默认值） ──
THEME_OVERRIDE = {}
