"""Puzzle service: the headless, language-agnostic side of the game.

The pygame clients in ``text_adventure/`` and ``text_adventure_zh/`` grew into
1584-line files with a hard-coded 14-way ``isinstance`` dispatch in both the
event path and the draw path, and the list of kinds was duplicated in two
modules. This package replaces that with a registry: a kind announces itself,
and everything else (selection, the RPC surface, the view model) reads from the
registry instead of naming kinds.

Layout:

``registry``
    Kind discovery and metadata, resolved per language.
``service``
    Live sessions, answer checking, scoring, and state snapshots.
``views``
    Per-kind adapter turning a puzzle object into a render-agnostic view model.

Nothing in here imports pygame, and nothing imports a language build at module
import time: ``sys.path`` decides whether ``text_adventure`` or
``text_adventure_zh`` supplies ``gameplay_pool``, so build selection is an
explicit call (see ``shared.paths.bootstrap_import_path``).
"""

from __future__ import annotations

__all__ = ["__version__"]

__version__ = "0.1.0"
