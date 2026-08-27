"""Core entity types: enemies and pickups.

These are *base* types (architecture rule #6): defined exactly once here in
``core`` and imported everywhere via
``from doom_game.core.entities import Enemy, Pickup, PickupType, EnemyType``.
They never redefine ``Vector2`` / ``TextureType`` - those come from
``doom_game.core.types``.
"""
import math
from enum import Enum

from doom_game.core.types import Vector2
from doom_game.config import (
    ENEMY_HP,
    ENEMY_DAMAGE,
    ENEMY_SPEED,
    ENEMY_PERCEPTION_RANGE,
    ENEMY_CONTACT_DIST,
    ENEMY_CONTACT_COOLDOWN,
    ENEMY_ATTACK_RANGE,
    ENEMY_ATTACK_COOLDOWN,
    PROJECTILE_SPEED,
    PROJECTILE_DAMAGE,
    PROJECTILE_HIT_DIST,
    PROJECTILE_MAX_DIST,
    HEALTH_PICKUP_AMOUNT,
    SCORE_PICKUP_AMOUNT,
    PICKUP_CONTACT_DIST,
)


class PickupType(Enum):
    """Category of a collectible item."""
    HEALTH = "health"
    SCORE = "score"


class EnemyType(Enum):
    """Category of an enemy."""
    BASIC = "basic"


def _blocked(world_map, x: float, y: float, radius: float = 0.2) -> bool:
    """True if any grid cell within ``radius`` of (x, y) is a wall.

    Mirrors ``GameWorld._is_blocked`` so entities reuse the authoritative grid
    collision structure (architecture ambiguity #2).
    """
    for cx in (int(x - radius), int(x + radius)):
        for cy in (int(y - radius), int(y + radius)):
            if world_map.is_wall(cx, cy):
                return True
    return False


class Projectile:
    """A straight-flying enemy bullet (base type, defined once in ``core``).

    The direction supplied at construction time is normalised and frozen: the
    projectile never tracks the player (design Q3). Movement is measured in
    grid units per *frame* (same unit as ``ENEMY_SPEED``); the ``dt`` argument
    of :meth:`update` is accepted for API symmetry with ``Enemy.update`` and
    reserved for a future time-based conversion.
    """

    def __init__(self, x: float, y: float, dir_x: float, dir_y: float,
                 speed: float = PROJECTILE_SPEED,
                 damage: float = PROJECTILE_DAMAGE,
                 max_dist: float = PROJECTILE_MAX_DIST):
        self.pos = Vector2(x, y)
        length = math.hypot(dir_x, dir_y)
        if length < 1e-9:
            # Degenerate direction: default to +x so the projectile still
            # flies (and dies on a wall / max distance) instead of stalling.
            self.vx, self.vy = 1.0, 0.0
        else:
            self.vx = dir_x / length
            self.vy = dir_y / length
        self.speed = float(speed)
        self.damage = float(damage)
        self.max_dist = float(max_dist)
        self.traveled = 0.0
        self.alive = True

    def update(self, world_map, player, dt: float) -> float:
        """Advance one frame; return the damage dealt to the player (or 0).

        Death paths (``alive`` -> False): player hit (returns ``damage`` -
        the *caller* applies it to ``player.hp``, entities never mutate the
        player directly), wall / out-of-bounds impact, or exceeding
        ``max_dist``. ``dt`` is currently unused (per-frame stepping).
        """
        if not self.alive:
            return 0.0

        self.pos.x += self.vx * self.speed
        self.pos.y += self.vy * self.speed
        self.traveled += self.speed

        # Player hit -> report damage and die.
        if self.pos.distance_to(player.pos) < PROJECTILE_HIT_DIST:
            self.alive = False
            return self.damage

        # Wall / out-of-bounds impact (is_wall treats out-of-bounds as wall).
        if world_map.is_wall(int(self.pos.x), int(self.pos.y)):
            self.alive = False
            return 0.0

        # Exceeded maximum flight distance.
        if self.traveled >= self.max_dist:
            self.alive = False
            return 0.0
        return 0.0

    def __repr__(self) -> str:
        return (f"Projectile(pos={self.pos}, traveled={self.traveled:.2f}, "
                f"alive={self.alive})")


