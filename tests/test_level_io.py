"""Tests for ``doom_game.world.level_io`` (R2.5 level I/O).

Verifies:
  * JSON is a *lossless* round-trip (load -> save -> load).
  * ASCII is *structure-stable* only (metadata is rebuilt from config
    defaults, per design section 4.3) - assertions are deliberately scoped to
    the grid layout and entity placement.
  * The integer <-> ``TextureType`` mapping.
  * ``build_enemies`` / ``build_pickups`` entity construction.
  * Graceful handling of missing / malformed level files.
"""
import json

import pytest

from doom_game.config import (
    ENEMY_DAMAGE,
    ENEMY_HP,
    ENEMY_SPEED,
    HEALTH_PICKUP_AMOUNT,
    SCORE_PICKUP_AMOUNT,
)
from doom_game.core.entities import Enemy, EnemyType, Pickup, PickupType
from doom_game.core.types import TextureType
from doom_game.world.level_io import (
    INT_TO_TEX,
    TEX_TO_INT,
    LevelData,
    ascii_to_json,
    build_enemies,
    build_pickups,
    json_to_ascii,
    load_map,
    save_map,
)

LEVEL_01 = "G:/loly/maps/level_01.json"


def _wall_mask(cells):
    """Reduce a grid to a boolean wall/empty mask (structure only)."""
    return [[1 if int(v) else 0 for v in row] for row in cells]


@pytest.fixture
def level_01():
    return load_map(LEVEL_01)


@pytest.fixture
def tiny_level():
    """A hand-built 5x4 level with one enemy and two pickups."""
    return LevelData(
        version=1,
        width=5,
        height=4,
        cells=[
            [2, 2, 2, 2, 2],
            [2, 0, 0, 0, 2],
            [2, 0, 1, 0, 2],
            [2, 2, 2, 2, 2],
        ],
        player_start={"x": 1.5, "y": 1.5, "angle": 0.0},
        enemies=[{"x": 3.5, "y": 1.5, "hp": 30, "damage": 10,
                  "speed": 0.06, "type": "basic"}],
        pickups=[{"x": 1.5, "y": 2.5, "kind": "health", "amount": 25},
                 {"x": 3.5, "y": 2.5, "kind": "score", "amount": 100}],
    )


# --------------------------------------------------------------------------- #
# Integer <-> TextureType mapping
# --------------------------------------------------------------------------- #
class TestTextureMapping:
    def test_int_to_tex_table(self):
        assert INT_TO_TEX == {
            0: None,
            1: TextureType.BRICK,
            2: TextureType.STONE,
            3: TextureType.METAL,
            4: TextureType.WOOD,
        }

    def test_tex_to_int_is_the_inverse(self):
        for i, tex in INT_TO_TEX.items():
            assert TEX_TO_INT[tex] == i

    def test_every_texture_type_is_mapped(self):
        for tex in TextureType:
            assert tex in TEX_TO_INT


