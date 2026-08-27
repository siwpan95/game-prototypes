"""
Styles — 统一 UI 样式定义（暗色地狱主题）。

所有游戏共享同一套视觉风格。
子类可通过 config.py 中的 style_overrides 覆盖个别颜色/尺寸。
"""

from __future__ import annotations

import tkinter.font as tkfont


# ============================================================
# 调色板
# ============================================================

BG_DARKEST = "#0d0d1a"
BG_DARK = "#1a1a2e"
BG_MEDIUM = "#16213e"
BG_PANEL = "#1f2030"
BG_INPUT = "#252540"

TEXT_PRIMARY = "#e0d8c8"
TEXT_SECONDARY = "#8a8578"
TEXT_DIM = "#5a5550"
TEXT_BRIGHT = "#ffeedd"

ACCENT_BLOOD = "#c0392b"
ACCENT_FLAME = "#e67e22"
ACCENT_GOLD = "#d4a017"
ACCENT_PURPLE = "#8e44ad"
ACCENT_BLUE = "#2980b9"
ACCENT_GREEN = "#27ae60"

STATUS_SANITY_HIGH = "#2ecc71"
STATUS_SANITY_MED = "#f39c12"
STATUS_SANITY_LOW = "#e74c3c"
STATUS_CORRUPTION = "#8e44ad"

BORDER_DARK = "#2a2a40"
BORDER_LIGHT = "#3a3a55"
BORDER_ACCENT = "#4a3050"

BTN_BG = "#2a2a45"
BTN_HOVER = "#3a3a60"
BTN_ACTIVE = "#4a3070"
BTN_TEXT = "#e0d8c8"

# ============================================================
# 字体
# ============================================================

FONT_FAMILY_MONO = "Consolas"
FONT_FAMILY_SANS = "Segoe UI"


def get_fonts() -> dict[str, tkfont.Font]:
    """创建并返回所有游戏字体。"""
    return {
        "title": tkfont.Font(family=FONT_FAMILY_MONO, size=18, weight="bold"),
        "heading": tkfont.Font(family=FONT_FAMILY_MONO, size=14, weight="bold"),
        "body": tkfont.Font(family=FONT_FAMILY_MONO, size=11),
        "body_large": tkfont.Font(family=FONT_FAMILY_MONO, size=13),
        "small": tkfont.Font(family=FONT_FAMILY_MONO, size=9),
        "button": tkfont.Font(family=FONT_FAMILY_SANS, size=11),
        "input": tkfont.Font(family=FONT_FAMILY_MONO, size=12),
        "status": tkfont.Font(family=FONT_FAMILY_MONO, size=10, weight="bold"),
        "ending": tkfont.Font(family=FONT_FAMILY_MONO, size=14),
        "puzzle": tkfont.Font(family=FONT_FAMILY_MONO, size=12),
    }


# ============================================================
# 尺寸
# ============================================================

WINDOW_WIDTH = 1100
WINDOW_HEIGHT = 720
WINDOW_MIN_WIDTH = 900
WINDOW_MIN_HEIGHT = 560

PANEL_LEFT_WIDTH = 680
PANEL_RIGHT_WIDTH = 380
PANEL_BOTTOM_HEIGHT = 160

PADDING_SM = 5
PADDING_MD = 10
PADDING_LG = 15

# 打字效果速度
TYPING_SPEED_FAST = 0.01
TYPING_SPEED_NORMAL = 0.03
TYPING_SPEED_SLOW = 0.05


class Styles:
    """样式容器 — 方便统一访问和覆写。"""

    def __init__(self, overrides: dict | None = None):
        self.overrides = overrides or {}
        # 颜色
        for name in [
            "BG_DARKEST", "BG_DARK", "BG_MEDIUM", "BG_PANEL", "BG_INPUT",
            "TEXT_PRIMARY", "TEXT_SECONDARY", "TEXT_DIM", "TEXT_BRIGHT",
            "ACCENT_BLOOD", "ACCENT_FLAME", "ACCENT_GOLD",
            "ACCENT_PURPLE", "ACCENT_BLUE", "ACCENT_GREEN",
            "STATUS_SANITY_HIGH", "STATUS_SANITY_MED", "STATUS_SANITY_LOW",
            "STATUS_CORRUPTION",
            "BORDER_DARK", "BORDER_LIGHT", "BORDER_ACCENT",
            "BTN_BG", "BTN_HOVER", "BTN_ACTIVE", "BTN_TEXT",
        ]:
            setattr(self, name, self.overrides.get(name, globals()[name]))

        self.WINDOW_WIDTH = self.overrides.get("WINDOW_WIDTH", WINDOW_WIDTH)
        self.WINDOW_HEIGHT = self.overrides.get("WINDOW_HEIGHT", WINDOW_HEIGHT)
        self.WINDOW_MIN_WIDTH = self.overrides.get("WINDOW_MIN_WIDTH", WINDOW_MIN_WIDTH)
        self.WINDOW_MIN_HEIGHT = self.overrides.get("WINDOW_MIN_HEIGHT", WINDOW_MIN_HEIGHT)
        self.PANEL_LEFT_WIDTH = self.overrides.get("PANEL_LEFT_WIDTH", PANEL_LEFT_WIDTH)
        self.PANEL_RIGHT_WIDTH = self.overrides.get("PANEL_RIGHT_WIDTH", PANEL_RIGHT_WIDTH)
        self.PANEL_BOTTOM_HEIGHT = self.overrides.get("PANEL_BOTTOM_HEIGHT", PANEL_BOTTOM_HEIGHT)

        # 内边距
        self.PADDING_SM = self.overrides.get("PADDING_SM", PADDING_SM)
        self.PADDING_MD = self.overrides.get("PADDING_MD", PADDING_MD)
        self.PADDING_LG = self.overrides.get("PADDING_LG", PADDING_LG)

        # 打字速度
        self.TYPING_SPEED_FAST = self.overrides.get("TYPING_SPEED_FAST", TYPING_SPEED_FAST)
        self.TYPING_SPEED_NORMAL = self.overrides.get("TYPING_SPEED_NORMAL", TYPING_SPEED_NORMAL)
        self.TYPING_SPEED_SLOW = self.overrides.get("TYPING_SPEED_SLOW", TYPING_SPEED_SLOW)

        self.fonts = get_fonts()
