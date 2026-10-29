"""Combat system — handles all damage, healing, and combat resolution."""

from __future__ import annotations
from ecs import System, World
from components import (
    HealthComponent, AttackComponent, CardComponent,
    MinionComponent, EnemyComponent, RenderComponent,
    FloatingTextComponent, WaveComponent,
    EnergyComponent, PlayerComponent, BoardComponent,
    KeywordComponent, HandComponent, PositionComponent,
)
from game_state import GameState, Phase
from constants import (
    FLOAT_DAMAGE, FLOAT_HEAL, FLOAT_SHIELD,
    FLASH_DURATION, FLOAT_TEXT_SPEED, MINION_BG,
)
import random


class CombatSystem(System):
    """Processes combat: attacks, damage, healing, death."""

    def __init__(self, game_state: GameState) -> None:
        self.gs = game_state

    def update(self, world: World, dt: float, events: list | None = None) -> None:
        pass  # Combat is event-driven, not per-frame

    # ── Card Play Resolution ─────────────────────────────────────────────

    def resolve_card(self, world: World, card_entity, target_entity=None) -> None:
        """Execute a played card's effect."""
        card = world.get_component(card_entity, CardComponent)
        if card is None:
            return

        player_health = self._get_player_health(world)
        player_atk = self._get_player_attack(world)

        if card.card_type == "attack":
            self._resolve_attack_card(world, card, target_entity)
        elif card.card_type == "skill":
            self._resolve_skill_card(world, card, target_entity, player_health)
        elif card.card_type == "minion":
            self._resolve_minion_card(world, card_entity, card)

        # Track card play
        player_comp = self._get_player_component(world)
        if player_comp:
            player_comp.cards_played += 1

    # ── Attack Card ─────────────────────────────────────────────────────

    def _resolve_attack_card(self, world: World, card: CardComponent, target) -> None:
        damage = card.damage or 0

        # Lifesteal
        lifesteal = "Lifesteal" in (card.keywords or [])

        # Apply damage to target
        if target is not None:
            target_health = world.get_component(target, HealthComponent)
            if target_health:
                actual_dmg = target_health.take_damage(damage)
                self._spawn_float(world, target, f"-{damage}", FLOAT_DAMAGE)
                self._flash_entity(world, target)

                if lifesteal and actual_dmg > 0:
                    player_h = self._get_player_health(world)
                    if player_h:
                        healed = player_h.heal(actual_dmg)
                        self._spawn_float(world, None, f"+{healed} HP", FLOAT_HEAL)

        # Apply shield to self
        if card.shield > 0:
            player_h = self._get_player_health(world)
            if player_h:
                player_h.shield += card.shield
                self._spawn_float(world, None, f"+{card.shield} Shield", FLOAT_SHIELD)

        # Apply heal to self
        if card.heal > 0:
            player_h = self._get_player_health(world)
            if player_h:
                healed = player_h.heal(card.heal)
                self._spawn_float(world, None, f"+{healed} HP", FLOAT_HEAL)

    # ── Skill Card ──────────────────────────────────────────────────────

    def _resolve_skill_card(self, world: World, card: CardComponent,
                            target, player_health: HealthComponent) -> None:
        # Shield
        if card.shield > 0:
            if player_health:
                player_health.shield += card.shield
                self._spawn_float(world, None, f"+{card.shield} Shield", FLOAT_SHIELD)

        # Heal
        if card.heal > 0:
            if player_health:
                healed = player_health.heal(card.heal)
                self._spawn_float(world, None, f"+{healed} HP", FLOAT_HEAL)

        # AOE damage (Holy Nova, Hellfire)
        if card.damage > 0 and card.target == "none":
            # Damage all enemies + enemy minions
            enemy_entities = world.get_entities_with(EnemyComponent, HealthComponent)
            for e in enemy_entities:
                eh = world.get_component(e, HealthComponent)
                if eh:
                    dmg = card.damage
                    # Hellfire also hits player minions
                    if card.name.lower() == "hellfire":
                        pass  # handled separately
                    eh.take_damage(dmg)
                    self._spawn_float(world, e, f"-{dmg}", FLOAT_DAMAGE)
                    self._flash_entity(world, e)
                    self._check_death(world, e)

            # Hellfire damages player minions too
            if card.name.lower() == "hellfire":
                minion_ents = world.get_entities_with(MinionComponent, HealthComponent)
                for m in minion_ents:
                    m_comp = world.get_component(m, MinionComponent)
                    if m_comp and m_comp.owner == "player":
                        mh = world.get_component(m, HealthComponent)
                        if mh:
                            mh.take_damage(card.damage)
                            self._spawn_float(world, m, f"-{card.damage}", FLOAT_DAMAGE)
                            self._check_death(world, m)

            # Heal self for Holy Nova
            if card.heal > 0 and player_health:
                healed = player_health.heal(card.heal)
                self._spawn_float(world, None, f"+{healed} HP", FLOAT_HEAL)

    # ── Minion Card ─────────────────────────────────────────────────────

    def _resolve_minion_card(self, world: World, card_entity, card: CardComponent) -> None:
        from card_factory import create_minion_from_card
        from components import BoardComponent

        # Check board space
        board_ents = world.get_entities_with(BoardComponent)
        board = None
        if board_ents:
            board_ent = next(iter(board_ents))
            board = world.get_component(board_ent, BoardComponent)

        if board and board.is_full:
            self.gs.show_message("Board is full!")
            return

        # Spawn minion
        minion_ent = create_minion_from_card(world, card_entity)

        # Execute battlecry
        if card.battlecry:
            self._execute_battlecry(world, minion_ent, card.battlecry)

        # Place on board
        if board and minion_ent:
            board.minions.append(minion_ent)

    # ── Battlecry / Deathrattle ───────────────────────────────────────

    def _execute_battlecry(self, world: World, minion_entity, battlecry: dict) -> None:
        bt = battlecry.get("type", "")
        val = battlecry.get("value", 0)

        if bt == "damage_self":
            h = world.get_component(minion_entity, HealthComponent)
            if h:
                h.take_damage(val)
                self._spawn_float(world, minion_entity, f"-{val} HP", FLOAT_DAMAGE)

        elif bt == "freeze":
            # Give freeze component
            from components import KeywordComponent
            kw = world.get_component(minion_entity, KeywordComponent)
            if not kw:
                kw = KeywordComponent()
                world.add_component(minion_entity, kw)
            # Mark frozen via a simple flag or custom component
            # For simplicity, we'll add a "frozen" flag via a generic tag
            setattr(minion_entity, "_frozen_turns", val)

        elif bt == "damage_equal_attack":
            atk = world.get_component(minion_entity, AttackComponent)
            if atk:
                # Deal damage to random enemy
                enemy_ents = list(world.get_entities_with(EnemyComponent, HealthComponent))
                if enemy_ents:
                    import random
                    target = random.choice(enemy_ents)
                    eh = world.get_component(target, HealthComponent)
                    if eh:
                        eh.take_damage(atk.attack)
                        self._spawn_float(world, target, f"-{atk.attack}", FLOAT_DAMAGE)
                        self._check_death(world, target)

        elif bt == "draw":
            # Draw cards - handled in game logic outside combat system
            pass

        elif bt == "buff_attack":
            atk = world.get_component(minion_entity, AttackComponent)
            if atk:
                atk.attack += val

        elif bt == "buff_health_per_card":
            # Simplified: just give flat +val health
            h = world.get_component(minion_entity, HealthComponent)
            if h:
                h.hp += val
                h.max_hp += val

        elif bt == "set_stats":
            h = world.get_component(minion_entity, HealthComponent)
            a = world.get_component(minion_entity, AttackComponent)
            if h:
                h.hp = val
                h.max_hp = val
            if a:
                a.attack = val

    def execute_deathrattle(self, world: World, entity) -> None:
        """Called when a minion dies."""
        card_comp = world.get_component(entity, CardComponent)
        if not card_comp or not card_comp.deathrattle:
            return
        dr = card_comp.deathrattle
        bt = dr.get("type", "")
        val = dr.get("value", 0)

        if bt == "draw":
            # Signal to game logic to draw `val` cards
            # We set a flag on the world or game state
            self.gs._pending_draw = getattr(self.gs, "_pending_draw", 0) + val

    # ── Minion Combat (Enemy Turn) ────────────────────────────────────

    def minion_attack(self, world: World, attacker_entity, target_entity) -> None:
        """A minion attacks a target."""
        atk_comp = world.get_component(attacker_entity, AttackComponent)
        if not atk_comp or not atk_comp.can_attack:
            return

        # Check Taunt redirection
        actual_target = self._resolve_taunt(world, target_entity)

        # Deal damage
        dmg = atk_comp.effective_attack
        target_h = world.get_component(actual_target, HealthComponent)
        if target_h:
            actual_dmg = target_h.take_damage(dmg)
            self._spawn_float(world, actual_target, f"-{dmg}", FLOAT_DAMAGE)
            self._flash_entity(world, actual_target)

            # Poisonous
            kw = world.get_component(attacker_entity, KeywordComponent)
            if kw and kw.poisonous and actual_dmg > 0:
                target_h.hp = 0
                self._spawn_float(world, actual_target, "POISON!", (50, 200, 100))

        # Take damage back (if target is a minion with attack)
        target_atk = world.get_component(actual_target, AttackComponent)
        if target_atk and target_atk.attack > 0:
            atk_h = world.get_component(attacker_entity, HealthComponent)
            if atk_h:
                back_dmg = target_atk.effective_attack
                atk_h.take_damage(back_dmg)
                self._spawn_float(world, attacker_entity, f"-{back_dmg}", FLOAT_DAMAGE)
                self._flash_entity(world, attacker_entity)

        # Lifesteal
        kw = world.get_component(attacker_entity, KeywordComponent)
        if kw and kw.lifesteal and actual_dmg > 0:
            player_h = self._get_player_health(world)
            if player_h:
                healed = player_h.heal(actual_dmg)
                self._spawn_float(world, None, f"+{healed} HP", FLOAT_HEAL)

        # Mark attack used
        atk_comp.attacks_this_turn += 1

        # Check deaths
        self._check_death(world, actual_target)
        self._check_death(world, attacker_entity)

    def _resolve_taunt(self, world: World, intended_target) -> object:
        """If any taunt minions exist, redirect attack to one of them."""
        taunters = []
        minion_ents = world.get_entities_with(MinionComponent, KeywordComponent, HealthComponent)
        for e in minion_ents:
            kw = world.get_component(e, KeywordComponent)
            m_comp = world.get_component(e, MinionComponent)
            h = world.get_component(e, HealthComponent)
            if kw and kw.taunt and h and h.alive and m_comp:
                # Only enemy taunts redirect player attacks
                taunters.append(e)
        return random.choice(taunters) if taunters else intended_target

    # ── Enemy Attacks Player ─────────────────────────────────────────────

    def enemy_attack_player(self, world: World, enemy_entity) -> None:
        atk_comp = world.get_component(enemy_entity, AttackComponent)
        if not atk_comp:
            return

        dmg = atk_comp.attack
        player_h = self._get_player_health(world)
        if player_h:
            absorbed = min(player_h.shield, dmg)
            player_h.shield -= absorbed
            remaining = dmg - absorbed
            player_h.hp -= remaining
            self._spawn_float(world, None, f"-{dmg} (enemy)", FLOAT_DAMAGE)

        # Check game over
        if player_h and player_h.hp <= 0:
            self.gs.phase = Phase.GAME_OVER

    # ── Death Checking ──────────────────────────────────────────────────

    def _check_death(self, world: World, entity) -> None:
        h = world.get_component(entity, HealthComponent)
        if h and not h.alive:
            self.execute_deathrattle(world, entity)
            # Remove from board
            from components import BoardComponent
            board_ents = world.get_entities_with(BoardComponent)
            for be in board_ents:
                board = world.get_component(be, BoardComponent)
                if entity in board.minions:
                    board.minions.remove(entity)
            world.destroy_entity(entity)

    # ── Helpers ─────────────────────────────────────────────────────────

    def _get_player_health(self, world: World) -> HealthComponent | None:
        for e in world.entities:
            h = world.get_component(e, HealthComponent)
            p = world.get_component(e, PlayerComponent)
            if h and p:
                return h
        # Fallback: first HealthComponent
        for e in world.entities:
            h = world.get_component(e, HealthComponent)
            if h:
                return h
        return None

    def _get_player_component(self, world: World):
        for e in world.entities:
            p = world.get_component(e, PlayerComponent)
            if p:
                return p
        return None

    def _get_player_attack(self, world: World) -> int:
        return 0  # Player doesn't have base attack in this game

    def _spawn_float(self, world: World, entity, text: str, color: tuple) -> None:
        x = 640
        y = 360
        if entity:
            pos = world.get_component(entity, PositionComponent)
            if pos:
                x = pos.x
                y = pos.y
        ft = FloatingTextComponent(text, x, y, color)
        e = world.create_entity()
        world.add_component(e, ft)

    def _flash_entity(self, world: World, entity) -> None:
        render = world.get_component(entity, RenderComponent)
        if render:
            render.flash_timer = FLASH_DURATION

    def end_player_turn(self, world: World) -> None:
        """Clean up after player turn: reset attacks, clear buffs."""
        # Reset minion attacks
        for e in world.get_entities_with(AttackComponent):
            atk = world.get_component(e, AttackComponent)
            atk.attacks_this_turn = 0
            atk.temp_attack_buff = 0

        # Reset just_played flag
        for e in world.get_entities_with(MinionComponent):
            m = world.get_component(e, MinionComponent)
            if m:
                m.just_played = False

        # Remove temp keywords (Rush can't attack after summon turn unless Rush)
        # Charge minions already handled

        # Refresh energy
        energy_ents = world.get_entities_with(EnergyComponent)
        for e in energy_ents:
            eng = world.get_component(e, EnergyComponent)
            if eng:
                eng.refresh()

        # Draw 1 card
        from components import DeckComponent, HandComponent
        deck_ents = list(world.get_entities_with(DeckComponent))
        hand_ents = list(world.get_entities_with(HandComponent))
        if deck_ents and hand_ents:
            deck = world.get_component(deck_ents[0], DeckComponent)
            hand = world.get_component(hand_ents[0], HandComponent)
            card = deck.draw_one()
            if card:
                hand.cards.append(card)

        self.gs.phase = Phase.ENEMY_TURN
        self.gs.clear_selection()
