"""Headless smoke test: proves both builds boot, paint, and can be played.

Run it directly (``python scripts/smoke_headless.py``) or through
``scripts/rebuild_venv.ps1``, which calls it as its final verification step. It
needs no display: SDL is forced onto the dummy video/audio drivers, so it is
safe on a build machine and in CI.

Each build is exercised in a **separate child process** because the two builds
export identically named top-level modules (``engine``, ``gameplay_pool``, ...),
so loading both in one interpreter would silently test the same code twice.

Exit codes: 0 all checks passed, 1 a check failed, 3 environment error (a
missing project root, pygame, or interpreter is reported, never skipped).
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def _child(build: str) -> int:
    """Entry point of the per-build child process."""
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
    from shared.paths import bootstrap_import_path

    if bootstrap_import_path(build) is None:
        print("ENVIRONMENT ERROR: project root not found", file=sys.stderr)
        return 3
    from shared.ui_boot import run_build

    try:
        print(f"OK    {build} build: {run_build(build)}")
    except Exception:
        import traceback

        print(f"FAIL  {build} build", file=sys.stderr)
        traceback.print_exc()
        return 1
    return 0


def _check_font() -> str:
    import pygame

    from shared import font_utils

    pygame.init()
    font = font_utils.load_cjk_font(20)
    families = sorted(font_utils.available_families())
    height = font.get_height()
    pygame.quit()
    if height <= 0:
        raise AssertionError("font has zero height")
    return f"{len(families)} families visible, CJK font height {height}px"


def _wrong_answer_for(puzzle):
    """A *type-correct*, definitely wrong answer for the unfinished puzzle."""
    data = getattr(puzzle, "data", {}) or {}
    answer = data.get("answer", data.get("target"))
    if isinstance(answer, bool):
        return not answer
    if isinstance(answer, int):
        return 2**31 - 1
    if isinstance(answer, str):
        return answer + "\u0000__wrong__"
    return "__definitely_wrong__"


def _check_puzzles() -> str:
    """Every kind must generate, hint, and reject a wrong answer without raising.

    A wrong answer of the right type must come back as ``False``; raising means
    the kind does not normalise its input. Those kinds are *reported* (they are
    handled at the RPC boundary, not silently tolerated).
    """
    from shared.paths import bootstrap_import_path

    bootstrap_import_path("zh")
    from gameplay_pool import PUZZLE_CLASSES

    problems: list[str] = []
    not_rejecting: list[str] = []
    for cls in PUZZLE_CLASSES:
        try:
            puzzle = cls(difficulty="easy")
            if not puzzle.get_hint():
                problems.append(f"{cls.__name__}: empty hint")
        except Exception as exc:
            problems.append(f"{cls.__name__}: {type(exc).__name__}: {exc}")
            continue
        try:
            accepted = puzzle.check_answer(_wrong_answer_for(puzzle))
        except Exception as exc:
            not_rejecting.append(f"{cls.__name__}({type(exc).__name__})")
            continue
        if accepted:
            problems.append(f"{cls.__name__}: accepted a wrong answer")

    if problems:
        raise AssertionError("; ".join(problems))
    detail = f"{len(PUZZLE_CLASSES)} kinds generate + hint"
    if not_rejecting:
        detail += f"; {len(not_rejecting)} raise on wrong-typed input (RPC normalises): " + ", ".join(
            not_rejecting
        )
    return detail


def main() -> int:
    if len(sys.argv) >= 3 and sys.argv[1] == "--build":
        return _child(sys.argv[2])

    try:
        import pygame  # noqa: F401
    except Exception as exc:
        print(f"ENVIRONMENT ERROR: pygame is not importable: {exc}", file=sys.stderr)
        return 3

    failures: list[str] = []

    def check(label: str, fn) -> None:
        try:
            detail = fn()
        except Exception:
            import traceback

            failures.append(label)
            print(f"FAIL  {label}", file=sys.stderr)
            traceback.print_exc()
        else:
            print(f"OK    {label} — {detail}")

    check("puzzle registry (headless logic)", _check_puzzles)
    check("CJK font resolves without a hard-coded path", _check_font)

    for build in ("zh", "en"):
        label = f"{build} build boots, paints and plays"
        proc = subprocess.run(
            [sys.executable, str(Path(__file__).resolve()), "--build", build],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if proc.returncode != 0:
            failures.append(label)
            print(f"FAIL  {label} (exit {proc.returncode})", file=sys.stderr)
            sys.stderr.write(proc.stderr)
        else:
            print(f"OK    {label} — {proc.stdout.strip()}")

    print()
    if failures:
        print(f"SMOKE FAILED: {len(failures)} check(s): {', '.join(failures)}")
        return 1
    print("SMOKE PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
