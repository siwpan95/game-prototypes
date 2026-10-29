"""Weapon and WeaponMod models."""
import random
from typing import Dict, List, Optional


class WeaponMod:
    """A modification that can be attached to a weapon."""

    def __init__(
        self,
        name: str = "Mod",
        mod_type: str = "silencer",
        accuracy_bonus: float = 0.0,
        damage_bonus: int = 0,
        ammo_bonus: int = 0,
        noise_modifier: int = 0,
    ) -> None:
        self.name: str = name
        self.mod_type: str = mod_type
        self.accuracy_bonus: float = accuracy_bonus
        self.damage_bonus: int = damage_bonus
        self.ammo_bonus: int = ammo_bonus
        self.noise_modifier: int = noise_modifier

    def to_dict(self) -> dict:
        """Serialize to dict."""
        return {
            "name": self.name,
            "mod_type": self.mod_type,
            "accuracy_bonus": self.accuracy_bonus,
            "damage_bonus": self.damage_bonus,
            "ammo_bonus": self.ammo_bonus,
            "noise_modifier": self.noise_modifier,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "WeaponMod":
        """Deserialize from dict."""
        return cls(
            name=data.get("name", "Mod"),
            mod_type=data.get("mod_type", "silencer"),
            accuracy_bonus=data.get("accuracy_bonus", 0.0),
            damage_bonus=data.get("damage_bonus", 0),
            ammo_bonus=data.get("ammo_bonus", 0),
            noise_modifier=data.get("noise_modifier", 0),
        )


class Weapon:
    """A weapon with stats, mods, and firing logic."""

    MAX_MOD_SLOTS = 3

    def __init__(
        self,
        name: str = "Pistol",
        weapon_type: str = "pistol",
        damage: int = 12,
        accuracy: float = 0.75,
        fire_rate: int = 1,
        ammo: int = 15,
        max_ammo: int = 15,
        base_noise: int = 3,
    ) -> None:
        self.name: str = name
        self.weapon_type: str = weapon_type
        self.damage: int = damage
        self.accuracy: float = accuracy
        self.fire_rate: int = fire_rate
        self.ammo: int = ammo
        self.max_ammo: int = max_ammo
        self.base_noise: int = base_noise
        self.mods: List[WeaponMod] = []

    def fire(self) -> dict:
        """Fire the weapon. Returns result dict."""
        if not self.can_fire():
            return {
                "hit": False,
                "damage": 0,
                "ammo_remaining": self.ammo,
                "message": f"{self.name} has no ammo! Need to reload.",
            }

        self.ammo -= 1
        effective_acc = self.effective_accuracy()
        hit = random.random() < effective_acc

        if hit:
            dmg = self.effective_damage()
            return {
                "hit": True,
                "damage": dmg,
                "ammo_remaining": self.ammo,
                "message": f"{self.name} hits for {dmg} damage!",
            }
        return {
            "hit": False,
            "damage": 0,
            "ammo_remaining": self.ammo,
            "message": f"{self.name} misses!",
        }

    def reload(self, max_ammo_override: Optional[int] = None) -> dict:
        """Reload the weapon to max ammo. Returns reload result."""
        cap = max_ammo_override if max_ammo_override is not None else self.effective_max_ammo()
        old_ammo = self.ammo
        self.ammo = cap
        return {
            "reloaded": True,
            "ammo_before": old_ammo,
            "ammo_after": self.ammo,
            "message": f"{self.name} reloaded. {old_ammo} -> {self.ammo}",
        }

    def can_fire(self) -> bool:
        """Check if the weapon has ammo."""
        return self.ammo > 0

    def add_mod(self, mod: WeaponMod) -> bool:
        """Attach a mod if a slot is available."""
        if len(self.mods) >= self.MAX_MOD_SLOTS:
            return False
        self.mods.append(mod)
        return True

    def remove_mod(self, mod_type: str) -> Optional[WeaponMod]:
        """Remove a mod by type. Returns the removed mod or None."""
        for i, mod in enumerate(self.mods):
            if mod.mod_type == mod_type:
                return self.mods.pop(i)
        return None

    def effective_accuracy(self) -> float:
        """Calculate accuracy including mods."""
        total = self.accuracy + sum(m.accuracy_bonus for m in self.mods)
        return min(1.0, max(0.0, total))

    def effective_damage(self) -> int:
        """Calculate damage including mods."""
        return self.damage + sum(m.damage_bonus for m in self.mods)

    def effective_max_ammo(self) -> int:
        """Calculate max ammo including mods."""
        return self.max_ammo + sum(m.ammo_bonus for m in self.mods)

    def noise_generated(self) -> int:
        """Calculate noise level including mods."""
        total = self.base_noise + sum(m.noise_modifier for m in self.mods)
        return max(0, total)

    def to_dict(self) -> dict:
        """Serialize weapon to dict."""
        return {
            "name": self.name,
            "weapon_type": self.weapon_type,
            "damage": self.damage,
            "accuracy": self.accuracy,
            "fire_rate": self.fire_rate,
            "ammo": self.ammo,
            "max_ammo": self.max_ammo,
            "base_noise": self.base_noise,
            "mods": [m.to_dict() for m in self.mods],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Weapon":
        """Deserialize weapon from dict."""
        w = cls(
            name=data.get("name", "Pistol"),
            weapon_type=data.get("weapon_type", "pistol"),
            damage=data.get("damage", 12),
            accuracy=data.get("accuracy", 0.75),
            fire_rate=data.get("fire_rate", 1),
            ammo=data.get("ammo", 15),
            max_ammo=data.get("max_ammo", 15),
            base_noise=data.get("base_noise", 3),
        )
        w.mods = [WeaponMod.from_dict(m) for m in data.get("mods", [])]
        return w
