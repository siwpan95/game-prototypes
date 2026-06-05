"""KARD 游戏常量 - 吸血鬼幸存者 × 杀戮尖塔 × 炉石传说"""

import os
import sys

# ── 中文字体路径 ────────────────────────────────────────────────────
def _find_chinese_font() -> str | None:
    """查找系统可用的中文字体，返回字体路径或 None。"""
    # Windows 常见字体路径
    win_fonts = [
        r"C:\Windows\Fonts\msyh.ttc",      # 微软雅黑
        r"C:\Windows\Fonts\msyhbd.ttc",    # 微软雅黑 粗体
        r"C:\Windows\Fonts\simhei.ttf",    # 黑体
        r"C:\Windows\Fonts\simsun.ttc",    # 宋体
        r"C:\Windows\Fonts\msjh.ttc",      # 微软正黑体
        r"C:\Windows\Fonts\simkai.ttf",    # 楷体
    ]
    # macOS 常见字体路径
    mac_fonts = [
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/STHeiti Light.ttc",
        "/System/Library/Fonts/Hiragino Sans GB.ttc",
        "/Library/Fonts/Arial Unicode.ttf",
    ]
    # Linux 常见字体路径
    linux_fonts = [
        "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
        "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf",
        "/usr/share/fonts/truetype/arphic/uming.ttc",
    ]

    search_paths = []
    if sys.platform == "win32":
        search_paths = win_fonts
    elif sys.platform == "darwin":
        search_paths = mac_fonts
    else:
        search_paths = linux_fonts

    for fp in search_paths:
        if os.path.isfile(fp):
            return fp
    return None

FONT_PATH = _find_chinese_font()

# ── 窗口 ──────────────────────────────────────────────────────────
SCREEN_WIDTH = 1280
SCREEN_HEIGHT = 720
FPS = 60
TITLE = "KARD — 无尽卡牌生存"

# ── 颜色 ──────────────────────────────────────────────────────────
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

# ── 元素伤害颜色（TEW 最终物语元素体系）──────────────────────
ELEMENT_COLORS = {
    "fire":    (255, 80, 30),    # 火 — 橙红
    "ice":     (80, 180, 255),   # 冰 — 浅蓝
    "lightning":(220, 200, 40),  # 雷 — 金黄
    "wind":    (130, 220, 150),  # 风 — 翠绿
    "earth":   (160, 120, 60),   # 土 — 棕褐
    "dark":    (120, 60, 180),   # 暗 — 紫黑
    "light":   (255, 220, 120),  # 光 — 金色
}
ELEMENT_NAMES = {
    "fire": "火焰", "ice": "冰霜", "lightning": "雷电",
    "wind": "风暴", "earth": "大地", "dark": "暗影", "light": "神圣",
}

# ── 状态效果颜色 ───────────────────────────────────────────
STATUS_COLORS = {
    "stun":        (255, 220, 60),   # 眩晕 — 黄
    "slow":        (100, 180, 255),  # 迟缓 — 蓝
    "weaken":      (160, 100, 200),  # 虚弱 — 紫
    "freeze":      (140, 220, 255),  # 冰冻 — 冰蓝
    "shaken":      (200, 150, 80),   # 动摇 — 橙
    "burn":        (255, 100, 40),   # 燃烧 — 红橙
    "poison":      (80, 200, 100),   # 中毒 — 绿
    "shield_up":   (180, 210, 255),  # 护盾增强 — 白蓝
}

DIVIDER_COLOR = (60, 60, 90)

# ── 布局 ──────────────────────────────────────────────────────────
ENEMY_ZONE_TOP = 50
ENEMY_ZONE_HEIGHT = 100

ENEMY_BOARD_ZONE_TOP = 210
ENEMY_BOARD_ZONE_HEIGHT = 110

BOARD_ZONE_TOP = 330
BOARD_ZONE_HEIGHT = 160

HAND_ZONE_TOP = 530
HAND_ZONE_HEIGHT = 190

CARD_WIDTH = 120
CARD_HEIGHT = 170
CARD_RADIUS = 8

MINION_WIDTH = 100
MINION_HEIGHT = 100
MINION_RADIUS = 6

ENEMY_WIDTH = 130
ENEMY_HEIGHT = 130
ENEMY_RADIUS = 8

HAND_CARD_SPACING = 5
HAND_MAX_CARDS = 10
HAND_Y = 555
HAND_HOVER_LIFT = 30

BOARD_MINION_SPACING = 15
BOARD_MAX_MINIONS = 7
BOARD_Y = 365

ENEMY_SPACING = 25
ENEMY_Y = 75

ENEMY_BOARD_Y = 225

# ── 游戏平衡 ────────────────────────────────────────────────────────
STARTING_HP = 50
STARTING_ENERGY = 3
MAX_ENERGY = 10
DRAW_PER_TURN = 1
INITIAL_HAND_SIZE = 5
MAX_HAND_SIZE = 10

# ── 难度梯度系统（DifficultyManager 接管以下参数）────
# 保留旧常量以供参考，实际缩放由 DifficultyManager 统一管理
WAVE_ENEMY_BASE_HP = 12       # [legacy] base HP for tier-1 enemies
WAVE_ENEMY_HP_SCALE = 5       # [legacy] HP per room (now non-linear)
WAVE_ENEMY_BASE_ATK = 4       # [legacy] base ATK for tier-1 enemies
WAVE_ENEMY_ATK_SCALE = 1      # [legacy] ATK per room (now non-linear)
WAVE_BOSS_HP_MULTI = 4        # [legacy] boss HP multiplier
WAVE_BOSS_ATK_MULTI = 2       # [legacy] boss ATK multiplier

# ── 难度显示颜色 ──────────────────────────────────────
DIFFICULTY_TIER_COLORS = {
    1: (120, 200, 120),   # 新手 — 绿
    2: (200, 200, 80),    # 进阶 — 黄
    3: (240, 140, 40),    # 困难 — 橙
    4: (220, 60, 60),     # 地狱 — 红
    5: (180, 40, 180),    # 深渊 — 紫
}
ASCENSION_COLORS = {
    0: (160, 180, 200),   # 标准 — 灰蓝
    1: (200, 200, 80),    # 挑战 — 黄
    2: (240, 140, 40),    # 噩梦 — 橙
    3: (220, 60, 60),     # 地狱 — 红
    4: (180, 40, 180),    # 炼狱 — 紫
    5: (255, 80, 30),     # 终焉 — 深红
}

REWARD_CARD_COUNT = 3
RARITY_WEIGHTS = {"common": 55, "rare": 28, "epic": 12, "legendary": 5}

# ── 动画 ───────────────────────────────────────────────────────────
CARD_PLAY_SPEED = 400
FLOAT_TEXT_SPEED = 60
FLOAT_TEXT_DURATION = 1.2
FLASH_DURATION = 0.15
SHAKE_DURATION = 0.2
SHAKE_MAGNITUDE = 5

# ── 字体 ───────────────────────────────────────────────────────────
FONT_NAME = FONT_PATH          # 中文字体路径，优先系统字体，回退为 None（默认像素字体）
FONT_TITLE_SIZE = 48
FONT_LARGE_SIZE = 28
FONT_MEDIUM_SIZE = 20
FONT_SMALL_SIZE = 16
FONT_TINY_SIZE = 13


def get_font(size: int):
    """创建指定大小的字体（自动使用中文字体）。"""
    import pygame
    if FONT_PATH:
        return pygame.font.Font(FONT_PATH, size)
    else:
        # 回退：尝试 pygame 内置字体（不支持中文）
        return pygame.font.Font(None, size)