# --------------------------------------------------------------------------- #
# Loading the shipped level
# --------------------------------------------------------------------------- #
class TestLoadMap:
    def test_level_01_shape_and_entities(self, level_01):
        assert level_01.width == 24
        assert level_01.height == 24
        assert len(level_01.cells) == 24
        assert all(len(row) == 24 for row in level_01.cells)
        assert len(level_01.enemies) == 1
        assert len(level_01.pickups) == 2

    def test_level_01_player_start(self, level_01):
        assert level_01.player_start["x"] == pytest.approx(1.5)
        assert level_01.player_start["y"] == pytest.approx(1.5)

    def test_missing_file_raises_filenotfound(self):
        with pytest.raises(FileNotFoundError):
            load_map("G:/loly/maps/__missing_level__.json")

    def test_malformed_json_raises_valueerror(self, tmp_path):
        bad = tmp_path / "bad.json"
        bad.write_text("{ nope", encoding="utf-8")
        with pytest.raises(ValueError):
            load_map(str(bad))

    def test_json_without_cells_raises_valueerror(self, tmp_path):
        bad = tmp_path / "nocells.json"
        bad.write_text(json.dumps({"version": 1}), encoding="utf-8")
        with pytest.raises(ValueError):
            load_map(str(bad))

    def test_non_object_root_raises_valueerror(self, tmp_path):
        bad = tmp_path / "list.json"
        bad.write_text("[1, 2, 3]", encoding="utf-8")
        with pytest.raises(ValueError):
            load_map(str(bad))

    def test_missing_player_start_falls_back_to_default(self, tmp_path):
        path = tmp_path / "nostart.json"
        path.write_text(json.dumps({"cells": [[1, 1], [1, 1]]}),
                        encoding="utf-8")

        ld = load_map(str(path))

        assert ld.player_start["x"] == pytest.approx(1.5)
        assert ld.player_start["y"] == pytest.approx(1.5)

    def test_ragged_rows_are_padded_to_a_rectangle(self, tmp_path):
        path = tmp_path / "ragged.json"
        path.write_text(json.dumps({
            "cells": [[1, 1, 1], [1], [1, 1]],
            "player_start": {"x": 1.5, "y": 1.5, "angle": 0.0},
        }), encoding="utf-8")

        ld = load_map(str(path))

        assert ld.width == 3
        assert ld.height == 3
        assert all(len(row) == 3 for row in ld.cells)
        assert ld.cells[1] == [1, 0, 0]

    def test_null_entity_lists_become_empty_lists(self, tmp_path):
        path = tmp_path / "nulls.json"
        path.write_text(json.dumps({
            "cells": [[1, 1], [1, 1]],
            "player_start": {"x": 1.5, "y": 1.5},
            "enemies": None,
            "pickups": None,
        }), encoding="utf-8")

        ld = load_map(str(path))

        assert ld.enemies == []
        assert ld.pickups == []


# --------------------------------------------------------------------------- #
# JSON round-trip (lossless)
# --------------------------------------------------------------------------- #
class TestJsonRoundTrip:
    def test_level_01_round_trip_is_lossless(self, level_01, tmp_path):
        out = tmp_path / "rt" / "level_rt.json"
        returned = save_map(level_01, str(out))
        reloaded = load_map(str(out))

        assert returned == str(out)
        assert reloaded.width == level_01.width
        assert reloaded.height == level_01.height
        assert reloaded.cells == level_01.cells
        assert reloaded.player_start == level_01.player_start
        assert reloaded.enemies == level_01.enemies
        assert reloaded.pickups == level_01.pickups

    def test_tiny_level_round_trip_is_lossless(self, tiny_level, tmp_path):
        out = tmp_path / "tiny.json"
        save_map(tiny_level, str(out))
        reloaded = load_map(str(out))

        assert reloaded.cells == tiny_level.cells
        assert reloaded.player_start == tiny_level.player_start
        assert reloaded.enemies == tiny_level.enemies
        assert reloaded.pickups == tiny_level.pickups

    def test_double_round_trip_is_stable(self, tiny_level, tmp_path):
        first = tmp_path / "a.json"
        second = tmp_path / "b.json"
        save_map(tiny_level, str(first))
        ld2 = load_map(str(first))
        save_map(ld2, str(second))
        ld3 = load_map(str(second))

        assert ld3.cells == ld2.cells
        assert ld3.enemies == ld2.enemies
        assert ld3.pickups == ld2.pickups

    def test_save_map_creates_missing_directories(self, tiny_level, tmp_path):
        out = tmp_path / "deep" / "nested" / "lvl.json"
        save_map(tiny_level, str(out))
        assert out.exists()

    def test_saved_file_is_valid_json_with_expected_keys(self, tiny_level,
                                                         tmp_path):
        out = tmp_path / "keys.json"
        save_map(tiny_level, str(out))
        raw = json.loads(out.read_text(encoding="utf-8"))
        for key in ("version", "width", "height", "cells",
                    "player_start", "enemies", "pickups"):
            assert key in raw


