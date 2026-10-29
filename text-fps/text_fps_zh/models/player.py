"""Player model."""
from typing import Dict, List, Optional

from models.weapon import Weapon
from models.item import Item
from core.constants import MAX_HEALTH, MAX_ARMOR


class Player:
    """Player character with stats, weapons, and inventory."""

    def __init__(self, name: str = "Player") -> None:
        self.name: str = name
        self.health: int = MAX_HEALTH
        self.max_health: int = MAX_HEALTH
        self.armor: int = 0
        self.max_armor: int = MAX_ARMOR
        self.weapons: List[Weapon] = []
        self.current_weapon_idx: int = 0
        self.inventory: List[Item] = []
        self.position: str = ""
        self.kills: int = 0
        self.shots_fired: int = 0
        self.headshots: int = 0
        self.damage_taken: int = 0
        self.noise_level: int = 0
        self.is_aiming: bool = False
        self.in_cover: bool = False
        self.buffs: dict = {}  # transient combat buffs (e.g. stim: acc/dmg/turns)

    def is_alive(self) -> bool:
        """Check if the player is alive."""
        return self.health > 0

    def take_damage(self, amount: int) -> int:
        """Take damage, armor absorbs first. Returns actual health damage."""
        if amount <= 0:
            return 0
        armor_absorb = min(self.armor, amount)
        self.armor -= armor_absorb
        remaining = amount - armor_absorb
        self.health = max(0, self.health - remaining)
        self.damage_taken += amount
        return remaining

    def heal(self, amount: int) -> int:
        """Heal the player. Returns amount actually healed."""
        if amount <= 0:
            return 0
        old_health = self.health
        self.health = min(self.max_health, self.health + amount)
        return self.health - old_health

    def add_armor(self, amount: int) -> int:
        """Add armor. Returns amount actually added."""
        if amount <= 0:
            return 0
        old_armor = self.armor
        self.armor = min(self.max_armor, self.armor + amount)
        return self.armor - old_armor

    def current_weapon(self) -> Optional[Weapon]:
        """Get the currently equipped weapon."""
        if 0 <= self.current_weapon_idx < len(self.weapons):
            return self.weapons[self.current_weapon_idx]
        return None

    def to_dict(self) -> dict:
        """Serialize player to dict."""
        return {
            "name": self.name,
            "health": self.health,
            "max_health": self.max_health,
            "armor": self.armor,
            "max_armor": self.max_armor,
            "weapons": [w.to_dict() for w in self.weapons],
            "current_weapon_idx": self.current_weapon_idx,
            "inventory": [i.to_dict() for i in self.inventory],
            "position": self.position,
            "kills": self.kills,
            "shots_fired": self.shots_fired,
            "headshots": self.headshots,
            "damage_taken": self.damage_taken,
            "noise_level": self.noise_level,
            "is_aiming": self.is_aiming,
            "in_cover": self.in_cover,
            "buffs": dict(self.buffs),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Player":
        """Deserialize player from dict."""
        p = cls(name=data.get("name", "Player"))
        p.health = data.get("health", MAX_HEALTH)
        p.max_health = data.get("max_health", MAX_HEALTH)
        p.armor = data.get("armor", 0)
        p.max_armor = data.get("max_armor", MAX_ARMOR)
        p.weapons = [Weapon.from_dict(w) for w in data.get("weapons", [])]
        p.current_weapon_idx = data.get("current_weapon_idx", 0)
        p.inventory = [Item.from_dict(i) for i in data.get("inventory", [])]
        p.position = data.get("position", "")
        p.kills = data.get("kills", 0)
        p.shots_fired = data.get("shots_fired", 0)
        p.headshots = data.get("headshots", 0)
        p.damage_taken = data.get("damage_taken", 0)
        p.noise_level = data.get("noise_level", 0)
        p.is_aiming = data.get("is_aiming", False)
        p.in_cover = data.get("in_cover", False)
        p.buffs = data.get("buffs", {})
        return p
