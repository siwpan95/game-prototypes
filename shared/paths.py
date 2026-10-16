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


def bootstrap_import_path(start: Path | str | None = None) -> Path | None:
    """Put the project root on ``sys.path``.

    Every package now lives at the project root (``gameplay_pool``, ``client``,
    ``puzzle_service``, ``shared``), so one entry is enough. This used to take a
    *build* name to select between two parallel client directories; those were
    deleted in M5, and with them the reason for the parameter — two copies of
    ``gameplay_pool`` made the import depend on ``sys.path`` order.

    Idempotent. Returns the project root, or ``None`` when no marker file was found
    (the caller then decides whether that is fatal).
    """
    root = find_project_root(start) if start is not None else PROJECT_ROOT
    if root is None:
        return None
    entry = str(root)
    if entry not in sys.path:
        sys.path.insert(0, entry)
    return root
