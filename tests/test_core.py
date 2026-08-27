"""Unit tests for the core types: Vector2, WorldMap, Player.

All checks are numerical / behavioural and run with the real pygame import
(pygame-ce falls back to ``pygame``). No stubs.
"""
import math

import pytest

from doom_game.core.types import Vector2, TextureType
from doom_game.core.world_map import WorldMap
from doom_game.core.player import Player


# --------------------------------------------------------------------------- #
# Vector2
# --------------------------------------------------------------------------- #
class TestVector2:
    def test_rotate_90_degrees_about_origin(self):
        v = Vector2(1.0, 0.0).rotate(math.pi / 2.0)
        assert pytest.approx(v.x, abs=1e-9) == 0.0
        assert pytest.approx(v.y, abs=1e-9) == 1.0

    def test_rotate_180_degrees(self):
        v = Vector2(1.0, 0.0).rotate(math.pi)
        assert pytest.approx(v.x, abs=1e-9) == -1.0
        assert pytest.approx(v.y, abs=1e-9) == 0.0

    def test_rotate_preserves_magnitude(self):
        v = Vector2(3.0, 4.0)
        r = v.rotate(0.37)
        assert pytest.approx(r.distance_to(Vector2(0.0, 0.0))) == 5.0

    def test_translate(self):
        v = Vector2(1.0, 2.0).translate(3.0, 4.0)
        assert pytest.approx(v.x) == 4.0
        assert pytest.approx(v.y) == 6.0

    def test_distance_to(self):
        assert pytest.approx(Vector2(0.0, 0.0).distance_to(Vector2(3.0, 4.0))) == 5.0

    def test_copy_is_independent(self):
        v = Vector2(1.0, 2.0)
        c = v.copy()
        assert c.to_tuple() == (1.0, 2.0)
        c.x = 99.0
        assert v.x == 1.0  # original unchanged

    def test_to_tuple(self):
        assert Vector2(1.5, 2.5).to_tuple() == (1.5, 2.5)


# --------------------------------------------------------------------------- #
# WorldMap
# --------------------------------------------------------------------------- #
class TestWorldMap:
    def test_generate_maze_boundary_walls(self):
        wm = WorldMap()
        wm.generate_maze(24, 24, seed=42)
        # Corners and edges must be walls.
        assert wm.is_wall(0, 0) is True
        assert wm.is_wall(23, 23) is True
        assert wm.is_wall(0, 23) is True
        assert wm.is_wall(23, 0) is True
        # Boundary texture is STONE.
        assert wm.get_texture(0, 0) == TextureType.STONE

    def test_generate_maze_interior_has_open_cells(self):
        wm = WorldMap()
        wm.generate_maze(24, 24, seed=42)
        open_cells = sum(
            1 for y in range(wm.height) for x in range(wm.width)
            if not wm.is_wall(x, y)
        )
        # A 24x24 maze must leave the interior walkable.
        assert open_cells > 0

    def test_is_wall_out_of_bounds_treated_as_wall(self):
        wm = WorldMap()
        wm.generate_maze(10, 10, seed=1)
        assert wm.is_wall(-1, 5) is True
        assert wm.is_wall(5, -1) is True
        assert wm.is_wall(10, 5) is True
        assert wm.is_wall(5, 10) is True

    def test_get_texture_returns_none_for_open_cell(self):
        wm = WorldMap()
        wm.generate_maze(24, 24, seed=42)
        spawn = wm.find_open_cell()
        assert wm.get_texture(spawn[0], spawn[1]) is None

    def test_player_spawn_not_in_wall(self):
        wm = WorldMap()
        wm.generate_maze(24, 24, seed=42)
        spawn = wm.find_open_cell()
        assert not wm.is_wall(spawn[0], spawn[1])

    def test_collision_query_is_o1_direct_indexing(self):
        """is_wall / get_texture must read ``cells[gy][gx]`` directly."""
        wm = WorldMap()
        wm.generate_maze(24, 24, seed=42)
        gx, gy = 5, 7
        # The returned object identity proves a direct grid lookup (no list
        # traversal / no transformation).
        assert wm.get_texture(gx, gy) is wm.cells[gy][gx]
        assert wm.is_wall(gx, gy) == (wm.cells[gy][gx] is not None)

    def test_generate_maze_is_deterministic_with_seed(self):
        a = WorldMap()
        a.generate_maze(16, 16, seed=7)
        b = WorldMap()
        b.generate_maze(16, 16, seed=7)
        assert a.cells == b.cells


# --------------------------------------------------------------------------- #
# Player
# --------------------------------------------------------------------------- #
class TestPlayer:
    def test_move_forward_changes_position_along_facing(self):
        p = Player(0.0, 0.0, angle=0.0, speed=0.1)
        p.move(forward=1.0, strafe=0.0)
        # Facing +x -> position moves +0.1 on x, unchanged on y.
        assert pytest.approx(p.pos.x) == 0.1
        assert pytest.approx(p.pos.y) == 0.0

    def test_move_strafe_changes_position_perpendicular(self):
        p = Player(0.0, 0.0, angle=0.0, speed=0.1)
        p.move(forward=0.0, strafe=1.0)
        # Strafe is +90deg (perp) -> moves +0.1 on y.
        assert pytest.approx(p.pos.x) == 0.0
        assert pytest.approx(p.pos.y) == 0.1

    def test_move_magnitude_equals_speed(self):
        p = Player(0.0, 0.0, angle=0.0, speed=0.1)
        p.move(forward=1.0, strafe=0.0)
        assert pytest.approx(p.get_speed()) == 0.1

    def test_move_forward_at_90_degrees(self):
        p = Player(0.0, 0.0, angle=math.pi / 2.0, speed=0.2)
        p.move(forward=1.0, strafe=0.0)
        # Facing +y -> moves +0.2 on y.
        assert pytest.approx(p.pos.x, abs=1e-9) == 0.0
        assert pytest.approx(p.pos.y) == 0.2

    def test_rotate_changes_angle_in_radians(self):
        p = Player(0.0, 0.0, angle=0.0, rotate_speed=0.05)
        p.rotate(direction=1.0)
        assert pytest.approx(p.angle) == 0.05

    def test_rotate_wraps_into_zero_to_2pi(self):
        p = Player(0.0, 0.0, angle=2 * math.pi - 0.01, rotate_speed=0.05)
        p.rotate(direction=1.0)  # 2pi - 0.01 + 0.05 = 2pi + 0.04
        assert 0.0 <= p.angle < 2 * math.pi
        assert pytest.approx(p.angle) == 0.04

    def test_get_speed_zero_when_stationary(self):
        p = Player(0.0, 0.0, speed=0.1)
        assert pytest.approx(p.get_speed()) == 0.0
