"""Unit tests for enemy ranged attacks (incremental PRD V2, A1-A6).

Covers the ``Projectile`` base type (A1), the ``Enemy.try_fire`` firing
condition matrix (A2), the cooldown rate limit (A3), the three projectile
death paths (A4), rendering hooks (A5) and config constants (A6).
"""
import math

import pytest

import doom_game.config as config
from doom_game.config import (
    ENEMY_ATTACK_COOLDOWN,
    ENEMY_ATTACK_RANGE,
    ENEMY_PERCEPTION_RANGE,
    ENEMY_SPEED,
    FRAME_DT,
    PLAYER_MAX_HP,
    PROJECTILE_COLOR,
    PROJECTILE_DAMAGE,
    PROJECTILE_HIT_DIST,
    PROJECTILE_MAX_DIST,
    PROJECTILE_SPEED,
)
from doom_game.core.entities import Enemy, Projectile
from doom_game.core.player import Player
from doom_game.core.types import TextureType
from doom_game.core.world_map import WorldMap
from doom_game.world.game_world import GameWorld

LEVEL_01 = "G:/loly/maps/level_01.json"
ROOM_SIZE = 13          # stone border at 0 / 12, open interior 1..11


def make_room(size: int = ROOM_SIZE) -> WorldMap:
    """A fully enclosed square room with an empty interior."""
    wm = WorldMap(size, size)
    wm.cells = [
        [TextureType.STONE if (x in (0, size - 1) or y in (0, size - 1))
         else None for x in range(size)]
        for y in range(size)
    ]
    return wm


@pytest.fixture
def room():
    return make_room()


def make_static_enemy(x, y, **kwargs):
    """An enemy that never moves so distances stay exact in tests."""
    enemy = Enemy(x, y, **kwargs)
    enemy.speed = 0.0
    return enemy


# --------------------------------------------------------------------------- #
# A1: Projectile base type
# --------------------------------------------------------------------------- #
class TestProjectileConstruction:
    def test_importable_from_core_entities(self):
        from doom_game.core.entities import Projectile as P
        assert P is Projectile

    def test_new_projectile_is_alive_with_config_defaults(self):
        p = Projectile(2.0, 3.0, 1.0, 0.0)
        assert p.alive is True
        assert p.pos.x == pytest.approx(2.0)
        assert p.pos.y == pytest.approx(3.0)
        assert p.speed == pytest.approx(PROJECTILE_SPEED)
        assert p.damage == pytest.approx(PROJECTILE_DAMAGE)
        assert p.max_dist == pytest.approx(PROJECTILE_MAX_DIST)
        assert p.traveled == pytest.approx(0.0)

    def test_direction_is_normalised(self):
        p = Projectile(0.0, 0.0, 3.0, 4.0)
        assert p.vx == pytest.approx(0.6)
        assert p.vy == pytest.approx(0.8)
        assert math.hypot(p.vx, p.vy) == pytest.approx(1.0)

    def test_degenerate_direction_defaults_to_plus_x(self):
        p = Projectile(1.0, 1.0, 0.0, 0.0)
        assert (p.vx, p.vy) == (1.0, 0.0)
        assert p.alive is True


