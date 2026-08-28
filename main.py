"""KARD — main entry point.
Vampire Survivors + Slay the Spire + Hearthstone keywords + Endless Mode.
ECS architecture, pygame_ce, mouse-driven, English only.
"""

from __future__ import annotations
import pygame
import os
import sys

# Add project root to path so imports work
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ecs import World
from components import (
    HealthComponent, EnergyComponent,
    WaveComponent, EnemyComponent,
    AttackComponent, HandComponent, DeckComponent,
)
from game_state import GameState, Phase
from systems.combat_system import CombatSystem
from systems.keyword_system import KeywordSystem
from systems.render_system import RenderSystem
from systems.input_system import InputSystem
from card_factory import create_card_entity, pick_reward_cards


# ── Constants (re-import for convenience) ───────────────────────────────
from constants import *


def main() -> None:
    pygame.init()
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    pygame.display.set_caption(TITLE)
    clock = pygame.time.Clock()

    # ── ECS World ──────────────────────────────────────────────────────
    world = World()
    gs = GameState()

    # ── Systems ────────────────────────────────────────────────────────
    combat_sys = CombatSystem(gs)
    keyword_sys = KeywordSystem(gs)
    render_sys = RenderSystem(screen, gs)
    input_sys = InputSystem(gs, combat_sys)

    world.add_system(input_sys)     # input first
    world.add_system(combat_sys)     # combat resolution
    world.add_system(keyword_sys)    # keyword effects
    world.add_system(render_sys)     # drawing (runs last)

    # ── Generate template Excel files if missing ──────────────────────
    config_dir = os.path.join(os.path.dirname(__file__), "config")
    data_dir = os.path.join(os.path.dirname(__file__), "data")
    os.makedirs(config_dir, exist_ok=True)
    os.makedirs(data_dir, exist_ok=True)

    # ── Menu Phase ────────────────────────────────────────────────────
    gs.phase = Phase.MENU

    # ── Main Loop ─────────────────────────────────────────────────────
    running = True
    while running:
        dt = clock.tick(FPS) / 1000.0
        events = []

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
                continue
            events.append(event)

        # ── Phase: MENU ──────────────────────────────────────────
        if gs.phase == Phase.MENU:
            screen.fill(BG_COLOR)
            _draw_menu(screen)
            pygame.display.flip()
            input_sys.update(world, dt, events)
            continue

        # ── Phase: PLAYER_TURN ───────────────────────────────────
        # (input system handles this via mouse/keyboard)

        # ── Phase: ENEMY_TURN ───────────────────────────────────
        if gs.phase == Phase.ENEMY_TURN:
            _process_enemy_turn(world, gs, combat_sys, dt)

        # ── Phase: WAVE_CLEAR ─────────────────────────────────────
        if gs.phase == Phase.WAVE_CLEAR:
            gs.wave_clear_timer += dt
            if gs.wave_clear_timer >= 1.5:
                _show_reward(world, gs)
                gs.phase = Phase.REWARD
                gs.wave_clear_timer = 0.0

        # ── Phase: REWARD ──────────────────────────────────────
        # (input system handles reward card click)

        # ── Phase: GAME_OVER ──────────────────────────────────
        # (render system draws overlay, input system handles restart)

        # ── Message timer ────────────────────────────────────────
        if gs.message_timer > 0:
            gs.message_timer -= dt
            if gs.message_timer <= 0:
                gs.message = ""

        # ── Update all systems ─────────────────────────────────────
        world.update(dt, events)

        pygame.display.flip()

    pygame.quit()


# ── Phase Logic ──────────────────────────────────────────────────────────────

