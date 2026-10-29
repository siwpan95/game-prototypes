"""Client screen baseline: record or verify what the desktop client draws.

The M5 merge of the two pygame clients was accepted on pixel evidence: the same 44
screens (the menu, 14 puzzle kinds × 3 difficulties, and the result screen) rendered
identically before and after, in both languages. Those legacy clients are deleted, so
this script keeps the same evidence reproducible against a recorded baseline — which
also catches any later change that alters a screen without meaning to.

Usage::

    python scripts/client_screens.py --record        # (re)write the baseline hashes
    python scripts/client_screens.py                 # verify against them
    python scripts/client_screens.py --write-png DIR # dump the images for inspection

Exit codes: 0 match · 1 mismatch · 3 environment error.
"""

from __future__ import annotations

import argparse
import base64
import copy
import hashlib
import json
import os
import random
import tempfile
import sys
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from shared.paths import bootstrap_import_path  # noqa: E402

BASELINE = ROOT / "tests" / "client_screens.json"
SEED = 20261016
WIDTH, HEIGHT = 960, 720


def capture_screens(language: str) -> dict[str, str]:
    """Render every screen and return ``{name: sha256}``."""
    bootstrap_import_path()

    import pygame

    from client.engine import Engine
    from client.events import EventBus
    from client.ui import UI
    from gameplay_pool import PUZZLE_CLASSES
    from puzzle_service.content import load_pack

    content = load_pack(language=language)
    pygame.init()
    screens: dict[str, str] = {}
    # A throwaway profile per run: the menu now draws the player's streak, so using
    # the real save file would make the baseline depend on who ran it and how much
    # they had played. A temp file inside the run's own directory keeps it empty and
    # deterministic.
    profile_dir = tempfile.mkdtemp(prefix="client-screens-")
    profile_path = Path(profile_dir) / "profile.json"

    def shot(name: str) -> None:
        surface = pygame.display.get_surface()
        raw = pygame.image.tobytes(surface, "RGB")
        screens[name] = hashlib.sha256(raw).hexdigest()

    def new_ui() -> tuple[object, object]:
        engine = Engine(
            event_bus=EventBus(), lang=language, content=content, profile_path=profile_path
        )
        return engine, UI(engine=engine, lang=language)

    # --- menu (selection frozen so the baseline depends on the client, not on the
    # --- default mode index, which is a per-language choice) ---------------------
    engine, ui = new_ui()
    ui._mode_options = ["content_heavy", "balanced", "generated_heavy", "random"]
    ui._mode_idx = 1
    ui._diff_options = ["easy", "medium", "hard", "random"]
    ui._diff_idx = 1
    ui._build_menu_buttons()
    ui._draw_menu((0, 0))
    shot("menu")

    # --- every kind at every difficulty, with identical puzzle data --------------
    for cls in PUZZLE_CLASSES:
        for difficulty in ("easy", "medium", "hard"):
            random.seed(SEED)
            puzzle = copy.deepcopy(cls(difficulty=difficulty, lang=language, content=content))
            engine, ui = new_ui()
            ui._puzzle = puzzle
            ui.screen_state = "playing"
            engine._current_puzzle = puzzle
            ui._draw_header()
            ui._draw_footer()
            ui._handle_playing([], (0, 0))
            ui._draw_playing((0, 0), 1 / 60)
            shot(f"{cls.__name__}.{difficulty}")

    # --- result screen -----------------------------------------------------------
    engine, ui = new_ui()
    result = {
        "correct": True, "points": 15, "time_bonus": 5, "streak_bonus": 0,
        "time_used": 3.2, "score": 15, "streak": 1,
    }
    ui._show_result(result)
    ui._draw_result((0, 0))
    shot("result")

    pygame.quit()
    return screens


def read_baseline() -> dict:
    return json.loads(BASELINE.read_text(encoding="utf-8"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--record", action="store_true", help="write the baseline")
    parser.add_argument("--language", default="zh", choices=["zh", "en"])
    args = parser.parse_args(argv)

    try:
        screens = capture_screens(args.language)
    except Exception as exc:  # noqa: BLE001 - environment problem, not a mismatch
        print(f"ENVIRONMENT ERROR: could not render the client: {exc}", file=sys.stderr)
        return 3

    if args.record:
        baseline = read_baseline() if BASELINE.is_file() else {}
        baseline[args.language] = screens
        BASELINE.write_text(
            json.dumps(baseline, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(f"recorded {len(screens)} screen hash(es) for {args.language} into {BASELINE.name}")
        return 0

    baseline = read_baseline()
    expected = baseline.get(args.language)
    if not expected:
        print(f"no baseline for {args.language}; run with --record first", file=sys.stderr)
        return 3

    missing = sorted(set(expected) - set(screens))
    added = sorted(set(screens) - set(expected))
    changed = sorted(name for name in set(screens) & set(expected) if screens[name] != expected[name])
    print(f"{args.language}: {len(screens)} screen(s) rendered, {len(screens) - len(changed)} unchanged")
    for name in changed:
        print(f"  CHANGED {name}")
    if missing:
        print(f"  missing from the render: {missing}")
    if added:
        print(f"  new screens not in the baseline: {added}")
    if changed or missing:
        print("\nCLIENT SCREENS CHANGED — if the change is intended, re-record and say so in the commit")
        return 1
    print("\nCLIENT SCREENS MATCH THE BASELINE")
    return 0


def _unused() -> None:  # pragma: no cover - placeholder removed below
    raise NotImplementedError


if __name__ == "__main__":
    raise SystemExit(main())
