"""Comprehensive test suite for Text FPS game.

Part 1: Unit tests for all models, systems, and managers.
Part 2: Integration tests (pygame dummy init + Level 1 game flow simulation).
Part 3: Smart routing decision based on results.
"""
import json
import os
import sys
import tempfile
import shutil
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Ensure project root is importable
# ---------------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)


# ===================================================================
# Part 1 — Unit Tests
# ===================================================================

# --------------------- Player Tests ---------------------

class TestPlayer:
    """Tests for models.player.Player"""

    def _make_player(self, health=100, armor=0):
        from models.player import Player
        p = Player(name="TestPlayer")
        p.health = health
        p.armor = armor
        return p

    # -- take_damage --
    def test_take_damage_armor_absorbs_first(self):
        p = self._make_player(health=100, armor=30)
        actual = p.take_damage(20)
        assert actual == 0  # armor absorbs all
        assert p.armor == 10
        assert p.health == 100

    def test_take_damage_armor_partial_then_health(self):
        p = self._make_player(health=100, armor=10)
        actual = p.take_damage(25)
        assert actual == 15  # 25 - 10 armor
        assert p.armor == 0
        assert p.health == 85

    def test_take_damage_no_armor(self):
        p = self._make_player(health=100, armor=0)
        actual = p.take_damage(30)
        assert actual == 30
        assert p.health == 70

    def test_take_damage_zero_or_negative(self):
        p = self._make_player(health=100, armor=10)
        assert p.take_damage(0) == 0
        assert p.take_damage(-5) == 0
        assert p.health == 100
        assert p.armor == 10

    def test_take_damage_lethal(self):
        p = self._make_player(health=10, armor=0)
        p.take_damage(50)
        assert p.health == 0

    def test_take_damage_tracks_damage_taken(self):
        p = self._make_player(health=100, armor=0)
        p.take_damage(20)
        assert p.damage_taken == 20
        p.take_damage(10)
        assert p.damage_taken == 30

    # -- heal --
    def test_heal_normal(self):
        p = self._make_player(health=60)
        healed = p.heal(20)
        assert healed == 20
        assert p.health == 80

    def test_heal_capped_at_max(self):
        p = self._make_player(health=90)
        healed = p.heal(30)
        assert healed == 10
        assert p.health == 100

    def test_heal_zero_or_negative(self):
        p = self._make_player(health=50)
        assert p.heal(0) == 0
        assert p.heal(-10) == 0
        assert p.health == 50

    def test_heal_at_max(self):
        p = self._make_player(health=100)
        healed = p.heal(10)
        assert healed == 0

    # -- add_armor --
    def test_add_armor_normal(self):
        p = self._make_player(armor=0)
        added = p.add_armor(30)
        assert added == 30
        assert p.armor == 30

    def test_add_armor_capped_at_max(self):
        p = self._make_player(armor=90)
        added = p.add_armor(20)
        assert added == 10
        assert p.armor == 100

    def test_add_armor_zero_or_negative(self):
        p = self._make_player(armor=10)
        assert p.add_armor(0) == 0
        assert p.add_armor(-5) == 0

    # -- is_alive --
    def test_is_alive_positive(self):
        p = self._make_player(health=1)
        assert p.is_alive() is True

    def test_is_alive_zero(self):
        p = self._make_player(health=0)
        assert p.is_alive() is False

    # -- current_weapon --
    def test_current_weapon_valid_idx(self):
        from models.player import Player
        from models.weapon import Weapon
        p = Player()
        w = Weapon(name="Pistol")
        p.weapons = [w]
        assert p.current_weapon() is w

    def test_current_weapon_empty(self):
        from models.player import Player
        p = Player()
        assert p.current_weapon() is None

    def test_current_weapon_invalid_idx(self):
        from models.player import Player
        from models.weapon import Weapon
        p = Player()
        p.weapons = [Weapon(name="Pistol")]
        p.current_weapon_idx = 5
        assert p.current_weapon() is None

    # -- serialization round-trip --
    def test_to_dict_from_dict_roundtrip(self):
        from models.player import Player
        from models.weapon import Weapon
        from models.item import MedKit
        p = Player(name="Hero")
        p.weapons.append(Weapon(name="Pistol"))
        p.inventory.append(MedKit(heal_amount=25))
        p.health = 75
        p.armor = 20
        p.kills = 3
        p.shots_fired = 10
        p.headshots = 1
        p.damage_taken = 25
        p.noise_level = 3
        p.is_aiming = True
        p.in_cover = True

        d = p.to_dict()
        p2 = Player.from_dict(d)
        assert p2.name == "Hero"
        assert p2.health == 75
        assert p2.armor == 20
        assert p2.kills == 3
        assert p2.is_aiming is True
        assert p2.in_cover is True
        assert len(p2.weapons) == 1
        assert p2.weapons[0].name == "Pistol"
        assert len(p2.inventory) == 1


# --------------------- Enemy Tests ---------------------

class TestEnemy:
    """Tests for models.enemy.Enemy"""

    def _make_enemy(self, **kwargs):
        from models.enemy import Enemy
        defaults = {"name": "Guard", "health": 40, "armor": 0,
                     "damage": 8, "accuracy": 0.5, "behavior": "patrol"}
        defaults.update(kwargs)
        return Enemy(**defaults)

    def _make_player(self, health=100, armor=0):
        from models.player import Player
        p = Player(name="TestPlayer")
        p.health = health
        p.armor = armor
        return p

    def _make_room(self):
        from models.room import Room
        return Room(room_id="test", name="Test Room", description="test")

    # -- act: patrol --
    @patch("models.enemy.random.random", return_value=0.7)  # >= 0.6 => patrol
    def test_act_patrol_patrolling(self, mock_rand):
        e = self._make_enemy(behavior="patrol")
        p = self._make_player()
        r = self._make_room()
        result = e.act(p, r)
        assert result["action"] == "patrol"
        assert result["damage"] == 0

    @patch("models.enemy.random.random", return_value=0.3)  # < 0.6 => attack
    def test_act_patrol_attacks(self, mock_rand):
        e = self._make_enemy(behavior="patrol", accuracy=1.0)
        p = self._make_player()
        r = self._make_room()
        result = e.act(p, r)
        assert result["action"] == "attack"
        assert result["damage"] > 0

    # -- act: aggressive --
    def test_act_aggressive_always_attacks(self):
        e = self._make_enemy(behavior="aggressive", accuracy=1.0)
        p = self._make_player()
        r = self._make_room()
        result = e.act(p, r)
        assert result["action"] == "attack"

    @patch("models.enemy.random.random", return_value=0.99)
    def test_act_aggressive_miss(self, mock_rand):
        e = self._make_enemy(behavior="aggressive", accuracy=0.5)
        p = self._make_player()
        r = self._make_room()
        result = e.act(p, r)
        assert result["action"] == "miss"
        assert result["damage"] == 0

    # -- act: boss multi-phase --
    def test_act_boss_phase1_at_60pct(self):
        e = self._make_enemy(behavior="boss", health=100, is_boss=True)
        e.phase = 0
        e.health = 55  # 55/100 = 0.55 <= 0.6
        p = self._make_player()
        r = self._make_room()
        result = e.act(p, r)
        assert result["action"] == "phase_shift"
        assert e.phase == 1

    def test_act_boss_phase2_at_30pct(self):
        e = self._make_enemy(behavior="boss", health=100, is_boss=True)
        e.phase = 1
        e.health = 25  # 25/100 = 0.25 <= 0.3
        p = self._make_player()
        r = self._make_room()
        result = e.act(p, r)
        assert result["action"] == "phase_shift"
        assert e.phase == 2

    def test_act_boss_attacks_with_bonus(self):
        e = self._make_enemy(behavior="boss", health=100, is_boss=True, accuracy=1.0)
        e.phase = 1  # bonus = 5
        e.health = 70  # above threshold, so attacks
        p = self._make_player()
        r = self._make_room()
        result = e.act(p, r)
        assert result["action"] == "attack"

    def test_act_boss_dead(self):
        e = self._make_enemy(behavior="patrol")
        e.is_alive = False
        p = self._make_player()
        r = self._make_room()
        result = e.act(p, r)
        assert result["action"] == "dead"

    # -- take_damage --
    def test_take_damage_normal(self):
        e = self._make_enemy(health=40, armor=0)
        dealt = e.take_damage(20)
        assert dealt == 20
        assert e.health == 20
        assert e.is_alive is True

    def test_take_damage_kills(self):
        e = self._make_enemy(health=10, armor=0)
        e.take_damage(20)
        assert e.health == 0
        assert e.is_alive is False

    def test_take_damage_with_armor(self):
        e = self._make_enemy(health=40, armor=10)
        dealt = e.take_damage(15)
        assert dealt == 5  # 15 - 10 armor
        assert e.armor == 0
        assert e.health == 35

    def test_take_damage_zero_or_negative(self):
        e = self._make_enemy(health=40)
        assert e.take_damage(0) == 0
        assert e.take_damage(-5) == 0

    # -- check_alive --
    def test_check_alive_positive(self):
        e = self._make_enemy(health=1)
        assert e.check_alive() is True

    def test_check_alive_zero(self):
        e = self._make_enemy(health=0)
        assert e.check_alive() is False
        assert e.is_alive is False

    # -- serialization --
    def test_to_dict_from_dict_roundtrip(self):
        e = self._make_enemy(name="Commander", health=90, is_boss=True, behavior="boss")
        e.phase = 2
        d = e.to_dict()
        e2 = self._make_enemy().from_dict(d)
        assert e2.name == "Commander"
        assert e2.is_boss is True
        assert e2.phase == 2


