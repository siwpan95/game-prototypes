"""In-game level editor (GUI) for the DOOM-style raycaster.

The editor is a self-contained sub-package. It is entered from play mode via
the ``E`` key and **never** instantiated under headless runs. It edits a
``WorldMap`` grid plus player-start / enemy / pickup placements and (de)serialises
through the *same* level format used by :mod:`doom_game.world.level_io`, so a
file saved here loads directly with ``python main.py --map <file>``.

Controls (see README "Operations")::

    Digit 1..9  select brush (Brick / Stone / Metal / Wood / Player / Enemy /
                Health / Score / Eraser)
    Left mouse    place current brush at the hovered cell
    Right mouse   erase the hovered cell (wall + any entity there)
    Ctrl+S        save to_level_data() -> save_map()
    Ctrl+O        load_map() -> load_level_data()
    ESC (edit)    return to play, rebuilding the world from the edited level

All pygame usage is confined to ``render`` / ``handle_event`` so the module
imports cleanly even when no display is available.
"""
try:
    import pygame_ce as pygame
except ImportError:  # pragma: no cover
    import pygame

import copy
import os

from doom_game.config import (
    SCREEN_WIDTH, SCREEN_HEIGHT,
    DEFAULT_MAP_WIDTH, DEFAULT_MAP_HEIGHT, WORLD_SEED,
    ENEMY_HP, ENEMY_DAMAGE, ENEMY_SPEED,
    HEALTH_PICKUP_AMOUNT, SCORE_PICKUP_AMOUNT,
    DEFAULT_MAP_PATH, EDITOR_UNDO_DEPTH,
)
from doom_game.core.types import TextureType
from doom_game.core.world_map import WorldMap
from doom_game.core.entities import Enemy, Pickup, PickupType, EnemyType
from doom_game.world.level_io import (
    LevelData,
    INT_TO_TEX,
    TEX_TO_INT,
    load_map,
    save_map,
    build_enemies,
    build_pickups,
)


# Texture -> draw colour for the editor grid.
TEX_COLOR = {
    TextureType.BRICK: (170, 70, 60),
    TextureType.STONE: (130, 130, 140),
    TextureType.METAL: (110, 130, 160),
    TextureType.WOOD: (150, 110, 60),
}

# Ordered brush palette; index 0..8 mapped to digit keys 1..9.
BRUSHES = [
    ("Brick", TextureType.BRICK),
    ("Stone", TextureType.STONE),
    ("Metal", TextureType.METAL),
    ("Wood", TextureType.WOOD),
    ("Player", "player"),
    ("Enemy", "enemy"),
    ("Health", "health"),
    ("Score", "score"),
    ("Eraser", "eraser"),
]


