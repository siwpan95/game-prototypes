"""Weapon data definitions."""
from typing import List

from models.weapon import Weapon, WeaponMod


def get_all_weapons() -> List[Dict]:
    """Return all weapon template data."""
    return [
        {"weapon_type": "pistol", "name": "Pistol", "damage": 12, "accuracy": 0.75, "fire_rate": 1, "max_ammo": 15, "noise": 3},
        {"weapon_type": "rifle", "name": "Assault Rifle", "damage": 18, "accuracy": 0.65, "fire_rate": 1, "max_ammo": 30, "noise": 4},
        {"weapon_type": "shotgun", "name": "Shotgun", "damage": 30, "accuracy": 0.50, "fire_rate": 1, "max_ammo": 8, "noise": 5},
        {"weapon_type": "smg", "name": "SMG", "damage": 10, "accuracy": 0.60, "fire_rate": 1, "max_ammo": 25, "noise": 3},
        {"weapon_type": "sniper", "name": "Sniper Rifle", "damage": 35, "accuracy": 0.85, "fire_rate": 1, "max_ammo": 5, "noise": 4},
    ]


def create_weapon(weapon_type: str) -> Weapon:
    """Create a Weapon instance from template data."""
    templates = {w["weapon_type"]: w for w in get_all_weapons()}
    t = templates.get(weapon_type)
    if t is None:
        t = templates["pistol"]
    return Weapon(
        name=t["name"],
        weapon_type=t["weapon_type"],
        damage=t["damage"],
        accuracy=t["accuracy"],
        fire_rate=t["fire_rate"],
        ammo=t["max_ammo"],
        max_ammo=t["max_ammo"],
        base_noise=t["noise"],
    )


def get_all_mods() -> List[Dict]:
    """Return all weapon mod template data."""
    return [
        {
            "name": "Silencer",
            "mod_type": "silencer",
            "accuracy_bonus": 0.0,
            "damage_bonus": 0,
            "ammo_bonus": 0,
            "noise_modifier": -2,
        },
        {
            "name": "Red Dot Scope",
            "mod_type": "scope",
            "accuracy_bonus": 0.15,
            "damage_bonus": 0,
            "ammo_bonus": 0,
            "noise_modifier": 0,
        },
        {
            "name": "Extended Magazine",
            "mod_type": "extended_mag",
            "accuracy_bonus": 0.0,
            "damage_bonus": 0,
            "ammo_bonus": 10,
            "noise_modifier": 0,
        },
    ]


def create_mod(mod_type: str) -> WeaponMod:
    """Create a WeaponMod instance from template data."""
    templates = {m["mod_type"]: m for m in get_all_mods()}
    t = templates.get(mod_type)
    if t is None:
        t = templates["silencer"]
    return WeaponMod(
        name=t["name"],
        mod_type=t["mod_type"],
        accuracy_bonus=t["accuracy_bonus"],
        damage_bonus=t["damage_bonus"],
        ammo_bonus=t["ammo_bonus"],
        noise_modifier=t["noise_modifier"],
    )
