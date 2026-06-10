"""
UI 公共工具
"""
import os
import pygame

RARITY_COLORS = {
    "普通": (180, 180, 180),
    "稀有": (80, 160, 255),
    "史诗": (180, 80, 255),
    "传说": (255, 165, 0),
    "神话": (255, 50, 50),
}

# ── 字体加载（使用本地文件路径，绕过 SysFont 枚举 bug）──
_FONT_PATH = None


def _find_font():
    """查找系统中文字体文件路径，优先微软雅黑"""
    global _FONT_PATH
    candidates = [
        os.path.join(os.environ.get("SystemRoot", "C:\\Windows"), "Fonts", "msyh.ttc"),
        os.path.join(os.environ.get("SystemRoot", "C:\\Windows"), "Fonts", "msyh.ttf"),
        os.path.join(os.environ.get("SystemRoot", "C:\\Windows"), "Fonts", "simhei.ttf"),
        os.path.join(os.environ.get("SystemRoot", "C:\\Windows"), "Fonts", "simsun.ttc"),
    ]
    for p in candidates:
        if os.path.isfile(p):
            _FONT_PATH = p
            return p
    # 最终回退：让 pygame 用默认字体
    return None


def load_font(size, bold=False):
    """加载中文字体，返回 pygame Font 对象"""
    if _FONT_PATH is None:
        _find_font()
    try:
        if _FONT_PATH:
            return pygame.font.Font(_FONT_PATH, size)
    except Exception:
        pass
    # 回退到默认字体
    return pygame.font.Font(None, max(16, size))


def draw_rounded_rect(surface, color, rect, radius=10, width=0):
    """绘制圆角矩形"""
    x, y, w, h = rect
    if width == 0:
        pygame.draw.rect(surface, color, (x + radius, y, w - radius * 2, h))
        pygame.draw.rect(surface, color, (x, y + radius, w, h - radius * 2))
        pygame.draw.circle(surface, color, (x + radius, y + radius), radius)
        pygame.draw.circle(surface, color, (x + w - radius, y + radius), radius)
        pygame.draw.circle(surface, color, (x + radius, y + h - radius), radius)
        pygame.draw.circle(surface, color, (x + w - radius, y + h - radius), radius)
    else:
        pygame.draw.rect(surface, color, rect, width, border_radius=radius)


def draw_progress_bar(surface, x, y, w, h, progress, color, bg_color=(50, 50, 60)):
    """绘制进度条"""
    pygame.draw.rect(surface, bg_color, (x, y, w, h), border_radius=h // 2)
    bar_w = max(h, int(w * min(1.0, progress)))
    pygame.draw.rect(surface, color, (x, y, bar_w, h), border_radius=h // 2)
