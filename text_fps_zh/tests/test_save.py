"""Save / load (round-trip) unit tests for GameState.

Constructs a GameState purely from ``models`` (no pygame, no data factories, no
main), serializes via ``to_dict()`` and restores via ``from_dict()``, then asserts:
  * a killed enemy keeps ``is_alive == False`` and ``health == 0``
  * player inventory items are preserved
  * multi-room level state is preserved (room ids, room items, visited flag)
  * the ``version`` field exists in the serialized dict

Run with pytest (CI):  ``pytest tests/test_save.py``
Run without pytest:    ``python tests/run_manual.py``
"""
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from core.constants import PHASE_PLAYER_TURN
from core.game_state import GameState
from models.enemy import Enemy
from models.item import MedKit, ArmorPickup
from models.level import Level
from models.player import Player
from models.room import Room
from models.weapon import Weapon


def _build_state_with_kill_and_rooms():
    gs = GameState()
    p = Player(name="Hero")
    p.weapons.append(
        Weapon(name="Pistol", weapon_type="pistol",
               damage=12, accuracy=0.75, ammo=15, max_ammo=15)
    )
    p.inventory.append(MedKit(heal_amount=25))
    gs.player = p

    # --- Room 1: entrance, with a KILLED enemy + a room item, visited ---
    r1 = Room(
        room_id="entrance",
        name="Entrance",
        description="The starting room.",
        exits={"east": "storage"},
        cover_objects=["concrete pillar"],
    )
    dead = Enemy(name="Guard", health=40, armor=5)
    dead.health = 0
    dead.is_alive = False
    r1.enemies.append(dead)
    r1.items.append(ArmorPickup(armor_amount=25))
    r1.visited = True

    # --- Room 2: storage (empty, just to prove multi-room preservation) ---
    r2 = Room(
        room_id="storage",
        name="Storage",
        description="A dusty storeroom.",
        exits={"west": "entrance"},
    )

    lv = Level(
        level_id=1,
        name="Level 1",
        rooms={"entrance": r1, "storage": r2},
        start_room="entrance",
    )
    gs.levels.append(lv)
    gs.current_level = 1
    gs.current_room = r1
    gs.turn = 7
    gs.phase = PHASE_PLAYER_TURN
    gs.add_log("Entered the entrance.")
    gs.add_log("Guard eliminated.")
    return gs


def test_save_dict_has_version():
    gs = _build_state_with_kill_and_rooms()
    d = gs.to_dict()
    assert "version" in d
    assert d["version"] == 1


def test_save_roundtrip_killed_enemy():
    gs = _build_state_with_kill_and_rooms()
    gs2 = GameState.from_dict(gs.to_dict())

    entrance = gs2.levels[0].get_room("entrance")
    assert entrance is not None
    killed = next((en for en in entrance.enemies if en.name == "Guard"), None)
    assert killed is not None
    assert killed.is_alive is False
    assert killed.health == 0


def test_save_roundtrip_player_items():
    gs = _build_state_with_kill_and_rooms()
    gs2 = GameState.from_dict(gs.to_dict())

    assert gs2.player is not None
    assert len(gs2.player.inventory) == 1
    assert gs2.player.inventory[0].name == "MedKit"
    # weapon preserved
    assert len(gs2.player.weapons) == 1
    assert gs2.player.weapons[0].name == "Pistol"


def test_save_roundtrip_multi_room_state():
    gs = _build_state_with_kill_and_rooms()
    gs2 = GameState.from_dict(gs.to_dict())

    lv = gs2.levels[0]
    assert len(lv.rooms) == 2
    assert "entrance" in lv.rooms
    assert "storage" in lv.rooms

    entrance = lv.get_room("entrance")
    # room item preserved (ArmorPickup serializes as item_type "armor",
    # and its armor_amount is round-tripped).
    assert len(entrance.items) == 1
    assert entrance.items[0].item_type == "armor"
    assert entrance.items[0].armor_amount == 25
    # visited flag preserved
    assert entrance.visited is True
    # cover objects preserved
    assert "concrete pillar" in entrance.cover_objects


def test_save_roundtrip_scalars_and_current_room():
    gs = _build_state_with_kill_and_rooms()
    gs2 = GameState.from_dict(gs.to_dict())

    assert gs2.turn == 7
    assert gs2.phase == PHASE_PLAYER_TURN
    assert gs2.current_room is not None
    assert gs2.current_room.room_id == "entrance"
    # log is restored (to_dict keeps the last 50 entries)
    assert any("Guard eliminated" in line for line in gs2.log)
