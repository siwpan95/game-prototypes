"""Core shared data types.

These types are defined exactly once and imported everywhere else via
``from doom_game.core.types import ...`` (architecture rule #1, #6).
Reproducing any of these in render/audio/world/main is forbidden.

``Player`` lives in its own module ``doom_game.core.player`` so that the
package layout matches the documented file list (section 2).
"""
from enum import Enum
from typing import Tuple


class TextureType(Enum):
    """Wall surface categories. Each maps to a procedurally generated texture."""
    BRICK = "brick"
    STONE = "stone"
    METAL = "metal"
    WOOD = "wood"


class RenderMode(Enum):
    """Per-column drawing style for the DDA raycaster (architecture ambiguity #1)."""
    WIREFRAME = "wireframe"
    SOLID = "solid"
    TEXTURED = "textured"
    DOOM_STYLE = "doom_style"


class Vector2:
    """Minimal 2D vector used for player position and math helpers."""

    def __init__(self, x: float = 0.0, y: float = 0.0):
        self.x = float(x)
        self.y = float(y)

    def rotate(self, angle: float) -> "Vector2":
        """Return a new vector rotated by ``angle`` radians."""
        import math
        cos_a = math.cos(angle)
        sin_a = math.sin(angle)
        return Vector2(
            self.x * cos_a - self.y * sin_a,
            self.x * sin_a + self.y * cos_a,
        )

    def translate(self, dx: float, dy: float) -> "Vector2":
        """Return a new vector shifted by (dx, dy)."""
        return Vector2(self.x + dx, self.y + dy)

    def distance_to(self, other: "Vector2") -> float:
        """Euclidean distance to another vector."""
        import math
        return math.hypot(self.x - other.x, self.y - other.y)

    def copy(self) -> "Vector2":
        """Return an independent copy."""
        return Vector2(self.x, self.y)

    def to_tuple(self) -> Tuple[float, float]:
        """Return (x, y) as a plain tuple."""
        return (self.x, self.y)

    def __repr__(self) -> str:
        return f"Vector2({self.x:.2f}, {self.y:.2f})"


class Wall:
    """Semantic description of a single grid cell (architecture ambiguity #2).

    Used only as metadata; collision is resolved by the grid ``WorldMap``
    (``is_wall`` / ``get_texture`` are O(1)), never by list traversal.
    """

    def __init__(self, grid_x: int, grid_y: int,
                 texture_type: TextureType = TextureType.BRICK):
        self.grid_x = int(grid_x)
        self.grid_y = int(grid_y)
        self.texture_type = texture_type

    def __repr__(self) -> str:
        return f"Wall({self.grid_x}, {self.grid_y}, {self.texture_type.name})"