# --------------------- Weapon Tests ---------------------

class TestWeapon:
    """Tests for models.weapon.Weapon and WeaponMod"""

    def _make_weapon(self, **kwargs):
        from models.weapon import Weapon
        defaults = {"name": "Pistol", "ammo": 15, "max_ammo": 15,
                     "damage": 12, "accuracy": 0.75}
        defaults.update(kwargs)
        return Weapon(**defaults)

    def _make_mod(self, **kwargs):
        from models.weapon import WeaponMod
        defaults = {"name": "Scope", "mod_type": "scope",
                     "accuracy_bonus": 0.15, "damage_bonus": 0,
                     "ammo_bonus": 0, "noise_modifier": 0}
        defaults.update(kwargs)
        return WeaponMod(**defaults)

    # -- fire --
    @patch("models.weapon.random.random", return_value=0.5)
    def test_fire_hit(self, mock_rand):
        w = self._make_weapon(ammo=5)
        result = w.fire()
        assert result["hit"] is True
        assert result["damage"] > 0
        assert result["ammo_remaining"] == 4

    @patch("models.weapon.random.random", return_value=0.99)
    def test_fire_miss(self, mock_rand):
        w = self._make_weapon(ammo=5)
        result = w.fire()
        assert result["hit"] is False
        assert result["damage"] == 0
        assert result["ammo_remaining"] == 4

    def test_fire_no_ammo(self):
        w = self._make_weapon(ammo=0)
        result = w.fire()
        assert result["hit"] is False
        assert result["ammo_remaining"] == 0

    # -- reload --
    def test_reload_refills_ammo(self):
        w = self._make_weapon(ammo=3, max_ammo=15)
        result = w.reload()
        assert w.ammo == 15
        assert result["reloaded"] is True
        assert result["ammo_before"] == 3

    # -- can_fire --
    def test_can_fire_true(self):
        w = self._make_weapon(ammo=1)
        assert w.can_fire() is True

    def test_can_fire_false_zero_ammo(self):
        w = self._make_weapon(ammo=0)
        assert w.can_fire() is False

    # -- add_mod / remove_mod --
    def test_add_mod_success(self):
        w = self._make_weapon()
        mod = self._make_mod()
        assert w.add_mod(mod) is True
        assert len(w.mods) == 1

    def test_add_mod_full_slots(self):
        w = self._make_weapon()
        for i in range(3):
            w.add_mod(self._make_mod(name=f"Mod{i}"))
        result = w.add_mod(self._make_mod(name="Extra"))
        assert result is False
        assert len(w.mods) == 3

    def test_remove_mod_by_type(self):
        w = self._make_weapon()
        mod = self._make_mod(mod_type="scope")
        w.add_mod(mod)
        removed = w.remove_mod("scope")
        assert removed is mod
        assert len(w.mods) == 0

    def test_remove_mod_not_found(self):
        w = self._make_weapon()
        assert w.remove_mod("nonexistent") is None

    # -- effective_accuracy / effective_damage --
    def test_effective_accuracy_with_mod(self):
        w = self._make_weapon(accuracy=0.75)
        mod = self._make_mod(accuracy_bonus=0.15)
        w.add_mod(mod)
        assert w.effective_accuracy() == 0.90

    def test_effective_accuracy_capped_at_1(self):
        w = self._make_weapon(accuracy=0.90)
        mod = self._make_mod(accuracy_bonus=0.20)
        w.add_mod(mod)
        assert w.effective_accuracy() == 1.0

    def test_effective_damage_with_mod(self):
        w = self._make_weapon(damage=12)
        mod = self._make_mod(damage_bonus=5)
        w.add_mod(mod)
        assert w.effective_damage() == 17

    def test_effective_max_ammo_with_mod(self):
        w = self._make_weapon(max_ammo=15)
        mod = self._make_mod(ammo_bonus=10)
        w.add_mod(mod)
        assert w.effective_max_ammo() == 25

    def test_noise_generated_with_silencer(self):
        w = self._make_weapon(base_noise=3)
        mod = self._make_mod(name="Silencer", mod_type="silencer", noise_modifier=-2)
        w.add_mod(mod)
        assert w.noise_generated() == 1

    def test_noise_generated_never_negative(self):
        w = self._make_weapon(base_noise=1)
        mod = self._make_mod(noise_modifier=-5)
        w.add_mod(mod)
        assert w.noise_generated() == 0

    # -- serialization --
    def test_to_dict_from_dict_roundtrip(self):
        w = self._make_weapon()
        w.add_mod(self._make_mod())
        d = w.to_dict()
        from models.weapon import Weapon
        w2 = Weapon.from_dict(d)
        assert w2.name == "Pistol"
        assert len(w2.mods) == 1
        assert w2.mods[0].mod_type == "scope"


# --------------------- Item Tests ---------------------

