"""Level I/O: load / save / convert DOOM-style raycaster levels.

This module is the single authority for the on-disk level format. It is a
*pure I/O* layer (no pygame display dependency) so it is safe to call from
headless ``--map`` loads and from unit tests.

Format summary (see ``design/INCREMENTAL_ARCHITECTURE.md`` section 4):

* **JSON** is the authoritative, lossless format. It stores the integer grid
  (``cells[gy][gx]``), the player start, and full enemy / pickup metadata.
* **ASCII** is a human-readable, structure-only intermediate format. It cannot
  express enemy hp / damage / speed / type or pickup amount, so a
  ``JSON -> ASCII -> JSON`` round-trip only preserves *structure* (walls and
  entity positions); metadata is filled from ``config`` defaults.

Integer <-> ``TextureType`` mapping::

    {0: None, 1: BRICK, 2: STONE, 3: METAL, 4: WOOD}

Base entity types (``Enemy`` / ``Pickup``) live in ``doom_game.core.entities``
(architecture rule #6); this module imports them - never redefines them.
"""
import json
import os
from dataclasses import dataclass, field
from typing import Dict, List

try:
    import pygame_ce as pygame  # pragma: no cover - keep import style symmetric
except ImportError:  # pragma: no cover
    import pygame

from doom_game.config import (
    ENEMY_HP,
    ENEMY_DAMAGE,
    ENEMY_SPEED,
    HEALTH_PICKUP_AMOUNT,
    SCORE_PICKUP_AMOUNT,
    DEFAULT_MAP_PATH,
)
from doom_game.core.types import TextureType
from doom_game.core.entities import Enemy, Pickup, PickupType, EnemyType


# ---------------------------------------------------------------------------
# Shared mappings
# ---------------------------------------------------------------------------
INT_TO_TEX: Dict[int, object] = {
    0: None,
    1: TextureType.BRICK,
    2: TextureType.STONE,
    3: TextureType.METAL,
    4: TextureType.WOOD,
}

TEX_TO_INT: Dict[object, int] = {
    None: 0,
    TextureType.BRICK: 1,
    TextureType.STONE: 2,
    TextureType.METAL: 3,
    TextureType.WOOD: 4,
}

# ASCII <-> integer, mirrored from the design's section 4.2 table.
CHAR_TO_INT: Dict[str, int] = {
    ' ': 0, '.': 0, '#': 2, 'B': 1, 'S': 2,
    'M': 3, 'W': 4, 'P': 0, 'E': 0, 'H': 0, '$': 0,
}

TEX_TO_CHAR: Dict[int, str] = {0: ' ', 1: 'B', 2: 'S', 3: 'M', 4: 'W'}


# ---------------------------------------------------------------------------
# Data container
# ---------------------------------------------------------------------------
@dataclass
class LevelData:
    """Serializable level description (the data transfer object).

    ``cells`` stores *integers* (not ``TextureType``) so it is directly
    JSON-serialisable. ``player_start`` / ``enemies`` / ``pickups`` use plain
    dicts for the same reason.
    """
    version: int = 1
    width: int = 0
    height: int = 0
    cells: List[List[int]] = field(default_factory=list)
    player_start: dict = field(default_factory=dict)
    enemies: List[dict] = field(default_factory=list)
    pickups: List[dict] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------
def load_map(path: str) -> LevelData:
    """Load a level file into a ``LevelData``.

    Recognises ``.json`` (parsed directly) and ``.txt`` / ``.asc`` / ``.ascii``
    (converted from ASCII via :func:`ascii_to_json`). Pure I/O - never touches
    the display layer, so it is safe under ``SDL_VIDEODRIVER=dummy``.
    """
    if not os.path.exists(path):
        raise FileNotFoundError(path)
    ext = os.path.splitext(path)[1].lower().lstrip('.')
    if ext in ('txt', 'asc', 'ascii'):
        with open(path, 'r', encoding='utf-8') as fh:
            text = fh.read()
        return ascii_to_json(text)
    with open(path, 'r', encoding='utf-8') as fh:
        raw = json.load(fh)
    return _from_json_dict(raw)


