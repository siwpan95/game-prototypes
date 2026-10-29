"""Item data definitions."""
from typing import List

from models.item import (
    Item, MedKit, Grenade, AmmoPickup, ArmorPickup, WeaponModItem,
    Flashbang, BreachingCharge, Stim, HeavyArmor,
)
from models.weapon import WeaponMod
from data.weapons import create_mod


def get_all_items() -> List[Item]:
    """Return all item templates."""
    return [
        MedKit(name="医疗包", heal_amount=25),
        MedKit(name="大型医疗包", heal_amount=50),
        Grenade(name="手雷", damage=30),
        ArmorPickup(name="护甲板", armor_amount=25),
        HeavyArmor(name="重甲板", armor_amount=50),
        AmmoPickup(name="手枪弹药", amount=15, weapon_type="pistol"),
        AmmoPickup(name="步枪弹药", amount=30, weapon_type="rifle"),
        AmmoPickup(name="霰弹枪弹药", amount=8, weapon_type="shotgun"),
        WeaponModItem(name="消音器", mod=create_mod("silencer")),
        WeaponModItem(name="红点瞄准镜", mod=create_mod("scope")),
        WeaponModItem(name="扩容弹匣", mod=create_mod("extended_mag")),
        # --- New ballistics-grounded ammo loads & tactical items ---
        WeaponModItem(name="穿甲弹", mod=create_mod("ap_rounds")),
        WeaponModItem(name="空尖弹", mod=create_mod("hollow_point")),
        WeaponModItem(name="比赛级弹药", mod=create_mod("match_grade")),
        Flashbang(name="闪光弹", duration=2),
        BreachingCharge(name="破门炸药", damage=45),
        Stim(name="兴奋剂", heal_amount=25, buff_turns=3),
    ]


def create_medkit(heal_amount: int = 25) -> MedKit:
    """Create a MedKit."""
    name = "大型医疗包" if heal_amount >= 50 else "医疗包"
    return MedKit(name=name, heal_amount=heal_amount)


def create_grenade(damage: int = 30) -> Grenade:
    """Create a Grenade."""
    return Grenade(damage=damage)


def create_ammo(weapon_type: str, amount: int = 15) -> AmmoPickup:
    """Create an AmmoPickup."""
    names = {
        "pistol": "手枪弹药",
        "rifle": "步枪弹药",
        "shotgun": "霰弹枪弹药",
        "smg": "冲锋枪弹药",
        "sniper": "狙击枪弹药",
    }
    name = names.get(weapon_type, "弹药")
    return AmmoPickup(name=name, amount=amount, weapon_type=weapon_type)


def create_armor(armor_amount: int = 25) -> ArmorPickup:
    """Create an ArmorPickup."""
    return ArmorPickup(armor_amount=armor_amount)


def create_heavy_armor(armor_amount: int = 50) -> HeavyArmor:
    """Create a HeavyArmor plate."""
    return HeavyArmor(armor_amount=armor_amount)


def create_flashbang(duration: int = 2) -> Flashbang:
    """Create a Flashbang."""
    return Flashbang(duration=duration)


def create_breaching_charge(damage: int = 45) -> BreachingCharge:
    """Create a BreachingCharge."""
    return BreachingCharge(damage=damage)


def create_stim(heal_amount: int = 25, buff_turns: int = 3) -> Stim:
    """Create a Stim."""
    return Stim(heal_amount=heal_amount, buff_turns=buff_turns)


def create_weapon_mod_item(mod_type: str) -> WeaponModItem:
    """Create a WeaponModItem."""
    mod = create_mod(mod_type)
    return WeaponModItem(name=mod.name, mod=mod)
