"""Tests for the DopplerEffect helpers: distance->colour, frequency shift,
and cheap motion blur.
"""
import pytest

import pygame
from doom_game.render.doppler import DopplerEffect
from doom_game.config import MAX_RENDER_DIST


class TestDistanceToColor:
    def test_returns_valid_rgb_triple(self):
        for d in (0.001, 1.0, 5.0, 10.0, MAX_RENDER_DIST, 999.0):
            r, g, b = DopplerEffect.distance_to_color(d)
            assert isinstance(r, int) and 0 <= r <= 255
            assert isinstance(g, int) and 0 <= g <= 255
            assert isinstance(b, int) and 0 <= b <= 255

    def test_near_is_warm_bright(self):
        r, g, b = DopplerEffect.distance_to_color(0.001)
        # Near -> red/yellow dominant (warm).
        assert r == 255
        assert b == 50

    def test_far_is_cool_dark(self):
        r, g, b = DopplerEffect.distance_to_color(MAX_RENDER_DIST)
        # Far -> blue dominant (cool).
        assert b == 255

    def test_farther_is_not_brighter_than_near(self):
        near = DopplerEffect.distance_to_color(0.5)
        far = DopplerEffect.distance_to_color(MAX_RENDER_DIST)
        # Warm channel of the far colour must be dimmer than the near one.
        assert far[0] <= near[0]


class TestFrequencyShift:
    def test_approaching_shifts_up(self):
        base = 440.0
        up = DopplerEffect.calculate_frequency_shift(10.0, 10.0, base_frequency=base)
        assert up > base

    def test_receding_shifts_down(self):
        base = 440.0
        down = DopplerEffect.calculate_frequency_shift(10.0, -10.0, base_frequency=base)
        assert down < base

    def test_monotonic_in_approach_speed(self):
        slow = DopplerEffect.calculate_frequency_shift(10.0, 1.0)
        fast = DopplerEffect.calculate_frequency_shift(10.0, 30.0)
        assert fast > slow > 440.0

    def test_stationary_no_shift(self):
        assert DopplerEffect.calculate_frequency_shift(10.0, 0.0) == 440.0


class TestMotionBlur:
    def test_stationary_velocity_no_throw(self):
        surf = pygame.Surface((32, 32))
        out = DopplerEffect.apply_motion_blur(surf, 0.0, 0.0)
        assert out is not None
        assert out.get_size() == (32, 32)

    def test_moving_velocity_no_throw(self):
        surf = pygame.Surface((32, 32))
        out = DopplerEffect.apply_motion_blur(surf, 0.5, 0.7)
        assert out is not None
        assert out.get_size() == (32, 32)

    def test_none_surface_is_safe(self):
        assert DopplerEffect.apply_motion_blur(None, 1.0, 0.0) is None
