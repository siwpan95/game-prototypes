"""Keyword system — resolves Hearthstone-style keyword effects."""

from __future__ import annotations
from ecs import System, World
from components import (
    KeywordComponent, HealthComponent, AttackComponent,
    MinionComponent, EnemyComponent, RenderComponent, CardComponent,
)
from constants import KEYWORD_COLORS


class KeywordSystem(System):
    """Processes keyword-based effects each frame/update."""

    def __init__(self, game_state) -> None:
        self.gs = game_state

    def update(self, world: World, dt: float, events: list | None = None) -> None:
        """Process per-frame keyword visuals (taunt glow, divine shield flash)."""
        self._process_taunt_visuals(world)
        self._process_divine_shield_visuals(world)

    def _process_divine_shield_visuals(self, world: World) -> None:
        """Tick down divine shield flash timers."""
        for e in world.get_entities_with(KeywordComponent, RenderComponent):
            kw = world.get_component(e, KeywordComponent)
            render = world.get_component(e, RenderComponent)
            if kw and kw.divine_shield and render:
                # Visual: slightly brighter border when divine shield is up
                pass  # Render system handles the actual glow

    # ── Divine Shield ─────────────────────────────────────────────────

    def on_damage_pre(self, world: World, entity, damage: int) -> int:
        """Called before damage is applied. Returns remaining damage.

        If Divine Shield is active, absorbs all damage and removes shield.
        Returns 0 if shield absorbed all; returns `damage` unchanged otherwise.
        """
        kw = world.get_component(entity, KeywordComponent)
        if kw and kw.divine_shield:
            kw.divine_shield = False
            render = world.get_component(entity, RenderComponent)
            if render:
                render.flash_timer = 0.3
            return 0  # All damage absorbed
        return damage

    def on_minion_death(self, world: World, entity) -> None:
        """Called when a minion with Deathrattle dies."""
        card = world.get_component(entity, CardComponent)
        if card and card.deathrattle:
            self._execute_deathrattle(world, entity, card.deathrattle)

    def _execute_deathrattle(self, world: World, entity, dr: dict) -> None:
        bt = dr.get("type", "")
        val = dr.get("value", 0)

        if bt == "draw":
            # Signal draw — handled by game logic
            self.gs._pending_draw = getattr(self.gs, "_pending_draw", 0) + val

    # ── Windfury ─────────────────────────────────────────────────────

    def _process_windfury(self, world: World) -> None:
        for e in world.get_entities_with(KeywordComponent, AttackComponent):
            kw = world.get_component(e, KeywordComponent)
            atk = world.get_component(e, AttackComponent)
            if kw and kw.windfury:
                atk.max_attacks = 2
            else:
                atk.max_attacks = 1

    # ── Taunt ────────────────────────────────────────────────────────

    def get_valid_attack_targets(self, world: World, attacker_owner: str) -> list:
        """Return list of valid attack targets considering Taunt.

        attacker_owner: "player" or "enemy"
        """
        # Find all enemy minions with Taunt
        taunters = []
        all_minions = world.get_entities_with(MinionComponent, KeywordComponent, HealthComponent)

        target_owner = "enemy" if attacker_owner == "player" else "player"

        for e in all_minions:
            m = world.get_component(e, MinionComponent)
            h = world.get_component(e, HealthComponent)
            if m and m.owner == target_owner and h and h.alive:
                kw = world.get_component(e, KeywordComponent)
                if kw and kw.taunt:
                    taunters.append(e)

        if taunters:
            return taunters

        # No taunts — can attack face (player or enemy directly)
        return []

    def _process_taunt_visuals(self, world: World) -> None:
        """Mark taunt minions as targetable with a glow."""
        for e in world.get_entities_with(KeywordComponent, RenderComponent):
            kw = world.get_component(e, KeywordComponent)
            render = world.get_component(e, RenderComponent)
            if kw and kw.taunt:
                # This is handled in render_system; just set a flag
                pass

    # ── Poisonous ───────────────────────────────────────────────────

    def on_after_combat(self, world: World, attacker, defender) -> None:
        """Called after combat resolves. Handles Poisonous."""
        kw_a = world.get_component(attacker, KeywordComponent)
        kw_d = world.get_component(defender, KeywordComponent)

        # Poisonous attacker kills defender
        if kw_a and kw_a.poisonous:
            h = world.get_component(defender, HealthComponent)
            if h:
                h.hp = 0

        if kw_d and kw_d.poisonous:
            h = world.get_component(attacker, HealthComponent)
            if h:
                h.hp = 0

    # ── Lifesteal ───────────────────────────────────────────────────

    def on_damage_dealt(self, world: World, source_entity, damage_dealt: int) -> None:
        """Heal source for damage dealt if Lifesteal."""
        if damage_dealt <= 0:
            return
        kw = world.get_component(source_entity, KeywordComponent)
        if kw and kw.lifesteal:
            # Find player health
            for e in world.entities:
                h = world.get_component(e, HealthComponent)
                p = world.get_component(e, PlayerComponent)
                if h and p:
                    h.heal(damage_dealt)
                    break

    # ── Rush ────────────────────────────────────────────────────────

    def can_minion_attack(self, world: World, minion_entity) -> bool:
        """Check if a minion can attack (checks Charge, Rush, just_played)."""
        m = world.get_component(minion_entity, MinionComponent)
        kw = world.get_component(minion_entity, KeywordComponent)
        atk = world.get_component(minion_entity, AttackComponent)

        if not m or not atk:
            return False

        if kw and kw.charge:
            return True

        if m.just_played and not (kw and kw.rush):
            return False  # Just played, can't attack (no Charge/Rush)

        return True

    # ── Freeze ──────────────────────────────────────────────────────

    def is_frozen(self, entity) -> bool:
        """Check if entity is frozen (skips its next attack)."""
        return getattr(entity, "_frozen_turns", 0) > 0

    def tick_frozen(self, world: World) -> None:
        """At end of turn, decrement freeze counters."""
        for e in world.entities:
            ft = getattr(e, "_frozen_turns", 0)
            if ft > 0:
                e._frozen_turns = ft - 1
