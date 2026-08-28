"""Integration tests for entity handling inside ``GameWorld.update``.

Covers R2.4 - R2.6: pickup collection, enemy contact damage with cooldown,
level-file loading and the maze-mode fallback.

``keys`` is simulated with ``collections.defaultdict(bool)`` because the real
``pygame.key.get_pressed()`` result (``ScancodeWrapper``) only supports
subscript access (``keys[K_w]``) - it has no ``.get()``.
"""
import collections
import os

import pytest

from doom_game.config import (
    DEFAULT_MAP_DIR,
    DEFAULT_MAP_PATH,
    ENEMY_DAMAGE,
    HEALTH_PICKUP_AMOUNT,
    PICKUP_CONTACT_DIST,
    PLAYER_MAX_HP,
    SCORE_PICKUP_AMOUNT,
)
from doom_game.core.entities import Enemy, Pickup, PickupType
from doom_game.world.game_world import GameWorld

LEVEL_01 = DEFAULT_MAP_PATH


@pytest.fixture
def no_keys():
    """A ``ScancodeWrapper``-like object where no key is pressed."""
    return collections.defaultdict(bool)


@pytest.fixture
def world():
    """A maze-mode ``GameWorld`` with audio forced off (headless safety)."""
    gw = GameWorld()
    gw.audio.enabled = False
    yield gw
    gw.cleanup()


def _place_player(gw, x, y):
    gw.player.pos.x = float(x)
    gw.player.pos.y = float(y)


# --------------------------------------------------------------------------- #
# Maze mode keeps the legacy behaviour
# --------------------------------------------------------------------------- #
class TestMazeModeUnchanged:
    def test_maze_mode_has_no_entities(self, world):
        assert world.enemies == []
        assert world.pickups == []

    def test_update_without_entities_does_not_change_health(self, world,
                                                            no_keys):
        world.update(no_keys)
        assert world.player.hp == pytest.approx(float(PLAYER_MAX_HP))
        assert world.player.score == pytest.approx(0.0)

    def test_player_spawns_with_full_health(self, world):
        assert world.player.hp == pytest.approx(float(PLAYER_MAX_HP))
        assert world.player.max_hp == pytest.approx(float(PLAYER_MAX_HP))


# --------------------------------------------------------------------------- #
# Pickups
# --------------------------------------------------------------------------- #
class TestPickupCollection:
    def test_health_pickup_restores_hp_and_is_marked_taken(self, world,
                                                           no_keys):
        _place_player(world, 3.5, 3.5)
        world.player.hp = 50.0
        pickup = Pickup(3.5, 3.5, PickupType.HEALTH)
        world.pickups = [pickup]

        world.update(no_keys)

        assert world.player.hp == pytest.approx(50.0 + HEALTH_PICKUP_AMOUNT)
        assert pickup.taken is True

    def test_health_pickup_never_exceeds_max_hp(self, world, no_keys):
        _place_player(world, 3.5, 3.5)
        world.player.hp = float(PLAYER_MAX_HP) - 1.0
        world.pickups = [Pickup(3.5, 3.5, PickupType.HEALTH)]

        world.update(no_keys)

        assert world.player.hp == pytest.approx(float(PLAYER_MAX_HP))

    def test_score_pickup_increases_score_and_is_marked_taken(self, world,
                                                              no_keys):
        _place_player(world, 3.5, 3.5)
        pickup = Pickup(3.5, 3.5, PickupType.SCORE)
        world.pickups = [pickup]

        world.update(no_keys)

        assert world.player.score == pytest.approx(float(SCORE_PICKUP_AMOUNT))
        assert pickup.taken is True

    def test_score_pickup_does_not_change_hp(self, world, no_keys):
        _place_player(world, 3.5, 3.5)
        world.player.hp = 40.0
        world.pickups = [Pickup(3.5, 3.5, PickupType.SCORE)]

        world.update(no_keys)

        assert world.player.hp == pytest.approx(40.0)

    def test_distant_pickup_is_not_collected(self, world, no_keys):
        _place_player(world, 3.5, 3.5)
        far = Pickup(3.5 + PICKUP_CONTACT_DIST + 0.5, 3.5, PickupType.HEALTH)
        world.player.hp = 10.0
        world.pickups = [far]

        world.update(no_keys)

        assert far.taken is False
        assert world.player.hp == pytest.approx(10.0)

    def test_already_taken_pickup_is_not_collected_twice(self, world, no_keys):
        _place_player(world, 3.5, 3.5)
        world.player.hp = 10.0
        world.pickups = [Pickup(3.5, 3.5, PickupType.HEALTH, taken=True)]

        world.update(no_keys)

        assert world.player.hp == pytest.approx(10.0)

    def test_health_and_score_pickups_collected_in_the_same_frame(self, world,
                                                                  no_keys):
        _place_player(world, 3.5, 3.5)
        world.player.hp = 50.0
        health = Pickup(3.5, 3.5, PickupType.HEALTH)
        score = Pickup(3.6, 3.5, PickupType.SCORE)
        world.pickups = [health, score]

        world.update(no_keys)

        assert world.player.hp == pytest.approx(50.0 + HEALTH_PICKUP_AMOUNT)
        assert world.player.score == pytest.approx(float(SCORE_PICKUP_AMOUNT))
        assert health.taken is True and score.taken is True


