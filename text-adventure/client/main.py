"""Entry point for the unified desktop client: engine + UI, one language argument.

    python -m client.main            # default language (zh)
    python -m client.main --lang en  # English interface and content

The two legacy entry points (``text_adventure/main.py``, ``text_adventure_zh/main.py``)
did this twice; the only difference between them was which language they spoke.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from shared import ensure_importable

ensure_importable()

from client.engine import Engine  # noqa: E402
from client.events import EventBus  # noqa: E402
from client.ui import UI  # noqa: E402
from gameplay_pool import messages  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="text-adventure-pygame", description="桌面版文字解谜")
    parser.add_argument(
        "--lang", default=messages.DEFAULT_LANGUAGE, choices=list(messages.LANGUAGES),
        help="interface and content language",
    )
    args = parser.parse_args(argv)

    engine = Engine(event_bus=EventBus(), lang=args.lang)
    ui = UI(engine=engine, lang=args.lang)
    ui.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
