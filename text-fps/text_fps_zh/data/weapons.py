"""Weapon data definitions.

Stats are ballistics-grounded (see the code-review research pass): effective
range in metres and a 0..1 penetration factor mirror how real cartridges trade
muzzle energy / velocity for armor-piercing capability. The 5 original type
keys (pistol/rifle/shotgun/smg/sniper) are preserved so legacy saves and the
existing test matrix keep working; new weapons add extra type keys.
"""
from typing import Dict, List

from models.weapon import Weapon, WeaponMod


def get_all_weapons() -> List[Dict]:
    """Return all weapon template data."""
    return [
        # --- Sidearms (9x19 / .45 ACP) ---
        {"weapon_type": "pistol", "name": "9mm手枪", "damage": 12, "accuracy": 0.80,
         "fire_rate": 1, "max_ammo": 15, "noise": 3, "effective_range": 50,
         "penetration": 0.0, "ammo_type": "9x19mm", "suppression": 0.10},
        {"weapon_type": "pistol_45", "name": ".45手枪", "damage": 15, "accuracy": 0.72,
         "fire_rate": 1, "max_ammo": 7, "noise": 3, "effective_range": 40,
         "penetration": 0.0, "ammo_type": ".45 ACP", "suppression": 0.12},
        # --- PDW / SMG (5.7x28 / 9mm) ---
        {"weapon_type": "pdw", "name": "5.7 PDW", "damage": 11, "accuracy": 0.68,
         "fire_rate": 2, "max_ammo": 20, "noise": 3, "effective_range": 150,
         "penetration": 0.25, "ammo_type": "5.7x28mm", "suppression": 0.18},
        {"weapon_type": "smg", "name": "冲锋枪", "damage": 10, "accuracy": 0.60,
         "fire_rate": 2, "max_ammo": 30, "noise": 4, "effective_range": 80,
         "penetration": 0.0, "ammo_type": "9x19mm", "suppression": 0.22},
        # --- Rifles (5.56x45 / 7.62x39 / 5.45x39 / 5.8x42) ---
        {"weapon_type": "rifle", "name": "突击步枪", "damage": 18, "accuracy": 0.65,
         "fire_rate": 1, "max_ammo": 30, "noise": 4, "effective_range": 400,
         "penetration": 0.05, "ammo_type": "5.56x45mm", "suppression": 0.20},
        {"weapon_type": "ak", "name": "AK式步枪", "damage": 20, "accuracy": 0.58,
         "fire_rate": 1, "max_ammo": 30, "noise": 4, "effective_range": 350,
         "penetration": 0.10, "ammo_type": "7.62x39mm", "suppression": 0.22},
        {"weapon_type": "ak_545", "name": "5.45步枪", "damage": 19, "accuracy": 0.62,
         "fire_rate": 1, "max_ammo": 30, "noise": 4, "effective_range": 400,
         "penetration": 0.08, "ammo_type": "5.45x39mm", "suppression": 0.20},
        {"weapon_type": "rifle_58", "name": "5.8步枪", "damage": 19, "accuracy": 0.66,
         "fire_rate": 1, "max_ammo": 30, "noise": 4, "effective_range": 400,
         "penetration": 0.10, "ammo_type": "5.8x42mm", "suppression": 0.20},
        # --- DMR / Marksman (7.62x51) ---
        {"weapon_type": "dmr", "name": "精确射手步枪", "damage": 26, "accuracy": 0.78,
         "fire_rate": 1, "max_ammo": 20, "noise": 4, "effective_range": 800,
         "penetration": 0.15, "ammo_type": "7.62x51mm", "suppression": 0.16},
        # --- Shotgun (12ga) ---
        {"weapon_type": "shotgun", "name": "霰弹枪", "damage": 30, "accuracy": 0.50,
         "fire_rate": 1, "max_ammo": 8, "noise": 5, "effective_range": 25,
         "penetration": 0.05, "ammo_type": "12号", "suppression": 0.15},
        # --- Sniper / Anti-materiel (.338 Lapua / .50 BMG) ---
        {"weapon_type": "sniper", "name": "狙击步枪", "damage": 45, "accuracy": 0.92,
         "fire_rate": 1, "max_ammo": 5, "noise": 4, "effective_range": 1500,
         "penetration": 0.40, "ammo_type": ".338 Lapua", "suppression": 0.10},
        {"weapon_type": "amr", "name": ".50反器材步枪", "damage": 60, "accuracy": 0.90,
         "fire_rate": 1, "max_ammo": 5, "noise": 6, "effective_range": 1800,
         "penetration": 0.70, "ammo_type": ".50 BMG", "suppression": 0.12},
        # --- LMG (suppressive) ---
        {"weapon_type": "lmg", "name": "轻机枪", "damage": 16, "accuracy": 0.55,
         "fire_rate": 2, "max_ammo": 60, "noise": 5, "effective_range": 400,
         "penetration": 0.05, "ammo_type": "5.56x45mm", "suppression": 0.55},
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
        effective_range=t.get("effective_range", 50),
        penetration=t.get("penetration", 0.0),
        ammo_type=t.get("ammo_type", ""),
        suppression=t.get("suppression", 0.0),
    )


def get_all_mods() -> List[Dict]:
    """Return all weapon mod template data."""
    return [
        {
            "name": "消音器",
            "mod_type": "silencer",
            "accuracy_bonus": 0.0,
            "damage_bonus": 0,
            "ammo_bonus": 0,
            "noise_modifier": -2,
            "penetration_bonus": 0.0,
        },
        {
            "name": "红点瞄准镜",
            "mod_type": "scope",
            "accuracy_bonus": 0.15,
            "damage_bonus": 0,
            "ammo_bonus": 0,
            "noise_modifier": 0,
            "penetration_bonus": 0.0,
        },
        {
            "name": "扩容弹匣",
            "mod_type": "extended_mag",
            "accuracy_bonus": 0.0,
            "damage_bonus": 0,
            "ammo_bonus": 10,
            "noise_modifier": 0,
            "penetration_bonus": 0.0,
        },
        # --- Ballistics-grounded ammo loads (reuse the mod slot) ---
        {
            "name": "穿甲弹",
            "mod_type": "ap_rounds",
            "accuracy_bonus": -0.03,
            "damage_bonus": 0,
            "ammo_bonus": 0,
            "noise_modifier": 0,
            "penetration_bonus": 0.35,
        },
        {
            "name": "空尖弹",
            "mod_type": "hollow_point",
            "accuracy_bonus": 0.0,
            "damage_bonus": 6,
            "ammo_bonus": 0,
            "noise_modifier": 0,
            "penetration_bonus": -0.10,
        },
        {
            "name": "比赛级弹药",
            "mod_type": "match_grade",
            "accuracy_bonus": 0.10,
            "damage_bonus": 0,
            "ammo_bonus": 0,
            "noise_modifier": 0,
            "penetration_bonus": 0.0,
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
        penetration_bonus=t.get("penetration_bonus", 0.0),
    )
