# -*- coding: utf-8 -*-
"""游戏全局常量 — Logging Quest 暖色纸卷风格 + Progress Quest 改进"""

import os

# --- 路径 ---
# PyInstaller: frozen 时 _MEIPASS 是内嵌资源目录（只读），exe 目录用于外部配置
import sys as _sys
if getattr(_sys, 'frozen', False):
    # 打包后运行：JSON 数据内嵌在 _MEIPASS，Excel 和存档在 exe 同目录
    _BUNDLED = _sys._MEIPASS
    _EXE_DIR = os.path.dirname(_sys.executable)
    DATA_DIR = os.path.join(_BUNDLED, "data")
    CONFIG_DIR = _EXE_DIR           # game_data.xlsx 放在 exe 旁边
    SAVE_FILE = os.path.join(_EXE_DIR, "save.json")
else:
    # 开发环境运行：数据从项目目录加载
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    DATA_DIR = os.path.join(BASE_DIR, "data")
    CONFIG_DIR = os.path.join(BASE_DIR, "config")
    SAVE_FILE = os.path.join(BASE_DIR, "save.json")

# --- 窗口尺寸 ---
WIN_W = 820
WIN_H = 660

# --- 主色调：暖米色纸卷风 ---
C_BG              = "#EDE4D3"
C_PANEL_BG        = "#F5F0E6"
C_CONTENT_BG      = "#FAF6EE"

C_TAB_BAR_BG      = "#D4C5A9"
C_TAB_ACTIVE      = "#2A9D8F"
C_TAB_INACTIVE    = "#8B7D6B"
C_TAB_ACTIVE_TEXT = "#1A1008"

C_TEXT            = "#2C1810"
C_TEXT_LIGHT      = "#6B5D4F"
C_TEXT_HINT       = "#A89880"

C_GOLD            = "#B8860B"
C_ACCENT_TEAL     = "#2A9D8F"
C_ACCENT_RED      = "#E76F51"
C_ACCENT_GREEN    = "#6A994E"

C_ROW_EVEN        = "#FAF6EE"
C_ROW_ODD         = "#E8F0E3"

C_BTN_NORMAL      = "#D4C5A9"
C_BTN_HOVER       = "#C4B590"
C_BTN_TEXT         = "#2C1810"
C_BTN_DANGER       = "#E76F51"
C_BTN_DANGER_TEXT  = "#FFFFFF"
C_BTN_PRIMARY      = "#2A9D8F"
C_BTN_PRIMARY_TEXT = "#FFFFFF"

C_SEPARATOR        = "#C4B998"
C_SECTION_TITLE    = "#8B6914"
C_TIMESTAMP        = "#2A9D8F"

# --- 角色职业色 ---
C_JOB_WARRIOR = "#C1121F"
C_JOB_MAGE    = "#7B2D8E"
C_JOB_ROGUE   = "#2A9D8F"
C_JOB_CLERIC  = "#E9C46A"

# --- 选中高亮 ---
C_SELECTED_BG     = "#D4E8D0"
C_SELECTED_BORDER = "#2A9D8F"

# --- 字体 ---
FONT_TITLE   = ("Microsoft YaHei", 16, "bold")
FONT_LABEL   = ("Microsoft YaHei", 11)
FONT_SMALL   = ("Microsoft YaHei", 9)
FONT_TINY    = ("Microsoft YaHei", 8)
FONT_LOG     = ("Consolas", 10)
FONT_BIG     = ("Microsoft YaHei", 14, "bold")
FONT_TAB     = ("Microsoft YaHei", 11, "bold")
FONT_STAT    = ("Consolas", 11)       # 属性数字等宽
FONT_NARRATIVE = ("Microsoft YaHei", 9, "italic")

# --- 游戏规则 ---
MAX_PARTY_SIZE    = 3
MAX_SKILLS        = 4
MAX_BATTLE_TURNS  = 20
FLOOR_DELAY_MS    = 1500
BATTLE_DELAY_MS   = 800
INN_COST          = 20
EQUIP_DROP_CHANCE = 0.2
NARRATIVE_INTERVAL = 8000   # 叙事文字切换间隔 ms
