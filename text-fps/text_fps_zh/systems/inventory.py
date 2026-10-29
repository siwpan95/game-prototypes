"""InventorySystem - Player inventory management."""
from typing import TYPE_CHECKING, List, Optional

from core.constants import MAX_INVENTORY
from models.player import Player
from models.room import Room
from models.item import Item, Grenade, WeaponModItem

if TYPE_CHECKING:
    from systems.combat import CombatSystem


class InventorySystem:
    """Manages player inventory: pickup, use, drop, switch weapons."""

    def __init__(self) -> None:
        pass

    def pickup(self, player: Player, room: Room, item_index: int) -> dict:
        """Pick up an item from the room by index.

        Returns dict with success, message.
        """
        if item_index < 0 or item_index >= len(room.items):
            return {
                "success": False,
                "message": "无效的物品编号。",
            }

        if len(player.inventory) >= MAX_INVENTORY:
            return {
                "success": False,
                "message": f"背包已满！({MAX_INVENTORY}/{MAX_INVENTORY})",
            }

        item = room.items[item_index]
        room.remove_item(item)
        player.inventory.append(item)

        return {
            "success": True,
            "message": f"拾取了{item.name}。",
        }

    def pickup_all(self, player: Player, room: Room) -> dict:
        """Pick up all items from the room.

        Returns dict with success, message, count.
        """
        if len(room.items) == 0:
            return {
                "success": False,
                "message": "这里没有可拾取的物品。",
                "count": 0,
            }

        picked = 0
        messages = []
        # Iterate over a copy since we modify the list
        items_to_pickup = list(room.items)
        for item in items_to_pickup:
            if len(player.inventory) >= MAX_INVENTORY:
                messages.append("背包已满——部分物品被留下了。")
                break
            room.remove_item(item)
            player.inventory.append(item)
            picked += 1

        msg = f"拾取了{picked}件物品。" if picked > 0 else "没有拾取任何物品。"
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
        combat_system: Optional["CombatSystem"] = None,
        enemies: Optional[List] = None,
    ) -> dict:
        """Use an item from inventory by index.

        For Grenades, pass combat_system and enemies.
        Returns dict with success, message.
        """
        if item_index < 0 or item_index >= len(player.inventory):
            return {
                "success": False,
                "message": "无效的物品编号。",
            }

        item = player.inventory[item_index]

        if not item.usable:
            return {
                "success": False,
                "message": f"无法使用{item.name}。",
            }

        # Handle different item types
        if isinstance(item, Grenade):
            if combat_system is None:
                return {
                    "success": False,
                    "message": "现在无法投掷手雷。",
                }
            # Bug B: pass the exact selected grenade so the right one is consumed
            result = combat_system.execute_grenade(
                player, enemies or [], grenade_item=item
            )
            return result

        elif isinstance(item, WeaponModItem):
            return self._attach_mod_to_current_weapon(player, item)

        else:
            # MedKit, ArmorPickup, AmmoPickup — use directly
            msg = item.use(player)
            player.inventory.pop(item_index)
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
                "message": "只有一把武器。",
            }

        player.current_weapon_idx = (
            (player.current_weapon_idx + direction) % len(player.weapons)
        )
        weapon = player.current_weapon()

        return {
            "success": True,
            "message": f"切换到{weapon.name} ({weapon.ammo}/{weapon.effective_max_ammo()})" if weapon else "没有武器。",
        }

    def modify_weapon(self, player: Player, mod_item_index: int) -> dict:
        """Attach a WeaponModItem from inventory to the current weapon.

        Returns dict with success, message.
        """
        if mod_item_index < 0 or mod_item_index >= len(player.inventory):
            return {
                "success": False,
                "message": "无效的物品编号。",
            }

        item = player.inventory[mod_item_index]
        if not isinstance(item, WeaponModItem):
            return {
                "success": False,
                "message": f"{item.name}不是武器改装件。",
            }

        return self._attach_mod_to_current_weapon(player, item)

    def _attach_mod_to_current_weapon(
        self, player: Player, mod_item: WeaponModItem
    ) -> dict:
        """Attach a WeaponModItem to the player's current weapon (F11: shared by
        ``use_item`` and ``modify_weapon``)."""
        weapon = player.current_weapon()
        if weapon is None:
            return {
                "success": False,
                "message": "没有武器可以安装改装件。",
            }
        if weapon.add_mod(mod_item.mod):
            player.inventory.remove(mod_item)
            return {
                "success": True,
                "message": f"已将{mod_item.name}安装到{weapon.name}！",
            }
        return {
            "success": False,
            "message": f"无法安装{mod_item.name}——{weapon.name}的改装槽位已满。",
        }

    def drop_item(self, player: Player, item_index: int, room: Room) -> dict:
        """Drop an item from inventory into the current room.

        Returns dict with success, message.
        """
        if item_index < 0 or item_index >= len(player.inventory):
            return {
                "success": False,
                "message": "无效的物品编号。",
            }

        item = player.inventory.pop(item_index)
        room.add_item(item)

        return {
            "success": True,
            "message": f"丢弃了{item.name}。",
        }
