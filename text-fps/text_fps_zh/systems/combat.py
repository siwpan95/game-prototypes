"""CombatSystem - Turn-based combat logic."""
from typing import TYPE_CHECKING, List, Optional

from core.constants import (
    AIM_BONUS,
    COVER_ACCURACY_PENALTY,
    EXPOSED_ACCURACY_BONUS,
    EXPOSED_DAMAGE_BONUS,
    SUPPRESSION_ACCURACY_PENALTY,
    SUPPRESSION_SCALE,
    SUPPRESSION_MAX,
)
from models.player import Player
from models.enemy import Enemy
from models.weapon import Weapon
from models.item import Grenade

if TYPE_CHECKING:
    from models.room import Room


class CombatSystem:
    """Core combat system handling player attacks, enemy turns, and damage."""

    def __init__(self) -> None:
        pass

    def execute_fire(self, player: Player, target: Enemy, room=None) -> dict:
        """Player fires at an enemy target.

        Returns dict with success, hit, damage, message, enemy_alive.

        New tactical layers:
          * F3 flank/exposure bonus — shooting an ``exposed`` enemy adds hit
            chance and flat damage (plus a "包抄加成" log note).
          * Stim buff — reads ``player.buffs`` for a temporary acc/dmg boost.
          * F2 suppression — the shot pins enemies in the room (suppressive
            fire), scaling with the weapon's ``suppression`` stat.
        """
        weapon = player.current_weapon()
        if weapon is None:
            return {
                "success": False,
                "hit": False,
                "damage": 0,
                "message": "你没有装备武器！",
                "enemy_alive": target.is_alive,
            }

        if not weapon.can_fire():
            return {
                "success": False,
                "hit": False,
                "damage": 0,
                "message": f"{weapon.name}没有弹药！需要换弹。",
                "enemy_alive": target.is_alive,
            }

        # Resolve the shot through the weapon (single source of truth for
        # hit-roll + damage variance). Aiming + flank/exposure + stim stack.
        bonus = AIM_BONUS if player.is_aiming else 0.0
        if getattr(target, "exposed", False):
            bonus += EXPOSED_ACCURACY_BONUS
        bonus += player.buffs.get("stim_acc", 0.0)
        shot = weapon.fire(accuracy_bonus=bonus)
        player.shots_fired += 1

        if shot["hit"]:
            damage = shot["damage"]
            # F3: flank/exposure flat damage bonus
            flanked = bool(getattr(target, "exposed", False))
            if flanked:
                damage += EXPOSED_DAMAGE_BONUS
            # Stim damage multiplier
            dmg_mult = player.buffs.get("stim_dmg", 1.0)
            if dmg_mult != 1.0:
                damage = int(damage * dmg_mult)
            target.take_damage(damage, penetration=weapon.effective_penetration())

            # Reset aiming
            player.is_aiming = False

            msg = f"你命中了{target.name}，造成{damage}点伤害！"
            if flanked:
                msg += "（包抄加成！）"
            if not target.is_alive:
                player.kills += 1
                msg += f" {target.name}已被消灭！"

            self._apply_suppression(player, room)
            return {
                "success": True,
                "hit": True,
                "damage": damage,
                "message": msg,
                "enemy_alive": target.is_alive,
            }
        else:
            player.is_aiming = False
            msg = f"你向{target.name}开火，但未命中！"

            self._apply_suppression(player, room)
            return {
                "success": True,
                "hit": False,
                "damage": 0,
                "message": msg,
                "enemy_alive": target.is_alive,
            }

    def _apply_suppression(self, player: Player, room) -> None:
        """Pin living enemies in ``room`` with the weapon's suppressive value.

        Suppressive fire (even on a miss) adds ``suppressed`` turns to every
        living enemy in the room; the LMG stacks hardest. Capped at SUPPRESSION_MAX.
        """
        weapon = player.current_weapon()
        if weapon is None or room is None:
            return
        supp = weapon.effective_suppression()
        if supp <= 0:
            return
        added = min(SUPPRESSION_MAX, max(1, int(round(supp * SUPPRESSION_SCALE))))
        for e in room.living_enemies():
            e.status_effects["suppressed"] = min(
                SUPPRESSION_MAX, e.status_effects.get("suppressed", 0) + added
            )

    def execute_aim(self, player: Player) -> dict:
        """Player aims for a more accurate shot next turn."""
        player.is_aiming = True
        return {
            "success": True,
            "message": "你稳住瞄准...（下一次射击命中率+25%）",
        }

    def execute_reload(self, player: Player) -> dict:
        """Reload the current weapon to full ammo."""
        weapon = player.current_weapon()
        if weapon is None:
            return {
                "success": False,
                "message": "没有武器可以换弹。",
                "ammo": 0,
            }

        result = weapon.reload()
        return {
            "success": True,
            "message": result["message"],
            "ammo": weapon.ammo,
        }

    def execute_grenade(
        self,
        player: Player,
        enemies: List[Enemy],
        grenade_item: Optional[Grenade] = None,
    ) -> dict:
        """Throw a grenade, dealing area damage to all living enemies.

        If ``grenade_item`` is provided it is used (Bug B: the exact grenade the
        player selected); otherwise the first Grenade in the inventory is used
        for backward compatibility.
        """
        if grenade_item is None:
            grenade_item = next(
                (i for i in player.inventory if isinstance(i, Grenade)), None
            )
        elif grenade_item not in player.inventory:
            return {
                "success": False,
                "message": "你身上没有这颗手雷。",
                "damage_dealt": 0,
                "killed": [],
            }

        if grenade_item is None:
            return {
                "success": False,
                "message": "你没有手雷！",
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
        player.inventory.remove(grenade_item)

        msg = f"你投掷了一颗手雷！命中{hit_count}名敌人，造成{total_damage}点总伤害。"
        if killed:
            msg += f" 击杀: {', '.join(e.name for e in killed)}！"

        return {
            "success": True,
            "message": msg,
            "damage_dealt": total_damage,
            "killed": killed,
        }

    def calculate_damage(self, weapon: Weapon) -> int:
        """Calculate actual damage with ±20% variance (armor applied in Enemy.take_damage)."""
        return weapon._roll_damage()

    def execute_enemy_turn(
        self, enemies: List[Enemy], player: Player, room: Optional["Room"] = None
    ) -> List[dict]:
        """All living enemies take their turns.

        If player is in cover, enemy accuracy is reduced by 0.20.
        Returns list of action result dicts.
        """
        results: List[dict] = []

        for enemy in enemies:
            if not enemy.is_alive:
                continue

            # Temporarily reduce accuracy if player is in cover, and further if
            # the enemy is currently suppressed (F2). Restored after the action.
            original_accuracy = enemy.accuracy
            if player.in_cover:
                enemy.accuracy = max(0.05, enemy.accuracy - COVER_ACCURACY_PENALTY)
            supp = enemy.status_effects.get("suppressed", 0)
            if supp > 0:
                enemy.accuracy = max(
                    0.02, enemy.accuracy - SUPPRESSION_ACCURACY_PENALTY * min(1, supp)
                )

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
