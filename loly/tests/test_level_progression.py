"""Unit tests for multi-level progression (incremental PRD V2, L1-L8).

Covers the LEVEL_SEQUENCE campaign files (L1), level advancement (L2),
completion detection (L3), the player hitscan attack (L4), the victory
freeze (L5), restart semantics (L6), HUD render smoke (L7) and the Q5
hp / score carry-over rules (L8).
"""
import collections

import pytest

from doom_game.config import (
    FRAME_DT,
    LEVEL_SEQUENCE,
    NEW_LEVEL_HP_FLOOR,
    PLAYER_ATTACK_COOLDOWN,
    PLAYER_ATTACK_DAMAGE,
    PLAYER_ATTACK_RANGE,
    PLAYER_MAX_HP,
)
from doom_game.core.entities import Enemy, Projectile
from doom_game.core.types import TextureType
from doom_game.core.world_map import WorldMap
from doom_game.world.game_world import GameWorld
from doom_game.world.level_io import TEX_TO_INT, load_map


@pytest.fixture
def no_keys():
    """A ScancodeWrapper-like mapping where no key is pressed."""
    return collections.defaultdict(bool)


@pytest.fixture
def campaign():
    """A GameWorld running the full LEVEL_SEQUENCE campaign."""
    gw = GameWorld(level_sequence=list(LEVEL_SEQUENCE))
    gw.audio.enabled = False
    yield gw
    gw.cleanup()


@pytest.fixture
def single():
    """Single-level (--map) mode: clearing the only level == victory."""
    gw = GameWorld(map_path=LEVEL_SEQUENCE[0])
    gw.audio.enabled = False
    yield gw
    gw.cleanup()


def _kill_all(gw):
    for enemy in gw.enemies:
        enemy.alive = False


def _make_room(size: int = 13) -> WorldMap:
    wm = WorldMap(size, size)
    wm.cells = [
        [TextureType.STONE if (x in (0, size - 1) or y in (0, size - 1))
         else None for x in range(size)]
        for y in range(size)
    ]
    return wm


def _arm_attack_scene(gw, enemy_x=5.5, enemy_y=6.5):
    """Open room, player at (2.5, 6.5) facing +x, one enemy ahead."""
    gw.world_map = _make_room()
    gw.player.pos.x, gw.player.pos.y = 2.5, 6.5
    gw.player.angle = 0.0
    gw.player.hp = float(PLAYER_MAX_HP)
    enemy = Enemy(enemy_x, enemy_y)
    gw.enemies = [enemy]
    gw.pickups = []
    gw.projectiles = []
    gw._player_attack_cd = 0.0
    return enemy


# --------------------------------------------------------------------------- #
# L1: every campaign level parses and loads
# --------------------------------------------------------------------------- #
class TestLevelSequenceFiles:
    def test_sequence_lists_three_levels(self):
        assert len(LEVEL_SEQUENCE) == 3

    @pytest.mark.parametrize("path", LEVEL_SEQUENCE)
    def test_level_file_parses(self, path):
        ld = load_map(path)
        assert ld.width > 0 and ld.height > 0
        assert len(ld.cells) == ld.height
        assert "x" in ld.player_start

    @pytest.mark.parametrize("path", LEVEL_SEQUENCE)
    def test_level_file_loads_into_game_world(self, path):
        expected = load_map(path)
        gw = GameWorld(map_path=path)
        gw.audio.enabled = False
        try:
            assert gw.world_map.width == expected.width
            assert gw.world_map.height == expected.height
            assert len(gw.enemies) == len(expected.enemies)
        finally:
            gw.cleanup()


# --------------------------------------------------------------------------- #
# L2: advance_level moves to the next level's content
# --------------------------------------------------------------------------- #
class TestAdvanceLevel:
    def test_advance_enters_next_level_content(self, campaign):
        _kill_all(campaign)
        assert campaign._check_level_complete() is True

        campaign.advance_level()

        expected = load_map(LEVEL_SEQUENCE[1])
        assert campaign.level_index == 1
        assert campaign.map_path == LEVEL_SEQUENCE[1]
        assert len(campaign.enemies) == len(expected.enemies)
        got_cells = [[TEX_TO_INT.get(cell, 0) for cell in row]
                     for row in campaign.world_map.cells]
        assert got_cells == expected.cells
        assert campaign.projectiles == []

    def test_update_detects_completion_and_advances(self, campaign, no_keys):
        _kill_all(campaign)
        campaign.update(no_keys)
        if campaign.level_clear_timer > 0.0:
            # Interactive branch (Q7): intermission started; any key skips.
            campaign.skip_level_clear()
        assert campaign.level_index == 1


# --------------------------------------------------------------------------- #
# L3: completion detection
# --------------------------------------------------------------------------- #
class TestLevelComplete:
    def test_not_complete_while_an_enemy_lives(self, campaign):
        assert len(campaign.enemies) > 0            # level 1 has enemies
        assert campaign._check_level_complete() is False

    def test_complete_once_all_enemies_dead(self, campaign):
        _kill_all(campaign)
        assert campaign._check_level_complete() is True

    def test_enemyless_level_is_immediately_complete(self, campaign):
        campaign.enemies = []                        # Q1: empty -> complete
        assert campaign._check_level_complete() is True


