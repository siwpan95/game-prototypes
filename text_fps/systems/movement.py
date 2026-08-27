"""MovementSystem - Player movement and room transitions."""
import random
from typing import Optional

from core.event_bus import EventBus
from core.game_state import GameState
from models.room import Room
from models.enemy import Enemy
from data.enemies import create_enemy


# Random event probabilities (each 5%, total 15%)
_EVENT_SUPPLY = 0.05
_EVENT_REINFORCE = 0.05
_EVENT_TRAP_TRIGGER = 0.05
_TOTAL_EVENT_CHANCE = _EVENT_SUPPLY + _EVENT_REINFORCE + _EVENT_TRAP_TRIGGER


class MovementSystem:
    """Handles player movement between rooms and random events."""

    def __init__(self, event_bus: EventBus) -> None:
        self.event_bus = event_bus

    def move(self, game_state: GameState, direction: str) -> dict:
        """Move the player to an adjacent room in the given direction.

        Returns dict with success, message, hostile.
        """
        player = game_state.player
        current_room = game_state.current_room
        if player is None or current_room is None:
            return {
                "success": False,
                "message": "Cannot move — no current location.",
                "hostile": False,
            }

        # Validate exit exists
        if not self.validate_exit(current_room, direction):
            return {
                "success": False,
                "message": f"No exit to the {direction}.",
                "hostile": False,
            }

        # Check if current room has living enemies (can't flee)
        living = current_room.living_enemies()
        if living:
            return {
                "success": False,
                "message": f"Can't leave — {living[0].name} and allies are blocking the way!",
                "hostile": True,
            }

        # Get target room
        target_room_id = current_room.get_exit(direction)
        if target_room_id is None:
            return {
                "success": False,
                "message": f"Exit to {direction} leads nowhere.",
                "hostile": False,
            }

        # Find the target room from current level
        level = game_state.levels[-1] if game_state.levels else None
        if level is None:
            return {
                "success": False,
                "message": "No level loaded.",
                "hostile": False,
            }

        target_room = level.get_room(target_room_id)
        if target_room is None:
            return {
                "success": False,
                "message": f"Room '{target_room_id}' not found.",
                "hostile": False,
            }

        # Perform the move
        player.position = target_room_id
        game_state.current_room = target_room
        player.in_cover = False
        player.is_aiming = False

        was_visited = target_room.visited
        target_room.visited = True

        # Build arrival message
        hostile = len(target_room.living_enemies()) > 0
        msg = f"You move {direction} into {target_room.name}."
        if not was_visited:
            msg = f"You enter {target_room.name}. {target_room.description}"

        # Publish event
        event_type = "movement.enter_hostile" if hostile else "movement.enter"
        self.event_bus.publish(event_type, {
            "room_id": target_room_id,
            "room_name": target_room.name,
            "hostile": hostile,
        })

        # Check for random events (only on new room entry)
        if not was_visited:
            event_msg = self._check_random_event(game_state, target_room)
            if event_msg:
                msg += f" {event_msg}"

        # Check for traps
        trap_msg = self._check_traps(player, target_room)
        if trap_msg:
            msg += f" {trap_msg}"

        return {
            "success": True,
            "message": msg,
            "hostile": hostile,
        }

    def validate_exit(self, room: Room, direction: str) -> bool:
        """Check if a room has an exit in the given direction."""
        return direction in room.exits

    def _check_random_event(self, game_state: GameState, room: Room) -> Optional[str]:
        """15% chance of a random event when entering a new room.

        5% supply drop, 5% enemy reinforcement, 5% trap trigger.
        Returns event message or None.
        """
        roll = random.random()
        if roll >= _TOTAL_EVENT_CHANCE:
            return None

        if roll < _EVENT_SUPPLY:
            return self._event_supply_drop(room)
        elif roll < _EVENT_SUPPLY + _EVENT_REINFORCE:
            return self._event_reinforcement(room)
        else:
            return self._event_trap(game_state, room)

    def _event_supply_drop(self, room: Room) -> str:
        """Random supply drop event."""
        from data.items import create_medkit, create_ammo, create_armor
        import random as rng

        options = [
            lambda: create_medkit(25),
            lambda: create_ammo("pistol", 15),
            lambda: create_armor(15),
        ]
        item = rng.choice(options)()
        room.add_item(item)
        return f"[Event] Supply drop! Found a {item.name} on the ground."

    def _event_reinforcement(self, room: Room) -> str:
        """Enemy reinforcement event."""
        reinforcement = create_enemy("Guard")
        room.enemies.append(reinforcement)
        return f"[Event] Enemy reinforcement! A {reinforcement.name} appeared!"

    def _event_trap(self, game_state: GameState, room: Room) -> str:
        """Trap trigger event."""
        player = game_state.player
        if player is None:
            return ""
        damage = random.randint(8, 15)
        actual = player.take_damage(damage)
        return f"[Event] Trap triggered! You take {actual} damage from a hidden hazard."

    def _check_traps(self, player, room: Room) -> Optional[str]:
        """Check and trigger room traps that haven't been triggered yet."""
        messages = []
        for trap in room.traps:
            if not trap.get("triggered", False):
                # 50% chance to trigger each untriggered trap
                if random.random() < 0.5:
                    trap["triggered"] = True
                    damage = trap.get("damage", 10)
                    actual = player.take_damage(damage)
                    messages.append(
                        f"You trigger a {trap['name']}! Take {actual} damage."
                    )
        return " ".join(messages) if messages else None
