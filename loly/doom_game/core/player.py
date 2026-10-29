"""Player entity: position, orientation, velocity and kinematics.

Kept in its own module (per the documented file layout) but still part of the
single, authoritative ``core`` type set - never redefined elsewhere.
"""
import math

from doom_game.core.types import Vector2
from doom_game.config import PLAYER_MAX_HP


class Player:
    """Player avatar: position, facing angle, velocity, kinematics."""

    def __init__(self, x: float, y: float, angle: float = 0.0,
                 speed: float = 0.1, rotate_speed: float = 0.05,
                 max_hp: float = PLAYER_MAX_HP, hp=None, score: float = 0):
        self.pos = Vector2(x, y)
        self.angle = float(angle)
        self.velocity_x = 0.0
        self.velocity_y = 0.0
        self.speed = float(speed)
        self.rotate_speed = float(rotate_speed)
        # Health / score model (incremental feature). ``hp`` defaults to the
        # maximum so existing callers that omit it spawn at full health.
        self.max_hp = float(max_hp)
        self.hp = float(self.max_hp) if hp is None else float(hp)
        self.score = float(score)

    def move(self, forward: float, strafe: float) -> None:
        """Apply forward/back and strafe movement along the current facing.

        ``forward`` and ``strafe`` are direction multipliers (-1, 0, +1).
        The per-frame displacement is stored as velocity for the audio system.
        """
        dir_x = math.cos(self.angle)
        dir_y = math.sin(self.angle)
        perp_x = math.cos(self.angle + math.pi / 2.0)
        perp_y = math.sin(self.angle + math.pi / 2.0)
        dx = (dir_x * forward + perp_x * strafe) * self.speed
        dy = (dir_y * forward + perp_y * strafe) * self.speed
        self.pos.x += dx
        self.pos.y += dy
        self.velocity_x = dx
        self.velocity_y = dy

    def rotate(self, direction: float) -> None:
        """Rotate by ``direction`` (sign) at ``rotate_speed`` (radians)."""
        self.angle += direction * self.rotate_speed
        two_pi = 2.0 * math.pi
        self.angle %= two_pi
        if self.angle < 0:
            self.angle += two_pi

    def get_speed(self) -> float:
        """Magnitude of the per-frame velocity (used for audio triggering)."""
        return math.hypot(self.velocity_x, self.velocity_y)

    def __repr__(self) -> str:
        return f"Player(pos={self.pos}, angle={self.angle:.2f})"
