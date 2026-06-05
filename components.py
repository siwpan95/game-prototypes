"""All game components for KARD — data only, no logic."""

from __future__ import annotations
from ecs import Component


# ── Core Stats ──────────────────────────────────────────────────────────────

class HealthComponent(Component):
    def __init__(self, hp: int, max_hp: int | None = None) -> None:
        self.hp: int = hp
        self.max_hp: int = max_hp or hp
        self.shield: int = 0

    def take_damage(self, amount: int) -> int:
        """Apply damage through shield first. Returns actual HP damage dealt."""
        absorbed = min(self.shield, amount)
        self.shield -= absorbed
        remaining = amount - absorbed
        self.hp -= remaining
        return remaining

    def heal(self, amount: int) -> int:
        old = self.hp
        self.hp = min(self.max_hp, self.hp + amount)
        return self.hp - old

    @property
    def alive(self) -> bool:
        return self.hp > 0


class AttackComponent(Component):
    def __init__(self, attack: int) -> None:
        self.base_attack: int = attack
        self.attack: int = attack
        self.attacks_this_turn: int = 0
        self.max_attacks: int = 1  # Windfury → 2
        self.temp_attack_buff: int = 0  # Cleared at end of turn

    @property
    def can_attack(self) -> bool:
        return self.attacks_this_turn < self.max_attacks

    @property
    def effective_attack(self) -> int:
        return self.attack + self.temp_attack_buff


class EnergyComponent(Component):
    def __init__(self, current: int = 3, max_energy: int = 3) -> None:
        self.current: int = current
        self.max_energy: int = max_energy

    def refresh(self) -> None:
        self.current = self.max_energy

    def spend(self, amount: int) -> bool:
        if self.current >= amount:
            self.current -= amount
            return True
        return False


# ── Card / Deck / Hand ─────────────────────────────────────────────────────

class CardComponent(Component):
    def __init__(
        self,
        card_id: str,
        name: str,
        cost: int,
        card_type: str,           # "attack", "skill", "minion"
        description: str,
        rarity: str = "common",
        attack: int = 0,
        health: int = 0,
        target_type: str = "enemy",  # "enemy","self","friendly_minion","none","any_minion"
        keywords: list[str] | None = None,
        battlecry: dict | None = None,
        deathrattle: dict | None = None,
        damage: int = 0,            # For attack cards
        shield: int = 0,            # For skill cards
        heal: int = 0,              # For skill cards
        upgraded: bool = False,     # Card upgrade status
        pool: str = "B",           # Card pool: "A"=player, "B"=shared, "C"=enemy
        element: str = "none",     # 元素类型: fire/ice/lightning/wind/earth/dark/light/none
        status_effect: dict | None = None,  # 施加状态: {"type": "burn", "turns":2, "value":3}
    ) -> None:
        self.card_id = card_id
        self.name = name
        self.cost = cost
        self.card_type = card_type
        self.description = description
        self.rarity = rarity
        self.attack = attack
        self.health = health
        self.target_type = target_type
        self.keywords: list[str] = keywords or []
        self.battlecry = battlecry
        self.deathrattle = deathrattle
        self.damage = damage
        self.shield = shield
        self.heal = heal
        self.upgraded = upgraded
        self.pool = pool
        self.element: str = element
        self.status_effect: dict | None = status_effect


class DeckComponent(Component):
    def __init__(self, cards: list | None = None, owner: str = "player") -> None:
        self.cards: list = cards or []       # Entity IDs in deck
        self.discard: list = []              # Entity IDs in discard
        self.owner: str = owner              # "player" or "enemy"

    def draw_one(self):
        if not self.cards:
            self._shuffle_discard_in()
        if self.cards:
            return self.cards.pop()
        return None

    def _shuffle_discard_in(self) -> None:
        import random
        self.cards = self.discard[:]
        random.shuffle(self.cards)
        self.discard.clear()

    def add_to_discard(self, card_entity) -> None:
        self.discard.append(card_entity)


class HandComponent(Component):
    def __init__(self, owner: str = "player") -> None:
        self.cards: list = []  # Entity IDs in hand
        self.owner: str = owner  # "player" or "enemy"


class BoardComponent(Component):
    def __init__(self, max_minions: int = 7) -> None:
        self.minions: list = []  # Entity IDs on board
        self.max_minions = max_minions

    @property
    def is_full(self) -> bool:
        return len(self.minions) >= self.max_minions


# ── Enemy ───────────────────────────────────────────────────────────────────

