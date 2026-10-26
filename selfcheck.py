"""Headless self-check for the DOOM-style raycaster's core logic.

Imports only pure modules (no display / audio initialisation):

* ``doom_game.core.world_map``  - grid collision + maze generation
* ``doom_game.world.level_io``  - JSON / ASCII level round-trips

Run from the project root::

    python selfcheck.py

Exits 0 on success, 1 on the first failed check.
"""
import os
import sys
import tempfile

# Keep pygame headless if importing level_io happens to touch its video layer.
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from doom_game.core.types import TextureType
from doom_game.core.world_map import WorldMap
from doom_game.world.level_io import (
    LevelData,
    ascii_to_json,
    build_enemies,
    build_pickups,
    json_to_ascii,
    load_map,
    save_map,
)


def check_maze():
    """Seeded maze generation is reproducible and properly enclosed."""
    a = WorldMap()
    a.generate_maze(12, 10, seed=1234)
    b = WorldMap()
    b.generate_maze(12, 10, seed=1234)

    if a.cells != b.cells:
        raise AssertionError("same seed produced different mazes")
    if len(a.cells) != 10 or any(len(row) != 12 for row in a.cells):
        raise AssertionError("maze dimensions are wrong")

    for x in range(a.width):
        if not a.is_wall(x, 0) or not a.is_wall(x, a.height - 1):
            raise AssertionError("top/bottom border is open")
    for y in range(a.height):
        if not a.is_wall(0, y) or not a.is_wall(a.width - 1, y):
            raise AssertionError("left/right border is open")
    if not a.is_wall(-1, 5) or not a.is_wall(a.width, 5):
        raise AssertionError("out-of-bounds cells must count as walls")

    # Interior must contain at least one open cell reachable from spawn.
    sx, sy = a.find_open_cell()
    if a.is_wall(sx, sy):
        raise AssertionError("find_open_cell returned a wall")
    if not a.line_of_sight(sx + 0.5, sy + 0.5, sx + 0.5, sy + 0.5):
        raise AssertionError("zero-length line of sight must be clear")


def check_los():
    """Walls block line of sight; an open corridor does not."""
    wm = WorldMap(5, 3)
    wm.cells = [[None] * 5 for _ in range(3)]
    wm.cells[1][2] = TextureType.STONE
    if wm.line_of_sight(0.5, 1.5, 4.5, 1.5):
        raise AssertionError("wall did not block line of sight")
    if not wm.line_of_sight(0.5, 0.5, 4.5, 0.5):
        raise AssertionError("clear row reported as blocked")


def check_json_roundtrip():
    """save_map -> load_map preserves grid, spawn and entity metadata."""
    ld = LevelData(
        version=1,
        width=4,
        height=3,
        cells=[[2, 1, 0, 0], [0, 0, 3, 0], [0, 0, 0, 4]],
        player_start={"x": 1.5, "y": 1.5, "angle": 0.25},
        enemies=[{"x": 2.5, "y": 2.5, "hp": 40, "damage": 12,
                  "speed": 0.05, "type": "basic"}],
        pickups=[{"x": 3.5, "y": 1.5, "kind": "score", "amount": 250}],
    )
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "level.json")
        save_map(ld, path)
        got = load_map(path)

    if got.cells != ld.cells or (got.width, got.height) != (4, 3):
        raise AssertionError("grid changed across JSON round-trip")
    if got.player_start != ld.player_start:
        raise AssertionError("player_start changed across JSON round-trip")
    if got.enemies != ld.enemies or got.pickups != ld.pickups:
        raise AssertionError("entity metadata changed across JSON round-trip")

    enemies = build_enemies(got)
    pickups = build_pickups(got)
    if len(enemies) != 1 or enemies[0].hp != 40:
        raise AssertionError("build_enemies lost hp")
    if len(pickups) != 1 or pickups[0].amount != 250:
        raise AssertionError("build_pickups lost amount")


def check_ascii_roundtrip():
    """JSON -> ASCII -> JSON keeps walls and entity positions."""
    text = "\n".join([
        "#####",
        "#P..#",
        "#.E.#",
        "#.H$#",
        "#####",
    ])
    parsed = ascii_to_json(text)
    if (parsed.width, parsed.height) != (5, 5):
        raise AssertionError("ASCII size parsed wrong")
    if parsed.player_start != {"x": 1.5, "y": 1.5, "angle": 0.0}:
        raise AssertionError("ASCII player start parsed wrong")
    if [(e["x"], e["y"]) for e in parsed.enemies] != [(2.5, 2.5)]:
        raise AssertionError("ASCII enemy position parsed wrong")
    if sorted((p["x"], p["y"], p["kind"]) for p in parsed.pickups) != [
        (2.5, 3.5, "health"), (3.5, 3.5, "score")
    ]:
        raise AssertionError("ASCII pickups parsed wrong")

    redrawn = ascii_to_json(json_to_ascii(parsed))
    if redrawn.cells != parsed.cells:
        raise AssertionError("walls changed in ASCII round-trip")
    if redrawn.player_start != parsed.player_start:
        raise AssertionError("spawn changed in ASCII round-trip")
    if [(e["x"], e["y"]) for e in redrawn.enemies] != [
        (e["x"], e["y"]) for e in parsed.enemies
    ]:
        raise AssertionError("enemy positions changed in ASCII round-trip")
    if [(p["x"], p["y"], p["kind"]) for p in redrawn.pickups] != [
        (p["x"], p["y"], p["kind"]) for p in parsed.pickups
    ]:
        raise AssertionError("pickup positions changed in ASCII round-trip")


def main():
    try:
        check_maze()
        check_los()
        check_json_roundtrip()
        check_ascii_roundtrip()
    except Exception as exc:  # noqa: BLE001 - report, never traceback-crash
        print("FAIL: %s: %s" % (type(exc).__name__, exc))
        return 1
    print("selfcheck ok: seeded maze determinism/borders, LOS blocking, "
          "JSON round-trip and ASCII structure round-trip")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
