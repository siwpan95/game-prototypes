"""Boot one pygame build headlessly and drive it through real UI code paths.

Used by ``scripts/smoke_headless.py``, which runs each build in its own process.
That isolation is required, not stylistic: ``text_adventure`` and
``text_adventure_zh`` each contain a ``gameplay_pool`` package and an ``engine``
module, so whichever build directory lands on ``sys.path`` first shadows the
other for the whole process.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from shared.paths import bootstrap_import_path

__all__ = ["run_build", "draw_method"]

TIME_STEP = 1.0 / 60.0
MOUSE_POS = (0, 0)


def _ensure_headless() -> None:
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    os.environ.setdefault("SDL_AUDIODRIVER", "dummy")


def run_build(build: str, frames: int = 2) -> str:
    """Boot *build* (``"en"`` or ``"zh"``), paint every screen once, submit an answer.

    Returns a one-line summary. Raises on any failure so a caller can report it
    loudly rather than treating a skipped screen as a pass.
    """
    _ensure_headless()
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    bootstrap_import_path(build)

    import pygame

    from engine import Engine  # type: ignore[import-not-found]  # noqa: E402
    from events import EventBus  # type: ignore[import-not-found]  # noqa: E402
    from ui import UI  # type: ignore[import-not-found]  # noqa: E402

    pygame.init()
    engine = Engine(event_bus=EventBus())
    ui = UI(engine=engine)  # the construction that used to raise ModuleNotFoundError

    assert getattr(ui, "_menu_buttons", None) is not None, "menu buttons were not built"

    # 1. menu screen
    for _ in range(max(1, frames)):
        ui._handle_menu([], MOUSE_POS)
        ui._draw_menu(MOUSE_POS)

    # 2. playing screen, with a real generated puzzle
    engine.configure("balanced", "easy")
    puzzle = engine.start_new_puzzle()
    ui._puzzle = puzzle
    ui.screen_state = "playing"
    for _ in range(max(1, frames)):
        ui._handle_playing([], MOUSE_POS)
        ui._draw_playing(MOUSE_POS, TIME_STEP)

    # 3. answer submission + result screen
    result = engine.submit_answer(_answer_for(puzzle))
    if not result["correct"] and result["score"] != 0:
        raise AssertionError(
            f"{type(puzzle).__name__}: a wrong answer scored {result['score']} points"
        )
    ui._show_result(result)
    ui._handle_result([], MOUSE_POS)
    ui._draw_result(MOUSE_POS)

    pygame.quit()
    return (
        f"{type(puzzle).__name__}: menu+playing+result painted, "
        f"correct={result['correct']} score={result['score']} streak={result['streak']}"
    )


def draw_method(ui) -> str:
    """Name of the method that paints *ui*'s current screen (diagnostics only)."""
    state = getattr(ui, "screen_state", "menu")
    return {
        "menu": "_draw_menu",
        "playing": "_draw_playing",
        "result": "_draw_result",
    }.get(state, "_draw_menu")


def _answer_for(puzzle):
    """Best-effort accepted answer; the smoke run never requires it to be right."""
    data = getattr(puzzle, "data", {}) or {}
    for key in ("answer", "solution", "word", "target"):
        if key in data:
            return data[key]
    return "__smoke_wrong_answer__"
