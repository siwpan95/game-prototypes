"""gui/theme.py — 颜色主题、塔罗图标、字体路径与字体注册。"""
import os
import ctypes
import glob
import tkinter as tk
from tkinter import font as tkfont

# ─── 字体路径（基于本文件位置推导项目根）───
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FONT_REGULAR = os.path.join(PROJECT_ROOT, "NotoSansSC-Regular.otf")
FONT_BOLD = os.path.join(PROJECT_ROOT, "NotoSansSC-Bold.otf")

# ─── 颜色主题：暗金神秘学 ───
CLR = {
    "bg":           "#0d0d1a",   # 深邃夜空
    "panel":        "#141428",   # 面板底色
    "panel_light":  "#1a1a35",   # 面板亮色
    "border":       "#2a2a4a",   # 边框
    "gold":         "#c9a84c",   # 金色主线
    "gold_dim":     "#7a6530",   # 暗金
    "text":         "#d0d0dc",   # 主文字
    "text_dim":     "#8888a0",   # 暗文字
    "text_bright":  "#f0e8d0",   # 亮字
    "accent":       "#8b5cf6",   # 紫罗兰（神秘学）
    "accent2":      "#e05a33",   # 暗红（危险）
    "accent3":      "#3b82f6",   # 蓝（锚）
    "accent4":      "#22c55e",   # 绿（消化）
    "pollution_0":  "#4ade80",   # 清醒-绿
    "pollution_1":  "#facc15",   # 低语-黄
    "pollution_2":  "#f97316",   # 幻觉-橙
    "pollution_3":  "#ef4444",   # 失控-红
    "pollution_4":  "#1a1a1a",   # 神殒-黑
}

# 22条途径的塔罗牌图标文字
TAROT_ICONS = {
    "fool":             "🃏", "error":           "🎭", "door":            "🚪",
    "tyrant":           "⛈️", "hanged_man":      "🪢", "visionary":       "👁️",
    "white_tower":      "🗼", "sun":             "☀️", "darkness":        "⭐",
    "eternal_sleeper":  "💀", "dusk_giant":      "💪", "bound_one":       "⛓️",
    "abyss":            "😈", "hermit":          "📜", "paragon":         "⚙️",
    "mother":           "🌿", "moon":            "🌙", "judge":           "⚖️",
    "black_emperor":    "👑", "red_priest":      "⚔️", "chaos_witch":     "🧙‍♀️",
    "wheel_of_fortune": "🎰",
}

def register_fonts(root):
    """注册中文字体到 tkinter"""
    import ctypes
    import glob

    # 尝试加载项目中的字体文件
    font_loaded = False
    try:
        if os.name == 'nt':
            for fpath in [FONT_REGULAR, FONT_BOLD]:
                if os.path.exists(fpath):
                    ctypes.windll.gdi32.AddFontResourceW(fpath)
                    font_loaded = True
    except Exception:
        pass

    # 检测可用中文字体族
    available = set(tkfont.families())
    zh_families = [f for f in available if any(
        kw in f.lower() for kw in ['noto sans sc', 'microsoft yahei',
                                    'simhei', 'simsun', 'dengxian'])]

    fn_regular = "Noto Sans SC"
    fn_bold = "Noto Sans SC Medium"  # Noto Sans SC 没有独立 Bold 变体，用 Medium
    fn_heavy = "Noto Sans SC Black"
    if not any('noto sans sc' in f.lower() for f in zh_families):
        fn_regular = "Microsoft YaHei"
        fn_bold = "Microsoft YaHei"
        fn_heavy = "Microsoft YaHei"
        if not any('microsoft yahei' in f.lower() for f in zh_families):
            fn_regular = "SimHei"
            fn_bold = "SimHei"
            fn_heavy = "SimHei"

    return {
        "tiny":   (fn_bold, 9),
        "small":  (fn_regular, 10),
        "body":   (fn_regular, 12),
        "title":  (fn_bold, 16),
        "h1":     (fn_heavy, 24),
        "h2":     (fn_heavy, 20),
        "mono":   ("Consolas", 10),
    }

