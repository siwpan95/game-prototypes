"""CombatSystem - Turn-based combat logic."""
import random
from typing import List

from core.event_bus import EventBus
from core.constants import AIM_BONUS
from models.player import Player
from models.enemy import Enemy
from models.weapon import Weapon
from models.item import Grenade


class CombatSystem:
    """Core combat system handling player attacks, enemy turns, and damage."""

    def __init__(self, event_bus: EventBus) -> None:
        self.event_bus = event_bus

    def execute_fire(self, player: Player, target: Enemy) -> dict:
        """Player fires at an enemy target.

        Returns dict with success, hit, damage, message, enemy_alive.
        """
        weapon = player.current_weapon()
        if weapon is None:
            return {
                "success": False,
                "hit": False,
                "damage": 0,
                "message": "You have no weapon equipped!",
                "enemy_alive": target.is_alive,
            }

        if not weapon.can_fire():
            return {
                "success": False,
                "hit": False,
                "damage": 0,
                "message": f"{weapon.name} has no ammo! Need to reload.",
                "enemy_alive": target.is_alive,
            }

        # Consume ammo
        weapon.ammo -= 1
        player.shots_fired += 1

        # Calculate hit chance
        hit_chance = weapon.effective_accuracy()
        if player.is_aiming:
            hit_chance += AIM_BONUS
        hit_chance = min(1.0, hit_chance)

        # Roll to hit
        if random.random() < hit_chance:
            damage = self.calculate_damage(weapon, target.armor)
            target.take_damage(damage)

            # Reset aiming
            player.is_aiming = False

            msg = f"You hit {target.name} for {damage} damage!"
            if not target.is_alive:
                player.kills += 1
                msg += f" {target.name} is eliminated!"

            self.event_bus.publish("combat.fire", {
                "player": player.name,
                "target": target.name,
                "hit": True,
                "damage": damage,
            })

            return {
                "success": True,
                "hit": True,
                "damage": damage,
                "message": msg,
                "enemy_alive": target.is_alive,
            }
        else:
            player.is_aiming = False
            msg = f"You fire at {target.name} but miss!"

            self.event_bus.publish("combat.fire", {
                "player": player.name,
                "target": target.name,
                "hit": False,
                "damage": 0,
            })

            return {
                "success": True,
                "hit": False,
                "damage": 0,
                "message": msg,
                "enemy_alive": target.is_alive,
            }

    def execute_aim(self, player: Player) -> dict:
        """Player aims for a more accurate shot next turn."""
        player.is_aiming = True
        return {
            "success": True,
            "message": "You steady your aim... (+25% accuracy next shot)",
        }

    def execute_reload(self, player: Player) -> dict:
        """Reload the current weapon to full ammo."""
        weapon = player.current_weapon()
        if weapon is None:
            return {
                "success": False,
                "message": "No weapon to reload.",
                "ammo": 0,
            }

        result = weapon.reload()
        return {
            "success": True,
            "message": result["message"],
            "ammo": weapon.ammo,
        }

    def execute_grenade(self, player: Player, enemies: List[Enemy]) -> dict:
        """Throw a grenade, dealing area damage to all living enemies."""
        # Find grenade in inventory
        grenade_item = None
        grenade_idx = -1
        for i, item in enumerate(player.inventory):
            if isinstance(item, Grenade):
                grenade_item = item
                grenade_idx = i
                break

        if grenade_item is None:
            return {
                "success": False,
                "message": "You don't have a grenade!",
                "damage_dealt": 0,
                "killed": [],
            }

        # Deal damage to all living enemies
        total_damage = 0
        hit_count = 0
        killed: List[Enemy] = []
        for enemy in enemies:
            if enemy.is_alive:
                dealt = enemy.take_damage(grenade_item.damage)
                total_damage += dealt
                hit_count += 1
                if not enemy.is_alive:
                    killed.append(enemy)
                    player.kills += 1

        # Remove grenade from inventory
        player.inventory.pop(grenade_idx)

        msg = f"You throw a grenade! Hit {hit_count} enemies for {total_damage} total damage."
        if killed:
            msg += f" Killed: {', '.join(e.name for e in killed)}!"

        self.event_bus.publish("combat.grenade", {
            "damage": total_damage,
            "killed": [e.name for e in killed],
        })

        return {
            "success": True,
            "message": msg,
            "damage_dealt": total_damage,
            "killed": killed,
        }

    def calculate_damage(self, weapon: Weapon, target_armor: int) -> int:
        """Calculate actual damage with ±20% variance and armor absorption."""
        base = weapon.effective_damage()
        # ±20% random variance
        variance = random.uniform(0.8, 1.2)
        base = int(base * variance)
        # Armor absorption
        armor_absorb = min(target_armor, base)
        return base - armor_absorb

    def execute_enemy_turn(
        self, enemies: List[Enemy], player: Player, room
    ) -> List[dict]:
        """All living enemies take their turns.

        If player is in cover, enemy accuracy is reduced by 0.20.
        Returns list of action result dicts.
        """
        results: List[dict] = []

        for enemy in enemies:
            if not enemy.is_alive:
                continue

            # Temporarily reduce accuracy if player is in cover
            original_accuracy = enemy.accuracy
            if player.in_cover:
                enemy.accuracy = max(0.05, enemy.accuracy - 0.20)

            result = enemy.act(player, room)

            # Restore original accuracy
            enemy.accuracy = original_accuracy

            # Tag with enemy name for UI
            result["enemy_name"] = enemy.name
            results.append(result)

            # Stop if player dies
            if not player.is_alive():
                break

        return results