# --------------------------------------------------------------------------- #
# Enemy contact damage through GameWorld.update
# --------------------------------------------------------------------------- #
class TestEnemyContactThroughUpdate:
    def test_adjacent_enemy_damages_the_player(self, world, no_keys):
        _place_player(world, 3.5, 3.5)
        world.enemies = [Enemy(3.6, 3.5)]

        world.update(no_keys)

        assert world.player.hp == pytest.approx(
            float(PLAYER_MAX_HP) - ENEMY_DAMAGE)

    def test_contact_cooldown_prevents_double_hit_on_consecutive_frames(
            self, world, no_keys):
        _place_player(world, 3.5, 3.5)
        world.enemies = [Enemy(3.6, 3.5)]

        world.update(no_keys)
        hp_after_first = world.player.hp
        world.update(no_keys)
        hp_after_second = world.player.hp

        assert hp_after_first == pytest.approx(
            float(PLAYER_MAX_HP) - ENEMY_DAMAGE)
        assert hp_after_second == pytest.approx(hp_after_first)

    def test_many_frames_do_not_drain_health_instantly(self, world, no_keys):
        """60 frames == 1 second of nominal dt -> at most two contact hits."""
        _place_player(world, 3.5, 3.5)
        world.enemies = [Enemy(3.6, 3.5)]

        for _ in range(60):
            world.update(no_keys)

        lost = float(PLAYER_MAX_HP) - world.player.hp
        assert lost <= 2 * ENEMY_DAMAGE

    def test_hp_is_clamped_at_zero(self, world, no_keys):
        _place_player(world, 3.5, 3.5)
        world.player.hp = 1.0
        world.enemies = [Enemy(3.6, 3.5)]

        world.update(no_keys)

        assert world.player.hp == pytest.approx(0.0)

    def test_dead_enemy_deals_no_damage(self, world, no_keys):
        _place_player(world, 3.5, 3.5)
        enemy = Enemy(3.6, 3.5)
        enemy.take_damage(enemy.hp)
        world.enemies = [enemy]

        world.update(no_keys)

        assert world.player.hp == pytest.approx(float(PLAYER_MAX_HP))

    def test_distant_enemy_deals_no_damage(self, world, no_keys):
        _place_player(world, 3.5, 3.5)
        world.enemies = [Enemy(3.5, 3.5 + 3.0)]

        world.update(no_keys)

        assert world.player.hp == pytest.approx(float(PLAYER_MAX_HP))


# --------------------------------------------------------------------------- #
# Level file loading
# --------------------------------------------------------------------------- #
class TestLevelFileLoading:
    def test_level_01_loads_expected_entity_counts(self):
        gw = GameWorld(map_path=LEVEL_01)
        gw.audio.enabled = False
        try:
            assert os.path.exists(LEVEL_01)
            assert len(gw.enemies) == 1
            assert len(gw.pickups) == 2
            kinds = sorted(p.kind.value for p in gw.pickups)
            assert kinds == ["health", "score"]
        finally:
            gw.cleanup()

    def test_level_01_applies_player_start_and_grid(self):
        gw = GameWorld(map_path=LEVEL_01)
        gw.audio.enabled = False
        try:
            assert gw.world_map.width == 24
            assert gw.world_map.height == 24
            assert gw.player.pos.x == pytest.approx(1.5)
            assert gw.player.pos.y == pytest.approx(1.5)
            assert not gw.world_map.is_wall(1, 1)
        finally:
            gw.cleanup()

    def test_level_01_player_starts_at_full_health_zero_score(self):
        gw = GameWorld(map_path=LEVEL_01)
        gw.audio.enabled = False
        try:
            assert gw.player.hp == pytest.approx(float(PLAYER_MAX_HP))
            assert gw.player.score == pytest.approx(0.0)
        finally:
            gw.cleanup()

    def test_level_01_updates_without_error(self, no_keys):
        gw = GameWorld(map_path=LEVEL_01)
        gw.audio.enabled = False
        try:
            for _ in range(5):
                gw.update(no_keys)
        finally:
            gw.cleanup()

    def test_missing_map_file_falls_back_to_maze(self):
        gw = GameWorld(map_path=os.path.join(DEFAULT_MAP_DIR, "__does_not_exist__.json"))
        gw.audio.enabled = False
        try:
            assert gw.enemies == []
            assert gw.pickups == []
            assert gw.world_map.width == 24
            assert gw.world_map.height == 24
        finally:
            gw.cleanup()

    def test_corrupted_map_file_falls_back_to_maze(self, tmp_path):
        bad = tmp_path / "broken.json"
        bad.write_text("{ this is not json", encoding="utf-8")

        gw = GameWorld(map_path=str(bad))
        gw.audio.enabled = False
        try:
            assert gw.enemies == []
            assert gw.pickups == []
            assert gw.world_map.width == 24
        finally:
            gw.cleanup()
