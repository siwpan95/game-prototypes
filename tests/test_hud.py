"""Tests for the HUD overlay additions (R2.7 minimap markers, R2.8 HP/score/death).

Everything is drawn onto a real ``pygame.Surface`` under
``SDL_VIDEODRIVER=dummy``; assertions are made on actual pixels rather than on
mocks, so a silently-not-drawing HUD would be caught.
"""
import numpy as np
import pytest

try:
    import pygame_ce as pygame
except ImportError:  # pragma: no cover
    import pygame

from doom_game.config import PLAYER_MAX_HP, SCREEN_HEIGHT, SCREEN_WIDTH
from doom_game.core.entities import Enemy, Pickup, PickupType
from doom_game.core.player import Player
from doom_game.core.types import TextureType
from doom_game.core.world_map import WorldMap
from doom_game.world.hud import HUD

# A pixel inside the *filled* part of the HP bar even at low ratios.
# The bar starts at x=10 with a 1px border and is at least 120px wide, so at
# 5% health the fill still covers x=11..19 -> x=12 is always inside it.
HP_BAR_PROBE = (12, SCREEN_HEIGHT - 160)


@pytest.fixture
def hud():
    return HUD()


@pytest.fixture
def surface():
    return pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))


def snapshot(surf):
    return pygame.surfarray.array3d(surf).copy()


def changed(surf, before):
    return not np.array_equal(before, pygame.surfarray.array3d(surf))


class _FakeWorld:
    """Minimal ``GameWorld`` stand-in for ``render_minimap``."""

    def __init__(self, world_map, enemies=None, pickups=None):
        self.world_map = world_map
        self.enemies = enemies if enemies is not None else []
        self.pickups = pickups if pickups is not None else []


@pytest.fixture
def fake_world():
    wm = WorldMap(8, 8)
    wm.cells = [
        [TextureType.STONE if (x in (0, 7) or y in (0, 7)) else None
         for x in range(8)]
        for y in range(8)
    ]
    return _FakeWorld(wm)


# --------------------------------------------------------------------------- #
# HP bar
# --------------------------------------------------------------------------- #
class TestRenderHpBar:
    def test_draws_without_raising(self, hud, surface):
        hud.render_hp_bar(surface, Player(1.5, 1.5))

    def test_draws_visible_pixels(self, hud, surface):
        before = snapshot(surface)
        hud.render_hp_bar(surface, Player(1.5, 1.5))
        assert changed(surface, before)

    def test_threshold_colours_are_distinct(self):
        colours = {HUD.HP_COLOR_HIGH, HUD.HP_COLOR_MID, HUD.HP_COLOR_LOW}
        assert len(colours) == 3

    @pytest.mark.parametrize("hp, expected", [
        (100.0, HUD.HP_COLOR_HIGH),   # 100% -> green
        (80.0, HUD.HP_COLOR_HIGH),    # 80%  -> green
        (60.0, HUD.HP_COLOR_MID),     # 60%  -> yellow (boundary)
        (45.0, HUD.HP_COLOR_MID),     # 45%  -> yellow
        (30.0, HUD.HP_COLOR_MID),     # 30%  -> yellow (boundary)
        (25.0, HUD.HP_COLOR_LOW),     # 25%  -> red
        (5.0, HUD.HP_COLOR_LOW),      # 5%   -> red
    ])
    def test_fill_colour_matches_ratio_band(self, hud, hp, expected):
        surf = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
        hud.render_hp_bar(surf, Player(1.5, 1.5, max_hp=100, hp=hp))
        assert surf.get_at(HP_BAR_PROBE)[:3] == expected

    def test_zero_hp_draws_empty_bar_background(self, hud, surface):
        hud.render_hp_bar(surface, Player(1.5, 1.5, max_hp=100, hp=0))
        # No fill is drawn at 0 hp -> the probe shows the dark backdrop.
        assert surface.get_at(HP_BAR_PROBE)[:3] == (40, 40, 40)

    def test_hp_above_max_is_clamped(self, hud, surface):
        hud.render_hp_bar(surface, Player(1.5, 1.5, max_hp=100, hp=500))
        assert surface.get_at(HP_BAR_PROBE)[:3] == HUD.HP_COLOR_HIGH

    def test_negative_hp_does_not_raise(self, hud, surface):
        hud.render_hp_bar(surface, Player(1.5, 1.5, max_hp=100, hp=-40))

    def test_zero_max_hp_does_not_divide_by_zero(self, hud, surface):
        hud.render_hp_bar(surface, Player(1.5, 1.5, max_hp=0, hp=0))

    def test_none_surface_is_a_noop(self, hud):
        hud.render_hp_bar(None, Player(1.5, 1.5))

    def test_none_player_is_a_noop(self, hud, surface):
        before = snapshot(surface)
        hud.render_hp_bar(surface, None)
        assert not changed(surface, before)


