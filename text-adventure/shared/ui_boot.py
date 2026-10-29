"""Boot the desktop client headlessly and drive it through real UI code paths.

Used by ``scripts/smoke_headless.py``, which runs each language in its own process.
Two languages in one process would fight over the display and the imported modules,
so isolation is a requirement, not a preference.
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

from shared.paths import bootstrap_import_path

__all__ = ["run_build", "draw_method"]

TIME_STEP = 1.0 / 60.0
MOUSE_POS = (0, 0)
#: Middle of the play area (below the 50px header, above the 50px footer). Used to
#: send a real click, because some handlers only fail once an event reaches them.
CLICK_POS = (480, 360)


def _ensure_headless() -> None:
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    os.environ.setdefault("SDL_AUDIODRIVER", "dummy")


def run_build(build: str, frames: int = 2) -> str:
    """Boot the desktop client for *build* ("en" or "zh") and drive every puzzle kind.

    Returns a one-line summary. Raises on any failure so a caller can report it
    loudly rather than treating a skipped screen as a pass.

    Every kind is exercised on purpose. An earlier version played one random puzzle,
    which meant a defect in a single kind's screen showed up only when the random draw
    happened to hit it — a latent ``UnboundLocalError`` in the crossword handler
    survived that way until 2026-10-16.
    """
    _ensure_headless()
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    bootstrap_import_path()

    import pygame

    from client.engine import Engine
    from client.events import EventBus
    from client.ui import UI
    from gameplay_pool import PUZZLE_CLASSES

    language = "zh" if build == "zh" else "en"
    pygame.init()
    engine = Engine(event_bus=EventBus(), lang=language)
    ui = UI(engine=engine, lang=language)  # the construction that used to raise

    assert getattr(ui, "_menu_buttons", None) is not None, "menu buttons were not built"
    assert ui.lang == language, f"UI speaks {ui.lang!r}, expected {language!r}"

    # 1. menu screen
    for _ in range(max(1, frames)):
        ui._handle_menu([], MOUSE_POS)
        ui._draw_menu(MOUSE_POS)

    failures: list[str] = []
    for puzzle_cls in PUZZLE_CLASSES:
        name = puzzle_cls.__name__
        try:
            # Ask the engine for a puzzle of this kind. The engine's picker cannot do
            # that by construction (it selects pools by mode), so the kind is
            # instantiated here and handed to the engine — which also proves the
            # engine accepts a puzzle supplied from outside its picker.
            puzzle = puzzle_cls(
                difficulty="easy", lang=language, content=engine.content
            )
            engine.configure("balanced", "easy")
            engine._current_puzzle = puzzle
            engine._puzzle_start_time = time.time()
            ui._puzzle = puzzle
            ui.screen_state = "playing"
            # A click in the middle of the play area, so the kind's click handling
            # actually runs (not just its drawing path).
            click = pygame.event.Event(
                pygame.MOUSEBUTTONDOWN, {"pos": CLICK_POS, "button": 1}
            )
            for _ in range(max(1, frames)):
                ui._handle_playing([], MOUSE_POS)
                ui._draw_playing(MOUSE_POS, TIME_STEP)
                ui._handle_playing([click], CLICK_POS)
                ui._draw_playing(MOUSE_POS, TIME_STEP)
        except Exception as exc:  # noqa: BLE001 - collect, then report all of them
            failures.append(f"{name}: {type(exc).__name__}: {exc}")

    # Result screen, driven by a real engine-scored outcome.
    try:
        engine.configure("balanced", "easy")
        scored = engine.start_new_puzzle()
        ui._puzzle = scored
        result = engine.submit_answer(_answer_for(scored))
        if not result["correct"] and result.get("score", 0) != 0:
            failures.append(f"{type(scored).__name__}: a wrong answer scored {result['score']}")
        ui._show_result(result)
        ui._handle_result([], MOUSE_POS)
        ui._draw_result(MOUSE_POS)
    except Exception as exc:  # noqa: BLE001
        failures.append(f"result screen: {type(exc).__name__}: {exc}")

    pygame.quit()
    if failures:
        raise AssertionError("; ".join(failures))
    return (
        f"{language}: {len(PUZZLE_CLASSES)} kinds — menu + every playing screen + result "
        "painted, each with a simulated click"
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
