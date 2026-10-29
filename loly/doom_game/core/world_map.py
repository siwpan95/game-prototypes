"""Grid-based world map with O(1) collision queries.

This is the authoritative collision structure (architecture ambiguity #2).
Walls are stored in a 2D grid ``cells[gy][gx]`` of ``Optional[TextureType]``;
``is_wall`` / ``get_texture`` are O(1) lookups, which the DDA raycaster and
the physics sonar both rely on.
"""
import math
from typing import List, Optional

from doom_game.core.types import TextureType


class WorldMap:
    """A maze represented as a grid of optional wall textures."""

    def __init__(self, width: int = 0, height: int = 0):
        self.width = int(width)
        self.height = int(height)
        self.cells: List[List[Optional[TextureType]]] = []

    def generate_maze(self, w: int, h: int, seed: Optional[int] = None) -> None:
        """Generate an enclosed maze: solid outer walls + random inner walls.

        If ``seed`` is provided, generation is reproducible (no global side
        effects on shared RNG state beyond a local reseed).
        """
        import random
        if seed is not None:
            random.seed(seed)

        self.width = int(w)
        self.height = int(h)
        textures = list(TextureType)
        # Initialise an all-empty grid.
        self.cells = [[None for _ in range(self.width)]
                      for _ in range(self.height)]

        # Outer boundary walls.
        for x in range(self.width):
            self.cells[0][x] = TextureType.STONE
            self.cells[self.height - 1][x] = TextureType.STONE
        for y in range(self.height):
            self.cells[y][0] = TextureType.STONE
            self.cells[y][self.width - 1] = TextureType.STONE

        # Inner walls on an even lattice, with occasional extensions.
        for x in range(2, self.width - 2, 2):
            for y in range(2, self.height - 2, 2):
                texture = random.choice(textures)
                if random.random() > 0.3:
                    if random.random() > 0.5:
                        self.cells[y][x] = texture
                        if random.random() > 0.5 and x + 1 < self.width - 1:
                            self.cells[y][x + 1] = texture
                    else:
                        self.cells[y][x] = texture
                        if random.random() > 0.5 and y + 1 < self.height - 1:
                            self.cells[y + 1][x] = texture

    def is_wall(self, gx: int, gy: int) -> bool:
        """Return True if the grid cell is a wall or out of bounds (O(1))."""
        if gx < 0 or gy < 0 or gx >= self.width or gy >= self.height:
            return True
        return self.cells[gy][gx] is not None

    def get_texture(self, gx: int, gy: int) -> Optional[TextureType]:
        """Return the texture at a grid cell, or None if empty/out of bounds."""
        if gx < 0 or gy < 0 or gx >= self.width or gy >= self.height:
            return None
        return self.cells[gy][gx]

    def find_open_cell(self) -> tuple:
        """Return (x, y) of the first empty cell, used to spawn the player."""
        for y in range(self.height):
            for x in range(self.width):
                if self.cells[y][x] is None:
                    return (x, y)
        return (1, 1)

    def line_of_sight(self, x0: float, y0: float, x1: float, y1: float) -> bool:
        """Return True if the segment (x0,y0)->(x1,y1) is unobstructed.

        Uses dense sampling of the grid (step ~0.05 cell). Endpoints are
        skipped so callers positioned flush against a wall are not falsely
        flagged. Any sampled cell that is a wall breaks the line of sight.
        """
        dx = x1 - x0
        dy = y1 - y0
        dist = math.hypot(dx, dy)
        if dist < 1e-9:
            return True
        steps = max(1, int(dist / 0.05))
        # Skip the first and last sample (the caller positions are open cells).
        for i in range(1, steps):
            t = i / steps
            sx = x0 + dx * t
            sy = y0 + dy * t
            gx = int(sx)
            gy = int(sy)
            if self.is_wall(gx, gy):
                return False
        return True
