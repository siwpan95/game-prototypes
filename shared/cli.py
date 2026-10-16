"""Console entry points.

``text_adventure/main.py`` and ``text_adventure_zh/main.py`` insert their own
directory into ``sys.path`` and then use flat imports (``from engine import
Engine``). Importing those modules from a console script or a test runner does
not run that preamble, so the import roots are installed here first.
"""

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
    """Launch the Chinese build."""
    _root_or_die()
    from text_adventure_zh.main import main

    main()


def main_en() -> None:
    """Launch the English build."""
    _root_or_die()
    from text_adventure.main import main

    main()