# --------------------------------------------------------------------------- #
# ASCII conversion (structure-stable only)
# --------------------------------------------------------------------------- #
class TestAsciiConversion:
    def test_json_to_ascii_produces_expected_dimensions(self, tiny_level):
        text = json_to_ascii(tiny_level)
        lines = text.split("\n")
        assert len(lines) == tiny_level.height
        assert all(len(line) == tiny_level.width for line in lines)

    def test_round_trip_preserves_grid_dimensions(self, level_01):
        back = ascii_to_json(json_to_ascii(level_01))
        assert back.width == level_01.width
        assert back.height == level_01.height

    def test_round_trip_preserves_wall_layout(self, level_01):
        back = ascii_to_json(json_to_ascii(level_01))
        assert _wall_mask(back.cells) == _wall_mask(level_01.cells)

    def test_round_trip_preserves_entity_counts(self, level_01):
        back = ascii_to_json(json_to_ascii(level_01))
        assert len(back.enemies) == len(level_01.enemies)
        assert len(back.pickups) == len(level_01.pickups)

    def test_round_trip_preserves_entity_cells(self, tiny_level):
        back = ascii_to_json(json_to_ascii(tiny_level))

        def cells(items):
            return sorted((int(i["x"]), int(i["y"])) for i in items)

        assert cells(back.enemies) == cells(tiny_level.enemies)
        assert cells(back.pickups) == cells(tiny_level.pickups)

    def test_round_trip_preserves_player_start_cell(self, tiny_level):
        back = ascii_to_json(json_to_ascii(tiny_level))
        assert int(back.player_start["x"]) == int(tiny_level.player_start["x"])
        assert int(back.player_start["y"]) == int(tiny_level.player_start["y"])

    def test_ascii_is_idempotent_after_the_first_conversion(self, level_01):
        once = json_to_ascii(level_01)
        twice = json_to_ascii(ascii_to_json(once))
        assert once == twice

    def test_ascii_characters_parse_to_expected_integers(self):
        ld = ascii_to_json("#B S\nMW..")
        assert ld.cells[0] == [2, 1, 0, 2]
        assert ld.cells[1] == [3, 4, 0, 0]

    def test_entity_markers_are_floor_cells(self):
        ld = ascii_to_json("#####\n#PEH#\n#$..#\n#####")
        assert ld.cells[1][1] == 0   # P
        assert ld.cells[1][2] == 0   # E
        assert ld.cells[1][3] == 0   # H
        assert ld.cells[2][1] == 0   # $

    def test_markers_create_the_right_entities(self):
        ld = ascii_to_json("#####\n#PEH#\n#$..#\n#####")
        assert len(ld.enemies) == 1
        assert ld.enemies[0]["x"] == pytest.approx(2.5)
        assert ld.enemies[0]["y"] == pytest.approx(1.5)
        kinds = sorted(p["kind"] for p in ld.pickups)
        assert kinds == ["health", "score"]

    def test_first_player_marker_wins(self):
        ld = ascii_to_json("#####\n#P.P#\n#####")
        assert ld.player_start["x"] == pytest.approx(1.5)

    def test_ascii_without_player_marker_uses_default_start(self):
        ld = ascii_to_json("###\n#.#\n###")
        assert ld.player_start["x"] == pytest.approx(1.5)
        assert ld.player_start["y"] == pytest.approx(1.5)

    def test_ascii_metadata_defaults_come_from_config(self):
        ld = ascii_to_json("#####\n#PEH#\n#$..#\n#####")
        assert ld.enemies[0]["hp"] == ENEMY_HP
        assert ld.enemies[0]["damage"] == ENEMY_DAMAGE
        assert ld.enemies[0]["speed"] == ENEMY_SPEED
        amounts = {p["kind"]: p["amount"] for p in ld.pickups}
        assert amounts["health"] == HEALTH_PICKUP_AMOUNT
        assert amounts["score"] == SCORE_PICKUP_AMOUNT

    def test_unknown_characters_become_empty_cells(self):
        ld = ascii_to_json("Z?\n@!")
        assert ld.cells == [[0, 0], [0, 0]]

    def test_empty_ascii_is_handled(self):
        ld = ascii_to_json("")
        assert ld.width == 0
        assert ld.height == 0
        assert ld.cells == []

    def test_load_map_reads_ascii_extension(self, tmp_path):
        path = tmp_path / "lvl.txt"
        path.write_text("#####\n#PEH#\n#####", encoding="utf-8")

        ld = load_map(str(path))

        assert ld.width == 5
        assert ld.height == 3
        assert len(ld.enemies) == 1