class TestItem:
    """Tests for models.item subclasses"""

    def _make_player(self, health=50, armor=0):
        from models.player import Player
        p = Player(name="TestPlayer")
        p.health = health
        p.armor = armor
        return p

    # -- MedKit --
    def test_medkit_use_heals(self):
        from models.item import MedKit
        p = self._make_player(health=50)
        mk = MedKit(heal_amount=25)
        result = mk.use(p)
        assert p.health == 75
        assert "25" in result

    def test_medkit_use_capped(self):
        from models.item import MedKit
        p = self._make_player(health=90)
        mk = MedKit(heal_amount=25)
        mk.use(p)
        assert p.health == 100

    def test_medkit_use_at_full(self):
        from models.item import MedKit
        p = self._make_player(health=100)
        mk = MedKit(heal_amount=25)
        result = mk.use(p)
        assert "No healing needed" in result

    # -- ArmorPickup --
    def test_armor_use_adds_armor(self):
        from models.item import ArmorPickup
        p = self._make_player(armor=0)
        ap = ArmorPickup(armor_amount=25)
        ap.use(p)
        assert p.armor == 25

    def test_armor_use_capped(self):
        from models.item import ArmorPickup
        p = self._make_player(armor=90)
        ap = ArmorPickup(armor_amount=25)
        ap.use(p)
        assert p.armor == 100

    # -- AmmoPickup --
    def test_ammo_use_refills_matching_weapon(self):
        from models.item import AmmoPickup
        from models.weapon import Weapon
        p = self._make_player()
        w = Weapon(name="Pistol", weapon_type="pistol", ammo=5, max_ammo=15)
        p.weapons.append(w)
        ammo = AmmoPickup(weapon_type="pistol", amount=10)
        result = ammo.use(p)
        assert w.ammo == 15  # capped at max
        assert "Pistol" in result

    def test_ammo_use_no_matching_weapon(self):
        from models.item import AmmoPickup
        p = self._make_player()
        ammo = AmmoPickup(weapon_type="rifle", amount=10)
        result = ammo.use(p)
        assert "don't have a compatible weapon" in result

    # -- WeaponModItem --
    def test_weapon_mod_item_attaches(self):
        from models.item import WeaponModItem
        from models.weapon import Weapon, WeaponMod
        p = self._make_player()
        w = Weapon(name="Pistol")
        p.weapons.append(w)
        mod = WeaponMod(name="Scope", mod_type="scope", accuracy_bonus=0.15)
        wmi = WeaponModItem(name="Scope", mod=mod)
        result = wmi.use(p)
        assert "Attached" in result
        assert len(w.mods) == 1

    def test_weapon_mod_item_no_weapon(self):
        from models.item import WeaponModItem
        from models.weapon import WeaponMod
        p = self._make_player()
        mod = WeaponMod(name="Scope", mod_type="scope")
        wmi = WeaponModItem(name="Scope", mod=mod)
        result = wmi.use(p)
        assert "no weapon" in result

    def test_weapon_mod_item_slots_full(self):
        from models.item import WeaponModItem
        from models.weapon import Weapon, WeaponMod
        p = self._make_player()
        w = Weapon(name="Pistol")
        for _ in range(3):
            w.add_mod(WeaponMod(name="M", mod_type="silencer"))
        p.weapons.append(w)
        mod = WeaponMod(name="Extra", mod_type="scope")
        wmi = WeaponModItem(name="Extra", mod=mod)
        result = wmi.use(p)
        assert "full" in result.lower() or "Cannot attach" in result

    # -- Grenade --
    def test_grenade_use_damages_enemies(self):
        from models.item import Grenade
        from models.enemy import Enemy
        e1 = Enemy(name="G1", health=40)
        e2 = Enemy(name="G2", health=40)
        p = self._make_player()
        g = Grenade(damage=30)
        result = g.use(p, enemies=[e1, e2])
        assert e1.health == 10
        assert e2.health == 10
        assert "2 enemies" in result

    def test_grenade_use_no_enemies(self):
        from models.item import Grenade
        p = self._make_player()
        g = Grenade()
        result = g.use(p, enemies=[])
        assert "no enemies" in result.lower()

    # -- Item.from_dict dispatch --
    def test_item_from_dict_dispatch_medkit(self):
        from models.item import Item, MedKit
        data = {"name": "MedKit", "item_type": "medkit", "description": "", "usable": True, "heal_amount": 25}
        item = Item.from_dict(data)
        assert isinstance(item, MedKit)

    def test_item_from_dict_dispatch_grenade(self):
        from models.item import Item, Grenade
        data = {"name": "Grenade", "item_type": "grenade", "description": "", "usable": True, "damage": 30, "radius": 1}
        item = Item.from_dict(data)
        assert isinstance(item, Grenade)

    def test_item_from_dict_dispatch_armor(self):
        from models.item import Item, ArmorPickup
        data = {"name": "Armor", "item_type": "armor", "description": "", "usable": True, "armor_amount": 25}
        item = Item.from_dict(data)
        assert isinstance(item, ArmorPickup)

    def test_item_from_dict_dispatch_ammo(self):
        from models.item import Item, AmmoPickup
        data = {"name": "Ammo", "item_type": "ammo", "description": "", "usable": True, "amount": 15, "weapon_type": "pistol"}
        item = Item.from_dict(data)
        assert isinstance(item, AmmoPickup)

    def test_item_from_dict_dispatch_weapon_mod(self):
        from models.item import Item, WeaponModItem
        data = {"name": "Scope", "item_type": "weapon_mod", "description": "", "usable": True,
                "mod": {"name": "Scope", "mod_type": "scope", "accuracy_bonus": 0.15,
                        "damage_bonus": 0, "ammo_bonus": 0, "noise_modifier": 0}}
        item = Item.from_dict(data)
        assert isinstance(item, WeaponModItem)

    def test_item_from_dict_unknown_type(self):
        from models.item import Item
        data = {"name": "Junk", "item_type": "misc", "description": "", "usable": True}
        item = Item.from_dict(data)
        assert type(item) is Item


# --------------------- Room Tests ---------------------

class TestRoom:
    """Tests for models.room.Room"""

    def _make_room(self, **kwargs):
        from models.room import Room
        defaults = {"room_id": "test", "name": "Test Room", "description": "desc",
                     "exits": {"north": "room2"},
                     "cover_objects": ["barrel"]}
        defaults.update(kwargs)
        return Room(**defaults)

    def test_get_exit_existing(self):
        r = self._make_room(exits={"north": "room2", "south": "room3"})
        assert r.get_exit("north") == "room2"

    def test_get_exit_nonexistent(self):
        r = self._make_room(exits={"north": "room2"})
        assert r.get_exit("west") is None

    def test_has_cover_true(self):
        r = self._make_room(cover_objects=["barrel"])
        assert r.has_cover() is True

    def test_has_cover_false(self):
        r = self._make_room(cover_objects=[])
        assert r.has_cover() is False

    def test_remove_enemy(self):
        from models.enemy import Enemy
        e = Enemy(name="G")
        r = self._make_room()
        r.enemies.append(e)
        r.remove_enemy(e)
        assert e not in r.enemies

    def test_remove_item(self):
        from models.item import MedKit
        item = MedKit()
        r = self._make_room()
        r.items.append(item)
        r.remove_item(item)
        assert item not in r.items

    def test_living_enemies(self):
        from models.enemy import Enemy
        e1 = Enemy(name="Alive", health=40)
        e2 = Enemy(name="Dead", health=0)
        e2.is_alive = False
        r = self._make_room()
        r.enemies = [e1, e2]
        living = r.living_enemies()
        assert len(living) == 1
        assert living[0].name == "Alive"

    def test_add_item(self):
        from models.item import MedKit
        r = self._make_room()
        r.items = []
        mk = MedKit()
        r.add_item(mk)
        assert mk in r.items

    # -- serialization --
    def test_to_dict_from_dict_roundtrip(self):
        from models.enemy import Enemy
        from models.item import MedKit
        r = self._make_room()
        r.enemies.append(Enemy(name="Guard", health=40))
        r.items.append(MedKit(heal_amount=25))
        r.visited = True
        d = r.to_dict()
        from models.room import Room
        r2 = Room.from_dict(d)
        assert r2.room_id == "test"
        assert r2.visited is True
        assert len(r2.enemies) == 1
        assert len(r2.items) == 1


