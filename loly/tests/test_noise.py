"""Tests for procedural wall-texture / surface noise generation.

Determinism is verified pixel-for-pixel using pygame.surfarray (numpy).
"""
import time

import numpy as np
import pygame
import pytest

from doom_game.render.noise import NoiseAlgorithm


class TestGenerateWallTexture:
    def test_returns_64x64_surface(self):
        surf = NoiseAlgorithm.generate_wall_texture(64, 64, seed=1)
        assert surf.get_size() == (64, 64)

    def test_same_seed_is_deterministic(self):
        a = NoiseAlgorithm.generate_wall_texture(64, 64, seed=5)
        b = NoiseAlgorithm.generate_wall_texture(64, 64, seed=5)
        arr_a = np.array_equal(
            __import__("pygame").surfarray.array3d(a),
            __import__("pygame").surfarray.array3d(b),
        )
        assert arr_a is True

    def test_different_seed_differs(self):
        a = NoiseAlgorithm.generate_wall_texture(64, 64, seed=1)
        b = NoiseAlgorithm.generate_wall_texture(64, 64, seed=2)
        diff = np.any(
            np.not_equal(
                __import__("pygame").surfarray.array3d(a),
                __import__("pygame").surfarray.array3d(b),
            )
        )
        assert diff


class TestSurfarrayParity:
    """R2.9: the numpy/surfarray rewrite must stay deterministic and correct.

    ``generate_wall_texture`` was changed from a per-pixel ``set_at`` loop to a
    vectorised numpy + ``pygame.surfarray.blit_array`` implementation. These
    tests pin the properties that rewrite must not break.
    """

    SEEDS = (1, 2, 3, 4)   # brick / stone / metal / wood

    @staticmethod
    def _pixels(surface):
        return pygame.surfarray.array3d(surface)

    @pytest.mark.parametrize("seed", SEEDS)
    def test_same_seed_is_pixel_identical(self, seed):
        a = NoiseAlgorithm.generate_wall_texture(64, 64, seed=seed)
        b = NoiseAlgorithm.generate_wall_texture(64, 64, seed=seed)
        assert np.array_equal(self._pixels(a), self._pixels(b))

    def test_repeated_generation_stays_stable(self):
        first = self._pixels(
            NoiseAlgorithm.generate_wall_texture(64, 64, seed=2))
        for _ in range(4):
            again = self._pixels(
                NoiseAlgorithm.generate_wall_texture(64, 64, seed=2))
            assert np.array_equal(first, again)

    def test_different_seeds_produce_different_pixels(self):
        arrays = [self._pixels(
            NoiseAlgorithm.generate_wall_texture(64, 64, seed=s))
            for s in self.SEEDS]
        for i in range(len(arrays)):
            for j in range(i + 1, len(arrays)):
                assert not np.array_equal(arrays[i], arrays[j]), (
                    f"seeds {self.SEEDS[i]} and {self.SEEDS[j]} "
                    f"produced identical textures")

    @pytest.mark.parametrize("seed", SEEDS)
    def test_all_four_materials_generate_at_64x64(self, seed):
        surf = NoiseAlgorithm.generate_wall_texture(64, 64, seed=seed)
        assert surf.get_size() == (64, 64)
        assert self._pixels(surf).shape == (64, 64, 3)

    @pytest.mark.parametrize("size", [(1, 1), (8, 16), (32, 32), (128, 64)])
    def test_non_square_and_tiny_sizes_are_supported(self, size):
        w, h = size
        surf = NoiseAlgorithm.generate_wall_texture(w, h, seed=1)
        assert surf.get_size() == (w, h)

    def test_pixels_stay_in_valid_rgb_range(self):
        arr = self._pixels(NoiseAlgorithm.generate_wall_texture(64, 64, seed=3))
        assert arr.min() >= 0
        assert arr.max() <= 255

    def test_texture_is_not_a_flat_colour(self):
        """The noise must actually vary - a constant fill would be a bug."""
        arr = self._pixels(NoiseAlgorithm.generate_wall_texture(64, 64, seed=1))
        assert len(np.unique(arr.reshape(-1, 3), axis=0)) > 1

    def test_vectorised_matches_scalar_fractal_noise(self):
        """``_fractal_2d_vec`` must reproduce the scalar ``_fractal_2d``."""
        xs = np.array([[0.0, 1.5], [3.25, 7.75]])
        ys = np.array([[0.0, 2.5], [4.75, 9.5]])
        vec = NoiseAlgorithm._fractal_2d_vec(xs, ys, 2, octaves=4)
        for iy in range(2):
            for ix in range(2):
                scalar = NoiseAlgorithm._fractal_2d(
                    float(xs[iy, ix]), float(ys[iy, ix]), 2, octaves=4)
                assert vec[iy, ix] == pytest.approx(scalar, abs=1e-12)

    def test_generation_benchmark_is_printed(self, capsys):
        """Rough timing for the four materials (informational, no assertion)."""
        start = time.perf_counter()
        for seed in self.SEEDS:
            NoiseAlgorithm.generate_wall_texture(64, 64, seed=seed)
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        with capsys.disabled():
            print(f"\n[BENCH] 4 x generate_wall_texture(64, 64) "
                  f"= {elapsed_ms:.2f} ms "
                  f"({elapsed_ms / 4.0:.2f} ms per texture)")
        assert elapsed_ms >= 0.0


class TestApplySurfaceNoise:
    def test_does_not_raise_and_keeps_size(self):
        base = NoiseAlgorithm.generate_wall_texture(32, 32, seed=3)
        out = NoiseAlgorithm.apply_surface_noise(base, intensity=0.1)
        assert out is not None
        assert out.get_size() == (32, 32)

    def test_returns_a_surface(self):
        base = NoiseAlgorithm.generate_wall_texture(16, 16, seed=4)
        out = NoiseAlgorithm.apply_surface_noise(base, intensity=0.2)
        assert hasattr(out, "get_size")
