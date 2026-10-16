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

__all__ = [
    "load_font",
    "load_cjk_font",
    "available_families",
    "supports_cjk",
    "clear_cache",
]

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

_cache: dict[tuple[int, bool], pygame.font.Font] = {}
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
    """Return ``(family_or_None, found_cjk_family)`` (diagnostics only)."""
    family = _pick_family(prefer_cjk)
    if family is None and prefer_cjk:
        return None, False
    is_cjk = family is not None and family in _CJK_FAMILIES
    return family, is_cjk


#: A character no Latin-only font can render; used to prove CJK coverage.
_CJK_PROBE = "\u89e3"  # 解
_LATIN_PROBE = "M"


def supports_cjk(font: pygame.font.Font) -> bool:
    """Whether *font* really renders CJK, instead of drawing a tofu box.

    ``pygame.font.SysFont`` falls back to a default font **silently** when the
    requested family cannot be loaded, and the fallback draws CJK text as empty
    boxes with no error (pygame issue #3025). Comparing rendered widths is a
    cheap, dependency-free way to catch that: a font with CJK glyphs gives the
    ideograph a different advance than a Latin capital.
    """
    try:
        cjk_width = font.size(_CJK_PROBE)[0]
        latin_width = font.size(_LATIN_PROBE)[0]
        hei = font.size("\u9ed1")[0]
        kou = font.size("\u53e3")[0]
    except Exception:  # pragma: no cover - font backend failure
        return False
    if cjk_width <= 0:
        return False
    # Two different ideographs of the same size class must both be wider than a
    # capital, and must measure equal to each other (they share an advance box).
    return cjk_width > latin_width and hei == kou == cjk_width


def load_font(size: int, prefer_cjk: bool = False) -> pygame.font.Font:
    """Load a font at *size* points without relying on a fixed file path.

    Args:
        size: point size.
        prefer_cjk: pick the first available family that **provably** renders CJK
            (Chinese build). Families are only trusted after :func:`supports_cjk`
            confirms them, because SysFont falls back silently.

    Returns:
        A :class:`pygame.font.Font`. Falls back to pygame's bundled default
        (carrying a stderr notice) when no CJK-capable family can be proven.
    """
    global _warned
    cache_key = (int(size), prefer_cjk)
    cached = _cache.get(cache_key)
    if cached is not None:
        return cached

    font: pygame.font.Font | None = None
    if prefer_cjk:
        font = _load_cjk(size)
    if font is None:
        family = _pick_family(prefer_cjk)
        font = pygame.font.SysFont(family, size) if family else pygame.font.Font(None, size)
        if prefer_cjk and not _warned:
            _warned = True
            print(
                "[font_utils] no CJK-capable system font could be verified; "
                "Chinese text may render as boxes. Install one of: "
                + ", ".join(_CJK_FAMILIES),
                file=sys.stderr,
            )

    _cache[cache_key] = font
    return font


def _load_cjk(size: int) -> pygame.font.Font | None:
    """First CJK family whose rendered output actually contains CJK glyphs."""
    for family in _CJK_FAMILIES:
        candidate = pygame.font.SysFont(family, size)
        if supports_cjk(candidate):
            return candidate
    return None


def load_cjk_font(size: int) -> pygame.font.Font:
    """Load a font that can render Chinese text (name preserved from the call sites)."""
    return load_font(size, prefer_cjk=True)


def clear_cache() -> None:
    """Drop cached fonts (tests, or after a display re-init)."""
    _cache.clear()