# --------------------------------------------------------------------------- #
# Score
# --------------------------------------------------------------------------- #
class TestRenderScore:
    def test_draws_without_raising(self, hud, surface):
        hud.render_score(surface, Player(1.5, 1.5, score=1234))

    def test_zero_score_does_not_raise(self, hud, surface):
        hud.render_score(surface, Player(1.5, 1.5, score=0))

    def test_large_and_fractional_scores_do_not_raise(self, hud, surface):
        hud.render_score(surface, Player(1.5, 1.5, score=987654.4))

    def test_none_surface_is_a_noop(self, hud):
        hud.render_score(None, Player(1.5, 1.5))

    def test_none_player_is_a_noop(self, hud, surface):
        before = snapshot(surface)
        hud.render_score(surface, None)
        assert not changed(surface, before)


# --------------------------------------------------------------------------- #
# Death overlay
# --------------------------------------------------------------------------- #
class TestRenderDeath:
    def test_alive_player_draws_nothing(self, hud, surface):
        before = snapshot(surface)
        hud.render_death(surface, Player(1.5, 1.5, max_hp=100, hp=100))
        assert not changed(surface, before)

    def test_barely_alive_player_draws_nothing(self, hud, surface):
        before = snapshot(surface)
        hud.render_death(surface, Player(1.5, 1.5, max_hp=100, hp=1))
        assert not changed(surface, before)

    def test_dead_player_draws_overlay(self, hud, surface):
        before = snapshot(surface)
        hud.render_death(surface, Player(1.5, 1.5, max_hp=100, hp=0))
        assert changed(surface, before)

    def test_negative_hp_also_draws_overlay(self, hud, surface):
        before = snapshot(surface)
        hud.render_death(surface, Player(1.5, 1.5, max_hp=100, hp=-10))
        assert changed(surface, before)

    def test_none_surface_is_a_noop(self, hud):
        hud.render_death(None, Player(1.5, 1.5, hp=0))

    def test_none_player_is_a_noop(self, hud, surface):
        before = snapshot(surface)
        hud.render_death(surface, None)
        assert not changed(surface, before)