# --------------------------------------------------------------------------- #
# A2: try_fire condition matrix
# --------------------------------------------------------------------------- #
class TestTryFireConditions:
    def test_fires_when_in_range_with_los_and_cooldown_ready(self, room):
        enemy = make_static_enemy(3.5, 6.5)
        player = Player(6.5, 6.5)                    # distance 3.0 < range 5
        enemy.update(player, room, FRAME_DT)
        assert enemy.state == "chasing"

        projectile = enemy.try_fire(player, room)
        assert isinstance(projectile, Projectile)
        # Direction frozen at fire time: straight toward the player (+x).
        assert projectile.vx == pytest.approx(1.0)
        assert projectile.vy == pytest.approx(0.0, abs=1e-9)

    def test_exactly_one_shot_within_cooldown_window(self, room):
        enemy = make_static_enemy(3.5, 6.5)
        player = Player(6.5, 6.5)
        enemy.update(player, room, FRAME_DT)

        first = enemy.try_fire(player, room)
        second = enemy.try_fire(player, room)        # same cooldown window
        assert first is not None
        assert second is None

    def test_no_fire_when_los_blocked_by_wall(self, room):
        room.cells[6][5] = TextureType.STONE         # wall on the segment
        enemy = make_static_enemy(3.5, 6.5)
        player = Player(6.5, 6.5)
        enemy.update(player, room, FRAME_DT)

        assert enemy.state == "idle"                 # perception needs LOS
        assert enemy.try_fire(player, room) is None
        # Even with a forced chasing state, the second LOS check refuses.
        enemy.state = "chasing"
        assert enemy.try_fire(player, room) is None

    def test_no_fire_beyond_attack_range(self, room):
        enemy = make_static_enemy(3.5, 6.5)
        player = Player(9.0, 6.5)                    # 5.5 > ATTACK_RANGE 5.0
        assert (enemy.pos.distance_to(player.pos)
                <= ENEMY_PERCEPTION_RANGE)
        enemy.update(player, room, FRAME_DT)

        assert enemy.state == "chasing"              # sees, but out of range
        assert enemy.try_fire(player, room) is None

    def test_no_fire_while_cooldown_not_ready(self, room):
        enemy = make_static_enemy(3.5, 6.5)
        player = Player(6.5, 6.5)
        enemy.update(player, room, FRAME_DT)
        enemy._attack_cd = 1.0
        assert enemy.try_fire(player, room) is None

    def test_no_fire_when_idle_or_dead(self, room):
        enemy = make_static_enemy(3.5, 6.5)
        player = Player(6.5, 6.5)
        enemy.state = "idle"
        assert enemy.try_fire(player, room) is None
        enemy.state = "chasing"
        enemy.alive = False
        assert enemy.try_fire(player, room) is None

    def test_per_enemy_attack_range_override_a7(self, room):
        enemy = make_static_enemy(3.5, 6.5, attack_range=2.0)
        player = Player(6.5, 6.5)                    # distance 3.0 > 2.0
        enemy.update(player, room, FRAME_DT)
        assert enemy.state == "chasing"
        assert enemy.try_fire(player, room) is None


# --------------------------------------------------------------------------- #
# A3: cooldown rate limit over a 3-second simulation
# --------------------------------------------------------------------------- #
class TestCooldownRate:
    def test_shots_within_three_seconds_bounded_by_cooldown(self, room):
        enemy = make_static_enemy(3.5, 6.5)
        player = Player(6.5, 6.5)
        frames = int(round(3.0 / FRAME_DT))          # 180 frames = 3 seconds
        fired = 0
        for _ in range(frames):
            enemy.update(player, room, FRAME_DT)
            if enemy.try_fire(player, room) is not None:
                fired += 1
        limit = math.ceil(3.0 / ENEMY_ATTACK_COOLDOWN)
        assert fired <= limit
        assert fired == 2                            # t=0 and t=1.5s


