"""Pygame client entry points (one client, one language argument)."""

from __future__ import annotations

import sys

from shared.paths import bootstrap_import_path


def _root_or_die():
    root = bootstrap_import_path()
    if root is None:
        print(
            "[text-adventure] project root not found: no pyproject.toml/requirements.txt "
            "with a shared/ directory above this file.",
            file=sys.stderr,
        )
        raise SystemExit(3)
    return root


def main_zh() -> None:
    """Launch the desktop client in Chinese."""
    _root_or_die()
    from client.main import main

    main(["--lang", "zh"])


def main_en() -> None:
    """Launch the desktop client in English."""
    _root_or_die()
    from client.main import main

    main(["--lang", "en"])
