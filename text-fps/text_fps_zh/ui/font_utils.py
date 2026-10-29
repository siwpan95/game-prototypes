"""CJK-capable font loading for text_fps_zh (ADR-008 scheme A: vendored).

Searches common system CJK font paths per platform and returns a
pygame.font.Font, or None when no CJK font is available so callers can
fall back to a bundled/latin font.
"""
import os
import sys
from typing import Optional

try:
    import pygame_ce as pygame
except ImportError:
    import pygame


def _candidate_paths() -> list:
    """Common CJK font file locations per platform."""
    paths = []
    if sys.platform.startswith("win"):
        windir = os.environ.get("WINDIR", r"C:\Windows")
        paths += [
            os.path.join(windir, "Fonts", "msyh.ttc"),   # Microsoft YaHei
            os.path.join(windir, "Fonts", "simsun.ttc"),  # SimSun
            os.path.join(windir, "Fonts", "simhei.ttf"),  # SimHei
        ]
    elif sys.platform == "darwin":
        paths += [
            "/System/Library/Fonts/PingFang.ttc",
            "/System/Library/Fonts/STHeiti Light.ttc",
            "/Library/Fonts/Arial Unicode.ttf",
        ]
    else:
        paths += [
            "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
            "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
            "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
        ]
    return paths


def load_cjk_font(size: int) -> Optional["pygame.font.Font"]:
    """Return a CJK-capable pygame font, or None if none available.

    Callers MUST handle None and fall back to a bundled/latin font.
    """
    for path in _candidate_paths():
        if os.path.exists(path):
            try:
                return pygame.font.Font(path, size)
            except (FileNotFoundError, OSError):
                continue
    return None