# --------------------------------------------------------------------------- #
# Minimap entity markers
# --------------------------------------------------------------------------- #
class TestRenderMinimapMarkers:
    def test_marker_colours_are_distinct(self):
        colours = {HUD.ENEMY_DOT_COLOR, HUD.HEALTH_DOT_COLOR,
                   HUD.SCORE_DOT_COLOR}
        assert len(colours) == 3

    def test_renders_with_no_entities(self, hud, surface, fake_world):
        hud.render_minimap(surface, fake_world, Player(1.5, 1.5))

    def test_renders_with_enemies_and_pickups(self, hud, surface, fake_world):
        fake_world.enemies = [Enemy(2.5, 2.5), Enemy(5.5, 3.5)]
        fake_world.pickups = [Pickup(3.5, 4.5, PickupType.HEALTH),
                              Pickup(4.5, 5.5, PickupType.SCORE)]
        hud.render_minimap(surface, fake_world, Player(1.5, 1.5))

    def test_enemy_dot_is_drawn(self, hud, surface, fake_world):
        base = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
        hud.render_minimap(base, fake_world, Player(1.5, 1.5))
        reference = snapshot(base)

        fake_world.enemies = [Enemy(3.5, 3.5)]
        hud.render_minimap(surface, fake_world, Player(1.5, 1.5))

        assert not np.array_equal(reference,
                                  pygame.surfarray.array3d(surface))

    def test_dead_enemy_marker_is_skipped(self, hud, fake_world):
        alive_surf = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
        dead_surf = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
        player = Player(1.5, 1.5)

        hud.render_minimap(alive_surf, fake_world, player)   # no entities
        dead = Enemy(3.5, 3.5)
        dead.take_damage(dead.hp)
        fake_world.enemies = [dead]
        hud.render_minimap(dead_surf, fake_world, player)

        assert np.array_equal(pygame.surfarray.array3d(alive_surf),
                              pygame.surfarray.array3d(dead_surf))

    def test_taken_pickup_marker_is_skipped(self, hud, fake_world):
        clean = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
        with_taken = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
        player = Player(1.5, 1.5)

        hud.render_minimap(clean, fake_world, player)
        fake_world.pickups = [Pickup(3.5, 3.5, PickupType.HEALTH, taken=True)]
        hud.render_minimap(with_taken, fake_world, player)

        assert np.array_equal(pygame.surfarray.array3d(clean),
                              pygame.surfarray.array3d(with_taken))

    def test_health_and_score_markers_differ_visually(self, hud, fake_world):
        health_surf = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
        score_surf = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
        player = Player(1.5, 1.5)

        fake_world.pickups = [Pickup(3.5, 3.5, PickupType.HEALTH)]
        hud.render_minimap(health_surf, fake_world, player)
        fake_world.pickups = [Pickup(3.5, 3.5, PickupType.SCORE)]
        hud.render_minimap(score_surf, fake_world, player)

        assert not np.array_equal(pygame.surfarray.array3d(health_surf),
                                  pygame.surfarray.array3d(score_surf))

    def test_none_surface_is_a_noop(self, hud, fake_world):
        hud.render_minimap(None, fake_world, Player(1.5, 1.5))

    def test_world_without_entity_attributes_still_renders(self, hud, surface,
                                                           fake_world):
        """``getattr(..., None) or []`` must tolerate a bare world object."""
        del fake_world.enemies
        del fake_world.pickups
        hud.render_minimap(surface, fake_world, Player(1.5, 1.5))


# --------------------------------------------------------------------------- #
# Combined HUD pass (mirrors GameWorld.render ordering)
# --------------------------------------------------------------------------- #
class TestFullHudPass:
    def test_full_overlay_for_a_living_player(self, hud, surface, fake_world):
        player = Player(1.5, 1.5, max_hp=PLAYER_MAX_HP, hp=55, score=250)
        fake_world.enemies = [Enemy(2.5, 2.5)]
        fake_world.pickups = [Pickup(4.5, 4.5, PickupType.HEALTH)]

        hud.render_minimap(surface, fake_world, player)
        hud.render_hp_bar(surface, player)
        hud.render_score(surface, player)
        hud.render_death(surface, player)

        assert surface.get_at(HP_BAR_PROBE)[:3] == HUD.HP_COLOR_MID

    def test_full_overlay_for_a_dead_player(self, hud, surface, fake_world):
        player = Player(1.5, 1.5, max_hp=PLAYER_MAX_HP, hp=0, score=0)
        before = snapshot(surface)

        hud.render_minimap(surface, fake_world, player)
        hud.render_hp_bar(surface, player)
        hud.render_score(surface, player)
        hud.render_death(surface, player)

        assert changed(surface, before)
