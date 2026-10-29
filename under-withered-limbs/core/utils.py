"""
Utility functions shared across systems.
"""

import pygame

from core.paths import ROOT


def _load_font(size, bold=False):
    """字体加载：优先包内字体 → 跨平台 SysFont → 最终兜底"""
    # 包内字体路径（兼容开发环境和 PyInstaller 打包后）
    font_dir = ROOT / "assets" / "fonts"
    if bold:
        pkg_path = font_dir / "msyhbd.ttc"
    else:
        pkg_path = font_dir / "msyh.ttc"

    if pkg_path.exists():
        try:
            return pygame.font.Font(str(pkg_path), size)
        except (FileNotFoundError, OSError):
            pass

    # fallback：跨平台 SysFont（替代硬编码 C:/Windows/Fonts/...）
    from shared.font_utils import load_cjk_font
    return load_cjk_font(size, bold=bold)
