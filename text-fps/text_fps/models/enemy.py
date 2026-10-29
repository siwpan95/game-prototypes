"""Enemy model."""
import random
from typing import Dict, List, Optional

from models.item import Item


class Enemy:
    """An enemy entity with behavior patterns and combat stats."""

    def __init__(
        self,
        name: str = "Enemy",
        health: int = 40,
        armor: int = 0,
        damage: int = 8,
        accuracy: float = 0.5,
        behavior: str = "patrol",
        is_boss: bool = False,
        loot: Optional[List[Item]] = None,
    ) -> None:
        self.name: str = name
        self.health: int = health
        self.max_health: int = health
        self.armor: int = armor
        self.damage: int = damage
        self.accuracy: float = accuracy
        self.behavior: str = behavior
        self.is_alive: bool = True
        self.loot: List[Item] = loot if loot is not None else []
        self.is_boss: bool = is_boss
        self.phase: int = 0

    def act(self, player, room) -> dict:
        """Determine and execute enemy action. Returns action dict."""
        if not self.is_alive:
            return {"action": "dead", "damage": 0, "message": f"{self.name} is dead."}

        if self.behavior == "patrol":
            return self._act_patrol(player, room)
        elif self.behavior == "aggressive":
            return self._act_aggressive(player, room)
        elif self.behavior == "boss":
            return self._act_boss(player, room)
        return {"action": "idle", "damage": 0, "message": f"{self.name} does nothing."}

    def _act_patrol(self, player, room) -> dict:
        """Patrol behavior: 60% chance to attack, 40% to patrol."""
        if random.random() < 0.6:
            return self._attack(player)
        return {
            "action": "patrol",
            "damage": 0,
            "message": f"{self.name} is patrolling and hasn't noticed you.",
        }

    def _act_aggressive(self, player, room) -> dict:
        """Aggressive behavior: always attacks."""
        return self._attack(player)

    def _act_boss(self, player, room) -> dict:
        """Boss behavior: switches phase based on health ratio."""
        health_ratio = self.health / self.max_health
        if health_ratio <= 0.3 and self.phase < 2:
            self.phase = 2
            return {
                "action": "phase_shift",
                "damage": 0,
                "message": f"{self.name} enters a berserk rage! Phase 2!",
            }
        elif health_ratio <= 0.6 and self.phase < 1:
            self.phase = 1
            return {
                "action": "phase_shift",
                "damage": 0,
                "message": f"{self.name} becomes more aggressive! Phase 1!",
            }

        # Boss attacks with bonus damage based on phase
        bonus = self.phase * 5
        return self._attack(player, damage_bonus=bonus)

    def _attack(self, player, damage_bonus: int = 0) -> dict:
        """Attempt to attack the player."""
        if random.random() < self.accuracy:
            total_damage = self.damage + damage_bonus
            actual = player.take_damage(total_damage)
            return {
                "action": "attack",
                "damage": actual,
                "message": f"{self.name} hits you for {actual} damage!",
            }
        return {
            "action": "miss",
            "damage": 0,
            "message": f"{self.name} attacks but misses!",
        }

    def take_damage(self, amount: int) -> int:
        """Apply damage to enemy. Returns health damage dealt."""
        if amount <= 0:
            return 0
        armor_absorb = min(self.armor, amount)
        self.armor -= armor_absorb
        remaining = amount - armor_absorb
        self.health = max(0, self.health - remaining)
        self.check_alive()
        return remaining

    def check_alive(self) -> bool:
        """Check and update alive status."""
        if self.health <= 0:
            self.is_alive = False
        return self.is_alive

    def to_dict(self) -> dict:
        """Serialize enemy to dict."""
        return {
            "name": self.name,
            "health": self.health,
            "max_health": self.max_health,
            "armor": self.armor,
            "damage": self.damage,
            "accuracy": self.accuracy,
            "behavior": self.behavior,
            "is_alive": self.is_alive,
            "loot": [i.to_dict() for i in self.loot],
            "is_boss": self.is_boss,
            "phase": self.phase,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Enemy":
        """Deserialize enemy from dict."""
        e = cls(
            name=data.get("name", "Enemy"),
            health=data.get("health", 40),
            armor=data.get("armor", 0),
            damage=data.get("damage", 8),
            accuracy=data.get("accuracy", 0.5),
            behavior=data.get("behavior", "patrol"),
            is_boss=data.get("is_boss", False),
            loot=[Item.from_dict(i) for i in data.get("loot", [])],
        )
        e.max_health = data.get("max_health", e.health)
        e.is_alive = data.get("is_alive", True)
        e.phase = data.get("phase", 0)
        return e