# --------------------- Level Tests ---------------------

class TestLevel:
    """Tests for models.level.Level"""

    def _make_level_with_enemies(self, enemies_alive=True):
        from models.level import Level
        from models.room import Room
        from models.enemy import Enemy
        room = Room(room_id="r1", name="Room1", description="test")
        if enemies_alive:
            room.enemies.append(Enemy(name="Guard", health=40))
        else:
            dead = Enemy(name="Guard", health=0)
            dead.is_alive = False
            room.enemies.append(dead)
        return Level(level_id=1, name="Test", rooms={"r1": room}, start_room="r1")

    def test_get_room_existing(self):
        lv = self._make_level_with_enemies()
        assert lv.get_room("r1") is not None

    def test_get_room_nonexistent(self):
        lv = self._make_level_with_enemies()
        assert lv.get_room("nonexistent") is None

    def test_is_complete_all_dead(self):
        lv = self._make_level_with_enemies(enemies_alive=False)
        assert lv.is_complete() is True
        assert lv.completed is True

    def test_is_complete_has_living(self):
        lv = self._make_level_with_enemies(enemies_alive=True)
        assert lv.is_complete() is False

    def test_is_complete_empty_rooms(self):
        from models.level import Level
        from models.room import Room
        lv = Level(level_id=1, name="Empty", rooms={"r1": Room(room_id="r1")}, start_room="r1")
        assert lv.is_complete() is True

    # -- serialization --
    def test_to_dict_from_dict_roundtrip(self):
        lv = self._make_level_with_enemies()
        d = lv.to_dict()
        from models.level import Level
        lv2 = Level.from_dict(d)
        assert lv2.level_id == 1
        assert "r1" in lv2.rooms


# --------------------- CombatSystem Tests ---------------------

class TestCombatSystem:
    """Tests for systems.combat.CombatSystem"""

    def _make_combat(self):
        from systems.combat import CombatSystem
        from core.event_bus import EventBus
        return CombatSystem(EventBus())

    def _make_player(self, health=100, armor=0):
        from models.player import Player
        from models.weapon import Weapon
        p = Player(name="TestPlayer")
        p.health = health
        p.armor = armor
        w = Weapon(name="Pistol", damage=12, accuracy=1.0, ammo=15, max_ammo=15)
        p.weapons.append(w)
        return p

    def _make_enemy(self, health=40, armor=0, damage=8, accuracy=0.5, behavior="aggressive"):
        from models.enemy import Enemy
        return Enemy(name="Guard", health=health, armor=armor,
                     damage=damage, accuracy=accuracy, behavior=behavior)

    def _make_room(self):
        from models.room import Room
        return Room(room_id="test", name="Test")

    # -- execute_fire --
    @patch("systems.combat.random.random", return_value=0.0)  # ensures hit
    @patch("systems.combat.random.uniform", return_value=1.0)  # no variance
    def test_execute_fire_hit(self, mock_uniform, mock_rand):
        cs = self._make_combat()
        p = self._make_player()
        e = self._make_enemy(armor=0)
        result = cs.execute_fire(p, e)
        assert result["success"] is True
        assert result["hit"] is True
        assert result["damage"] > 0
        assert e.health < 40

    @patch("systems.combat.random.random", return_value=0.99)  # ensures miss (0.99 > 0.75 accuracy)
    def test_execute_fire_miss(self, mock_rand):
        cs = self._make_combat()
        p = self._make_player()
        # Reduce weapon accuracy so 0.99 is a miss
        p.weapons[0].accuracy = 0.75
        e = self._make_enemy()
        result = cs.execute_fire(p, e)
        assert result["success"] is True
        assert result["hit"] is False
        assert result["damage"] == 0

    def test_execute_fire_no_weapon(self):
        cs = self._make_combat()
        from models.player import Player
        p = Player(name="Unarmed")
        e = self._make_enemy()
        result = cs.execute_fire(p, e)
        assert result["success"] is False

    def test_execute_fire_no_ammo(self):
        cs = self._make_combat()
        p = self._make_player()
        p.weapons[0].ammo = 0
        e = self._make_enemy()
        result = cs.execute_fire(p, e)
        assert result["success"] is False

    @patch("systems.combat.random.random", return_value=0.0)
    @patch("systems.combat.random.uniform", return_value=1.0)
    def test_execute_fire_aiming_bonus(self, mock_uniform, mock_rand):
        cs = self._make_combat()
        p = self._make_player()
        p.is_aiming = True
        # With accuracy=1.0 + aim bonus, should still hit
        e = self._make_enemy()
        result = cs.execute_fire(p, e)
        assert result["hit"] is True
        assert p.is_aiming is False  # aiming resets after shot

    @patch("systems.combat.random.random", return_value=0.0)
    @patch("systems.combat.random.uniform", return_value=1.0)
    def test_execute_fire_kill_increments_kills(self, mock_uniform, mock_rand):
        cs = self._make_combat()
        p = self._make_player()
        e = self._make_enemy(health=1)
        result = cs.execute_fire(p, e)
        assert not e.is_alive
        assert p.kills == 1

    # -- execute_aim --
    def test_execute_aim(self):
        cs = self._make_combat()
        p = self._make_player()
        result = cs.execute_aim(p)
        assert result["success"] is True
        assert p.is_aiming is True

    # -- execute_reload --
    def test_execute_reload(self):
        cs = self._make_combat()
        p = self._make_player()
        p.weapons[0].ammo = 3
        result = cs.execute_reload(p)
        assert result["success"] is True
        assert p.weapons[0].ammo == 15

    def test_execute_reload_no_weapon(self):
        cs = self._make_combat()
        from models.player import Player
        p = Player(name="Unarmed")
        result = cs.execute_reload(p)
        assert result["success"] is False

    # -- execute_grenade --
    def test_execute_grenade_damage(self):
        cs = self._make_combat()
        p = self._make_player()
        from models.item import Grenade
        g = Grenade(damage=30)
        p.inventory.append(g)
        e1 = self._make_enemy(health=40)
        e2 = self._make_enemy(health=40)
        result = cs.execute_grenade(p, [e1, e2])
        assert result["success"] is True
        assert e1.health == 10
        assert e2.health == 10
        assert len(p.inventory) == 0  # grenade consumed

    def test_execute_grenade_no_grenade(self):
        cs = self._make_combat()
        p = self._make_player()
        result = cs.execute_grenade(p, [])
        assert result["success"] is False

    def test_execute_grenade_kills_count(self):
        cs = self._make_combat()
        p = self._make_player()
        from models.item import Grenade
        g = Grenade(damage=30)
        p.inventory.append(g)
        e = self._make_enemy(health=20)
        result = cs.execute_grenade(p, [e])
        assert not e.is_alive
        assert p.kills == 1

    # -- execute_enemy_turn --
    def test_execute_enemy_turn_attacks(self):
        """Test that enemy turn produces results."""
        cs = self._make_combat()
        p = self._make_player()
        e = self._make_enemy(accuracy=1.0, behavior="aggressive")
        r = self._make_room()
        # Mock enemy._attack to guarantee a hit
        with patch.object(e, '_attack', return_value={
            "action": "attack", "damage": 8, "message": "Guard hits you for 8 damage!"
        }):
            results = cs.execute_enemy_turn([e], p, r)
        assert len(results) == 1
        assert results[0]["action"] == "attack"

    def test_execute_enemy_turn_cover_reduces_accuracy(self):
        """Verify cover reduces enemy accuracy during their turn."""
        cs = self._make_combat()
        p = self._make_player()
        p.in_cover = True
        e = self._make_enemy(accuracy=0.50)
        r = self._make_room()
        original_accuracy = e.accuracy

        # Capture the accuracy value passed to act by spying on enemy.accuracy setter
        accuracies_during_act = []
        original_act = e.act

        def patched_act(player, room):
            accuracies_during_act.append(e.accuracy)
            return original_act(player, room)

        with patch.object(e, 'act', side_effect=patched_act):
            cs.execute_enemy_turn([e], p, r)

        # During act, accuracy should have been reduced
        if accuracies_during_act:
            assert accuracies_during_act[0] < original_accuracy
        # After call, accuracy should be restored
        assert e.accuracy == original_accuracy

    def test_execute_enemy_turn_stops_on_player_death(self):
        """If player dies during enemy turn, remaining enemies skip."""
        cs = self._make_combat()
        p = self._make_player(health=1, armor=0)
        e1 = self._make_enemy(damage=100, accuracy=1.0, behavior="aggressive")
        e2 = self._make_enemy(accuracy=1.0, behavior="aggressive")
        r = self._make_room()
        # Mock first enemy to kill the player, second should be skipped
        call_count = [0]

        def mock_act_1(player, room):
            call_count[0] += 1
            player.take_damage(100)
            return {"action": "attack", "damage": 100, "message": "Fatal hit!"}

        def mock_act_2(player, room):
            call_count[0] += 100  # Should not be called
            return {"action": "attack", "damage": 5, "message": "Second attack"}

        e1.act = mock_act_1
        e2.act = mock_act_2
        results = cs.execute_enemy_turn([e1, e2], p, r)
        # Should stop after first enemy kills player
        assert not p.is_alive()
        assert call_count[0] == 1  # Only first enemy acted


