"""Tests for the entity layer: ``Enemy``, ``Pickup`` and ``WorldMap.line_of_sight``.

Covers R2.1 - R2.3 of ``design/INCREMENTAL_PRD.md``:
  * enemy initial state / damage / death
  * enemy chase AI gated by perception range **and** line of sight
  * enemy contact damage with cooldown
  * pickup ``taken`` semantics and HEALTH / SCORE differentiation
  * grid line-of-sight queries

All maps are hand-built so every assertion is exact (no reliance on the
random maze generator).
"""
import math

import pytest

from doom_game.config import (
    ENEMY_CONTACT_COOLDOWN,
    ENEMY_CONTACT_DIST,
    ENEMY_DAMAGE,
    ENEMY_HP,
    ENEMY_PERCEPTION_RANGE,
    ENEMY_SPEED,
    HEALTH_PICKUP_AMOUNT,
    SCORE_PICKUP_AMOUNT,
)
from doom_game.core.entities import Enemy, EnemyType, Pickup, PickupType
from doom_game.core.player import Player
from doom_game.core.types import TextureType
from doom_game.core.world_map import WorldMap

FRAME = 1.0 / 60.0


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def make_map(width: int, height: int, walls=()) -> WorldMap:
    """Build an enclosed ``width`` x ``height`` room with optional inner walls.

    ``walls`` is an iterable of ``(gx, gy)`` cells set to BRICK.
    """
    wm = WorldMap(width, height)
    wm.cells = [
        [TextureType.STONE if (x in (0, width - 1) or y in (0, height - 1))
         else None
         for x in range(width)]
        for y in range(height)
    ]
    for gx, gy in walls:
        wm.cells[gy][gx] = TextureType.BRICK
    return wm


# --------------------------------------------------------------------------- #
# WorldMap.line_of_sight
# --------------------------------------------------------------------------- #
class TestLineOfSight:
    def test_clear_horizontal_line_is_visible(self):
        wm = make_map(9, 5)
        assert wm.line_of_sight(2.5, 2.5, 6.5, 2.5) is True

    def test_clear_diagonal_line_is_visible(self):
        wm = make_map(9, 7)
        assert wm.line_of_sight(1.5, 1.5, 5.5, 5.5) is True

    def test_wall_between_blocks_sight(self):
        wm = make_map(9, 5, walls=[(4, 2)])
        assert wm.line_of_sight(2.5, 2.5, 6.5, 2.5) is False

    def test_same_cell_endpoints_are_visible(self):
        wm = make_map(9, 5, walls=[(4, 2)])
        assert wm.line_of_sight(3.5, 2.5, 3.5, 2.5) is True

    def test_identical_points_inside_a_wall_still_visible(self):
        """Zero-length segments short-circuit to True (endpoints are skipped)."""
        wm = make_map(9, 5, walls=[(4, 2)])
        assert wm.line_of_sight(4.5, 2.5, 4.5, 2.5) is True

    def test_endpoints_are_not_sampled(self):
        """A caller standing flush against a wall is not falsely blocked."""
        wm = make_map(9, 5, walls=[(4, 2)])
        # Straight line along y=1.5 never crosses the wall cell (4, 2).
        assert wm.line_of_sight(1.5, 1.5, 7.5, 1.5) is True


# --------------------------------------------------------------------------- #
# Enemy - construction / health model
# --------------------------------------------------------------------------- #
class TestEnemyInitialState:
    def test_defaults_come_from_config(self):
        enemy = Enemy(3.5, 4.5)
        assert enemy.pos.x == pytest.approx(3.5)
        assert enemy.pos.y == pytest.approx(4.5)
        assert enemy.hp == pytest.approx(float(ENEMY_HP))
        assert enemy.damage == pytest.approx(float(ENEMY_DAMAGE))
        assert enemy.speed == pytest.approx(float(ENEMY_SPEED))
        assert enemy.type is EnemyType.BASIC
        assert enemy.state == "idle"
        assert enemy.alive is True

    def test_explicit_overrides_are_honoured(self):
        enemy = Enemy(1.0, 2.0, hp=55, damage=7, speed=0.5, angle=1.25,
                      type=EnemyType.BASIC)
        assert enemy.hp == pytest.approx(55.0)
        assert enemy.damage == pytest.approx(7.0)
        assert enemy.speed == pytest.approx(0.5)
        assert enemy.angle == pytest.approx(1.25)

    def test_repr_is_informative(self):
        assert "Enemy(" in repr(Enemy(1.5, 1.5))


