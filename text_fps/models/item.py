"""Item models - collectible and usable items."""
from typing import List, Optional

from models.weapon import WeaponMod


class Item:
    """Base class for all items."""

    def __init__(
        self,
        name: str = "Item",
        item_type: str = "misc",
        description: str = "",
        usable: bool = True,
    ) -> None:
        self.name: str = name
        self.item_type: str = item_type
        self.description: str = description
        self.usable: bool = usable

    def use(self, player) -> str:
        """Use the item. Returns result message."""
        return f"Cannot use {self.name}."

    def to_dict(self) -> dict:
        """Serialize item to dict."""
        return {
            "name": self.name,
            "item_type": self.item_type,
            "description": self.description,
            "usable": self.usable,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Item":
        """Deserialize item from dict. Dispatches to correct subclass."""
        item_type = data.get("item_type", "misc")
        subclass_map = {
            "medkit": MedKit,
            "grenade": Grenade,
            "ammo": AmmoPickup,
            "armor": ArmorPickup,
            "weapon_mod": WeaponModItem,
        }
        target_cls = subclass_map.get(item_type, Item)
        if target_cls is Item:
            return cls(
                name=data.get("name", "Item"),
                item_type=item_type,
                description=data.get("description", ""),
                usable=data.get("usable", True),
            )
        return target_cls._from_dict_impl(data)

    @classmethod
    def _from_dict_impl(cls, data: dict) -> "Item":
        """Internal from_dict for base Item."""
        return cls(
            name=data.get("name", "Item"),
            item_type=data.get("item_type", "misc"),
            description=data.get("description", ""),
            usable=data.get("usable", True),
        )


class MedKit(Item):
    """Healing item."""

    def __init__(self, name: str = "MedKit", heal_amount: int = 25, description: str = "") -> None:
        desc = description or f"Restores {heal_amount} health."
        super().__init__(name=name, item_type="medkit", description=desc, usable=True)
        self.heal_amount: int = heal_amount

    def use(self, player) -> str:
        """Heal the player."""
        healed = player.heal(self.heal_amount)
        if healed > 0:
            return f"Used {self.name}. Restored {healed} health. (HP: {player.health}/{player.max_health})"
        return f"Used {self.name}. No healing needed. (HP: {player.health}/{player.max_health})"

    def to_dict(self) -> dict:
        d = super().to_dict()
        d["heal_amount"] = self.heal_amount
        return d

    @classmethod
    def _from_dict_impl(cls, data: dict) -> "MedKit":
        return cls(
            name=data.get("name", "MedKit"),
            heal_amount=data.get("heal_amount", 25),
            description=data.get("description", ""),
        )


class Grenade(Item):
    """Explosive that damages all enemies in the room."""

    def __init__(self, name: str = "Grenade", damage: int = 30, radius: int = 1, description: str = "") -> None:
        desc = description or f"Deals {damage} damage to all enemies in range."
        super().__init__(name=name, item_type="grenade", description=desc, usable=True)
        self.damage: int = damage
        self.radius: int = radius

    def use(self, player, enemies: Optional[List] = None) -> str:
        """Deal damage to all enemies in range."""
        if enemies is None or len(enemies) == 0:
            return f"Threw {self.name}, but there are no enemies."

        total_damage = 0
        hit_count = 0
        for enemy in enemies:
            if enemy.is_alive:
                dealt = enemy.take_damage(self.damage)
                total_damage += dealt
                hit_count += 1

        return f"Threw {self.name}! Hit {hit_count} enemies for {total_damage} total damage."

    def to_dict(self) -> dict:
        d = super().to_dict()
        d["damage"] = self.damage
        d["radius"] = self.radius
        return d

    @classmethod
    def _from_dict_impl(cls, data: dict) -> "Grenade":
        return cls(
            name=data.get("name", "Grenade"),
            damage=data.get("damage", 30),
            radius=data.get("radius", 1),
            description=data.get("description", ""),
        )


class AmmoPickup(Item):
    """Ammunition pickup for a specific weapon type."""

    def __init__(
        self, name: str = "Pistol Ammo", amount: int = 15,
        weapon_type: str = "pistol", description: str = "",
    ) -> None:
        desc = description or f"Adds {amount} ammo for {weapon_type}."
        super().__init__(name=name, item_type="ammo", description=desc, usable=True)
        self.amount: int = amount
        self.weapon_type: str = weapon_type

    def use(self, player) -> str:
        """Add ammo to matching weapon."""
        for weapon in player.weapons:
            if weapon.weapon_type == self.weapon_type:
                old = weapon.ammo
                weapon.ammo = min(weapon.effective_max_ammo(), weapon.ammo + self.amount)
                added = weapon.ammo - old
                return f"Picked up {self.name}. {weapon.name}: {old} -> {weapon.ammo} ammo."
        return f"Picked up {self.name}, but you don't have a compatible weapon."

    def to_dict(self) -> dict:
        d = super().to_dict()
        d["amount"] = self.amount
        d["weapon_type"] = self.weapon_type
        return d

    @classmethod
    def _from_dict_impl(cls, data: dict) -> "AmmoPickup":
        return cls(
            name=data.get("name", "Pistol Ammo"),
            amount=data.get("amount", 15),
            weapon_type=data.get("weapon_type", "pistol"),
            description=data.get("description", ""),
        )


class ArmorPickup(Item):
    """Armor plate pickup."""

    def __init__(self, name: str = "Armor Plate", armor_amount: int = 25, description: str = "") -> None:
        desc = description or f"Adds {armor_amount} armor."
        super().__init__(name=name, item_type="armor", description=desc, usable=True)
        self.armor_amount: int = armor_amount

    def use(self, player) -> str:
        """Add armor to the player."""
        added = player.add_armor(self.armor_amount)
        return f"Equipped {self.name}. Armor: {player.armor}/{player.max_armor} (+{added})"

    def to_dict(self) -> dict:
        d = super().to_dict()
        d["armor_amount"] = self.armor_amount
        return d

    @classmethod
    def _from_dict_impl(cls, data: dict) -> "ArmorPickup":
        return cls(
            name=data.get("name", "Armor Plate"),
            armor_amount=data.get("armor_amount", 25),
            description=data.get("description", ""),
        )


class WeaponModItem(Item):
    """A weapon modification that can be picked up and auto-equipped."""

    def __init__(self, name: str = "Silencer", mod: Optional[WeaponMod] = None, description: str = "") -> None:
        if mod is None:
            mod = WeaponMod(name=name, mod_type="silencer")
        desc = description or f"Weapon mod: {mod.name} ({mod.mod_type})"
        super().__init__(name=name, item_type="weapon_mod", description=desc, usable=True)
        self.mod: WeaponMod = mod

    def use(self, player) -> str:
        """Auto-equip mod to current weapon."""
        weapon = player.current_weapon()
        if weapon is None:
            return f"Found {self.name}, but you have no weapon to attach it to."

        if weapon.add_mod(self.mod):
            return f"Attached {self.name} to {weapon.name}!"
        return f"Cannot attach {self.name} to {weapon.name} — all mod slots full."

    def to_dict(self) -> dict:
        d = super().to_dict()
        d["mod"] = self.mod.to_dict()
        return d

    @classmethod
    def _from_dict_impl(cls, data: dict) -> "WeaponModItem":
        mod_data = data.get("mod", {})
        mod = WeaponMod.from_dict(mod_data)
        return cls(
            name=data.get("name", mod.name),
            mod=mod,
            description=data.get("description", ""),
        )
