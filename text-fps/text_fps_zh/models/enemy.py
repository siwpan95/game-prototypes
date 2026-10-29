"""Enemy model."""
import random
from typing import Dict, List, Optional

from models.item import Item


class Enemy:
    """An enemy entity with behavior patterns and combat stats.

    ``behavior`` doubles as the tactical archetype (patrol / aggressive / boss /
    rusher / suppressor / medic / marksman). The first three keep the legacy
    decision logic (so existing tests stay green); the latter four use a
    utility-scored brain (see ``decide_action``) grounded in tactical-shooter AI
    research: score options by health, incoming fire, cover availability and
    archetype weights, then act.
    """

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
        support_power: int = 0,
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
        # New tactical fields
        self.support_power: int = support_power  # healing output (medic)
        self.status_effects: dict = {"suppressed": 0}  # suppressed: turns remaining
        self.exposed: bool = False  # vulnerable to player's return/flank fire

    def act(self, player, room) -> dict:
        """Determine and execute enemy action. Returns action dict."""
        if not self.is_alive:
            return {"action": "dead", "damage": 0, "message": f"{self.name}已死亡。"}

        handler = {
            "patrol": self._act_patrol,
            "aggressive": self._act_aggressive,
            "boss": self._act_boss,
            "rusher": self._act_rusher,
            "suppressor": self._act_suppressor,
            "medic": self._act_medic,
            "marksman": self._act_marksman,
        }.get(self.behavior, self._act_idle)
        result = handler(player, room)
        self._tick_status()
        return result

    # ------------------------------------------------------------------
    # Utility-scored brain for the new archetypes
    # ------------------------------------------------------------------
    def decide_action(self, player, room) -> dict:
        """Score tactical options and pick one (with a little noise).

        Returns an action dict. Lower health pushes toward retreat; medics
        prioritize healing wounded allies; flankers (rusher) push in and become
        exposed; marksmen/suppressors simply take the shot.
        """
        import random as _r

        health_ratio = self.health / max(1, self.max_health)
        cover_available = bool(room is not None and room.has_cover())
        suppressed = self.status_effects.get("suppressed", 0) > 0

        # Base score: always an option to shoot.
        options = {"attack": 1.0 + self.accuracy}
        if health_ratio < 0.3:
            options["retreat"] = 1.4  # wounded => fall back
        if self.behavior == "medic":
            wounded = self._wounded_ally(room)
            if wounded is not None:
                options["heal"] = 2.5  # medics heal first
        if self.behavior == "rusher" and not player.in_cover:
            options["flank"] = 1.6  # close in when player is exposed
        if suppressed and cover_available:
            options["take_cover"] = 1.8  # pinned => hug cover

        # Add human-like noise so the AI isn't perfectly predictable.
        choice = max(options, key=lambda k: options[k] + _r.uniform(-0.25, 0.25))

        # Exposure: a flanker closing in, or any enemy that peeks out to shoot
        # you while YOU are in cover, is vulnerable to your return/flank fire.
        self.exposed = (choice == "flank") or (
            choice == "attack" and getattr(player, "in_cover", False)
        )

        if choice == "retreat":
            return {"action": "retreat", "damage": 0,
                    "message": f"{self.name}受伤后后撤重组。"}
        if choice == "heal":
            return self._do_heal(room)
        if choice == "take_cover":
            self.exposed = False
            return {"action": "take_cover", "damage": 0,
                    "message": f"{self.name}被压制，躲回掩体。"}
        if choice == "flank":
            self.exposed = True  # closing in -> vulnerable to your return fire
            return self._attack(player, flank_bonus=0.10)
        return self._attack(player)

    def _wounded_ally(self, room):
        """Return the living ally (incl. self) with the lowest health ratio, or None."""
        if room is None:
            return None
        allies = [e for e in room.living_enemies() if e is not None]
        wounded = [e for e in allies if e.health < e.max_health]
        if not wounded:
            return None
        return min(wounded, key=lambda e: e.health / max(1, e.max_health))

    def _do_heal(self, room) -> dict:
        """Heal the most wounded ally. Returns an action dict."""
        target = self._wounded_ally(room)
        if target is None or self.support_power <= 0:
            return {"action": "idle", "damage": 0,
                    "message": f"{self.name}没有可治疗的队友。"}
        healed = min(self.support_power, target.max_health - target.health)
        target.health += healed
        return {"action": "heal", "damage": 0,
                "message": f"{self.name}为{target.name}治疗了{healed}点生命。"}

    def _act_patrol(self, player, room) -> dict:
        """Patrol behavior: 60% chance to attack, 40% to patrol."""
        if random.random() < 0.6:
            return self._attack(player)
        return {
            "action": "patrol",
            "damage": 0,
            "message": f"{self.name}正在巡逻，没有注意到你。",
        }

    def _act_aggressive(self, player, room) -> dict:
        """Aggressive behavior: always attacks."""
        return self._attack(player)

    def _act_boss(self, player, room) -> dict:
        """Boss behavior: switches phase based on health ratio."""
        health_ratio = self.health / max(1, self.max_health)
        if health_ratio <= 0.3 and self.phase < 2:
            self.phase = 2
            return {
                "action": "phase_shift",
                "damage": 0,
                "message": f"{self.name}进入狂暴状态！第二阶段！",
            }
        elif health_ratio <= 0.6 and self.phase < 1:
            self.phase = 1
            return {
                "action": "phase_shift",
                "damage": 0,
                "message": f"{self.name}变得更加凶猛！第一阶段！",
            }

        # Boss attacks with bonus damage based on phase
        bonus = self.phase * 5
        return self._attack(player, damage_bonus=bonus)

    def _act_idle(self, player, room) -> dict:
        """Fallback for unknown behavior."""
        return {"action": "idle", "damage": 0, "message": f"{self.name}没有行动。"}

    def _act_rusher(self, player, room) -> dict:
        """Aggressive flanker — uses the utility brain."""
        return self.decide_action(player, room)

    def _act_suppressor(self, player, room) -> dict:
        """Heavy DPS bruiser — uses the utility brain."""
        return self.decide_action(player, room)

    def _act_marksman(self, player, room) -> dict:
        """Long-range marksman — uses the utility brain."""
        return self.decide_action(player, room)

    def _act_medic(self, player, room) -> dict:
        """Support — heals wounded allies first, else fights."""
        return self.decide_action(player, room)

    def _attack(self, player, damage_bonus: int = 0, flank_bonus: float = 0.0) -> dict:
        """Attempt to attack the player. ``flank_bonus`` adds hit chance."""
        eff_acc = min(1.0, max(0.0, self.accuracy + flank_bonus))
        if random.random() < eff_acc:
            total_damage = self.damage + damage_bonus
            actual = player.take_damage(total_damage)
            return {
                "action": "attack",
                "damage": actual,
                "message": f"{self.name}命中你，造成{actual}点伤害！",
            }
        return {
            "action": "miss",
            "damage": 0,
            "message": f"{self.name}攻击但未命中！",
        }

    def take_damage(self, amount: int, penetration: float = 0.0) -> int:
        """Apply damage to enemy. Returns health damage dealt.

        ``penetration`` (0..1) reduces how much armor can absorb: effective
        armor is scaled by (1 - penetration), so armor-piercing rounds chew
        through plating. Defaults to 0 (legacy behavior, keeps tests stable).
        """
        if amount <= 0:
            return 0
        effective_armor = self.armor * (1.0 - max(0.0, min(1.0, penetration)))
        armor_absorb = min(effective_armor, amount)
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

    def _tick_status(self) -> None:
        """Decrement timed status effects at the end of the enemy's turn."""
        if self.status_effects.get("suppressed", 0) > 0:
            self.status_effects["suppressed"] -= 1

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
            "support_power": self.support_power,
            "status_effects": dict(self.status_effects),
            "exposed": self.exposed,
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
            support_power=data.get("support_power", 0),
        )
        e.max_health = data.get("max_health", e.health)
        e.is_alive = data.get("is_alive", True)
        e.phase = data.get("phase", 0)
        e.status_effects = data.get("status_effects", {"suppressed": 0})
        e.exposed = data.get("exposed", False)
        return e
