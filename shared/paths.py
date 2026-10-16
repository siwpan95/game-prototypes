"""Locate the project root and make the import roots reachable.

This module deliberately imports nothing from the project, so it can be the
first thing any entry point (CLI, test, RPC server) runs. Keeping the discovery
here means the rule "no machine-absolute path" is implemented once: the root is
found by walking up from a file's own location to the directory that holds
``pyproject.toml``.
"""

from __future__ import annotations

import sys
from pathlib import Path

__all__ = ["find_project_root", "bootstrap_import_path", "PROJECT_ROOT"]

# Marker files that identify the project root (any one of them is enough).
# They are deliberately specific: a bare `requirements.txt` also exists in
# unrelated parent directories, and matching one of those would silently point
# the import roots at the wrong tree.
_ROOT_MARKERS = ("pyproject.toml", "requirements.txt")
_ROOT_SIGNATURES = ("shared",)

# Import roots for the pygame front ends. `engine`/`ui`/`events`/`domain` are flat
# modules inside each client directory, so that directory has to be on sys.path when
# one of those clients runs.
#
# NOTE (M5): the puzzle pool is unified at the project root
# (``gameplay_pool/``), and the per-client copies were deleted for exactly the
# reason this comment used to warn about — two copies of ``gameplay_pool`` made the
# import depend on sys.path order. Passing a build name here now selects the
# *client* to run; the pool is the same for both.
_IMPORT_ROOTS: dict[str, str] = {
    "en": "text_adventure",
    "zh": "text_adventure_zh",
}


def find_project_root(start: Path | str | None = None) -> Path | None:
    """Walk up from *start* (default: this file) to the project root."""
    base = Path(start).resolve() if start is not None else Path(__file__).resolve()
    for candidate in (base, *base.parents):
        has_marker = any((candidate / marker).is_file() for marker in _ROOT_MARKERS)
        has_signature = any(
            (candidate / name).is_dir() for name in _ROOT_SIGNATURES
        )
        if has_marker and has_signature:
            return candidate
    return None


PROJECT_ROOT: Path | None = find_project_root()


def bootstrap_import_path(
    build: str | None = None, start: Path | str | None = None
) -> Path | None:
    """Put the project root, and at most one build directory, on ``sys.path``.

    Args:
        build: ``"en"`` or ``"zh"`` to select that build's flat-import root.
            Pass ``None`` for headless tools that use package-qualified imports
            only (the puzzle service, tests), so neither build shadows the other.
        start: directory to search upwards from (defaults to this file).

    Idempotent. Returns the project root, or ``None`` when no marker file was
    found (the caller then decides whether that is fatal).
    """
    if build is not None and build not in _IMPORT_ROOTS:
        raise ValueError(
            f"unknown build {build!r}; expected one of {sorted(_IMPORT_ROOTS)} or None"
        )

    root = find_project_root(start) if start is not None else PROJECT_ROOT
    if root is None:
        return None

    wanted = [str(root)]
    if build is not None:
        build_dir = root / _IMPORT_ROOTS[build]
        if not build_dir.is_dir():
            raise FileNotFoundError(f"build directory missing: {build_dir}")
        wanted.append(str(build_dir))

    for entry in reversed(wanted):
        if entry not in sys.path:
            sys.path.insert(0, entry)
    return root
