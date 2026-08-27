"""Procedural noise used to synthesise wall textures.

All generation is deterministic given a ``seed`` and never touches the global
``random`` module state (architecture ambiguity #6 / rule #6), so headless
tests are fully reproducible.
"""
import math

try:
    import pygame_ce as pygame
except ImportError:  # pragma: no cover - pygame_ce exposed as pygame
    import pygame

import numpy as np


class NoiseAlgorithm:
    """Deterministic value/Perlin noise + wall texture generation."""

    # ------------------------------------------------------------------ #
    # Deterministic hash-based gradients (no global RNG side effects)
    # ------------------------------------------------------------------ #
    @staticmethod
    def _hash1(i: int, seed: int) -> float:
        """Deterministic pseudo-random gradient in [-1, 1] for 1D noise."""
        state = (i * 2654435761 + seed * 40503) & 0x7FFFFFFF
        state = (state ^ (state >> 13)) * 1274126177 & 0x7FFFFFFF
        state = (state ^ (state >> 16)) & 0x7FFFFFFF
        return (state / 0x7FFFFFFF) * 2.0 - 1.0

    @staticmethod
    def _hash2(ix: int, iy: int, seed: int) -> float:
        """Deterministic pseudo-random gradient in [-1, 1] for 2D noise."""
        state = (ix * 374761393 + iy * 668265263 + seed * 2147483647) & 0x7FFFFFFF
        state = (state ^ (state >> 13)) * 1274126177 & 0x7FFFFFFF
        state = (state ^ (state >> 16)) & 0x7FFFFFFF
        return (state / 0x7FFFFFFF) * 2.0 - 1.0

    # ------------------------------------------------------------------ #
    # 1D noise (kept for interface compatibility / fractal detail)
    # ------------------------------------------------------------------ #
    @staticmethod
    def perlin_noise_1d(x: float, seed: int = 0) -> float:
        """Simplified 1D value-noise with smooth (fade) interpolation."""
        x0 = int(math.floor(x))
        x1 = x0 + 1
        dx = x - x0
        g0 = NoiseAlgorithm._hash1(x0, seed)
        g1 = NoiseAlgorithm._hash1(x1, seed)
        n0 = g0 * dx
        n1 = g1 * (dx - 1.0)
        fade = dx * dx * (3.0 - 2.0 * dx)
        return n0 + fade * (n1 - n0)

    @staticmethod
    def fractal_noise(x: float, octaves: int = 4, persistence: float = 0.5,
                      seed: int = 0) -> float:
        """Multi-octave 1D fractal noise, normalised to roughly [-1, 1]."""
        value = 0.0
        amplitude = 1.0
        frequency = 1.0
        max_value = 0.0
        for o in range(max(1, octaves)):
            value += NoiseAlgorithm.perlin_noise_1d(
                x * frequency, seed + o * 101) * amplitude
            max_value += amplitude
            amplitude *= persistence
            frequency *= 2.0
        if max_value > 0:
            value /= max_value
        return value

    # ------------------------------------------------------------------ #
    # 2D noise (used for texturing)
    # ------------------------------------------------------------------ #
    @staticmethod
    def _value_noise_2d(x: float, y: float, seed: int) -> float:
        """Single-octave 2D value noise in [-1, 1]."""
        x0 = int(math.floor(x))
        y0 = int(math.floor(y))
        dx = x - x0
        dy = y - y0
        fade_x = dx * dx * (3.0 - 2.0 * dx)
        fade_y = dy * dy * (3.0 - 2.0 * dy)
        v00 = NoiseAlgorithm._hash2(x0, y0, seed)
        v10 = NoiseAlgorithm._hash2(x0 + 1, y0, seed)
        v01 = NoiseAlgorithm._hash2(x0, y0 + 1, seed)
        v11 = NoiseAlgorithm._hash2(x0 + 1, y0 + 1, seed)
        top = v00 + fade_x * (v10 - v00)
        bottom = v01 + fade_x * (v11 - v01)
        return top + fade_y * (bottom - top)

    @staticmethod
    def _fractal_2d(x: float, y: float, seed: int,
                    octaves: int = 4, persistence: float = 0.5) -> float:
        """Multi-octave 2D fractal noise, normalised to [-1, 1]."""
        value = 0.0
        amplitude = 1.0
        frequency = 1.0
        max_value = 0.0
        for o in range(max(1, octaves)):
            value += NoiseAlgorithm._value_noise_2d(
                x * frequency, y * frequency, seed + o * 1013) * amplitude
            max_value += amplitude
            amplitude *= persistence
            frequency *= 2.0
        if max_value > 0:
            value /= max_value
        return value

    # ------------------------------------------------------------------ #
    # Vectorised (numpy + surfarray) variants - pixel-identical to the
    # scalar loops above, used by generate_wall_texture for speed.
    # ------------------------------------------------------------------ #
    @staticmethod
    def _hash2_vec(ix, iy, seed):
        """Vectorised ``_hash2`` over numpy int64 arrays -> float64 in [-1, 1].

        Integer arithmetic matches the scalar ``_hash2`` exactly (all
        intermediate values stay within int64 range), so the result is
        bit-for-bit identical to calling ``_hash2`` per pixel.
        """
        ix = ix.astype(np.int64)
        iy = iy.astype(np.int64)
        mask = np.int64(0x7FFFFFFF)
        seed = np.int64(seed)
        state = (ix * 374761393 + iy * 668265263 + seed * 2147483647) & mask
        state = (state ^ (state >> 13)) * 1274126177 & mask
        state = (state ^ (state >> 16)) & mask
        return (state.astype(np.float64) / 0x7FFFFFFF) * 2.0 - 1.0

    @staticmethod
    def _value_noise_2d_vec(x, y, seed):
        """Vectorised single-octave 2D value noise (matches ``_value_noise_2d``)."""
        x0 = np.floor(x).astype(np.int64)
        y0 = np.floor(y).astype(np.int64)
        dx = x - x0.astype(np.float64)
        dy = y - y0.astype(np.float64)
        fade_x = dx * dx * (3.0 - 2.0 * dx)
        fade_y = dy * dy * (3.0 - 2.0 * dy)
        v00 = NoiseAlgorithm._hash2_vec(x0, y0, seed)
        v10 = NoiseAlgorithm._hash2_vec(x0 + 1, y0, seed)
        v01 = NoiseAlgorithm._hash2_vec(x0, y0 + 1, seed)
        v11 = NoiseAlgorithm._hash2_vec(x0 + 1, y0 + 1, seed)
        top = v00 + fade_x * (v10 - v00)
        bottom = v01 + fade_x * (v11 - v01)
        return top + fade_y * (bottom - top)

    @staticmethod
    def _fractal_2d_vec(x, y, seed, octaves: int = 4, persistence: float = 0.5):
        """Vectorised multi-octave 2D fractal noise (matches ``_fractal_2d``).

        Octaves are accumulated left-to-right exactly like the scalar loop so
        per-pixel floating point results are identical.
        """
        value = np.zeros_like(x, dtype=np.float64)
        max_value = 0.0
        amplitude = 1.0
        frequency = 1.0
        for o in range(max(1, octaves)):
            arr = NoiseAlgorithm._value_noise_2d_vec(
                x * frequency, y * frequency, seed + o * 1013) * amplitude
            value = value + arr
            max_value += amplitude
            amplitude *= persistence
            frequency *= 2.0
        if max_value > 0:
            value = value / max_value
        return value

    # ------------------------------------------------------------------ #
    # Texture generation
    # ------------------------------------------------------------------ #
    @staticmethod
    def generate_wall_texture(w: int, h: int, seed: int = 0):
        """Generate a deterministic wall texture surface of size (w, h).

        Different ``seed`` values produce visually distinct materials
        (brick / stone / metal / wood) while remaining reproducible. The
        pixels are computed with numpy + ``pygame.surfarray`` (no per-pixel
        ``set_at`` loop) but are bit-for-bit identical to the old scalar
        implementation, preserving determinism (architecture ambiguity #6).
        """
        # Per-seed base tints so the four wall types look different.
        palette = {
            1: (150, 70, 55),    # brick  - reddish
            2: (130, 130, 135),  # stone  - neutral grey
            3: (120, 130, 150),  # metal  - blue-grey
            4: (150, 110, 70),   # wood   - brown
        }
        base_r, base_g, base_b = palette.get(seed, (128, 128, 128))

        # Mesh of pixel coordinates; Xs[y, x] == x, Ys[y, x] == y.
        xs = np.arange(w, dtype=np.float64)
        ys = np.arange(h, dtype=np.float64)
        Xs, Ys = np.meshgrid(xs, ys, indexing="xy")

        # Same expression as the old loop: _fractal_2d(x * 0.15, y * 0.15, seed).
        n = NoiseAlgorithm._fractal_2d_vec(Xs * 0.15, Ys * 0.15, seed, octaves=4)

        # shade = int((n + 1.0) * 0.5 * 70) - 35  (n in [-1, 1] -> [-35, +35]).
        # (n + 1) >= 0 so int() == floor() == trunc(); identical to scalar int().
        shade = np.trunc((n + 1.0) * 0.5 * 70).astype(np.int64) - 35

        r = np.clip(base_r + shade, 0, 255).astype(np.uint8)
        g = np.clip(base_g + shade, 0, 255).astype(np.uint8)
        b = np.clip(base_b + shade, 0, 255).astype(np.uint8)

        # Stack into (h, w, 3) then transpose to surfarray's (w, h, 3) layout.
        arr = np.stack([r, g, b], axis=-1)            # (h, w, 3)
        arr = np.transpose(arr, (1, 0, 2))            # (w, h, 3)

        surface = pygame.Surface((w, h))
        pygame.surfarray.blit_array(surface, arr)
        return surface

    @staticmethod
    def apply_surface_noise(surface, intensity: float = 0.1):
        """Return a copy of ``surface`` with deterministic per-pixel grain."""
        if surface is None:
            return surface
        w = surface.get_width()
        h = surface.get_height()
        out = surface.copy()
        for y in range(h):
            for x in range(w):
                r, g, b, a = surface.get_at((x, y))
                n = NoiseAlgorithm._hash2(x, y, 777) * intensity
                r = max(0, min(255, int(r * (1.0 + n))))
                g = max(0, min(255, int(g * (1.0 + n))))
                b = max(0, min(255, int(b * (1.0 + n))))
                out.set_at((x, y), (r, g, b, a))
        return out
