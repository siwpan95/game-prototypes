"""Entry point: wires up engine + ui and runs the game."""

import sys
import os

# Ensure the project root is on sys.path so imports work
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from engine import Engine
from events import EventBus
from ui import UI


def main() -> None:
    bus = EventBus()
    eng = Engine(event_bus=bus)
    ui = UI(engine=eng)
    ui.run()


if __name__ == "__main__":
    main()
