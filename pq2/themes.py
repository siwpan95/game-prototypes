"""主题系统 — 三套视觉主题

字体说明：
    主题字体统一使用 STKaiti（华文楷体），由 gui/tkinter_gui.py 启动时
    通过 AddFontResourceEx 从项目根目录的 assets/ 子目录加载 STKAITI.TTF
    （2026-07-27 起字体归档至 assets/）。
    mono 字体保留为等宽西文字体，用于数据列对齐。
"""

THEMES = {
    "original": {
        "name": "经典",
        "bg": "#f5f0e8",
        "fg": "#4a3728",
        "fg_secondary": "#555",
        "fg_muted": "#666",
        "accent": "#6b8e5a",
        "accent_text": "white",
        "panel_bg": "#f5f0e8",
        "progress_bg": "#ddd",
        "progress_fill": "#6b8e5a",
        "button_bg": "#d4c5a9",
        "gold": "#DAA520",
        "font_title": ("STKaiti", 16, "bold"),
        "font_heading": ("STKaiti", 12, "bold"),
        "font_normal": ("STKaiti", 10),
        "font_small": ("STKaiti", 9),
        "font_mono": ("Consolas", 10),
    },
    "dragon-crown": {
        "name": "龙之皇冠",
        "bg": "#3c2415",
        "fg": "#d4c5a0",
        "fg_secondary": "#a08060",
        "fg_muted": "#706050",
        "accent": "#c8a040",
        "accent_text": "#2a1808",
        "panel_bg": "#4a3020",
        "progress_bg": "#2a1808",
        "progress_fill": "#c8a040",
        "button_bg": "#6a4830",
        "gold": "#c8a040",
        "font_title": ("STKaiti", 16, "bold"),
        "font_heading": ("STKaiti", 12, "bold"),
        "font_normal": ("STKaiti", 10),
        "font_small": ("STKaiti", 9),
        "font_mono": ("Courier New", 10),
    },
    "hollow-knight": {
        "name": "空洞骑士",
        "bg": "#0a1218",
        "fg": "#a0d8d0",
        "fg_secondary": "#608880",
        "fg_muted": "#406060",
        "accent": "#40d8c0",
        "accent_text": "#0a1218",
        "panel_bg": "#101820",
        "progress_bg": "#152028",
        "progress_fill": "#40d8c0",
        "button_bg": "#203840",
        "gold": "#40d8c0",
        "font_title": ("STKaiti", 16, "bold"),
        "font_heading": ("STKaiti", 12, "bold"),
        "font_normal": ("STKaiti", 10),
        "font_small": ("STKaiti", 9),
        "font_mono": ("Courier New", 10),
    },
}

DEFAULT_THEME = "original"
