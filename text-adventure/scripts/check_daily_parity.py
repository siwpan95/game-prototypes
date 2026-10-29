"""Check that every client hands out the same puzzle of the day.

The desktop engine, the puzzle service and the terminal client each start the daily
in their own way. If two of them disagree about a date, each looks correct on its own
and only a player with both clients open would notice. This compares them directly and
pins the mapping in a test, so a change to the eligible-kind list has to be deliberate.

Usage: python scripts/check_daily_parity.py [--days N]
"""

from __future__ import annotations

import argparse
import os
import sys
import tempfile
from datetime import date, timedelta
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--days", type=int, default=21, help="how many consecutive days to check")
    parser.add_argument("--start", default="2026-10-01")
    args = parser.parse_args(argv)

    from client.engine import Engine
    from client.events import EventBus
    from puzzle_service.service import PuzzleService

    profile = Path(tempfile.mkdtemp()) / "profile.json"
    desktop = Engine(event_bus=EventBus(), lang="zh", profile_path=profile)
    service = PuzzleService(language="zh")

    start = date.fromisoformat(args.start)
    problems: list[str] = []
    for offset in range(args.days):
        day = (start + timedelta(days=offset)).isoformat()
        from_desktop = desktop.start_daily(day).kind
        from_service = service.new_daily("parity", day=day)["kind"]
        if from_desktop != from_service:
            problems.append(
                f"{day}: desktop={from_desktop!r} service={from_service!r}"
            )

    print(f"compared {args.days} day(s) from {args.start}")
    print(f"  sample: {start.isoformat()} -> {service.new_daily('p', day=start.isoformat())['kind']}")
    if problems:
        print("\nDAILY PARITY FAILED:")
        for line in problems:
            print("  " + line)
        return 1
    print("\nDAILY PARITY PASSED — one date, one puzzle, every client")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