class TestEnemyDamage:
    def test_partial_damage_keeps_enemy_alive(self):
        enemy = Enemy(1.5, 1.5, hp=30)
        enemy.take_damage(10)
        assert enemy.hp == pytest.approx(20.0)
        assert enemy.alive is True

    def test_lethal_damage_kills_and_clamps_hp_to_zero(self):
        enemy = Enemy(1.5, 1.5, hp=30)
        enemy.take_damage(45)
        assert enemy.hp == pytest.approx(0.0)
        assert enemy.alive is False

    def test_exactly_lethal_damage_kills(self):
        enemy = Enemy(1.5, 1.5, hp=30)
        enemy.take_damage(30)
        assert enemy.hp == pytest.approx(0.0)
        assert enemy.alive is False

    def test_dead_enemy_does_not_update(self):
        wm = make_map(9, 5)
        player = Player(6.5, 2.5)
        enemy = Enemy(2.5, 2.5)
        enemy.take_damage(ENEMY_HP)
        before = (enemy.pos.x, enemy.pos.y)
        assert enemy.update(player, wm, FRAME) == pytest.approx(0.0)
        assert (enemy.pos.x, enemy.pos.y) == before


# --------------------------------------------------------------------------- #
# Enemy - chase AI
# --------------------------------------------------------------------------- #
class TestEnemyChase:
    def test_chases_player_in_range_with_clear_sight(self):
        wm = make_map(9, 5)
        player = Player(6.5, 2.5)
        enemy = Enemy(2.5, 2.5, speed=ENEMY_SPEED)

        damage = enemy.update(player, wm, FRAME)

        assert enemy.state == "chasing"
        assert damage == pytest.approx(0.0)
        # Player is due east -> the enemy advances exactly one speed step in +x.
        assert enemy.pos.x == pytest.approx(2.5 + ENEMY_SPEED)
        assert enemy.pos.y == pytest.approx(2.5)
        assert enemy.angle == pytest.approx(0.0, abs=1e-9)

    def test_does_not_move_when_player_out_of_perception_range(self):
        wm = make_map(20, 5)
        player = Player(18.5, 2.5)
        enemy = Enemy(1.5, 2.5)
        assert player.pos.x - enemy.pos.x > ENEMY_PERCEPTION_RANGE

        enemy.update(player, wm, FRAME)

        assert enemy.state == "idle"
        assert enemy.pos.x == pytest.approx(1.5)
        assert enemy.pos.y == pytest.approx(2.5)

    def test_does_not_move_when_wall_blocks_line_of_sight(self):
        wm = make_map(9, 5, walls=[(4, 2)])
        player = Player(6.5, 2.5)
        enemy = Enemy(2.5, 2.5)
        assert player.pos.distance_to(enemy.pos) <= ENEMY_PERCEPTION_RANGE

        enemy.update(player, wm, FRAME)

        assert enemy.state == "idle"
        assert enemy.pos.x == pytest.approx(2.5)
        assert enemy.pos.y == pytest.approx(2.5)

    def test_chase_moves_diagonally_toward_player(self):
        wm = make_map(11, 11)
        player = Player(6.5, 6.5)
        enemy = Enemy(3.5, 3.5)

        enemy.update(player, wm, FRAME)

        step = ENEMY_SPEED / math.sqrt(2.0)
        assert enemy.pos.x == pytest.approx(3.5 + step)
        assert enemy.pos.y == pytest.approx(3.5 + step)
        assert enemy.state == "chasing"

    def test_chase_never_walks_through_a_wall(self):
        """A wall directly between the two blocks the x-axis step."""
        wm = make_map(9, 5, walls=[(4, 2)])
        player = Player(6.5, 2.5)
        enemy = Enemy(3.5, 2.5)
        enemy.state = "chasing"

        # Force many chase steps; the enemy must never enter the wall cell.
        for _ in range(200):
            enemy._chase(player, wm)
            assert not wm.is_wall(int(enemy.pos.x), int(enemy.pos.y))
        assert enemy.pos.x < 4.0

    def test_repeated_chase_steps_accumulate(self):
        wm = make_map(15, 5)
        player = Player(10.5, 2.5)
        enemy = Enemy(5.5, 2.5)
        for _ in range(3):
            enemy.update(player, wm, FRAME)
        assert enemy.pos.x == pytest.approx(5.5 + 3 * ENEMY_SPEED)


