"""Input system — handles all mouse/keyboard interactions."""

from __future__ import annotations
import pygame
from ecs import System, World
from components import (
    CardComponent, RenderComponent, HandComponent,
    BoardComponent, EnergyComponent, DeckComponent,
    EnemyComponent, MinionComponent, WaveComponent,
    HealthComponent, PlayerComponent,
)
from game_state import Phase, GameState
from constants import *


class InputSystem(System):
    """Processes mouse clicks and keyboard input."""

    def __init__(self, game_state: GameState, combat_system) -> None:
        self.gs: GameState = game_state
        self.combat = combat_system
        self.mouse_pressed = False

    def update(self, world: World, dt: float, events: list | None = None) -> None:
        if events is None:
            return

        mouse_down = pygame.mouse.get_pressed()[0]
        clicked = mouse_down and not self.mouse_pressed
        self.mouse_pressed = mouse_down

        for event in events:
            if event.type == pygame.KEYDOWN:
                self._handle_key(world, event)

        if clicked:
            mx, my = pygame.mouse.get_pos()
            self._handle_click(world, mx, my)

        # Update hover every frame
        self._update_hover(world)

    # ── Click dispatch ───────────────────────────────────────────

    def _handle_click(self, world: World, mx: int, my: int) -> None:
        phase = self.gs.phase

        if phase == Phase.GAME_OVER:
            self._handle_game_over_click(world)
            return

        if phase == Phase.MENU:
            self._handle_menu_click(world)
            return

        if phase == Phase.REWARD:
            self._handle_reward_click(world, mx, my)
            return

        if phase == Phase.PLAYER_TURN:
            self._handle_player_click(world, mx, my)
            return

        if phase == Phase.ENEMY_TURN:
            return  # ignore clicks during enemy turn

        # Always check buttons
        self._check_buttons(world, mx, my)

    # ── Hover update ─────────────────────────────────────────────

    def _update_hover(self, world: World) -> None:
        mx, my = pygame.mouse.get_pos()
        for e in world.get_entities_with(RenderComponent):
            render = world.get_component(e, RenderComponent)
            if render and render.rect:
                rx, ry, rw, rh = render.rect
                x, y = render.rect[:2]
                w = render.rect[2] if len(render.rect) > 2 else 0
                h = render.rect[3] if len(render.rect) > 3 else 0
                in_rect = (rx <= mx <= rx + rw) if hasattr(render, '_r') else False
                # Simplified: check rect tuple
                if len(render.rect) == 4:
                    in_rect = (render.rect[0] <= mx <= render.rect[0] + render.rect[2] and
                               render.rect[1] <= my <= render.rect[1] + render.rect[3])
                else:
                    in_rect = False
                render.hovered = bool(in_rect)

    # ── Menu ─────────────────────────────────────────────────────

    def _handle_menu_click(self, world: World) -> None:
        self._start_new_game(world)

    # ── Game Over ───────────────────────────────────────────────

    def _handle_game_over_click(self, world: World) -> None:
        self._start_new_game(world)

    # ── Player Turn Click ───────────────────────────────────────

    def _handle_player_click(self, world: World, mx: int, my: int) -> None:
        # Case 1: Have a card selected → need to pick a target
        if self.gs.has_card_selected:
            card_ent = self.gs.selected_card_entity
            card = world.get_component(card_ent, CardComponent)
            if card:
                target = self._find_click_target(world, mx, my, card.target_type)
                if target:
                    self._play_card(world, card_ent, target)
                else:
                    # Clicked nothing valid → deselect
                    self._deselect_all(world)
                    self.gs.clear_selection()
            return

        # Case 2: Have a minion selected → pick enemy to attack
        if self.gs.has_minion_selected:
            minion_ent = self.gs.selected_minion_entity
            target = self._find_click_target(world, mx, my, "enemy")
            if target:
                self.combat.minion_attack(world, minion_ent, target)
            self._deselect_all(world)
            self.gs.clear_selection()
            return

        # Case 3: Nothing selected → find what was clicked
        clicked_entity = self._find_entity_at(world, mx, my)
        if clicked_entity is None:
            self._deselect_all(world)
            self.gs.clear_selection()
            # Also check buttons
            self._check_buttons(world, mx, my)
            return

        # Check if it's a hand card
        hand_ents = list(world.get_entities_with(HandComponent))
        if hand_ents:
            hand = world.get_component(hand_ents[0], HandComponent)
            if clicked_entity in hand.cards:
                self._select_card(world, clicked_entity)
                return

        # Check if it's a player minion (for attack)
        board_ents = list(world.get_entities_with(BoardComponent))
        if board_ents:
            board = world.get_component(board_ents[0], BoardComponent)
            if clicked_entity in board.minions:
                m_comp = world.get_component(clicked_entity, MinionComponent)
                atk = world.get_component(clicked_entity, AttackComponent)
                if m_comp and m_comp.owner == "player" and atk and atk.can_attack:
                    self._select_minion(world, clicked_entity)
                    return

        # Nothing actionable
        self._deselect_all(world)
        self.gs.clear_selection()

    # ── Play Card ───────────────────────────────────────────────

    def _play_card(self, world: World, card_entity, target) -> None:
        card = world.get_component(card_entity, CardComponent)
        energy = self._get_energy(world)
        if not card:
            return

        # Check energy
        if energy and energy.current < card.cost:
            self.gs.show_message("Not enough Energy!")
            return

        # Spend energy
        if energy:
            energy.spend(card.cost)

        # Resolve effect
        self.combat.resolve_card(world, card_entity, target)

        # Remove from hand
        self._remove_from_hand(world, card_entity)

        # Put card entity into discard (for non-minion cards)
        # For minion cards, the minion is now on board
        if card.card_type != "minion":
            self._add_to_discard(world, card_entity)
        # For minion cards, card_entity is now a minion on board

        self.gs.clear_selection()
        self._deselect_all(world)

    # ── Target Finding ──────────────────────────────────────────

    def _find_click_target(self, world: World, mx: int, my: int, target_type: str):
        """Find a valid target under the mouse cursor."""
        if target_type == "enemy":
            for e in world.get_entities_with(EnemyComponent, RenderComponent):
                render = world.get_component(e, RenderComponent)
                if render and render.rect and self._point_in_rect(mx, my, render.rect):
                    return e
            return None

        if target_type == "self":
            return "self"

        if target_type == "none":
            return "none"

        if target_type == "friendly_minion":
            board_ents = list(world.get_entities_with(BoardComponent))
            if board_ents:
                board = world.get_component(board_ents[0], BoardComponent)
                for m_ent in board.minions:
                    render = world.get_component(m_ent, RenderComponent)
                    m_comp = world.get_component(m_ent, MinionComponent)
                    if render and render.rect and self._point_in_rect(mx, my, render.rect):
                        if m_comp and m_comp.owner == "player":
                            return m_ent
            return None

        if target_type == "any_minion":
            for e in world.get_entities_with(MinionComponent, RenderComponent):
                render = world.get_component(e, RenderComponent)
                if render and render.rect and self._point_in_rect(mx, my, render.rect):
                    return e
            return None

        return None

    def _find_entity_at(self, world: World, mx: int, my: int):
        """Find any clickable entity under the cursor (top-most first)."""
        # Check hand cards (top-most = last in list = drawn last = visually on top)
        hand_ents = list(world.get_entities_with(HandComponent))
        if hand_ents:
            hand = world.get_component(hand_ents[0], HandComponent)
            for c_ent in reversed(hand.cards):
                render = world.get_component(c_ent, RenderComponent)
                if render and render.rect and self._point_in_rect(mx, my, render.rect):
                    return c_ent

        # Check board minions
        board_ents = list(world.get_entities_with(BoardComponent))
        if board_ents:
            board = world.get_component(board_ents[0], BoardComponent)
            for m_ent in reversed(board.minions):
                render = world.get_component(m_ent, RenderComponent)
                if render and render.rect and self._point_in_rect(mx, my, render.rect):
                    return m_ent

        # Check enemies
        for e in world.get_entities_with(EnemyComponent, RenderComponent):
            render = world.get_component(e, RenderComponent)
            if render and render.rect and self._point_in_rect(mx, my, render.rect):
                return e

        return None

    # ── Selection ────────────────────────────────────────────────

    def _select_card(self, world: World, card_entity) -> None:
        self._deselect_all(world)
        self.gs.selected_card_entity = card_entity
        render = world.get_component(card_entity, RenderComponent)
        if render:
            render.selected = True

        # Highlight valid targets
        card = world.get_component(card_entity, CardComponent)
        if card and card.target_type in ("enemy", "any_minion", "friendly_minion"):
            self._highlight_targets(world, card.target_type)

    def _select_minion(self, world: World, minion_entity) -> None:
        self._deselect_all(world)
        self.gs.selected_minion_entity = minion_entity
        render = world.get_component(minion_entity, RenderComponent)
        if render:
            render.selected = True

        # Highlight enemies as targets
        self._highlight_targets(world, "enemy")

    def _deselect_all(self, world: World) -> None:
        for e in world.get_entities_with(RenderComponent):
            render = world.get_component(e, RenderComponent)
            if render:
                render.selected = False
                render.targetable = False

    def _highlight_targets(self, world: World, target_type: str) -> None:
        if target_type == "enemy":
            for e in world.get_entities_with(EnemyComponent, RenderComponent):
                render = world.get_component(e, RenderComponent)
                if render:
                    render.targetable = True
        elif target_type == "any_minion":
            for e in world.get_entities_with(MinionComponent, RenderComponent):
                render = world.get_component(e, RenderComponent)
                if render:
                    render.targetable = True
        elif target_type == "friendly_minion":
            for e in world.get_entities_with(MinionComponent, RenderComponent):
                render = world.get_component(e, RenderComponent)
                m_comp = world.get_component(e, MinionComponent)
                if render and m_comp and m_comp.owner == "player":
                    render.targetable = True

    # ── Buttons ────────────────────────────────────────────────

    def _check_buttons(self, world: World, mx: int, my: int) -> None:
        # Buttons are drawn by render_system; we check via stored rects
        # For simplicity, hardcode button rects here matching render_system
        # End Turn button
        end_rect = pygame.Rect(SCREEN_WIDTH - 160, SCREEN_HEIGHT - 90, 140, 36)
        if end_rect.collidepoint(mx, my) and self.gs.is_player_turn:
            self._end_player_turn(world)
            return

        # Next Wave button
        next_rect = pygame.Rect(SCREEN_WIDTH - 160, SCREEN_HEIGHT - 135, 140, 36)
        if next_rect.collidepoint(mx, my):
            self._start_next_wave(world)
            return

    # ── Wave / Reward / Game Over ──────────────────────────────

    def _start_next_wave(self, world: World) -> None:
        from enemy_factory import generate_wave_enemies
        from excel_loader import load_enemies
        import json, os

        wave_comp = self._get_wave_comp(world)
        if not wave_comp:
            return

        wave_comp.wave_number += 1
        wave_comp.wave_cleared = False

        data_dir = os.path.join(os.path.dirname(__file__), "..", "data")
        data_dir = os.path.normpath(data_dir)
        config_dir = os.path.join(os.path.dirname(__file__), "..", "config")
        config_dir = os.path.normpath(config_dir)

        enemies_data = load_enemies(config_dir, data_dir)
        if not enemies_data:
            json_path = os.path.join(data_dir, "enemies.json")
            if os.path.exists(json_path):
                with open(json_path, "r", encoding="utf-8") as f:
                    enemies_data = json.load(f)

        if not enemies_data:
            self.gs.show_message("No enemy data found!")
            return

        new_enemies = generate_wave_enemies(world, enemies_data, wave_comp.wave_number)
        wave_comp.enemies_alive = len(new_enemies)

        # Refresh player energy for new turn
        energy = self._get_energy(world)
        if energy:
            energy.refresh()

        # Draw 1 card at start of wave
        self._draw_one(world)

        self.gs.phase = Phase.PLAYER_TURN
        self.gs.clear_selection()

    def _handle_reward_click(self, world: World, mx: int, my: int) -> None:
        for c_ent in self.gs.reward_cards:
            render = world.get_component(c_ent, RenderComponent)
            if render and render.rect and self._point_in_rect(mx, my, render.rect):
                # Pick this card — add to deck
                self._add_to_deck(world, c_ent)
                # Remove reward UI
                self.gs.reward_cards.clear()
                self.gs.phase = Phase.PLAYER_TURN
                self.gs.clear_selection()
                return

    # ── Keyboard ────────────────────────────────────────────────

    def _handle_key(self, world: World, event) -> None:
        if event.key in (pygame.K_RETURN, pygame.K_SPACE):
            if self.gs.phase == Phase.GAME_OVER:
                self._start_new_game(world)
            elif self.gs.phase == Phase.MENU:
                self._start_new_game(world)
            elif self.gs.is_player_turn:
                self._end_player_turn(world)

        if event.key == pygame.K_ESCAPE:
            self.gs.clear_selection()
            self._deselect_all(world)

        if event.key == pygame.K_n and self.gs.phase != Phase.GAME_OVER:
            self._start_next_wave(world)

    # ── Game Start / Restart ────────────────────────────────────

    def _start_new_game(self, world: World) -> None:
        import json, os, random
        from excel_loader import load_cards
        from card_factory import create_card_entity

        # Clear world
        world.clear()

        # Create player entity
        player = world.create_entity()
        world.add_component(player, HealthComponent(STARTING_HP, STARTING_HP))
        world.add_component(player, EnergyComponent(STARTING_ENERGY, MAX_ENERGY))
        world.add_component(player, PlayerComponent())
        world.add_component(player, RenderComponent())

        # Create wave entity
        wave_ent = world.create_entity()
        world.add_component(wave_ent, WaveComponent())

        # Create deck entity and populate starter deck
        deck_ent = world.create_entity()
        deck_comp = DeckComponent()

        data_dir = os.path.join(os.path.dirname(__file__), "..", "data")
        data_dir = os.path.normpath(data_dir)
        config_dir = os.path.join(os.path.dirname(__file__), "..", "config")
        config_dir = os.path.normpath(config_dir)

        cards_data = load_cards(config_dir, data_dir)
        if not cards_data:
            json_path = os.path.join(data_dir, "cards.json")
            if os.path.exists(json_path):
                with open(json_path, "r", encoding="utf-8") as f:
                    cards_data = json.load(f)

        card_pool_map = {c["id"]: c for c in (cards_data or [])}

        # Starter deck
        starter_ids = (["strike"] * 3 + ["defend"] * 3 +
                       ["shield_bearer"] * 3 + ["arcane_missiles"] * 2)
        valid_ids = [sid for sid in starter_ids if sid in card_pool_map]
        random.shuffle(valid_ids)

        for cid in valid_ids:
            c_ent = create_card_entity(world, card_pool_map[cid])
            deck_comp.cards.append(c_ent)

        world.add_component(deck_ent, deck_comp)

        # Create hand entity
        hand_ent = world.create_entity()
        world.add_component(hand_ent, HandComponent())

        # Create board entity
        board_ent = world.create_entity()
        world.add_component(board_ent, BoardComponent())

        # Draw starting hand
        for _ in range(INITIAL_HAND_SIZE):
            self._draw_one(world)

        # Start first wave
        self.gs.phase = Phase.PLAYER_TURN
        self.gs.clear_selection()
        self._start_next_wave(world)

    # ── Helpers ──────────────────────────────────────────────────

    def _draw_one(self, world: World) -> None:
        hand_ents = list(world.get_entities_with(HandComponent))
        deck_ents = list(world.get_entities_with(DeckComponent))
        if not hand_ents or not deck_ents:
            return
        hand = world.get_component(hand_ents[0], HandComponent)
        deck = world.get_component(deck_ents[0], DeckComponent)
        if len(hand.cards) >= MAX_HAND_SIZE:
            return
        card = deck.draw_one()
        if card:
            hand.cards.append(card)

    def _remove_from_hand(self, world: World, card_entity) -> None:
        hand_ents = list(world.get_entities_with(HandComponent))
        if not hand_ents:
            return
        hand = world.get_component(hand_ents[0], HandComponent)
        if card_entity in hand.cards:
            hand.cards.remove(card_entity)

    def _add_to_discard(self, world: World, card_entity) -> None:
        deck_ents = list(world.get_entities_with(DeckComponent))
        if not deck_ents:
            return
        deck = world.get_component(deck_ents[0], DeckComponent)
        deck.add_to_discard(card_entity)

    def _add_to_deck(self, world: World, card_entity) -> None:
        deck_ents = list(world.get_entities_with(DeckComponent))
        if not deck_ents:
            return
        deck = world.get_component(deck_ents[0], DeckComponent)
        deck.cards.append(card_entity)

    def _end_player_turn(self, world: World) -> None:
        self.combat.end_player_turn(world)
        # After ending turn, start enemy turn
        self.gs.phase = Phase.ENEMY_TURN
        self.gs.enemy_turn_index = 0
        self.gs.enemy_turn_timer = 0.0

    def _get_energy(self, world: World) -> EnergyComponent | None:
        for e in world.entities:
            eng = world.get_component(e, EnergyComponent)
            if eng:
                return eng
        return None

    def _get_wave_comp(self, world: World) -> WaveComponent | None:
        for e in world.entities:
            w = world.get_component(e, WaveComponent)
            if w:
                return w
        return None

    def _point_in_rect(self, x: int, y: int, rect) -> bool:
        if not rect or len(rect) < 4:
            return False
        rx, ry, rw, rh = rect[0], rect[1], rect[2], rect[3]
        return rx <= x <= rx + rw and ry <= y <= ry + rh
