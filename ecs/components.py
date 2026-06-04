"""
Components - Pure data containers for the endless highway game.

Each component is a dataclass that holds state; no logic.
"""

from dataclasses import dataclass
from ecs import Component


# ── Position & Movement ──────────────────────────────────────────

@dataclass
class Position(Component):
    """World position (top-left anchor for rects, start-point for lines)."""
    x: float
    y: float


@dataclass
class Speed(Component):
    """Speed scalar applied horizontally on input."""
    value: float = 5.0


# ── Rendering ─────────────────────────────────────────────────────

@dataclass
class RectRender(Component):
    """Renders a filled rectangle at the entity's Position."""
    width: int
    height: int
    color: tuple
    z_order: int = 0


@dataclass
class LineRender(Component):
    """Renders a line from Position(x,y) to (x2,y2). Drives edge lines."""
    x2: float
    y2: float
    color: tuple
    line_width: int = 5
    z_order: int = 0


@dataclass
class DashedLineRender(Component):
    """Renders a repeating dashed line (center lane)."""
    dash_length: int = 50
    gap_length: int = 30
    line_width: int = 10
    color: tuple = (255, 255, 255)
    offset_y: float = 0.0


# ── Road ──────────────────────────────────────────────────────────

@dataclass
class RoadSurface(Component):
    """Marks the grey road background rectangle."""
    width: int = 400
    height: int = 600
    color: tuple = (30, 30, 30)


@dataclass
class RoadEdge(Component):
    """Marker for left/right edge – used by collision system."""
    side: str = "left"  # "left" or "right"


# ── Decorations ────────────────────────────────────────────────────

@dataclass
class Decoration(Component):
    """Roadside decoration entity that scrolls with the road."""
    deco_type: str = "cactus"   # "cactus" | "rock" | "dead_bush" | "guardrail"
    side: str = "left"          # "left" or "right"
    size: int = 20              # pixel size
    color: tuple = (34, 139, 34)  # primary color
    active: bool = True


# ── Gameplay ──────────────────────────────────────────────────────

@dataclass
class VehicleControl(Component):
    """Player-steered with arrow keys."""
    pass


@dataclass
class Drift(Component):
    """Random left/right push applied each frame."""
    chance: float = 0.015
    min_push: float = 3.0
    max_push: float = 7.0


# ── Stats & State ─────────────────────────────────────────────────

@dataclass
class GameState(Component):
    """Singleton component tracking global game state."""
    alive: bool = True
    paused: bool = False
    drift_count: int = 0
    distance_km: float = 0.0
