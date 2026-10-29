"""Item data definitions."""
from typing import List

from models.item import (
    Item, MedKit, Grenade, AmmoPickup, ArmorPickup, WeaponModItem,
)
from models.weapon import WeaponMod
from data.weapons import create_mod


def get_all_items() -> List[Item]:
    """Return all item templates."""
    return [
        MedKit(name="MedKit", heal_amount=25),
        MedKit(name="Large MedKit", heal_amount=50),
        Grenade(name="Grenade", damage=30),
        ArmorPickup(name="Armor Plate", armor_amount=25),
        AmmoPickup(name="Pistol Ammo", amount=15, weapon_type="pistol"),
        AmmoPickup(name="Rifle Ammo", amount=30, weapon_type="rifle"),
        AmmoPickup(name="Shotgun Shells", amount=8, weapon_type="shotgun"),
        WeaponModItem(name="Silencer", mod=create_mod("silencer")),
        WeaponModItem(name="Red Dot Scope", mod=create_mod("scope")),
        WeaponModItem(name="Extended Magazine", mod=create_mod("extended_mag")),
    ]


def create_medkit(heal_amount: int = 25) -> MedKit:
    """Create a MedKit."""
    name = "Large MedKit" if heal_amount >= 50 else "MedKit"
    return MedKit(name=name, heal_amount=heal_amount)


def create_grenade(damage: int = 30) -> Grenade:
    """Create a Grenade."""
    return Grenade(damage=damage)


def create_ammo(weapon_type: str, amount: int = 15) -> AmmoPickup:
    """Create an AmmoPickup."""
    names = {
        "pistol": "Pistol Ammo",
        "rifle": "Rifle Ammo",
        "shotgun": "Shotgun Shells",
        "smg": "SMG Ammo",
        "sniper": "Sniper Ammo",
    }
    name = names.get(weapon_type, "Ammo")
    return AmmoPickup(name=name, amount=amount, weapon_type=weapon_type)


def create_armor(armor_amount: int = 25) -> ArmorPickup:
    """Create an ArmorPickup."""
    return ArmorPickup(armor_amount=armor_amount)


def create_weapon_mod_item(mod_type: str) -> WeaponModItem:
    """Create a WeaponModItem."""
    mod = create_mod(mod_type)
    return WeaponModItem(name=mod.name, mod=mod)
