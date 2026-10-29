"""Render the desktop client's screens and dump the raw surface (merge evidence).

One run per client: it walks the menu, every puzzle kind and the result screen, and
writes each surface two ways — a PNG for a human to look at, and the raw pixels
(base64) for an exact comparison. Rendering the *same* puzzle data through both the
old and the new client and diffing the pixels is the only equivalence argument that
does not depend on reading the diff correctly.

Usage: python scripts/_client_snapshot.py <legacy-en|legacy-zh|unified> <out-dir> [lang]
"""

from __future__ import annotations

import base64
import copy
import json
import os
import sys
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from shared.paths import bootstrap_import_path  # noqa: E402

WIDTH, HEIGHT = 960, 720
SEED = 20261016


def _load_client(source: str, lang: str):
    """Import the client modules for one source, in isolation."""
    if source == "unified":
        bootstrap_import_path()
        from client.engine import Engine
        from client.ui import UI
        from client.events import EventBus

        return Engine, UI, EventBus, {"lang": lang}
    build = "text_adventure" if source == "legacy-en" else "text_adventure_zh"
    bootstrap_import_path("en" if source == "legacy-en" else "zh")
    from engine import Engine  # type: ignore[import-not-found]
    from ui import UI  # type: ignore[import-not-found]
    from events import EventBus  # type: ignore[import-not-found]

    return Engine, UI, EventBus, {}


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__)
        return 2
    source, out_dir = argv[0], Path(argv[1])
    lang = argv[2] if len(argv) > 2 else ("zh" if source == "legacy-zh" else "en")
    out_dir.mkdir(parents=True, exist_ok=True)

    import random

    import pygame

    from gameplay_pool import PUZZLE_CLASSES
    from puzzle_service.content import load_pack

    Engine, UI, EventBus, extra = _load_client(source, lang)
    content = load_pack(language=lang)
    # The engine takes the content pack and the language; the UI takes the language
    # only (it renders whatever the engine hands it).
    engine_kwargs = dict(extra)
    ui_kwargs = {key: value for key, value in extra.items() if key != "content"}
    if source == "unified":
        engine_kwargs["content"] = content

    pygame.init()
    screens: dict[str, dict] = {}

    def capture(name: str, ui) -> None:
        surface = pygame.display.get_surface()
        raw = pygame.image.tobytes(surface, "RGB")
        pygame.image.save(surface, str(out_dir / f"{name}.png"))
        screens[name] = {
            "sha256": __import__("hashlib").sha256(raw).hexdigest(),
            "raw_b64": base64.b64encode(raw).decode(),
            "size": list(surface.get_size()),
        }

    def guarded(name: str, draw) -> None:
        """Paint one screen, recording which screen failed instead of aborting."""
        try:
            draw()
        except Exception as exc:  # noqa: BLE001 - the harness reports, the run continues
            import traceback

            screens.setdefault("_errors", {})[name] = traceback.format_exc()
            print(f"  FAILED to paint {name}: {type(exc).__name__}: {exc}", file=sys.stderr)
            return
        capture(name, ui_holder["ui"])

    # --- menu -----------------------------------------------------------------
    engine = Engine(event_bus=EventBus(), **engine_kwargs)
    ui = UI(engine=engine, **ui_kwargs)
    # Freeze the menu state so both clients show the same selection: the mode list
    # itself differs by design (zh offers only `random`), and that difference is
    # recorded in client/translations.py rather than smoothed over here.
    ui._mode_options = ["content_heavy", "balanced", "generated_heavy", "random"]
    ui._mode_idx = 1
    ui._diff_options = ["easy", "medium", "hard", "random"]
    ui._diff_idx = 1
    ui._build_menu_buttons()
    ui._draw_menu((0, 0))
    capture("menu", ui)

    # --- every puzzle kind, same data through both clients ---------------------
    for cls in PUZZLE_CLASSES:
        for difficulty in ("easy", "medium", "hard"):
            random.seed(SEED)
            puzzle = cls(difficulty=difficulty, lang=lang, content=content)
            shared = copy.deepcopy(puzzle)
            engine = Engine(event_bus=EventBus(), **engine_kwargs)
            ui = UI(engine=engine, **ui_kwargs)
            ui._puzzle = shared
            ui.screen_state = "playing"
            engine._current_puzzle = shared
            ui._draw_header()
            ui._draw_footer()
            # Dispatch, then paint — the same pair the game loop performs.
            try:
                ui._handle_playing([], (0, 0))
            except Exception as exc:  # the handler may need a real event; paint anyway
                screens.setdefault("_handler_errors", {})[f"{cls.__name__}.{difficulty}"] = (
                    f"{type(exc).__name__}: {exc}"
                )
            ui._draw_playing((0, 0), 1 / 60)
            capture(f"{cls.__name__}.{difficulty}", ui)

    # --- result screen ---------------------------------------------------------
    engine = Engine(event_bus=EventBus(), **engine_kwargs)
    ui = UI(engine=engine, **ui_kwargs)
    ui._last_result = {
        "correct": True, "points": 15, "time_bonus": 5, "streak_bonus": 0,
        "time_used": 3.2, "score": 15, "streak": 1,
    }
    ui._show_result(ui._last_result)
    ui._draw_result((0, 0))
    capture("result", ui)

    pygame.quit()
    (out_dir / "screens.json").write_text(
        json.dumps(
            {key: value for key, value in screens.items() if not key.startswith("_")},
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    errors = screens.get("_handler_errors")
    if errors:
        (out_dir / "handler_errors.json").write_text(
            json.dumps(errors, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    print(f"{source} ({lang}): captured {len(screens)} screen(s) into {out_dir}")
    print(f"  surface hash: {screens['menu']['sha256'][:16]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