def _from_json_dict(raw: dict) -> LevelData:
    """Build ``LevelData`` from an already-parsed JSON dict."""
    if not isinstance(raw, dict):
        raise ValueError("level JSON root must be an object")
    cells = raw.get("cells", [])
    if not cells:
        raise ValueError("level JSON missing 'cells'")
    height = len(cells)
    width = max((len(row) for row in cells), default=0)
    # Normalise to a rectangular grid (pad short rows with 0 = empty).
    norm_cells = [
        [int(v) for v in row] + [0] * (width - len(row)) for row in cells
    ]

    player_start = raw.get("player_start")
    if not isinstance(player_start, dict) or "x" not in player_start:
        print("[WARN] level missing 'player_start'; using default (1.5, 1.5)")
        player_start = {"x": 1.5, "y": 1.5, "angle": 0.0}

    enemies = raw.get("enemies", []) or []
    pickups = raw.get("pickups", []) or []
    return LevelData(
        version=int(raw.get("version", 1)),
        width=int(width),
        height=int(height),
        cells=norm_cells,
        player_start=dict(player_start),
        enemies=[dict(e) for e in enemies],
        pickups=[dict(p) for p in pickups],
    )


# ---------------------------------------------------------------------------
# Saving
# ---------------------------------------------------------------------------
def save_map(ld: LevelData, path: str) -> str:
    """Write ``LevelData`` to ``path`` as indented JSON (the authoritative form)."""
    data = {
        "version": int(ld.version),
        "width": int(ld.width),
        "height": int(ld.height),
        "cells": [[int(v) for v in row] for row in ld.cells],
        "player_start": ld.player_start,
        "enemies": ld.enemies,
        "pickups": ld.pickups,
    }
    parent = os.path.dirname(os.path.abspath(path))
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(path, 'w', encoding='utf-8') as fh:
        json.dump(data, fh, indent=2)
    return path


# ---------------------------------------------------------------------------
# ASCII conversion
# ---------------------------------------------------------------------------
def ascii_to_json(text: str) -> LevelData:
    """Parse an ASCII level into a ``LevelData`` (metadata defaults from config).

    The ASCII grid uses one character per cell (see ``CHAR_TO_INT``). 'P' marks
    the player start (first occurrence wins), 'E' enemy spawns, 'H' health
    pickups, '$' score pickups. Any metadata not expressible in ASCII is filled
    from ``config`` defaults.
    """
    lines = [ln.replace('\r', '') for ln in text.splitlines()]
    height = len(lines)
    width = max((len(ln) for ln in lines), default=0)
    cells = [[0] * width for _ in range(height)]
    player_start = None
    enemies: List[dict] = []
    pickups: List[dict] = []

    for gy, line in enumerate(lines):
        for gx, ch in enumerate(line):
            if ch in CHAR_TO_INT:
                cells[gy][gx] = CHAR_TO_INT[ch]
            else:
                cells[gy][gx] = 0
            if ch == 'P':
                if player_start is None:
                    player_start = {"x": gx + 0.5, "y": gy + 0.5, "angle": 0.0}
            elif ch == 'E':
                enemies.append({
                    "x": gx + 0.5, "y": gy + 0.5,
                    "hp": ENEMY_HP, "damage": ENEMY_DAMAGE,
                    "speed": ENEMY_SPEED, "type": "basic",
                })
            elif ch == 'H':
                pickups.append({
                    "x": gx + 0.5, "y": gy + 0.5,
                    "kind": "health", "amount": HEALTH_PICKUP_AMOUNT,
                })
            elif ch == '$':
                pickups.append({
                    "x": gx + 0.5, "y": gy + 0.5,
                    "kind": "score", "amount": SCORE_PICKUP_AMOUNT,
                })

    if player_start is None:
        print("[WARN] ASCII level has no 'P' player start; using (1.5, 1.5)")
        player_start = {"x": 1.5, "y": 1.5, "angle": 0.0}

    return LevelData(
        version=1,
        width=width,
        height=height,
        cells=cells,
        player_start=player_start,
        enemies=enemies,
        pickups=pickups,
    )


