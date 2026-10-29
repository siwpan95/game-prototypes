"""Shared helpers used by every build (English and Chinese).

The pygame builds import this package as ``shared.*``. Because the two builds
are plain script directories rather than an installed package, a direct
``python text_adventure/ui.py`` would not put the project root on ``sys.path``
and the import would fail. :func:`ensure_importable` fixes that without any
machine-absolute path.
"""

from __future__ import annotations

from shared.paths import PROJECT_ROOT, bootstrap_import_path

__all__ = ["PROJECT_ROOT", "ensure_importable", "load_cjk_font", "load_font"]


def ensure_importable() -> None:
    """Make the project root importable (idempotent, never raises)."""
    bootstrap_import_path()


def __getattr__(name: str):
    """Lazily expose the font helpers so importing ``shared`` needs no pygame.

    Only :mod:`shared.font_utils` touches pygame; keeping that import lazy lets
    headless tools (tests, the puzzle service, the RPC bridge) import ``shared``
    freely on a machine with no display.
    """
    if name in {"load_font", "load_cjk_font"}:
        from shared import font_utils

        return getattr(font_utils, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
