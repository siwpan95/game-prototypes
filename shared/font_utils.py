"""Cross-platform font loading shared by every renderer.

The original implementation imported a module that never existed in this
repository (``shared.font_utils``), which made both games fail at startup with
``ModuleNotFoundError`` before the first frame was drawn. This module is that
missing provider.

Discipline (see the distribution governance rules):

* **No machine-absolute path.** Fonts are resolved by *family name* through
  :func:`pygame.font.SysFont`, never by a baked-in font file location. A
  hard-coded ``C:/Windows/Fonts/...`` breaks on every machine but the author's.
* **No silent fallback.** When no CJK-capable family is present the caller gets
  pygame's default font and a one-line notice on stderr, so a missing font is
  visible instead of quietly rendering tofu boxes.
"""

from __future__ import annotations

import sys

import pygame

__all__ = ["load_font", "load_cjk_font", "available_families", "clear_cache"]

# Families that carry CJK glyphs, most preferred first. Resolved by name via
# SysFont, which maps a family name onto whatever the running platform provides.
_CJK_FAMILIES: tuple[str, ...] = (
    "Microsoft YaHei",   # Windows (zh-CN default UI font)
    "Microsoft YaHei UI",
    "SimHei",
    "Noto Sans CJK SC",  # Linux
    "Noto Sans SC",
    "Source Han Sans SC",
    "WenQuanYi Micro Hei",
    "PingFang SC",       # macOS
    "Hiragino Sans GB",
    "Heiti SC",
    "Arial Unicode MS",
)

# Families used when the UI text is Latin-only (English build).
_LATIN_FAMILIES: tuple[str, ...] = (
    "Segoe UI",
    "DejaVu Sans",
    "Liberation Sans",
    "Helvetica Neue",
    "Arial",
)

_cache: dict[tuple[str, int, bool], pygame.font.Font] = {}
_warned = False


def available_families() -> frozenset[str]:
    """Return the font family names the running SDL build can see."""
    try:
        return frozenset(pygame.font.get_fonts())
    except Exception:  # pragma: no cover - SDL backend without enumeration
        return frozenset()


def _pick_family(prefer_cjk: bool) -> str | None:
    """Choose the first wanted family this machine actually provides."""
    installed = {name.replace(" ", "").lower() for name in available_families()}
    wanted = _CJK_FAMILIES + _LATIN_FAMILIES if prefer_cjk else _LATIN_FAMILIES
    for family in wanted:
        if family.replace(" ", "").lower() in installed:
            return family
    return None


def _resolve(prefer_cjk: bool) -> tuple[str | None, bool]:
    """Return ``(family_or_None, found_cjk_family)``."""
    family = _pick_family(prefer_cjk)
    if family is None and prefer_cjk:
        return None, False
    is_cjk = family is not None and family in _CJK_FAMILIES
    return family, is_cjk


def load_font(size: int, prefer_cjk: bool = False) -> pygame.font.Font:
    """Load a font at *size* points without relying on a fixed file path.

    Args:
        size: point size.
        prefer_cjk: try CJK-capable families first (Chinese build).

    Returns:
        A :class:`pygame.font.Font`. Falls back to pygame's bundled default
        (carrying a stderr notice) when the platform exposes no known family.
    """
    global _warned
    key = ("cjk" if prefer_cjk else "latin", int(size), prefer_cjk)
    cached = _cache.get(key)
    if cached is not None:
        return cached

    family, found_cjk = _resolve(prefer_cjk)
    if family is None:
        font = pygame.font.Font(None, size)
        if prefer_cjk and not _warned:
            _warned = True
            print(
                "[font_utils] no CJK-capable system font found; "
                "falling back to pygame's default font (CJK glyphs may be missing). "
                "Install one of: " + ", ".join(_CJK_FAMILIES),
                file=sys.stderr,
            )
    else:
        if prefer_cjk and not found_cjk and not _warned:
            _warned = True
            print(
                f"[font_utils] CJK family not installed; using '{family}'. "
                "CJK glyphs may be missing.",
                file=sys.stderr,
            )
        font = pygame.font.SysFont(family, size)

    _cache[key] = font
    return font


def load_cjk_font(size: int) -> pygame.font.Font:
    """Load a font that can render Chinese text (name preserved from the call sites)."""
    return load_font(size, prefer_cjk=True)


def clear_cache() -> None:
    """Drop cached fonts (tests, or after a display re-init)."""
    _cache.clear()
