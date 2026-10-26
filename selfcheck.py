"""Headless self-check for text_fps.

Only imports the pygame-free logic packages (core / models / data / systems /
save).  The GUI entry points (text_fps/main.py, ui/) are never imported.

Run from the project root:  .venv\\Scripts\\python.exe selfcheck.py
"""
import os
import sys
import tempfile
from unittest import mock

ROOT = os.path.dirname(os.path.abspath(__file__))
PKG_DIR = os.path.join(ROOT, "text_fps")
if PKG_DIR not in sys.path:
    sys.path.insert(0, PKG_DIR)

from core.event_bus import EventBus
from core.game_state import GameState
from data.levels import get_available_levels, load_level
from data.weapons import create_mod, create_weapon
from models.enemy import Enemy
from models.player import Player
from models.weapon import Weapon
from save.save_manager import SaveManager
from systems.combat import CombatSystem


def _check(condition, message):
    if not condition:
        raise AssertionError(message)


def check_weapon_mods():
    """Weapon mod math: accuracy clamp, ammo bonus, noise floor, slot limit."""
    weapon = Weapon(name="Test Rifle", damage=10, accuracy=0.9, ammo=5,
                    max_ammo=5, base_noise=2)
    _check(weapon.add_mod(create_mod("scope")), "scope mod was rejected")
    _check(weapon.effective_accuracy() == 1.0,
           f"accuracy not clamped to 1.0: {weapon.effective_accuracy()}")
    _check(weapon.add_mod(create_mod("extended_mag")), "extended_mag rejected")
    _check(weapon.effective_max_ammo() == 15,
           f"ammo bonus not applied: {weapon.effective_max_ammo()}")
    _check(weapon.reload()["ammo_after"] == 15, "reload ignored ammo bonus")
    _check(weapon.add_mod(create_mod("silencer")), "silencer rejected")
    _check(weapon.noise_generated() == 0,
           f"noise floor broken: {weapon.noise_generated()}")
    _check(not weapon.add_mod(create_mod("scope")),
           "mod slot limit (3) not enforced")


def check_combat():
    """Combat: ammo/shot accounting, deterministic hit & miss, armor soak."""
    bus = EventBus()
    fired = []
    bus.subscribe("combat.fire", fired.append)
    combat = CombatSystem(bus)
    player = Player("Tester")
    player.weapons.append(create_weapon("pistol"))
    weapon = player.current_weapon()
    enemy = Enemy(name="Dummy", health=100, armor=0, damage=0, accuracy=0.0)

    with mock.patch("systems.combat.random.random", return_value=0.0), \
            mock.patch("systems.combat.random.uniform", return_value=1.0):
        hit = combat.execute_fire(player, enemy)
    _check(hit["success"] is True, "fire reported failure")
    _check(hit["hit"] is True, "guaranteed hit missed")
    _check(hit["damage"] == weapon.damage,
           f"damage {hit['damage']} != base {weapon.damage}")
    _check(weapon.ammo == weapon.max_ammo - 1,
           f"ammo not decremented: {weapon.ammo}")
    _check(player.shots_fired == 1, "shots_fired not incremented")
    _check(enemy.health == 100 - hit["damage"],
           f"enemy health {enemy.health} did not absorb the hit")
    _check(len(fired) == 1 and fired[0]["hit"] is True,
           "combat.fire event not published")

    with mock.patch("systems.combat.random.random", return_value=0.999):
        miss = combat.execute_fire(player, enemy)
    _check(miss["hit"] is False, "guaranteed miss reported a hit")
    _check(miss["damage"] == 0, "miss dealt damage")
    _check(weapon.ammo == weapon.max_ammo - 2, "miss did not consume ammo")

    drain = Weapon(name="Empty", ammo=0, max_ammo=5)
    _check(not drain.can_fire(), "empty weapon claims it can fire")
    _check(drain.fire()["hit"] is False, "empty weapon fired")

    soak = Weapon(name="Heavy", damage=30, accuracy=1.0, ammo=1, max_ammo=1)
    with mock.patch("systems.combat.random.uniform", return_value=1.0):
        _check(combat.calculate_damage(soak, 12) == 18,
               "armor did not absorb 12 damage")
        _check(combat.calculate_damage(soak, 100) == 0,
               "armor exceeding damage should clamp to 0")


def check_level_data():
    """Level data loads headlessly and is internally consistent."""
    _check(get_available_levels() == [1, 2, 3],
           f"unexpected level ids: {get_available_levels()}")
    for level_id in get_available_levels():
        level = load_level(level_id)
        _check(level.level_id == level_id, "level id mismatch")
        _check(level.start_room in level.rooms,
               f"level {level_id} start room {level.start_room!r} missing")
        _check(bool(level.rooms), f"level {level_id} has no rooms")
        for room_id, room in level.rooms.items():
            for direction, target in room.exits.items():
                _check(target in level.rooms,
                       f"level {level_id} room {room_id} exit {direction} -> "
                       f"missing room {target}")


def check_save_round_trip():
    """GameState -> JSON -> GameState preserves player, turn and room."""
    with tempfile.TemporaryDirectory() as tmp:
        manager = SaveManager(save_dir=tmp)
        state = GameState(EventBus())
        state.player = Player("SaveTester")
        state.player.health = 57
        state.player.weapons.append(create_weapon("rifle"))
        state.current_level = 2
        state.turn = 7
        level = load_level(2)
        state.current_room = level.get_room(level.start_room)

        _check(manager.has_save(1) is False, "slot 1 not empty before save")
        _check(manager.save(state, slot=1) is True, "save returned False")
        _check(manager.has_save(1) is True, "save file not created")
        _check(manager.save(state, slot=0) is False,
               "out-of-range slot was accepted")

        meta = manager.list_saves()[0]
        _check(meta["exists"] and meta["turn"] == 7 and meta["level"] == 2,
               f"save metadata wrong: {meta}")

        loaded = manager.load(EventBus(), slot=1)
        _check(loaded is not None, "load returned None")
        _check(loaded.player.health == 57,
               f"player health not restored: {loaded.player.health}")
        _check(loaded.turn == 7, f"turn not restored: {loaded.turn}")
        _check(loaded.current_level == 2, "level not restored")
        _check(loaded.player.weapons[0].name == "Assault Rifle",
               "weapon not restored")
        _check(loaded.current_room is not None
               and loaded.current_room.room_id == level.start_room,
               "current room not restored")
        _check(manager.load(EventBus(), slot=3) is None,
               "empty slot 3 returned data")
        _check(manager.delete_save(1) is True, "delete_save failed")
        _check(manager.has_save(1) is False, "save file still present")


CHECKS = (
    ("weapon-mod math", check_weapon_mods),
    ("turn-based combat", check_combat),
    ("level data integrity", check_level_data),
    ("save/load round trip", check_save_round_trip),
)


def main():
    passed = []
    for name, func in CHECKS:
        try:
            func()
        except AssertionError as exc:
            print(f"FAIL: {name}: {exc}")
            return 1
        except Exception as exc:  # noqa: BLE001 - report any unexpected error
            print(f"FAIL: {name}: {type(exc).__name__}: {exc}")
            return 1
        passed.append(name)
    print("selfcheck ok: " + ", ".join(passed))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