class LevelEditor:
    """A simple grid editor for walls and entities."""

    def __init__(self, screen_w: int = SCREEN_WIDTH,
                 screen_h: int = SCREEN_HEIGHT, map_path: str = None):
        self.screen_w = int(screen_w)
        self.screen_h = int(screen_h)
        self.map_path = map_path

        self.world_map = WorldMap()
        self.player_start = None          # {"x", "y", "angle"}
        self.enemies: list = []           # List[Enemy]
        self.pickups: list = []           # List[Pickup]
        self.brush_index = 0              # default brush = Brick
        self._undo_stack: list = []       # snapshots (dicts), newest last

        # Seed an initial grid so there is something to edit.
        if map_path and _safe_exists(map_path):
            try:
                self.load_level_data(load_map(map_path))
            except Exception as exc:                  # pragma: no cover
                print(f"[EDITOR] could not preload '{map_path}': {exc}")
                self.world_map.generate_maze(
                    DEFAULT_MAP_WIDTH, DEFAULT_MAP_HEIGHT, seed=WORLD_SEED)
        else:
            self.world_map.generate_maze(
                DEFAULT_MAP_WIDTH, DEFAULT_MAP_HEIGHT, seed=WORLD_SEED)

    # ------------------------------------------------------------------ #
    # Geometry helpers
    # ------------------------------------------------------------------ #
    def _cell_size(self) -> int:
        """Square cell size that fits the grid in the (centred) viewport."""
        if self.world_map.width <= 0 or self.world_map.height <= 0:
            return 16
        cell = min(self.screen_w, self.screen_h) // max(
            self.world_map.width, self.world_map.height)
        return max(2, cell)

    def _origin(self, cell: int) -> tuple:
        """Top-left pixel of the centred grid."""
        ox = (self.screen_w - cell * self.world_map.width) // 2
        oy = (self.screen_h - cell * self.world_map.height) // 2
        return ox, oy

    def screen_to_grid(self, mx: int, my: int):
        """Map a screen pixel to (gx, gy); returns None if outside the grid."""
        if self.world_map.width <= 0 or self.world_map.height <= 0:
            return None
        cell = self._cell_size()
        ox, oy = self._origin(cell)
        gx = (mx - ox) // cell
        gy = (my - oy) // cell
        if 0 <= gx < self.world_map.width and 0 <= gy < self.world_map.height:
            return gx, gy
        return None

    # ------------------------------------------------------------------ #
    # Event handling
    # ------------------------------------------------------------------ #
    def handle_event(self, event) -> None:
        """Process a pygame event routed here by the main loop."""
        if event.type == pygame.KEYDOWN:
            self._handle_key(event)
        elif event.type in (pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP):
            self._handle_mouse(event)

    def _handle_key(self, event) -> None:
        mods = pygame.key.get_mods()
        ctrl = (mods & pygame.KMOD_CTRL) != 0
        if ctrl and event.key == pygame.K_s:
            self.save()
            return
        if ctrl and event.key == pygame.K_o:
            self.load()
            return
        if ctrl and event.key == pygame.K_z:
            self.undo()
            return
        # Digit keys 1..9 select a brush.
        if pygame.K_1 <= event.key <= pygame.K_9:
            self.brush_index = event.key - pygame.K_1
            if self.brush_index >= len(BRUSHES):
                self.brush_index = len(BRUSHES) - 1

    def _handle_mouse(self, event) -> None:
        if event.type != pygame.MOUSEBUTTONDOWN:
            return
        cell = self.screen_to_grid(event.pos[0], event.pos[1])
        if cell is None:
            return
        gx, gy = cell
        if event.button == 1:           # left = place
            self._apply_brush(gx, gy)
        elif event.button == 3:         # right = erase
            self._erase(gx, gy)

    # ------------------------------------------------------------------ #
    # Undo (Ctrl+Z) - snapshot stack, U1-U5
    # ------------------------------------------------------------------ #
    def _snapshot(self) -> dict:
        """Full editor-state snapshot as a plain dict.

        Entities are stored as serialisable dicts (same shape as
        ``to_level_data``) and rebuilt into fresh objects on restore, so an
        undone state never shares references with live objects.
        """
        return {
            "width": int(self.world_map.width),
            "height": int(self.world_map.height),
            "cells": copy.deepcopy(self.world_map.cells),
            "player_start": (dict(self.player_start)
                             if self.player_start else None),
            "enemies": [{
                "x": e.pos.x, "y": e.pos.y,
                "hp": e.hp, "damage": e.damage,
                "speed": e.speed, "type": e.type.value,
            } for e in self.enemies],
            "pickups": [{
                "x": p.pos.x, "y": p.pos.y,
                "kind": p.kind.value, "amount": p.amount,
            } for p in self.pickups],
        }

    def _push_undo(self) -> None:
        """Push a snapshot; drop the oldest past ``EDITOR_UNDO_DEPTH``."""
        self._undo_stack.append(self._snapshot())
        if len(self._undo_stack) > EDITOR_UNDO_DEPTH:
            self._undo_stack.pop(0)

    def undo(self) -> bool:
        """Pop and restore the newest snapshot; False (silent) when empty."""
        if not self._undo_stack:
            return False                   # U5: empty stack -> no-op
        snap = self._undo_stack.pop()
        width = int(snap["width"])
        height = int(snap["height"])
        if (self.world_map.width != width
                or self.world_map.height != height):
            self.world_map = WorldMap(width, height)
        self.world_map.cells = copy.deepcopy(snap["cells"])
        self.player_start = (dict(snap["player_start"])
                             if snap["player_start"] else None)
        # Rebuild entity objects from dicts (same logic as build_enemies /
        # build_pickups) so no stale references survive the restore (U2).
        self.enemies = [
            Enemy(float(e["x"]), float(e["y"]),
                  hp=float(e.get("hp", ENEMY_HP)),
                  damage=float(e.get("damage", ENEMY_DAMAGE)),
                  speed=float(e.get("speed", ENEMY_SPEED)),
                  type=EnemyType.BASIC)
            for e in snap["enemies"]
        ]
        self.pickups = [
            Pickup(float(p["x"]), float(p["y"]),
                   (PickupType.SCORE if p.get("kind") == "score"
                    else PickupType.HEALTH),
                   amount=p.get("amount", None))
            for p in snap["pickups"]
        ]
        return True

    def _erase_would_change(self, gx: int, gy: int) -> bool:
        """True if erasing (gx, gy) would actually modify editor state (U1)."""
        if (0 <= gy < self.world_map.height
                and 0 <= gx < self.world_map.width
                and self.world_map.cells[gy][gx] is not None):
            return True
        for e in self.enemies:
            if int(e.pos.x) == gx and int(e.pos.y) == gy:
                return True
        for p in self.pickups:
            if int(p.pos.x) == gx and int(p.pos.y) == gy:
                return True
        if (self.player_start is not None
                and int(self.player_start.get("x", -1)) == gx
                and int(self.player_start.get("y", -1)) == gy):
            return True
        return False

    # ------------------------------------------------------------------ #
    # Brush application
    # ------------------------------------------------------------------ #
    def _apply_brush(self, gx: int, gy: int) -> None:
        brush = BRUSHES[self.brush_index][1]
        if brush in (TextureType.BRICK, TextureType.STONE,
                     TextureType.METAL, TextureType.WOOD):
            if self.world_map.cells[gy][gx] == brush:
                return                     # U1: same wall -> no-op, no push
            self._push_undo()
            self.world_map.cells[gy][gx] = brush
        elif brush == "player":
            self._push_undo()              # entity/player brushes always act
            self.world_map.cells[gy][gx] = None
            self.player_start = {"x": gx + 0.5, "y": gy + 0.5, "angle": 0.0}
        elif brush == "enemy":
            self._push_undo()
            self.world_map.cells[gy][gx] = None
            self._remove_entity_at(gx, gy)
            self.enemies.append(Enemy(gx + 0.5, gy + 0.5,
                                      hp=ENEMY_HP, damage=ENEMY_DAMAGE,
                                      speed=ENEMY_SPEED, type=EnemyType.BASIC))
        elif brush == "health":
            self._push_undo()
            self.world_map.cells[gy][gx] = None
            self._remove_entity_at(gx, gy)
            self.pickups.append(Pickup(gx + 0.5, gy + 0.5,
                                       PickupType.HEALTH,
                                       amount=HEALTH_PICKUP_AMOUNT))
        elif brush == "score":
            self._push_undo()
            self.world_map.cells[gy][gx] = None
            self._remove_entity_at(gx, gy)
            self.pickups.append(Pickup(gx + 0.5, gy + 0.5,
                                       PickupType.SCORE,
                                       amount=SCORE_PICKUP_AMOUNT))
        elif brush == "eraser":
            self._erase(gx, gy)            # _erase pushes its own snapshot

    def _erase(self, gx: int, gy: int) -> None:
        if not self._erase_would_change(gx, gy):
            return                         # U1: nothing to erase -> no push
        self._push_undo()
        if 0 <= gy < self.world_map.height and 0 <= gx < self.world_map.width:
            self.world_map.cells[gy][gx] = None
        self._remove_entity_at(gx, gy)
        if (self.player_start is not None
                and int(self.player_start.get("x", -1)) == gx
                and int(self.player_start.get("y", -1)) == gy):
            self.player_start = None

    def _remove_entity_at(self, gx: int, gy: int) -> None:
        self.enemies = [e for e in self.enemies
                        if not (int(e.pos.x) == gx and int(e.pos.y) == gy)]
        self.pickups = [p for p in self.pickups
                        if not (int(p.pos.x) == gx and int(p.pos.y) == gy)]

    # ------------------------------------------------------------------ #
    # Serialisation
    # ------------------------------------------------------------------ #
    def to_level_data(self) -> LevelData:
        """Snapshot the current editor state into a ``LevelData``."""
        wmap = self.world_map
        cells = [[TEX_TO_INT.get(wmap.cells[gy][gx], 0)
                  for gx in range(wmap.width)]
                 for gy in range(wmap.height)]

        ps = (dict(self.player_start) if self.player_start
              else {"x": 1.5, "y": 1.5, "angle": 0.0})
        # Validate: the player must not sit on a wall cell.
        px, py = int(ps.get("x", 1.5)), int(ps.get("y", 1.5))
        if (0 <= py < wmap.height and 0 <= px < wmap.width
                and wmap.cells[py][px] is not None):
            print("[WARN] editor: player start on a wall cell; clearing it")
            wmap.cells[py][px] = None

        enemies = [{
            "x": e.pos.x, "y": e.pos.y,
            "hp": e.hp, "damage": e.damage,
            "speed": e.speed, "type": e.type.value,
        } for e in self.enemies]
        pickups = [{
            "x": p.pos.x, "y": p.pos.y,
            "kind": p.kind.value, "amount": p.amount,
        } for p in self.pickups]

        return LevelData(
            version=1,
            width=wmap.width,
            height=wmap.height,
            cells=cells,
            player_start=ps,
            enemies=enemies,
            pickups=pickups,
        )

    def load_level_data(self, ld: LevelData) -> None:
        """Replace the editor state from a ``LevelData`` (in place)."""
        width = int(ld.width)
        height = int(ld.height)
        wmap = WorldMap(width, height)
        wmap.cells = [[INT_TO_TEX.get(int(v), None) for v in row]
                      for row in ld.cells]
        self.world_map = wmap
        self.player_start = (dict(ld.player_start) if ld.player_start
                             else None)
        self.enemies = build_enemies(ld)
        self.pickups = build_pickups(ld)
        # U4: a wholesale state replacement (Ctrl+O / entering the editor)
        # invalidates the undo history - cross-file undo is meaningless.
        self._undo_stack = []

    def save(self, path: str = None) -> None:
        """Persist the current level to JSON (Ctrl+S)."""
        target = path or self.map_path or DEFAULT_MAP_PATH
        save_map(self.to_level_data(), target)
        print(f"[EDITOR] saved level -> {target}")

    def load(self, path: str = None) -> None:
        """Load a level from JSON/ASCII (Ctrl+O)."""
        target = path or self.map_path or DEFAULT_MAP_PATH
        try:
            self.load_level_data(load_map(target))
            print(f"[EDITOR] loaded level <- {target}")
        except Exception as exc:
            print(f"[EDITOR] load failed: {exc}")

    # ------------------------------------------------------------------ #
    # Rendering
    # ------------------------------------------------------------------ #
    def render(self, surface) -> None:
        """Draw the editor grid, entities and the brush palette."""
        if surface is None:
            return
        surface.fill((20, 20, 26))

        if self.world_map.width <= 0 or self.world_map.height <= 0:
            return

        cell = self._cell_size()
        ox, oy = self._origin(cell)
        wmap = self.world_map

        # Walls.
        for gy in range(wmap.height):
            for gx in range(wmap.width):
                tex = wmap.cells[gy][gx]
                px, py = ox + gx * cell, oy + gy * cell
                if tex is None:
                    pygame.draw.rect(surface, (40, 40, 48),
                                     (px, py, cell, cell))
                else:
                    color = TEX_COLOR.get(tex, (120, 120, 120))
                    pygame.draw.rect(surface, color, (px, py, cell, cell))
                pygame.draw.rect(surface, (10, 10, 12),
                                 (px, py, cell, cell), 1)

        # Pickups.
        for p in self.pickups:
            cx = ox + int(p.pos.x * cell)
            cy = oy + int(p.pos.y * cell)
            color = (40, 210, 40) if p.kind == PickupType.HEALTH else (230, 210, 40)
            pygame.draw.circle(surface, color, (cx, cy), max(2, cell // 3))

        # Enemies.
        for e in self.enemies:
            cx = ox + int(e.pos.x * cell)
            cy = oy + int(e.pos.y * cell)
            pygame.draw.circle(surface, (220, 50, 50), (cx, cy),
                               max(2, cell // 3))

        # Player start.
        if self.player_start is not None:
            cx = ox + int(self.player_start.get("x", 1.5) * cell)
            cy = oy + int(self.player_start.get("y", 1.5) * cell)
            pygame.draw.circle(surface, (255, 220, 80), (cx, cy),
                               max(2, cell // 3))
            ang = float(self.player_start.get("angle", 0.0))
            ex = cx + int(__import__("math").cos(ang) * cell)
            ey = cy + int(__import__("math").sin(ang) * cell)
            pygame.draw.line(surface, (255, 220, 80), (cx, cy), (ex, ey), 2)

        self._render_palette(surface)

    def _render_palette(self, surface) -> None:
        """Draw the brush palette + a short help line at the top-left."""
        try:
            font = pygame.font.SysFont(None, 22)
        except Exception:                  # pragma: no cover
            font = None
        x0, y0 = 8, 8
        for idx, (label, _brush) in enumerate(BRUSHES):
            bx = x0 + idx * 96
            is_active = (idx == self.brush_index)
            bg = (70, 70, 90) if is_active else (45, 45, 55)
            pygame.draw.rect(surface, bg, (bx, y0, 90, 26))
            if is_active:
                pygame.draw.rect(surface, (255, 230, 120),
                                 (bx, y0, 90, 26), 2)
            if font is not None:
                txt = font.render(f"{idx + 1}.{label}", True, (230, 230, 230))
                surface.blit(txt, (bx + 4, y0 + 4))
        if font is not None:
            help_y = y0 + 34
            help_lines = [
                "LMB place | RMB erase | Ctrl+S save | Ctrl+O load "
                "| Ctrl+Z undo",
                "ESC return to play (rebuild world from this level)",
            ]
            for line in help_lines:
                txt = font.render(line, True, (200, 200, 200))
                surface.blit(txt, (x0, help_y))
                help_y += 22


def _safe_exists(path: str) -> bool:
    """Wrapper around os.path.exists that never raises."""
    try:
        return os.path.exists(path)
    except Exception:                      # pragma: no cover
        return False


__all__ = ["LevelEditor"]