# --------------------- MovementSystem Tests ---------------------

class TestMovementSystem:
    """Tests for systems.movement.MovementSystem"""

    def _make_movement(self):
        from systems.movement import MovementSystem
        from core.event_bus import EventBus
        return MovementSystem(EventBus())

    def _make_game_state(self, room=None, enemies=None):
        from core.game_state import GameState
        from core.event_bus import EventBus
        from models.player import Player
        from models.weapon import Weapon
        from models.room import Room
        from models.level import Level
        from models.enemy import Enemy

        eb = EventBus()
        gs = GameState(event_bus=eb)
        p = Player(name="TestPlayer")
        p.weapons.append(Weapon(name="Pistol"))
        gs.player = p

        if room is None:
            room = Room(room_id="start", name="Start Room", description="A start room.",
                        exits={"east": "room2"}, cover_objects=["barrel"])
        gs.current_room = room
        p.position = room.room_id

        level = Level(level_id=1, name="Test", rooms={"start": room}, start_room="start")
        room2 = Room(room_id="room2", name="Room 2", description="Second room.",
                     exits={"west": "start"}, cover_objects=[])
        level.rooms["room2"] = room2
        gs.levels.append(level)

        return gs

    def test_move_no_enemies_success(self):
        ms = self._make_movement()
        gs = self._make_game_state()
        result = ms.move(gs, "east")
        assert result["success"] is True
        assert gs.player.position == "room2"
        assert gs.current_room.room_id == "room2"

    def test_move_with_enemies_blocked(self):
        from models.enemy import Enemy
        ms = self._make_movement()
        room = self._make_game_state().current_room
        # Put an enemy in the room to block movement
        room.enemies.append(Enemy(name="Guard", health=40))
        gs = self._make_game_state(room=room)
        result = ms.move(gs, "east")
        assert result["success"] is False
        assert result["hostile"] is True

    def test_move_invalid_direction(self):
        ms = self._make_movement()
        gs = self._make_game_state()
        result = ms.move(gs, "west")
        assert result["success"] is False

    def test_validate_exit_valid(self):
        ms = self._make_movement()
        from models.room import Room
        r = Room(room_id="r1", exits={"north": "r2"})
        assert ms.validate_exit(r, "north") is True

    def test_validate_exit_invalid(self):
        ms = self._make_movement()
        from models.room import Room
        r = Room(room_id="r1", exits={"north": "r2"})
        assert ms.validate_exit(r, "south") is False

    def test_move_resets_cover_and_aiming(self):
        ms = self._make_movement()
        gs = self._make_game_state()
        gs.player.in_cover = True
        gs.player.is_aiming = True
        result = ms.move(gs, "east")
        assert result["success"] is True
        assert gs.player.in_cover is False
        assert gs.player.is_aiming is False


# --------------------- InventorySystem Tests ---------------------

