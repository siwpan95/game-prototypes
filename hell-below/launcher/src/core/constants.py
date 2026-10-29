"""Core constants for Hell Below Launcher Platform (Tkinter)."""

from __future__ import annotations

import pathlib
from enum import Enum, unique

# ── Paths ──────────────────────────────────────────────────────────
# constants.py 路径:  .../hell below/launcher/src/core/constants.py
# parent           :  .../hell below/launcher/src/core
# parent.parent    :  .../hell below/launcher/src
# parent.parent.parent      :  .../hell below/launcher
# parent.parent.parent.parent:  .../hell below      ← PROJECT_ROOT
PROJECT_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent.parent
LOCALES_DIR = PROJECT_ROOT / "launcher" / "locales"
GAMES_BASE_ZH = PROJECT_ROOT

# ── Window ────────────────────────────────────────────────────────
WIN_WIDTH = 960
WIN_HEIGHT = 720

# ── Colors (hex strings for Tkinter) ─────────────────────────────
COLOR_BG = "#0C0814"
COLOR_TEXT = "#DCD2C8"
COLOR_DIM = "#786E64"
COLOR_ACCENT = "#B43C3C"
COLOR_HIGHLIGHT = "#FFC850"
COLOR_GOLD = "#DCB43C"
COLOR_CHOICE_BG = "#1E1628"
COLOR_CHOICE_HOVER = "#372641"
COLOR_CHOICE_BORDER = "#503C64"
COLOR_CARD_BG = "#191223"
COLOR_CARD_HOVER = "#2D1E37"
COLOR_CARD_BORDER = "#46325A"
COLOR_CARD_BORDER_HOVER = "#DCB43C"
COLOR_VOLUME = "#50465A"
COLOR_GENRE = "#645546"
COLOR_SUBTITLE = "#8C8278"
COLOR_WHITE = "#FFFFFF"
COLOR_BLACK = "#000000"
COLOR_RED = "#C83232"
COLOR_GREEN = "#32C850"

# ── Fonts ─────────────────────────────────────────────────────────
FONT_FAMILY = "Microsoft YaHei"
FONT_FAMILY_MONO = "Consolas"

# ── Launcher State ─────────────────────────────────────────────────
@unique
class LauncherState(Enum):
    MAIN_MENU = "main_menu"
    GAME_GRID = "game_grid"
    GAME_RUNNING = "game_running"