# --------------------------------------------------------------------------- #
# A4: the three death paths
# --------------------------------------------------------------------------- #
class TestProjectileDeathPaths:
    def test_player_hit_reports_damage_once_and_dies(self, room):
        player = Player(5.5, 6.5)
        p = Projectile(5.0, 6.5, 1.0, 0.0)
        damage = p.update(room, player, FRAME_DT)    # moves to x=5.15
        assert damage == pytest.approx(PROJECTILE_DAMAGE)
        assert p.alive is False
        # A dead projectile never reports damage again.
        assert p.update(room, player, FRAME_DT) == pytest.approx(0.0)

    def test_wall_impact_dies_with_zero_damage(self, room):
        player = Player(2.5, 2.5)                    # far away from the path
        p = Projectile(10.5, 6.5, 1.0, 0.0)          # heading into x=12 wall
        total = 0.0
        for _ in range(60):
            total += p.update(room, player, FRAME_DT)
            if not p.alive:
                break
        assert p.alive is False
        assert total == pytest.approx(0.0)
        assert p.traveled < PROJECTILE_MAX_DIST      # died on the wall

    def test_max_distance_expiry_in_open_space(self, room):
        player = Player(2.5, 1.5)                    # off the flight line
        p = Projectile(1.5, 6.5, 1.0, 0.0)           # open run, no wall hit
        total = 0.0
        for _ in range(120):
            total += p.update(room, player, FRAME_DT)
            if not p.alive:
                break
        assert p.alive is False
        assert total == pytest.approx(0.0)
        assert p.traveled >= PROJECTILE_MAX_DIST
        assert not room.is_wall(int(p.pos.x), int(p.pos.y))

    def test_game_world_applies_hit_damage_once_and_filters(self):
        gw = GameWorld(map_path=LEVEL_01)
        gw.audio.enabled = False
        try:
            gw.world_map = make_room()
            gw.enemies = []
            gw.player.pos.x, gw.player.pos.y = 5.5, 6.5
            gw.player.hp = float(PLAYER_MAX_HP)
            p = Projectile(5.0, 6.5, 1.0, 0.0)
            gw.projectiles = [p]

            gw._update_projectiles(FRAME_DT)

            expected = float(PLAYER_MAX_HP) - PROJECTILE_DAMAGE
            assert gw.player.hp == pytest.approx(expected)
            assert p.alive is False
            assert gw.projectiles == []              # no leak (A4)
            gw._update_projectiles(FRAME_DT)         # no double damage
            assert gw.player.hp == pytest.approx(expected)
        finally:
            gw.cleanup()


# --------------------------------------------------------------------------- #
# A5: rendering hooks / A6: config constants
# --------------------------------------------------------------------------- #
class TestRenderingAndConfig:
    @pytest.mark.parametrize("name", [
        "ENEMY_ATTACK_RANGE", "ENEMY_ATTACK_COOLDOWN", "PROJECTILE_SPEED",
        "PROJECTILE_DAMAGE", "PROJECTILE_HIT_DIST", "PROJECTILE_MAX_DIST",
        "PROJECTILE_COLOR",
    ])
    def test_config_constant_exists(self, name):
        assert hasattr(config, name)

    def test_balance_relations_hold(self):
        assert ENEMY_ATTACK_RANGE <= ENEMY_PERCEPTION_RANGE
        assert PROJECTILE_SPEED > ENEMY_SPEED
        assert 0.0 < PROJECTILE_HIT_DIST < PROJECTILE_MAX_DIST

    def test_renderer_and_hud_reference_projectile_color(self):
        import doom_game.render.renderer as renderer_mod
        from doom_game.world.hud import HUD
        assert renderer_mod.PROJECTILE_COLOR == PROJECTILE_COLOR
        assert tuple(HUD.PROJECTILE_DOT_COLOR) == tuple(PROJECTILE_COLOR)

    def test_render_sprites_with_projectile_does_not_crash(
            self, display, small_renderer, room):
        player = Player(2.5, 6.5, angle=0.0)
        enemy = make_static_enemy(6.5, 6.5)
        p = Projectile(4.5, 6.5, 1.0, 0.0)
        small_renderer.render_sprites(player, room, [enemy], [],
                                      projectiles=[p])
        dead = Projectile(4.5, 6.5, 1.0, 0.0)
        dead.alive = False                           # dead ones are skipped
        small_renderer.render_sprites(player, room, [], [],
                                      projectiles=[dead])

    def test_game_world_render_with_projectile_in_flight(self, display):
        gw = GameWorld(map_path=LEVEL_01)
        gw.audio.enabled = False
        try:
            gw.projectiles.append(
                Projectile(gw.player.pos.x + 1.0, gw.player.pos.y, 1.0, 0.0))
            gw.render(display)                       # 3D + minimap dot (A5)
        finally:
            gw.cleanup()
