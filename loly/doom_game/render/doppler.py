"""Doppler-effect helpers.

Provides frequency-shift math, a distance->colour mapping (used as the visual
analogue of a doppler tone shift) and a cheap motion-blur approximation.
"""
import math

try:
    import pygame_ce as pygame
except ImportError:  # pragma: no cover
    import pygame

from doom_game.config import (SCREEN_WIDTH, SCREEN_HEIGHT, MAX_RENDER_DIST)


class DopplerEffect:
    """Static helpers modelling doppler-style visual/audio cues."""

    SPEED_OF_SOUND = 343.0  # m/s

    @staticmethod
    def calculate_frequency_shift(distance: float, velocity: float,
                                  base_frequency: float = 440.0) -> float:
        """Simplified doppler shift: f' = f * c / (c ∓ v).

        ``velocity`` > 0 means approaching (higher pitch), < 0 receding.
        """
        c = DopplerEffect.SPEED_OF_SOUND
        if velocity > 0:
            return base_frequency * (c / (c - velocity))
        return base_frequency * (c / (c + abs(velocity)))

    @staticmethod
    def distance_to_color(distance: float,
                          max_distance: float = MAX_RENDER_DIST):
        """Map a distance to a colour: warm (near) -> cool (far).

        This is the *visual* doppler cue layered onto wall columns.
        """
        if distance <= 0:
            distance = 0.001
        t = min(distance / max_distance, 1.0)
        if t < 0.3:                       # near - warm red/yellow
            r = 255
            g = int(200 * (1 - t / 0.3))
            b = 50
        elif t < 0.6:                     # mid
            r = int(255 * (1 - (t - 0.3) / 0.3))
            g = 150
            b = 100
        else:                             # far - cool blue/violet
            r = 50
            g = 100
            b = int(255 * (t - 0.6) / 0.4)
        return (r, g, b)

    @staticmethod
    def apply_motion_blur(surface, velocity: float, angle: float):
        """Cheap motion-blur approximation (architecture ambiguity #4).

        When the player is essentially stationary the surface is returned
        untouched. When moving, a few translucent "ghost" copies of the
        current frame are blitted along the velocity direction, producing a
        residual-trail effect without per-pixel full-screen passes.
        """
        if surface is None:
            return surface
        if abs(velocity) < 0.01:
            return surface
        blur_intensity = int(min(abs(velocity) * 40.0, 10))
        if blur_intensity <= 0:
            return surface
        offset_x = math.cos(angle)
        offset_y = math.sin(angle)
        for i in range(blur_intensity, 0, -1):
            alpha = max(1, 100 // (i + 1))
            ghost = surface.copy()
            ghost.set_alpha(alpha)
            surface.blit(ghost, (offset_x * i, offset_y * i))
        return surface
