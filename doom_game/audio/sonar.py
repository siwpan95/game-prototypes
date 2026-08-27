"""Physics-based dual-ray sonar.

Emits rays against the grid ``WorldMap`` to (a) estimate environment density
and (b) detect motion via the distance difference between two rays cast from
the current and the (slightly) displaced position. Produces an audio signal
that is silent when still, audible when moving, and weaker in open spaces
(architecture ambiguity #3 / physical constraints).
"""
import math
import time
from collections import deque

from doom_game.config import MAX_RENDER_DIST, MIN_AUDIO_VELOCITY


class PhysicsRaySonar:
    """Motion- and environment-aware sonar driving the audio signal."""

    def __init__(self, x: float = 0.0, y: float = 0.0, base_angle: float = 0.0,
                 sample_rate: int = 44100):
        self.x = float(x)
        self.y = float(y)
        self.base_angle = float(base_angle)
        self.sample_rate = sample_rate

        self.speed_of_sound = 343.0
        self.min_velocity_threshold = MIN_AUDIO_VELOCITY
        self.max_velocity = 5.0
        self.smoothing_alpha = 0.9
        self.last_audio_sample = 0.0

        self.velocity = 0.0
        self.acceleration = 0.0
        self.last_position = (float(x), float(y))
        self.last_time = time.time()

        # Ring buffers for diagnostics / visualisation.
        self.raw_distance_diff = deque(maxlen=100)
        self.environment_density = deque(maxlen=100)
        self.audio_buffer = deque(maxlen=200)

    # ------------------------------------------------------------------ #
    # Motion tracking
    # ------------------------------------------------------------------ #
    def calculate_motion(self, new_x: float, new_y: float):
        """Estimate velocity / acceleration from the last update."""
        now = time.time()
        dt = now - self.last_time
        if dt <= 0:
            self.last_position = (new_x, new_y)
            self.last_time = now
            return 0.0, 0.0
        dx = new_x - self.last_position[0]
        dy = new_y - self.last_position[1]
        displacement = math.hypot(dx, dy)
        new_velocity = displacement / dt
        new_accel = (new_velocity - self.velocity) / dt
        self.last_position = (new_x, new_y)
        self.last_time = now
        self.velocity = new_velocity
        self.acceleration = new_accel
        return new_velocity, new_accel

    # ------------------------------------------------------------------ #
    # Ray casting against the grid (O(1) per step via WorldMap)
    # ------------------------------------------------------------------ #
    def _cast_distance(self, sx: float, sy: float, angle: float,
                       world) -> float:
        """DDA distance to the nearest wall in ``world`` (or MAX_RENDER_DIST)."""
        rdx = math.cos(angle)
        rdy = math.sin(angle)
        mx = int(sx)
        my = int(sy)
        ddx = abs(1 / rdx) if rdx != 0 else 1e30
        ddy = abs(1 / rdy) if rdy != 0 else 1e30
        step_x = 1 if rdx >= 0 else -1
        step_y = 1 if rdy >= 0 else -1
        sdx = (sx - mx) * ddx if rdx < 0 else (mx + 1.0 - sx) * ddx
        sdy = (sy - my) * ddy if rdy < 0 else (my + 1.0 - sy) * ddy
        dist = 0.0
        while dist < MAX_RENDER_DIST:
            if sdx < sdy:
                sdx += ddx
                mx += step_x
                side = 0
            else:
                sdy += ddy
                my += step_y
                side = 1
            dist = sdx if side == 0 else sdy
            if mx < 0 or my < 0 or mx >= world.width or my >= world.height:
                return MAX_RENDER_DIST
            if world.cells[my][mx] is not None:
                return dist
        return MAX_RENDER_DIST

    def cast_ray_with_motion(self, angle: float, velocity: float, world,
                             is_second: bool = False) -> float:
        """Cast a ray, optionally displaced by the motion of the player."""
        if is_second and velocity > self.min_velocity_threshold:
            dt = 0.001                # 1 ms look-ahead
            disp = velocity * dt
            rx = self.x + math.cos(angle) * disp
            ry = self.y + math.sin(angle) * disp
        else:
            rx = self.x
            ry = self.y
        return self._cast_distance(rx, ry, angle, world)

    def calculate_environment_density(self, distances) -> float:
        """Density in [0,1]; 1 = very enclosed, 0 = very open."""
        if not distances:
            return 0.0
        avg = sum(distances) / len(distances)
        return 1.0 / (1.0 + avg)

    def generate_motion_triggered_audio(self, velocity, dist1, dist2,
                                        density) -> float:
        """Produce the audio sample for this frame.

        Physical constraints: still -> 0; moving -> non-zero; open -> weak.
        """
        if velocity < self.min_velocity_threshold:
            return 0.0
        diff = abs(dist1 - dist2)
        vfac = min(1.0, velocity / self.max_velocity)
        dfac = density
        if diff > 0.001:
            base = diff * vfac * dfac
            ffac = 1.0 + vfac * 2.0
            osc = math.sin(time.time() * ffac * 10.0)
            signal = base * osc
        else:
            signal = 0.0
        smoothed = (self.last_audio_sample * self.smoothing_alpha
                    + signal * (1.0 - self.smoothing_alpha))
        smoothed = max(-1.0, min(1.0, smoothed))
        self.last_audio_sample = smoothed
        return smoothed

    def update(self, x: float, y: float, angle: float, world):
        """Full sonar update; returns (signal, velocity, density)."""
        self.x = x
        self.y = y
        self.base_angle = angle

        velocity, _ = self.calculate_motion(x, y)

        # Sample eight directions to estimate openness.
        n = 8
        angles = [angle + i * (2.0 * math.pi / n) for i in range(n)]
        distances = [self._cast_distance(x, y, a, world) for a in angles]
        density = self.calculate_environment_density(distances)

        if velocity > self.min_velocity_threshold:
            d1 = self.cast_ray_with_motion(angle, velocity, world, False)
            d2 = self.cast_ray_with_motion(angle, velocity, world, True)
            signal = self.generate_motion_triggered_audio(
                velocity, d1, d2, density)
        else:
            signal = 0.0
            d1 = d2 = distances[0] if distances else MAX_RENDER_DIST

        if velocity > self.min_velocity_threshold:
            self.raw_distance_diff.append(abs(d1 - d2))
        self.environment_density.append(density)
        self.audio_buffer.append(signal)
        return signal, velocity, density