def _draw_menu(screen) -> None:
    """Draw the main menu."""
    font_title = pygame.font.Font(None, FONT_LARGE_SIZE)
    font_sub = pygame.font.Font(None, FONT_TINY_SIZE)
    font_hint = pygame.font.Font(None, FONT_MEDIUM_SIZE)
    font_ctrl = pygame.font.Font(None, FONT_TINY_SIZE)

    # Title
    title = font_title.render("KARD", True, (255, 220, 80))
    screen.blit(title, (SCREEN_WIDTH // 2 - title.get_width() // 2, 180))

    subtitle = font_sub.render(
        "Vampire Survivors x Slay the Spire x Hearthstone", True, TEXT_DIM)
    screen.blit(subtitle, (SCREEN_WIDTH // 2 - subtitle.get_width() // 2, 230))

    hint = font_hint.render("Click anywhere or press ENTER to start", True, (200, 200, 200))
    screen.blit(hint, (SCREEN_WIDTH // 2 - hint.get_width() // 2, 320))

    controls = [
        "Left Click: Select card / Play card / Attack",
        "Right Click / ESC: Deselect",
        "ENTER / Space: End turn",
        "N: Start next wave",
    ]
    cy = 420
    for line in controls:
        ls = font_ctrl.render(line, True, TEXT_DIM)
        screen.blit(ls, (SCREEN_WIDTH // 2 - ls.get_width() // 2, cy))
        cy += 22


def _process_enemy_turn(world: World, gs: GameState,
                         combat_sys: CombatSystem, dt: float) -> None:
    """Process enemy intents one by one with a small delay."""
    gs.enemy_turn_timer += dt

    if gs.enemy_turn_timer < 0.8:   # 0.8s between each enemy action
        return

    gs.enemy_turn_timer = 0.0

    # Find all alive enemies
    enemy_ents = list(world.get_entities_with(EnemyComponent, HealthComponent))
    if gs.enemy_turn_index >= len(enemy_ents):
        # All enemies acted — end enemy turn, start player turn
        _end_enemy_turn(world, gs)
        return

    enemy = enemy_ents[gs.enemy_turn_index]
    gs.enemy_turn_index += 1

    enemy_comp = world.get_component(enemy, EnemyComponent)
    atk_comp = world.get_component(enemy, AttackComponent)
    h_comp = world.get_component(enemy, HealthComponent)

    if not enemy_comp or not h_comp or not h_comp.alive:
        return

    # Execute intent
    if enemy_comp.intent == "attack":
        combat_sys.enemy_attack_player(world, enemy)
    elif enemy_comp.intent == "defend":
        if h_comp:
            h_comp.shield += enemy_comp.intent_value
    elif enemy_comp.intent == "buff":
        if atk_comp:
            atk_comp.attack += enemy_comp.intent_value

    # Choose next intent for next turn
    from enemy_factory import choose_next_intent
    choose_next_intent(enemy_comp, atk_comp)


def _end_enemy_turn(world: World, gs: GameState) -> None:
    """Clean up after enemy turn."""
    # Check if all enemies are dead
    enemy_ents = list(world.get_entities_with(EnemyComponent, HealthComponent))
    alive = [e for e in enemy_ents
             if world.get_component(e, HealthComponent)
             and world.get_component(e, HealthComponent).alive]

    if not alive:
        # Wave cleared!
        gs.phase = Phase.WAVE_CLEAR
        wave_comps = list(world.get_entities_with(WaveComponent))
        if wave_comps:
            w = world.get_component(wave_comps[0], WaveComponent)
            if w:
                w.wave_cleared = True
    else:
        # Still enemies alive — player's turn again
        gs.phase = Phase.PLAYER_TURN
        gs.clear_selection()
        # Refresh energy
        for e in world.entities:
            eng = world.get_component(e, EnergyComponent)
            if eng:
                eng.refresh()
                break
        # Draw 1 card
        _draw_one_card(world)


def _draw_one_card(world: World) -> None:
    """Draw one card from deck to hand."""
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


def _show_reward(world: World, gs: GameState) -> None:
    """Show 3 reward cards to choose from."""
    import json
    data_dir = os.path.join(os.path.dirname(__file__), "data")
    json_path = os.path.join(data_dir, "cards.json")
    with open(json_path, "r", encoding="utf-8") as f:
        card_pool = json.load(f)
    chosen = pick_reward_cards(card_pool, REWARD_CARD_COUNT)
    # Create card entities for display
    gs.reward_cards.clear()
    for cdata in chosen:
        ent = create_card_entity(world, cdata)
        gs.reward_cards.append(ent)


# ── Entry Point ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    main()
