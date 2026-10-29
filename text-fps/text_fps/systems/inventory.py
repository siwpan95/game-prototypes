"""InventorySystem - Player inventory management."""
from typing import List, Optional

from core.event_bus import EventBus
from models.player import Player
from models.room import Room
from models.item import Item, Grenade, WeaponModItem


MAX_INVENTORY_SIZE = 10


class InventorySystem:
    """Manages player inventory: pickup, use, drop, switch weapons."""

    def __init__(self, event_bus: EventBus) -> None:
        self.event_bus = event_bus

    def pickup(self, player: Player, room: Room, item_index: int) -> dict:
        """Pick up an item from the room by index.

        Returns dict with success, message.
        """
        if item_index < 0 or item_index >= len(room.items):
            return {
                "success": False,
                "message": "Invalid item index.",
            }

        if len(player.inventory) >= MAX_INVENTORY_SIZE:
            return {
                "success": False,
                "message": "Inventory full! (10/10)",
            }

        item = room.items[item_index]
        room.remove_item(item)
        player.inventory.append(item)

        self.event_bus.publish("inventory.pickup", {
            "item": item.name,
            "item_type": item.item_type,
        })

        return {
            "success": True,
            "message": f"Picked up {item.name}.",
        }

    def pickup_all(self, player: Player, room: Room) -> dict:
        """Pick up all items from the room.

        Returns dict with success, message, count.
        """
        if len(room.items) == 0:
            return {
                "success": False,
                "message": "Nothing to pick up here.",
                "count": 0,
            }

        picked = 0
        messages = []
        # Iterate over a copy since we modify the list
        items_to_pickup = list(room.items)
        for item in items_to_pickup:
            if len(player.inventory) >= MAX_INVENTORY_SIZE:
                messages.append("Inventory full — some items left behind.")
                break
            room.remove_item(item)
            player.inventory.append(item)
            picked += 1

        self.event_bus.publish("inventory.pickup", {
            "count": picked,
        })

        msg = f"Picked up {picked} item(s)." if picked > 0 else "No items picked up."
        if messages:
            msg += " " + " ".join(messages)

        return {
            "success": picked > 0,
            "message": msg,
            "count": picked,
        }

    def use_item(
        self,
        player: Player,
        item_index: int,
        combat_system=None,
        enemies: Optional[List] = None,
    ) -> dict:
        """Use an item from inventory by index.

        For Grenades, pass combat_system and enemies.
        Returns dict with success, message.
        """
        if item_index < 0 or item_index >= len(player.inventory):
            return {
                "success": False,
                "message": "Invalid item index.",
            }

        item = player.inventory[item_index]

        if not item.usable:
            return {
                "success": False,
                "message": f"Cannot use {item.name}.",
            }

        # Handle different item types
        if isinstance(item, Grenade):
            if combat_system is None:
                return {
                    "success": False,
                    "message": "Cannot throw grenade right now.",
                }
            # Use combat system's grenade execution
            result = combat_system.execute_grenade(player, enemies or [])
            return result

        elif isinstance(item, WeaponModItem):
            weapon = player.current_weapon()
            if weapon is None:
                return {
                    "success": False,
                    "message": "No weapon to attach mod to.",
                }
            if weapon.add_mod(item.mod):
                player.inventory.pop(item_index)
                return {
                    "success": True,
                    "message": f"Attached {item.name} to {weapon.name}!",
                }
            return {
                "success": False,
                "message": f"Cannot attach {item.name} — all mod slots full.",
            }

        else:
            # MedKit, ArmorPickup, AmmoPickup — use directly
            msg = item.use(player)
            player.inventory.pop(item_index)
            self.event_bus.publish("inventory.use", {
                "item": item.name,
                "item_type": item.item_type,
            })
            return {
                "success": True,
                "message": msg,
            }

    def switch_weapon(self, player: Player, direction: int = 1) -> dict:
        """Switch to next/previous weapon. direction=1 for next, -1 for prev.

        Returns dict with success, message.
        """
        if len(player.weapons) <= 1:
            return {
                "success": False,
                "message": "Only one weapon equipped.",
            }

        player.current_weapon_idx = (
            (player.current_weapon_idx + direction) % len(player.weapons)
        )
        weapon = player.current_weapon()

        self.event_bus.publish("inventory.switch_weapon", {
            "weapon": weapon.name if weapon else "",
        })

        return {
            "success": True,
            "message": f"Switched to {weapon.name} ({weapon.ammo}/{weapon.effective_max_ammo()})" if weapon else "No weapon.",
        }

    def modify_weapon(self, player: Player, mod_item_index: int) -> dict:
        """Attach a WeaponModItem from inventory to the current weapon.

        Returns dict with success, message.
        """
        if mod_item_index < 0 or mod_item_index >= len(player.inventory):
            return {
                "success": False,
                "message": "Invalid item index.",
            }

        item = player.inventory[mod_item_index]
        if not isinstance(item, WeaponModItem):
            return {
                "success": False,
                "message": f"{item.name} is not a weapon mod.",
            }

        weapon = player.current_weapon()
        if weapon is None:
            return {
                "success": False,
                "message": "No weapon to modify.",
            }

        if weapon.add_mod(item.mod):
            player.inventory.pop(mod_item_index)
            return {
                "success": True,
                "message": f"Attached {item.name} to {weapon.name}!",
            }

        return {
            "success": False,
            "message": f"Cannot attach {item.name} — all mod slots full on {weapon.name}.",
        }

    def drop_item(self, player: Player, item_index: int, room: Room) -> dict:
        """Drop an item from inventory into the current room.

        Returns dict with success, message.
        """
        if item_index < 0 or item_index >= len(player.inventory):
            return {
                "success": False,
                "message": "Invalid item index.",
            }

        item = player.inventory.pop(item_index)
        room.add_item(item)

        self.event_bus.publish("inventory.drop", {
            "item": item.name,
        })

        return {
            "success": True,
            "message": f"Dropped {item.name}.",
        }