class Enemy:
    """A simple chase-AI enemy.

    Perception: sees the player when there is line-of-sight and the player is
    within ``ENEMY_PERCEPTION_RANGE``. While chasing it walks toward the player
    with per-axis grid collision sliding (never passes through walls). On
    contact it deals ``damage`` (subject to a cooldown).
    """

    def __init__(self, x: float, y: float, hp: float = ENEMY_HP,
                 damage: float = ENEMY_DAMAGE, speed: float = ENEMY_SPEED,
                 angle: float = 0.0, type: EnemyType = EnemyType.BASIC,
                 attack_range=None, attack_cooldown=None):
        self.pos = Vector2(x, y)
        self.angle = float(angle)
        self.hp = float(hp)
        self.damage = float(damage)
        self.speed = float(speed)
        self.type = type
        self.state = "idle"            # "idle" | "chasing"
        self.alive = True
        self._contact_cd = 0.0         # contact-damage cooldown (seconds)
        # Ranged attack tunables (A7): ``None`` -> config defaults, so old
        # level files and existing constructor calls behave identically.
        self.attack_range = (float(attack_range) if attack_range is not None
                             else float(ENEMY_ATTACK_RANGE))
        self.attack_cooldown = (float(attack_cooldown)
                                if attack_cooldown is not None
                                else float(ENEMY_ATTACK_COOLDOWN))
        self._attack_cd = 0.0          # ranged-attack cooldown (seconds)

    # ------------------------------------------------------------------ #
    # Behaviour
    # ------------------------------------------------------------------ #
    def _can_see(self, player, world_map) -> bool:
        """True if there is no wall on the segment to the player."""
        return world_map.line_of_sight(
            self.pos.x, self.pos.y, player.pos.x, player.pos.y)

    def update(self, player, world_map, dt: float) -> float:
        """Advance AI one step.

        Returns the damage dealt to the player this step (>0 only on a fresh
        contact while the cooldown is ready), otherwise 0.
        """
        if not self.alive:
            return 0.0

        # Tick the contact / ranged-attack cooldowns down toward zero.
        if self._contact_cd > 0.0:
            self._contact_cd = max(0.0, self._contact_cd - dt)
        if self._attack_cd > 0.0:
            self._attack_cd = max(0.0, self._attack_cd - dt)

        dist = self.pos.distance_to(player.pos)

        # Perception: LOS + within range -> chase, else idle.
        if dist <= ENEMY_PERCEPTION_RANGE and self._can_see(player, world_map):
            self.state = "chasing"
        else:
            self.state = "idle"

        # Contact damage (cooldown-gated, applies regardless of state so a
        # player who walks into an idle enemy still gets hurt).
        if dist < ENEMY_CONTACT_DIST:
            if self._contact_cd <= 0.0:
                self._contact_cd = ENEMY_CONTACT_COOLDOWN
                return self.damage
            return 0.0

        # Otherwise, if chasing, walk toward the player.
        if self.state == "chasing":
            self._chase(player, world_map)
        return 0.0

    def _chase(self, player, world_map) -> None:
        """Move one step toward the player with per-axis wall sliding."""
        dx = player.pos.x - self.pos.x
        dy = player.pos.y - self.pos.y
        length = math.hypot(dx, dy)
        if length < 1e-6:
            return
        nx = dx / length
        ny = dy / length
        step = self.speed
        radius = 0.2
        # Per-axis slide so the enemy hugs walls instead of clipping through.
        if not _blocked(world_map, self.pos.x + nx * step, self.pos.y, radius):
            self.pos.x += nx * step
        if not _blocked(world_map, self.pos.x, self.pos.y + ny * step, radius):
            self.pos.y += ny * step
        self.angle = math.atan2(ny, nx)

    def try_fire(self, player, world_map):
        """Fire a :class:`Projectile` at the player, or return ``None``.

        Fires only when *all* conditions hold: alive, currently ``chasing``
        (LOS + perception already established by :meth:`update`), player
        within ``attack_range``, cooldown ready, and a second LOS check at the
        instant of firing. The direction is the normalised vector toward the
        player at fire time (straight flight, no tracking).
        """
        if not self.alive:
            return None
        if self.state != "chasing":
            return None
        if self._attack_cd > 0.0:
            return None
        if self.pos.distance_to(player.pos) > self.attack_range:
            return None
        if not self._can_see(player, world_map):
            return None
        self._attack_cd = self.attack_cooldown
        return Projectile(self.pos.x, self.pos.y,
                          player.pos.x - self.pos.x,
                          player.pos.y - self.pos.y)

    def take_damage(self, amount: float = 0.0) -> None:
        """Apply damage; mark dead when health reaches zero."""
        self.hp -= float(amount)
        if self.hp <= 0.0:
            self.hp = 0.0
            self.alive = False

    def __repr__(self) -> str:
        return (f"Enemy(pos={self.pos}, hp={self.hp:.0f}, "
                f"state={self.state}, alive={self.alive})")


class Pickup:
    """A collectible item placed in the world.

    ``HEALTH`` restores ``player.hp``; ``SCORE`` adds to ``player.score``.
    """

    def __init__(self, x: float, y: float, kind: PickupType,
                 amount=None, taken: bool = False):
        self.pos = Vector2(x, y)
        self.kind = kind
        if amount is None:
            amount = (HEALTH_PICKUP_AMOUNT if kind == PickupType.HEALTH
                      else SCORE_PICKUP_AMOUNT)
        self.amount = float(amount)
        self.taken = bool(taken)

    def __repr__(self) -> str:
        return (f"Pickup(pos={self.pos}, kind={self.kind.value}, "
                f"taken={self.taken})")