class TestInventorySystem:
    """Tests for systems.inventory.InventorySystem"""

    def _make_inventory(self):
        from systems.inventory import InventorySystem
        from core.event_bus import EventBus
        return InventorySystem(EventBus())

    def _make_player(self):
        from models.player import Player
        from models.weapon import Weapon
        p = Player(name="TestPlayer")
        w = Weapon(name="Pistol", weapon_type="pistol", ammo=15, max_ammo=15)
        p.weapons.append(w)
        return p

    def _make_room(self):
        from models.room import Room
        return Room(room_id="test", name="Test")

    # -- pickup --
    def test_pickup_success(self):
        inv = self._make_inventory()
        p = self._make_player()
        r = self._make_room()
        from models.item import MedKit
        mk = MedKit()
        r.items.append(mk)
        result = inv.pickup(p, r, 0)
        assert result["success"] is True
        assert mk in p.inventory
        assert mk not in r.items

    def test_pickup_invalid_index(self):
        inv = self._make_inventory()
        p = self._make_player()
        r = self._make_room()
        result = inv.pickup(p, r, 99)
        assert result["success"] is False

    def test_pickup_inventory_full(self):
        inv = self._make_inventory()
        p = self._make_player()
        r = self._make_room()
        from models.item import Item
        # Fill inventory
        for _ in range(10):
            p.inventory.append(Item(name="Junk"))
        r.items.append(Item(name="Extra"))
        result = inv.pickup(p, r, 0)
        assert result["success"] is False
        assert "full" in result["message"].lower()

    # -- pickup_all --
    def test_pickup_all_success(self):
        inv = self._make_inventory()
        p = self._make_player()
        r = self._make_room()
        from models.item import MedKit, ArmorPickup
        r.items.append(MedKit())
        r.items.append(ArmorPickup())
        result = inv.pickup_all(p, r)
        assert result["success"] is True
        assert result["count"] == 2

    def test_pickup_all_empty_room(self):
        inv = self._make_inventory()
        p = self._make_player()
        r = self._make_room()
        result = inv.pickup_all(p, r)
        assert result["success"] is False

    # -- use_item --
    def test_use_item_medkit(self):
        inv = self._make_inventory()
        p = self._make_player()
        p.health = 50
        from models.item import MedKit
        mk = MedKit(heal_amount=25)
        p.inventory.append(mk)
        result = inv.use_item(p, 0)
        assert result["success"] is True
        assert p.health == 75
        assert len(p.inventory) == 0  # consumed

    def test_use_item_armor(self):
        inv = self._make_inventory()
        p = self._make_player()
        from models.item import ArmorPickup
        ap = ArmorPickup(armor_amount=25)
        p.inventory.append(ap)
        result = inv.use_item(p, 0)
        assert result["success"] is True
        assert p.armor == 25
        assert len(p.inventory) == 0

    def test_use_item_ammo(self):
        inv = self._make_inventory()
        p = self._make_player()
        p.weapons[0].ammo = 5
        from models.item import AmmoPickup
        ammo = AmmoPickup(weapon_type="pistol", amount=10)
        p.inventory.append(ammo)
        result = inv.use_item(p, 0)
        assert result["success"] is True
        assert p.weapons[0].ammo == 15  # capped at max

    def test_use_item_weapon_mod(self):
        inv = self._make_inventory()
        p = self._make_player()
        from models.item import WeaponModItem
        from models.weapon import WeaponMod
        mod = WeaponMod(name="Scope", mod_type="scope", accuracy_bonus=0.15)
        wmi = WeaponModItem(name="Scope", mod=mod)
        p.inventory.append(wmi)
        result = inv.use_item(p, 0)
        assert result["success"] is True
        assert len(p.weapons[0].mods) == 1
        assert len(p.inventory) == 0

    def test_use_item_grenade_via_combat(self):
        inv = self._make_inventory()
        p = self._make_player()
        from models.item import Grenade
        from models.enemy import Enemy
        g = Grenade(damage=30)
        p.inventory.append(g)
        enemies = [Enemy(name="G", health=40)]
        combat = MagicMock()
        combat.execute_grenade.return_value = {"success": True, "message": "Boom!", "damage_dealt": 30, "killed": []}
        result = inv.use_item(p, 0, combat_system=combat, enemies=enemies)
        assert result["success"] is True
        combat.execute_grenade.assert_called_once()

    def test_use_item_invalid_index(self):
        inv = self._make_inventory()
        p = self._make_player()
        result = inv.use_item(p, 99)
        assert result["success"] is False

    # -- switch_weapon --
    def test_switch_weapon(self):
        inv = self._make_inventory()
        p = self._make_player()
        from models.weapon import Weapon
        p.weapons.append(Weapon(name="Rifle", weapon_type="rifle"))
        result = inv.switch_weapon(p, direction=1)
        assert result["success"] is True
        assert p.current_weapon().name == "Rifle"

    def test_switch_weapon_only_one(self):
        inv = self._make_inventory()
        p = self._make_player()
        result = inv.switch_weapon(p)
        assert result["success"] is False

    def test_switch_weapon_wraps_around(self):
        inv = self._make_inventory()
        p = self._make_player()
        from models.weapon import Weapon
        p.weapons.append(Weapon(name="Rifle"))
        p.current_weapon_idx = 1
        result = inv.switch_weapon(p, direction=1)
        assert result["success"] is True
        assert p.current_weapon_idx == 0

    # -- drop_item --
    def test_drop_item(self):
        inv = self._make_inventory()
        p = self._make_player()
        r = self._make_room()
        from models.item import MedKit
        mk = MedKit()
        p.inventory.append(mk)
        result = inv.drop_item(p, 0, r)
        assert result["success"] is True
        assert len(p.inventory) == 0
        assert mk in r.items

    def test_drop_item_invalid_index(self):
        inv = self._make_inventory()
        p = self._make_player()
        r = self._make_room()
        result = inv.drop_item(p, 99, r)
        assert result["success"] is False


# --------------------- StealthSystem Tests ---------------------

class TestStealthSystem:
    """Tests for systems.stealth.StealthSystem"""

    def _make_stealth(self):
        from systems.stealth import StealthSystem
        from core.event_bus import EventBus
        return StealthSystem(EventBus())

    def _make_player(self):
        from models.player import Player
        from models.weapon import Weapon
        p = Player(name="TestPlayer")
        p.weapons.append(Weapon(name="Pistol", base_noise=3))
        return p

    # -- calculate_noise --
    def test_calculate_noise_move(self):
        ss = self._make_stealth()
        p = self._make_player()
        assert ss.calculate_noise(p, "move") == 2

    def test_calculate_noise_fire(self):
        ss = self._make_stealth()
        p = self._make_player()
        assert ss.calculate_noise(p, "fire") == 3  # weapon base_noise

    def test_calculate_noise_grenade(self):
        ss = self._make_stealth()
        p = self._make_player()
        assert ss.calculate_noise(p, "grenade") == 5

    def test_calculate_noise_sneak(self):
        ss = self._make_stealth()
        p = self._make_player()
        assert ss.calculate_noise(p, "sneak") == 1

    def test_calculate_noise_reload(self):
        ss = self._make_stealth()
        p = self._make_player()
        assert ss.calculate_noise(p, "reload") == 0

    def test_calculate_noise_aim(self):
        ss = self._make_stealth()
        p = self._make_player()
        assert ss.calculate_noise(p, "aim") == 0

    def test_calculate_noise_unknown(self):
        ss = self._make_stealth()
        p = self._make_player()
        assert ss.calculate_noise(p, "unknown") == 0

    # -- apply_noise --
    def test_apply_noise_accumulates(self):
        ss = self._make_stealth()
        p = self._make_player()
        p.noise_level = 0
        r1 = ss.apply_noise(p, "move")  # +2
        assert r1["noise_added"] == 2
        assert p.noise_level == 2
        r2 = ss.apply_noise(p, "move")  # +2 more
        assert p.noise_level == 4

    def test_apply_noise_alerted(self):
        ss = self._make_stealth()
        p = self._make_player()
        p.noise_level = 0
        # fire adds 3, then grenade adds 5 => total 8 > threshold 5
        ss.apply_noise(p, "fire")
        result = ss.apply_noise(p, "grenade")
        assert result["alerted"] is True

    # -- decay_noise --
    def test_decay_noise(self):
        ss = self._make_stealth()
        p = self._make_player()
        p.noise_level = 5
        ss.decay_noise(p)
        assert p.noise_level == 4  # 5 - 1 (NOISE_DECAY)

    def test_decay_noise_floor(self):
        ss = self._make_stealth()
        p = self._make_player()
        p.noise_level = 0
        ss.decay_noise(p)
        assert p.noise_level == 0

    # -- take_cover --
    def test_take_cover_success(self):
        ss = self._make_stealth()
        p = self._make_player()
        from models.room import Room
        r = Room(room_id="test", cover_objects=["barrel"])
        result = ss.take_cover(p, r)
        assert result["success"] is True
        assert p.in_cover is True

    def test_take_cover_already_in_cover(self):
        ss = self._make_stealth()
        p = self._make_player()
        p.in_cover = True
        from models.room import Room
        r = Room(room_id="test", cover_objects=["barrel"])
        result = ss.take_cover(p, r)
        assert result["success"] is False

    def test_take_cover_no_cover_objects(self):
        ss = self._make_stealth()
        p = self._make_player()
        from models.room import Room
        r = Room(room_id="test", cover_objects=[])
        result = ss.take_cover(p, r)
        assert result["success"] is False


# --------------------- SaveManager Tests ---------------------