def json_to_ascii(ld: LevelData) -> str:
    """Serialise ``LevelData`` to the human-readable ASCII form.

    Walls map through ``TEX_TO_CHAR``; the player start is marked 'P', enemies
    'E' and pickups 'H' (health) / '$' (score). ``TextureType`` metadata lost in
    this form is expected (see design 4.3) - use JSON for lossless storage.
    """
    player_cell = None
    if ld.player_start:
        player_cell = (int(ld.player_start.get("x", 1.5)),
                       int(ld.player_start.get("y", 1.5)))
    enemy_cells = {
        (int(e.get("x", 1.5)), int(e.get("y", 1.5))) for e in ld.enemies
    }
    pickup_cells: Dict[tuple, str] = {}
    for p in ld.pickups:
        cx = int(p.get("x", 1.5))
        cy = int(p.get("y", 1.5))
        pickup_cells[(cx, cy)] = 'H' if p.get("kind", "health") == "health" else '$'

    rows: List[str] = []
    for gy in range(ld.height):
        row_chars: List[str] = []
        for gx in range(ld.width):
            if gy < len(ld.cells) and gx < len(ld.cells[gy]):
                v = int(ld.cells[gy][gx])
            else:
                v = 0
            ch = TEX_TO_CHAR.get(v, ' ')
            if player_cell is not None and (gx, gy) == player_cell:
                ch = 'P'
            elif (gx, gy) in enemy_cells:
                ch = 'E'
            elif (gx, gy) in pickup_cells:
                ch = pickup_cells[(gx, gy)]
            row_chars.append(ch)
        rows.append(''.join(row_chars))
    return '\n'.join(rows)


# ---------------------------------------------------------------------------
# Entity construction
# ---------------------------------------------------------------------------
def build_enemies(ld, world_map=None) -> List[Enemy]:
    """Build runtime ``Enemy`` objects from a ``LevelData``.

    ``world_map`` is accepted for API symmetry (an editor / loader may want to
    validate placement) but is optional; construction only reads the level dict.
    """
    enemies: List[Enemy] = []
    for e in ld.enemies:
        x = float(e.get("x", 1.5))
        y = float(e.get("y", 1.5))
        hp = float(e.get("hp", ENEMY_HP))
        damage = float(e.get("damage", ENEMY_DAMAGE))
        speed = float(e.get("speed", ENEMY_SPEED))
        type_str = str(e.get("type", "basic")).lower()
        etype = EnemyType.BASIC if type_str != "basic" else EnemyType.BASIC
        # Optional ranged-attack overrides (A7): missing keys -> None ->
        # Enemy falls back to config defaults, so old files load unchanged.
        attack_range = e.get("attack_range", None)
        attack_cooldown = e.get("attack_cooldown", None)
        enemies.append(Enemy(x, y, hp=hp, damage=damage,
                             speed=speed, type=etype,
                             attack_range=attack_range,
                             attack_cooldown=attack_cooldown))
    return enemies


def build_pickups(ld, world_map=None) -> List[Pickup]:
    """Build runtime ``Pickup`` objects from a ``LevelData``."""
    pickups: List[Pickup] = []
    for p in ld.pickups:
        x = float(p.get("x", 1.5))
        y = float(p.get("y", 1.5))
        kind_str = str(p.get("kind", "health")).lower()
        kind = PickupType.SCORE if kind_str == "score" else PickupType.HEALTH
        amount = p.get("amount", None)
        pickups.append(Pickup(x, y, kind, amount=amount))
    return pickups


__all__ = [
    "LevelData",
    "INT_TO_TEX",
    "TEX_TO_INT",
    "load_map",
    "save_map",
    "ascii_to_json",
    "json_to_ascii",
    "build_enemies",
    "build_pickups",
    "DEFAULT_MAP_PATH",
]