class EnemyComponent(Component):
    def __init__(
        self,
        enemy_id: str,
        name: str,
        intent: str = "attack",
        intent_value: int = 0,
        is_boss: bool = False,
        intent_pattern: str = "always_attack",
    ) -> None:
        self.enemy_id = enemy_id
        self.name = name
        self.intent = intent           # "attack", "defend", "buff"
        self.intent_value = intent_value
        self.is_boss = is_boss
        self.intent_pattern = intent_pattern  # For AI


# ── Minion ──────────────────────────────────────────────────────────────────

class MinionComponent(Component):
    def __init__(self, name: str, owner: str = "player") -> None:
        self.name = name
        self.owner = owner         # "player" or "enemy"
        self.turns_on_board: int = 0
        self.just_played: bool = True   # Reset at end of turn


# ── Keywords ────────────────────────────────────────────────────────────────

class KeywordComponent(Component):
    def __init__(
        self,
        taunt: bool = False,
        charge: bool = False,
        rush: bool = False,
        divine_shield: bool = False,
        poisonous: bool = False,
        lifesteal: bool = False,
        windfury: bool = False,
    ) -> None:
        self.taunt = taunt
        self.charge = charge
        self.rush = rush
        self.divine_shield = divine_shield
        self.poisonous = poisonous
        self.lifesteal = lifesteal
        self.windfury = windfury

    @property
    def active_keywords(self) -> list[str]:
        """Return list of keyword names that are True."""
        result = []
        for kw in ("taunt", "charge", "rush", "divine_shield",
                    "poisonous", "lifesteal", "windfury"):
            if getattr(self, kw):
                result.append(kw)
        return result


# ── Visual / UI ─────────────────────────────────────────────────────────────

class PositionComponent(Component):
    def __init__(self, x: float = 0, y: float = 0) -> None:
        self.x = x
        self.y = y


class RenderComponent(Component):
    def __init__(self) -> None:
        self.hovered: bool = False
        self.selected: bool = False
        self.targetable: bool = False
        self.rect: tuple | None = None  # (x, y, w, h)
        self.anim_offset_x: float = 0
        self.anim_offset_y: float = 0
        self.flash_timer: float = 0
        self.shake_timer: float = 0
        self.fade_alpha: float = 255


class FloatingTextComponent(Component):
    def __init__(
        self, text: str, x: float, y: float,
        color: tuple = (255, 60, 60), duration: float = 1.2,
    ) -> None:
        self.text = text
        self.x = x
        self.y = y
        self.start_y = y
        self.color = color
        self.duration = duration
        self.timer: float = 0


# ── Game State ──────────────────────────────────────────────────────────────

class WaveComponent(Component):
    def __init__(self) -> None:
        self.wave_number: int = 0
        self.enemies_alive: int = 0
        self.wave_cleared: bool = False


class PlayerComponent(Component):
    def __init__(self) -> None:
        self.kills: int = 0
        self.cards_played: int = 0
        self.highest_wave: int = 0
        self.turns_this_wave: int = 0
        self.temp_attack_buff: int = 0  # Permanent demon buff from events
        self.player_class: str = ""     # TEW class: 元素使/暗刃骑士/狂怒斗士 etc.


# ── Element / Status Effects (TEW 最终物语体系) ────────────────────────

class ElementComponent(Component):
    """赋予实体元素伤害类型。"""
    def __init__(self, element: str = "none") -> None:
        # "fire", "ice", "lightning", "wind", "earth", "dark", "light", "none"
        self.element: str = element


class StatusEffectComponent(Component):
    """实体当前的状态效果列表。

    每个状态是一个 dict: {"type": str, "turns": int, "value": int}
      - type: "stun"/"slow"/"weaken"/"freeze"/"shaken"/"burn"/"poison"/"shield_up"
      - turns: 剩余持续回合数（0 = 本回合结束时移除）
      - value: 效果强度（如 burn=每回合伤害，slow=攻击减益量）
    """
    def __init__(self) -> None:
        self.effects: list[dict] = []

    def add(self, effect_type: str, turns: int = 1, value: int = 0) -> None:
        """添加状态效果；同类型叠加时刷新回合数、取最大值。"""
        for ef in self.effects:
            if ef["type"] == effect_type:
                ef["turns"] = max(ef["turns"], turns)
                ef["value"] = max(ef["value"], value)
                return
        self.effects.append({"type": effect_type, "turns": turns, "value": value})

    def has(self, effect_type: str) -> bool:
        return any(ef["type"] == effect_type and ef["turns"] > 0 for ef in self.effects)

    def get_value(self, effect_type: str) -> int:
        for ef in self.effects:
            if ef["type"] == effect_type and ef["turns"] > 0:
                return ef["value"]
        return 0
