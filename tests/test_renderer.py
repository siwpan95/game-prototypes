"""Tests for the DDA raycaster (DOOMRenderer).

The DDA math is verified against hand calculations on a known 5x5 enclosed
map, and ``render`` is exercised for every RenderMode on a real pygame Surface.
"""
import math

import pytest

from doom_game.core.types import TextureType, RenderMode
from doom_game.core.player import Player
from doom_game.config import MAX_RENDER_DIST


class TestCastRayGeometry:
    def test_straight_ahead_hits_x_wall_distance_1_5(self, small_map, small_renderer):
        dist, tex, side = small_renderer.cast_ray(2.5, 2.5, 0.0, small_map)
        # Player at x=2.5 facing +x; wall face at x=4 -> perp distance = 1.5.
        assert pytest.approx(dist, abs=1e-9) == 1.5
        assert tex == TextureType.STONE
        assert side == 0  # vertical (x) wall face

    def test_straight_up_hits_y_wall_distance_1_5(self, small_map, small_renderer):
        dist, tex, side = small_renderer.cast_ray(2.5, 2.5, math.pi / 2.0, small_map)
        assert pytest.approx(dist, abs=1e-9) == 1.5
        assert tex == TextureType.STONE
        assert side == 1  # horizontal (y) wall face

    def test_45_degree_hits_corner_wall(self, small_map, small_renderer):
        dist, tex, side = small_renderer.cast_ray(2.5, 2.5, math.pi / 4.0, small_map)
        # Symmetric map -> hits y=4 face; perp distance = 1.5 / cos(45deg).
        expected = 1.5 / math.cos(math.pi / 4.0)
        assert pytest.approx(dist, abs=1e-4) == expected
        assert tex == TextureType.STONE
        assert side == 1

    def test_no_hit_returns_max_distance_and_none(self, empty_map, small_renderer):
        dist, tex, side = small_renderer.cast_ray(1.5, 1.5, 0.0, empty_map)
        assert tex is None
        assert pytest.approx(dist) == MAX_RENDER_DIST
        assert side in (0, 1)


class TestRenderModes:
    @pytest.mark.parametrize("mode", [
        RenderMode.WIREFRAME,
        RenderMode.SOLID,
        RenderMode.TEXTURED,
        RenderMode.DOOM_STYLE,
    ])
    def test_render_all_modes_do_not_raise(self, display, small_map,
                                           small_renderer, mode):
        player = Player(2.5, 2.5, angle=0.0)
        # Should complete without raising on a real dummy surface.
        small_renderer.render(player, small_map, mode)
        assert small_renderer.screen is not None

    def test_render_textures_are_cached(self, small_renderer):
        assert len(small_renderer.textures) == 4
        for tt in TextureType:
            assert tt in small_renderer.textures