# --------------------------------------------------------------------------- #
# Enemy - contact damage / cooldown
# --------------------------------------------------------------------------- #
class TestEnemyContactDamage:
    def test_first_contact_deals_damage(self):
        wm = make_map(9, 5)
        player = Player(3.5, 2.5)
        enemy = Enemy(3.6, 2.5)
        assert enemy.pos.distance_to(player.pos) < ENEMY_CONTACT_DIST

        assert enemy.update(player, wm, FRAME) == pytest.approx(ENEMY_DAMAGE)

    def test_second_consecutive_frame_is_blocked_by_cooldown(self):
        wm = make_map(9, 5)
        player = Player(3.5, 2.5)
        enemy = Enemy(3.6, 2.5)

        first = enemy.update(player, wm, FRAME)
        second = enemy.update(player, wm, FRAME)
        third = enemy.update(player, wm, FRAME)

        assert first == pytest.approx(ENEMY_DAMAGE)
        assert second == pytest.approx(0.0)
        assert third == pytest.approx(0.0)

    def test_damage_resumes_after_cooldown_elapses(self):
        """The cooldown is decremented at the *start* of ``update``.

        So a frame that only partially drains it deals no damage, and the
        frame whose dt brings it to zero is free to hit again.
        """
        wm = make_map(9, 5)
        player = Player(3.5, 2.5)
        enemy = Enemy(3.6, 2.5)
        half = ENEMY_CONTACT_COOLDOWN / 2.0

        assert enemy.update(player, wm, FRAME) == pytest.approx(ENEMY_DAMAGE)
        # Half the cooldown burned -> still on cooldown.
        assert enemy.update(player, wm, half) == pytest.approx(0.0)
        # Remaining half burned -> the cooldown hits zero and damage resumes.
        assert enemy.update(player, wm, half) == pytest.approx(ENEMY_DAMAGE)

    def test_cooldown_is_not_ready_before_it_fully_elapses(self):
        wm = make_map(9, 5)
        player = Player(3.5, 2.5)
        enemy = Enemy(3.6, 2.5)

        assert enemy.update(player, wm, FRAME) == pytest.approx(ENEMY_DAMAGE)
        # 59 more nominal frames == just under one second of cooldown.
        hits = sum(1 for _ in range(59)
                   if enemy.update(player, wm, FRAME) > 0.0)
        assert hits == 0

    def test_enemy_in_contact_does_not_also_move(self):
        wm = make_map(9, 5)
        player = Player(3.5, 2.5)
        enemy = Enemy(3.6, 2.5)
        enemy.update(player, wm, FRAME)
        assert enemy.pos.x == pytest.approx(3.6)
        assert enemy.pos.y == pytest.approx(2.5)

    def test_no_damage_when_out_of_contact_distance(self):
        wm = make_map(9, 5)
        player = Player(6.5, 2.5)
        enemy = Enemy(2.5, 2.5)
        assert enemy.update(player, wm, FRAME) == pytest.approx(0.0)


# --------------------------------------------------------------------------- #
# Pickup
# --------------------------------------------------------------------------- #
class TestPickup:
    def test_health_pickup_defaults(self):
        pickup = Pickup(2.5, 3.5, PickupType.HEALTH)
        assert pickup.kind is PickupType.HEALTH
        assert pickup.amount == pytest.approx(float(HEALTH_PICKUP_AMOUNT))
        assert pickup.taken is False
        assert pickup.pos.x == pytest.approx(2.5)
        assert pickup.pos.y == pytest.approx(3.5)

    def test_score_pickup_defaults(self):
        pickup = Pickup(1.5, 1.5, PickupType.SCORE)
        assert pickup.kind is PickupType.SCORE
        assert pickup.amount == pytest.approx(float(SCORE_PICKUP_AMOUNT))
        assert pickup.taken is False

    def test_health_and_score_are_distinct_kinds(self):
        health = Pickup(1.5, 1.5, PickupType.HEALTH)
        score = Pickup(1.5, 1.5, PickupType.SCORE)
        assert health.kind is not score.kind
        assert PickupType.HEALTH.value == "health"
        assert PickupType.SCORE.value == "score"

    def test_explicit_amount_overrides_default(self):
        assert Pickup(1.5, 1.5, PickupType.HEALTH, amount=7).amount == \
            pytest.approx(7.0)

    def test_taken_flag_can_be_preset_and_toggled(self):
        pickup = Pickup(1.5, 1.5, PickupType.SCORE, taken=True)
        assert pickup.taken is True
        pickup.taken = False
        assert pickup.taken is False

    def test_repr_mentions_kind_and_taken(self):
        text = repr(Pickup(1.5, 1.5, PickupType.HEALTH))
        assert "health" in text and "taken" in text


# --------------------------------------------------------------------------- #
# Player health / score extension (R2.4)
# --------------------------------------------------------------------------- #
class TestPlayerHealthScoreFields:
    def test_player_spawns_at_full_health_with_zero_score(self):
        player = Player(1.5, 1.5)
        assert player.hp == pytest.approx(player.max_hp)
        assert player.score == pytest.approx(0.0)

    def test_explicit_hp_and_score_are_honoured(self):
        player = Player(1.5, 1.5, max_hp=80, hp=25, score=300)
        assert player.max_hp == pytest.approx(80.0)
        assert player.hp == pytest.approx(25.0)
        assert player.score == pytest.approx(300.0)

    def test_new_fields_are_trailing_keyword_arguments(self):
        """Legacy positional construction must keep working unchanged."""
        player = Player(2.0, 3.0, 0.5, 0.1, 0.02)
        assert player.speed == pytest.approx(0.1)
        assert player.rotate_speed == pytest.approx(0.02)
        assert player.hp == pytest.approx(player.max_hp)