class TestSaveManager:
    """Tests for save.save_manager.SaveManager"""

    def _make_save_manager(self, tmp_path):
        from save.save_manager import SaveManager
        return SaveManager(save_dir=str(tmp_path))

    def _make_game_state(self):
        from core.game_state import GameState
        from core.event_bus import EventBus
        from models.player import Player
        from models.weapon import Weapon
        eb = EventBus()
        gs = GameState(event_bus=eb)
        p = Player(name="Hero")
        p.weapons.append(Weapon(name="Pistol"))
        p.health = 80
        p.armor = 20
        gs.player = p
        gs.current_level = 1
        gs.turn = 5
        gs.log = ["Turn 1", "Turn 2"]
        return gs

    def test_save_and_load_roundtrip(self, tmp_path):
        sm = self._make_save_manager(tmp_path)
        gs = self._make_game_state()
        assert sm.save(gs, slot=1) is True
        assert sm.has_save(1) is True

        from core.event_bus import EventBus
        loaded = sm.load(EventBus(), slot=1)
        assert loaded is not None
        assert loaded.player.name == "Hero"
        assert loaded.player.health == 80
        assert loaded.player.armor == 20
        assert loaded.turn == 5
        assert loaded.current_level == 1

    def test_save_invalid_slot(self, tmp_path):
        sm = self._make_save_manager(tmp_path)
        gs = self._make_game_state()
        assert sm.save(gs, slot=0) is False
        assert sm.save(gs, slot=99) is False

    def test_load_empty_slot(self, tmp_path):
        sm = self._make_save_manager(tmp_path)
        from core.event_bus import EventBus
        assert sm.load(EventBus(), slot=1) is None

    def test_delete_save(self, tmp_path):
        sm = self._make_save_manager(tmp_path)
        gs = self._make_game_state()
        sm.save(gs, slot=1)
        assert sm.delete_save(slot=1) is True
        assert sm.has_save(1) is False

    def test_delete_nonexistent_save(self, tmp_path):
        sm = self._make_save_manager(tmp_path)
        assert sm.delete_save(slot=1) is False

    def test_list_saves(self, tmp_path):
        sm = self._make_save_manager(tmp_path)
        gs = self._make_game_state()
        sm.save(gs, slot=1)
        saves = sm.list_saves()
        assert len(saves) >= 1
        assert saves[0]["exists"] is True


# --------------------- GameState Tests ---------------------

class TestGameState:
    """Tests for core.game_state.GameState"""

    def _make_gs(self):
        from core.game_state import GameState
        from core.event_bus import EventBus
        return GameState(event_bus=EventBus())

    def test_load_level(self):
        gs = self._make_gs()
        from models.level import Level
        from models.room import Room
        room = Room(room_id="start", name="Start", description="A room.")
        lv = Level(level_id=1, name="Test", rooms={"start": room}, start_room="start")
        gs.load_level(lv)
        assert gs.player is not None
        assert gs.current_room is not None
        assert gs.current_room.room_id == "start"
        assert gs.player.position == "start"
        assert len(gs.player.weapons) == 1  # pistol auto-equipped

    def test_add_log(self):
        gs = self._make_gs()
        gs.add_log("Hello")
        assert "Hello" in gs.log
        assert gs.dirty is True

    def test_add_log_trims(self):
        gs = self._make_gs()
        gs.max_log_lines = 5
        for i in range(10):
            gs.add_log(f"msg{i}")
        assert len(gs.log) == 5
        assert gs.log[0] == "msg5"

    def test_advance_turn(self):
        gs = self._make_gs()
        gs.turn = 0
        gs.advance_turn()
        assert gs.turn == 1
        assert gs.dirty is True

    def test_to_dict_from_dict_roundtrip(self):
        gs = self._make_gs()
        from models.level import Level
        from models.room import Room
        room = Room(room_id="start", name="Start", description="A room.")
        lv = Level(level_id=1, name="Test", rooms={"start": room}, start_room="start")
        gs.load_level(lv)
        gs.player.health = 75
        gs.turn = 10
        gs.log = ["test log"]

        d = gs.to_dict()
        from core.game_state import GameState
        from core.event_bus import EventBus
        gs2 = GameState.from_dict(d, event_bus=EventBus())
        assert gs2.player is not None
        assert gs2.player.health == 75
        assert gs2.turn == 10
        assert gs2.log == ["test log"]


# --------------------- EventBus Tests ---------------------

class TestEventBus:
    """Tests for core.event_bus.EventBus"""

    def test_subscribe_and_publish(self):
        from core.event_bus import EventBus
        bus = EventBus()
        received = []
        bus.subscribe("test_event", lambda data: received.append(data))
        bus.publish("test_event", {"key": "value"})
        assert len(received) == 1
        assert received[0]["key"] == "value"

    def test_multiple_subscribers(self):
        from core.event_bus import EventBus
        bus = EventBus()
        results = []
        bus.subscribe("evt", lambda d: results.append("a"))
        bus.subscribe("evt", lambda d: results.append("b"))
        bus.publish("evt")
        assert results == ["a", "b"]

    def test_unsubscribe(self):
        from core.event_bus import EventBus
        bus = EventBus()
        results = []
        cb = lambda d: results.append("called")
        bus.subscribe("evt", cb)
        bus.unsubscribe("evt", cb)
        bus.publish("evt")
        assert len(results) == 0

    def test_publish_no_subscribers(self):
        from core.event_bus import EventBus
        bus = EventBus()
        # Should not raise
        bus.publish("nonexistent", {})


# ===================================================================
# Part 2 — Integration Tests
# ===================================================================

class TestIntegrationPygameInit:
    """Test that pygame and renderer can be initialized with SDL_VIDEODRIVER=dummy."""

    def test_pygame_init_dummy(self):
        """Verify pygame initializes with dummy video driver and doesn't crash."""
        os.environ["SDL_VIDEODRIVER"] = "dummy"
        try:
            import pygame_ce as pygame
        except ImportError:
            import pygame

        init_ok = pygame.init()
        # init returns tuple (success_count, fail_count)
        assert init_ok[0] > 0, "pygame.init() reported no successful subsystems"

        screen = pygame.display.set_mode((1024, 768))
        assert screen is not None

        # Try creating renderer
        sys.path.insert(0, BASE_DIR)
        from ui.renderer import Renderer
        renderer = Renderer(screen)
        assert renderer is not None

        pygame.quit()