# --------------------------------------------------------------------------- #
# L4: player hitscan attack
# --------------------------------------------------------------------------- #
class TestPlayerAttack:
    def test_hit_reduces_enemy_hp(self, single):
        enemy = _arm_attack_scene(single)
        hp0 = enemy.hp
        assert single.player_attack() is True
        assert enemy.hp == pytest.approx(hp0 - PLAYER_ATTACK_DAMAGE)
        assert enemy.alive is True

    def test_hp_zero_marks_enemy_dead(self, single):
        enemy = _arm_attack_scene(single)
        enemy.hp = float(PLAYER_ATTACK_DAMAGE)       # one shot kills
        assert single.player_attack() is True
        assert enemy.hp == pytest.approx(0.0)
        assert enemy.alive is False

    def test_wall_blocks_the_shot(self, single):
        enemy = _arm_attack_scene(single)
        single.world_map.cells[6][4] = TextureType.STONE
        hp0 = enemy.hp
        assert single.player_attack() is False
        assert enemy.hp == pytest.approx(hp0)

    def test_out_of_range_enemy_not_hit(self, single):
        enemy = _arm_attack_scene(
            single, enemy_x=2.5 + PLAYER_ATTACK_RANGE + 1.0)
        hp0 = enemy.hp
        assert single.player_attack() is False
        assert enemy.hp == pytest.approx(hp0)

    def test_cooldown_blocks_immediate_second_shot(self, single):
        enemy = _arm_attack_scene(single)
        assert single.player_attack() is True
        assert single._player_attack_cd == pytest.approx(
            PLAYER_ATTACK_COOLDOWN)
        hp_after_first = enemy.hp
        assert single.player_attack() is False       # still cooling down
        assert enemy.hp == pytest.approx(hp_after_first)

    def test_attack_refused_while_dead_or_victorious(self, single):
        _arm_attack_scene(single)
        single.player.hp = 0.0
        assert single.player_attack() is False
        single.player.hp = float(PLAYER_MAX_HP)
        single.victory = True
        assert single.player_attack() is False


# --------------------------------------------------------------------------- #
# L5: final victory + entity freeze
# --------------------------------------------------------------------------- #
class TestVictoryFreeze:
    def test_last_level_advance_sets_victory(self, single, no_keys):
        _kill_all(single)
        single.advance_level()                       # only level -> victory
        assert single.victory is True
        assert single.projectiles == []

    def test_campaign_final_level_victory(self, campaign):
        campaign.level_index = len(LEVEL_SEQUENCE) - 1
        campaign.advance_level()
        assert campaign.victory is True

    def test_update_freezes_entities_after_victory(self, single, no_keys):
        enemy = _arm_attack_scene(single)
        single.victory = True
        projectile = Projectile(4.5, 6.5, 1.0, 0.0)
        single.projectiles = [projectile]
        ex, ey = enemy.pos.x, enemy.pos.y
        px, py = projectile.pos.x, projectile.pos.y
        hp0 = single.player.hp

        for _ in range(5):
            single.update(no_keys)

        assert (enemy.pos.x, enemy.pos.y) == (ex, ey)
        assert (projectile.pos.x, projectile.pos.y) == (px, py)
        assert single.projectiles == [projectile]    # not even filtered
        assert single.player.hp == pytest.approx(hp0)


# --------------------------------------------------------------------------- #
# L6: restart keeps the current level
# --------------------------------------------------------------------------- #
class TestRestartLevel:
    def test_death_restart_stays_on_level_two(self, campaign):
        _kill_all(campaign)
        campaign.advance_level()
        assert campaign.level_index == 1

        campaign.player.hp = 0.0                     # die on level 2
        campaign.restart_level()

        assert campaign.level_index == 1             # still level 2
        assert campaign.map_path == LEVEL_SEQUENCE[1]
        assert campaign.player.hp == pytest.approx(float(PLAYER_MAX_HP))
        assert campaign.victory is False
        assert campaign.projectiles == []

    def test_restart_rolls_score_back_to_level_entry(self, campaign):
        campaign.player.score = 300.0
        _kill_all(campaign)
        campaign.advance_level()                     # entry score = 300
        campaign.player.score = 350.0                # earn some, then die
        campaign.player.hp = 0.0
        campaign.restart_level()
        assert campaign.player.score == pytest.approx(300.0)


# --------------------------------------------------------------------------- #
# L7: HUD render smoke (banner / clear / victory)
# --------------------------------------------------------------------------- #
class TestHudRenderSmoke:
    def test_hud_exposes_level_overlays(self, campaign):
        for name in ("render_level_banner", "render_level_clear",
                     "render_victory"):
            assert callable(getattr(campaign.hud, name))

    def test_render_new_level_banner_does_not_crash(self, campaign, display):
        campaign.render(display)                     # LEVEL 1/3 banner

    def test_render_clear_and_victory_do_not_crash(self, campaign, display):
        campaign.level_clear_timer = 1.0
        campaign.render(display)                     # LEVEL CLEAR card
        campaign.level_clear_timer = 0.0
        campaign.victory = True
        campaign.render(display)                     # YOU WIN overlay


# --------------------------------------------------------------------------- #
# L8 / Q5: hp and score carry-over across levels
# --------------------------------------------------------------------------- #
class TestStatCarryOver:
    def test_score_accumulates_and_low_hp_floors_at_half(self, campaign):
        campaign.player.hp = 20.0
        campaign.player.score = 500.0
        _kill_all(campaign)
        campaign.advance_level()

        floor = NEW_LEVEL_HP_FLOOR * campaign.player.max_hp
        assert campaign.level_index == 1
        assert campaign.player.hp == pytest.approx(floor)
        assert campaign.player.score == pytest.approx(500.0)

    def test_high_hp_carries_over_unchanged(self, campaign):
        campaign.player.hp = 80.0
        _kill_all(campaign)
        campaign.advance_level()
        assert campaign.player.hp == pytest.approx(80.0)

    def test_full_hp_is_capped_at_max(self, campaign):
        campaign.player.hp = float(PLAYER_MAX_HP)
        _kill_all(campaign)
        campaign.advance_level()
        assert campaign.player.hp == pytest.approx(float(PLAYER_MAX_HP))
        assert campaign.player.hp <= campaign.player.max_hp