# --------------------------------------------------------------------------- #
# Entity construction
# --------------------------------------------------------------------------- #
class TestBuildEntities:
    def test_build_enemies_from_tiny_level(self, tiny_level):
        enemies = build_enemies(tiny_level)
        assert len(enemies) == 1
        enemy = enemies[0]
        assert isinstance(enemy, Enemy)
        assert enemy.pos.x == pytest.approx(3.5)
        assert enemy.pos.y == pytest.approx(1.5)
        assert enemy.hp == pytest.approx(30.0)
        assert enemy.damage == pytest.approx(10.0)
        assert enemy.speed == pytest.approx(0.06)
        assert enemy.type is EnemyType.BASIC
        assert enemy.alive is True

    def test_build_pickups_from_tiny_level(self, tiny_level):
        pickups = build_pickups(tiny_level)
        assert len(pickups) == 2
        assert all(isinstance(p, Pickup) for p in pickups)
        assert pickups[0].kind is PickupType.HEALTH
        assert pickups[0].amount == pytest.approx(25.0)
        assert pickups[1].kind is PickupType.SCORE
        assert pickups[1].amount == pytest.approx(100.0)
        assert all(p.taken is False for p in pickups)

    def test_build_from_level_01(self, level_01):
        assert len(build_enemies(level_01)) == 1
        assert len(build_pickups(level_01)) == 2

    def test_build_with_empty_level_returns_empty_lists(self):
        empty = LevelData(width=2, height=2, cells=[[0, 0], [0, 0]])
        assert build_enemies(empty) == []
        assert build_pickups(empty) == []

    def test_missing_enemy_fields_fall_back_to_config_defaults(self):
        ld = LevelData(enemies=[{"x": 2.5, "y": 3.5}])
        enemy = build_enemies(ld)[0]
        assert enemy.hp == pytest.approx(float(ENEMY_HP))
        assert enemy.damage == pytest.approx(float(ENEMY_DAMAGE))
        assert enemy.speed == pytest.approx(float(ENEMY_SPEED))

    def test_missing_pickup_amount_falls_back_to_config_default(self):
        ld = LevelData(pickups=[{"x": 2.5, "y": 3.5, "kind": "score"}])
        pickup = build_pickups(ld)[0]
        assert pickup.kind is PickupType.SCORE
        assert pickup.amount == pytest.approx(float(SCORE_PICKUP_AMOUNT))

    def test_unknown_pickup_kind_defaults_to_health(self):
        ld = LevelData(pickups=[{"x": 1.5, "y": 1.5, "kind": "mystery"}])
        assert build_pickups(ld)[0].kind is PickupType.HEALTH

    def test_pickup_kind_is_case_insensitive(self):
        ld = LevelData(pickups=[{"x": 1.5, "y": 1.5, "kind": "SCORE"}])
        assert build_pickups(ld)[0].kind is PickupType.SCORE

    def test_build_accepts_optional_world_map_argument(self, tiny_level,
                                                       small_map):
        assert len(build_enemies(tiny_level, small_map)) == 1
        assert len(build_pickups(tiny_level, small_map)) == 2


# --------------------------------------------------------------------------- #
# LevelData container
# --------------------------------------------------------------------------- #
class TestLevelData:
    def test_defaults_are_independent_instances(self):
        a = LevelData()
        b = LevelData()
        a.cells.append([1])
        a.enemies.append({"x": 1})
        assert b.cells == []
        assert b.enemies == []

    def test_default_version_is_one(self):
        assert LevelData().version == 1