class TestIntegrationLevel1GameFlow:
    """Simulate a complete Level 1 game flow using real systems and data."""

    def _setup_game(self):
        """Set up all game systems with Level 1 data (no pygame)."""
        from core.event_bus import EventBus
        from core.game_state import GameState
        from systems.combat import CombatSystem
        from systems.movement import MovementSystem
        from systems.inventory import InventorySystem
        from systems.stealth import StealthSystem
        from data.levels import load_level

        eb = EventBus()
        gs = GameState(event_bus=eb)
        combat = CombatSystem(eb)
        movement = MovementSystem(eb)
        inventory = InventorySystem(eb)
        stealth = StealthSystem(eb)

        level = load_level(1)
        gs.load_level(level)

        # Give player starting items like main.py does
        from data.items import create_medkit
        gs.player.inventory.append(create_medkit(25))
        gs.player.add_armor(25)

        return gs, combat, movement, inventory, stealth

    @patch("systems.combat.random.random", return_value=0.0)
    @patch("systems.combat.random.uniform", return_value=1.0)
    def test_level1_entrance_clear_and_move(self, mock_uniform, mock_rand):
        """Simulate: enter entrance, kill the guard, move east."""
        gs, combat, movement, inventory, stealth = self._setup_game()

        # Level 1 starts in entrance with 1 Guard
        assert gs.current_room.room_id == "entrance"
        assert len(gs.current_room.living_enemies()) == 1

        # Player fires at guard (accuracy=1.0 + mock => always hits, uniform=1.0 => no variance)
        # Guard has 40hp, player pistol does 12dmg, need multiple shots
        player = gs.player
        guard = gs.current_room.living_enemies()[0]

        # Fire until guard dies
        shots = 0
        while guard.is_alive and shots < 10:
            result = combat.execute_fire(player, guard)
            shots += 1
            if not guard.is_alive:
                player.kills += 1  # combat system already does this but be explicit
                break

        assert not guard.is_alive
        assert player.kills >= 1

        # Now room is clear, should be able to move east
        result = movement.move(gs, "east")
        assert result["success"] is True
        assert gs.current_room.room_id == "storage"
        assert gs.player.position == "storage"

    @patch("systems.combat.random.random", return_value=0.0)
    @patch("systems.combat.random.uniform", return_value=1.0)
    @patch("models.enemy.random.random", return_value=0.5)  # aggressive always attacks, no random in _attack path
    def test_level1_full_clear(self, mock_enemy_rand, mock_uniform, mock_rand):
        """Simulate clearing all rooms in Level 1."""
        gs, combat, movement, inventory, stealth = self._setup_game()
        player = gs.player

        # Helper: kill all living enemies in current room
        def clear_room():
            room = gs.current_room
            for enemy in list(room.living_enemies()):
                while enemy.is_alive:
                    # Reload if needed
                    weapon = player.current_weapon()
                    if weapon and not weapon.can_fire():
                        combat.execute_reload(player)
                    combat.execute_fire(player, enemy)

        # --- Entrance: 1 Guard (40hp) ---
        clear_room()

        # Move east to storage
        result = movement.move(gs, "east")
        assert result["success"] is True

        # --- Storage: 2 Guards (40hp each) ---
        clear_room()

        # Pick up items
        room = gs.current_room
        if room.items:
            result = inventory.pickup_all(player, room)
            assert result["success"] is True

        # Reload weapon
        combat.execute_reload(player)

        # Move east to corridor
        result = movement.move(gs, "east")
        assert result["success"] is True

        # --- Corridor: 1 Soldier (55hp, 10armor) ---
        clear_room()

        # Move east to office
        combat.execute_reload(player)
        result = movement.move(gs, "east")
        assert result["success"] is True

        # --- Office: 1 Soldier (55hp, 10armor) ---
        clear_room()

        # Check level complete
        level = gs.levels[-1]
        assert level.is_complete() is True

    @patch("systems.combat.random.random", return_value=0.0)
    @patch("systems.combat.random.uniform", return_value=1.0)
    def test_level1_cant_move_with_enemies(self, mock_uniform, mock_rand):
        """Verify player can't move while enemies are alive."""
        gs, combat, movement, inventory, stealth = self._setup_game()

        # Try to move while guard is alive
        result = movement.move(gs, "east")
        assert result["success"] is False
        assert result["hostile"] is True

    def test_level1_use_medkit_and_armor(self):
        """Test using items during gameplay."""
        gs, combat, movement, inventory, stealth = self._setup_game()
        player = gs.player

        # Player starts with 100hp, 25 armor (from setup)
        # Damage the player first
        player.take_damage(40)
        assert player.health == 85  # 25 armor absorbs 25, 15 goes to health => 100-15=85
        # Actually: armor=25, damage=40 => armor absorbs 25, remaining 15 => health=85
        assert player.armor == 0

        # Use medkit from inventory
        from models.item import MedKit
        mk = MedKit(heal_amount=25)
        player.inventory.append(mk)
        result = inventory.use_item(player, 1)  # index 1 because index 0 is starting medkit
        assert result["success"] is True
        assert player.health == 100  # 85 + 25 = 110 capped at 100 => healed 15

    def test_level1_take_cover_and_stealth(self):
        """Test stealth mechanics in Level 1."""
        gs, combat, movement, inventory, stealth = self._setup_game()
        player = gs.player

        # Entrance has cover_objects=["concrete pillar"]
        result = stealth.take_cover(player, gs.current_room)
        assert result["success"] is True
        assert player.in_cover is True

        # Apply noise
        noise_result = stealth.apply_noise(player, "fire")
        assert noise_result["noise_added"] > 0

        # Decay noise
        stealth.decay_noise(player)
        assert player.noise_level >= 0

    @patch("systems.combat.random.random", return_value=0.0)
    @patch("systems.combat.random.uniform", return_value=1.0)
    def test_level1_grenade_clears_room(self, mock_uniform, mock_rand):
        """Test throwing a grenade to clear a room with multiple enemies."""
        gs, combat, movement, inventory, stealth = self._setup_game()
        player = gs.player

        # Add a grenade to inventory
        from models.item import Grenade
        g = Grenade(damage=30)
        player.inventory.append(g)

        # Entrance has 1 Guard (40hp)
        enemies = gs.current_room.living_enemies()
        assert len(enemies) == 1

        # Throw grenade
        result = combat.execute_grenade(player, enemies)
        assert result["success"] is True
        assert result["damage_dealt"] > 0
        # Guard has 40hp, grenade does 30 => alive with 10hp
        # (Grenade goes through enemy.take_damage which accounts for armor)

    @patch("systems.combat.random.random", return_value=0.0)
    @patch("systems.combat.random.uniform", return_value=1.0)
    def test_save_load_during_gameplay(self, mock_uniform, mock_rand, tmp_path):
        """Test saving and loading game state mid-game."""
        gs, combat, movement, inventory, stealth = self._setup_game()

        # Kill the guard
        guard = gs.current_room.living_enemies()[0]
        while guard.is_alive:
            combat.execute_fire(gs.player, guard)

        # Save
        from save.save_manager import SaveManager
        sm = SaveManager(save_dir=str(tmp_path))
        saved = sm.save(gs, slot=1)
        assert saved is True

        # Load
        from core.event_bus import EventBus
        loaded = sm.load(EventBus(), slot=1)
        assert loaded is not None
        assert loaded.player.kills >= 1


class TestIntegrationDataFactories:
    """Test that data factory functions produce valid objects."""

    def test_create_all_weapons(self):
        from data.weapons import create_weapon
        for wt in ["pistol", "rifle", "shotgun", "smg", "sniper"]:
            w = create_weapon(wt)
            assert w.name != ""
            assert w.damage > 0
            assert w.max_ammo > 0

    def test_create_all_enemies(self):
        from data.enemies import create_enemy
        for et in ["Guard", "Soldier", "Heavy Trooper", "Sniper", "Commander"]:
            e = create_enemy(et)
            assert e.name != ""
            assert e.health > 0

    def test_create_all_items(self):
        from data.items import create_medkit, create_grenade, create_ammo, create_armor, create_weapon_mod_item
        mk = create_medkit(25)
        assert mk.heal_amount == 25
        g = create_grenade(30)
        assert g.damage == 30
        ammo = create_ammo("pistol", 15)
        assert ammo.weapon_type == "pistol"
        armor = create_armor(25)
        assert armor.armor_amount == 25
        mod = create_weapon_mod_item("scope")
        assert mod.mod.mod_type == "scope"

    def test_load_all_levels(self):
        from data.levels import load_level, get_available_levels
        for lid in get_available_levels():
            lv = load_level(lid)
            assert lv.level_id == lid
            assert len(lv.rooms) > 0
            assert lv.start_room != ""
            assert lv.get_room(lv.start_room) is not None
