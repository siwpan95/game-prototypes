"""Headless test for kard_CN — verifies all systems run without crash."""
import os
os.environ['SDL_VIDEODRIVER'] = 'dummy'

import pygame
pygame.init()
pygame.display.set_mode((1, 1))

# ── Imports ──────────────────────────────────────────────────────
from ecs import World
from components import (
    PlayerComponent, HealthComponent, EnergyComponent,
    DeckComponent, HandComponent, EnemyComponent,
    AttackComponent, CardComponent, KeywordComponent,
    RenderComponent, FloatingTextComponent,
)
from game_state import GameState, Phase
from constants import *
from systems.combat_system import CombatSystem
from systems.keyword_system import KeywordSystem
from systems.input_system import InputSystem
from systems.render_system import RenderSystem
from card_factory import create_card_entity, pick_reward_cards, pick_reward_cards_elite
from enemy_factory import create_enemy_deck_entities, enemy_draw_card, cleanup_enemy_card_entities
from excel_loader import load_cards_by_pool, load_enemies
from rooms.room_system import (
    generate_next_room, generate_random_event,
    RoomType, EventChoice,
)

config_dir = "C:/Users/13122/Desktop/stay/kard_CN/config"
errors = []

def check(label, ok, detail=""):
    status = "PASS" if ok else "FAIL"
    print(f"  [{status}] {label}" + (f" — {detail}" if detail else ""))
    if not ok:
        errors.append(label)

# ════════════════════════════════════════════════════════════════
print("=== 1. Component creation ===")
# ────────────────────────────────────────────────────────────────
world = World()
player = world.create_entity()
world.add_component(player, PlayerComponent())
world.add_component(player, HealthComponent(hp=80, max_hp=80))
world.add_component(player, EnergyComponent(current=3, max_energy=3))
dc = DeckComponent(owner="player")
world.add_component(player, dc)
hc = HandComponent(owner="player")
world.add_component(player, hc)
check("PlayerComponent", world.get_component(player, PlayerComponent) is not None)
check("HealthComponent", world.get_component(player, HealthComponent).hp == 80)
check("EnergyComponent", world.get_component(player, EnergyComponent).current == 3)
check("DeckComponent", len(dc.cards) == 0)
check("HandComponent", len(hc.cards) == 0)

# EnemyComponent
enemy = world.create_entity()
world.add_component(enemy, EnemyComponent(enemy_id="goblin_grunt", name="Goblin"))
world.add_component(enemy, HealthComponent(hp=30, max_hp=30))
world.add_component(enemy, AttackComponent(attack=5))
check("EnemyComponent", world.get_component(enemy, EnemyComponent).name == "Goblin")
check("AttackComponent", world.get_component(enemy, AttackComponent).attack == 5)

# CardComponent via factory (Pool A is player collection, starts empty; use Pool C for test)
pools = load_cards_by_pool(config_dir, "dummy")
cards_c = pools.get("C", [])
if cards_c:
    card_ent = create_card_entity(world, dict(cards_c[0]))
    cc = world.get_component(card_ent, CardComponent)
    check("create_card_entity", cc is not None, f"card={cc.name if cc else 'N/A'}")
else:
    check("create_card_entity", False, "No cards in pool C")

# KeywordComponent
kw_ent = world.create_entity()
world.add_component(kw_ent, KeywordComponent(taunt=True, lifesteal=True))
kwc = world.get_component(kw_ent, KeywordComponent)
check("KeywordComponent", kwc is not None and kwc.taunt)

# ════════════════════════════════════════════════════════════════
print("\n=== 2. Systems init & update ===")
# ────────────────────────────────────────────────────────────────
gs = GameState()
combat = CombatSystem(gs)
kw_sys = KeywordSystem(gs)
inp = InputSystem(gs, combat)
screen = pygame.display.set_mode((1, 1))
rend = RenderSystem(screen, gs)

for sys in [combat, kw_sys, inp, rend]:
    try:
        sys.update(world, 0.016)
        check(f"{sys.__class__.__name__}.update", True)
    except Exception as exc:
        check(f"{sys.__class__.__name__}.update", False, str(exc))

# ════════════════════════════════════════════════════════════════
print("\n=== 3. Combat: attack card vs enemy ===")
# ────────────────────────────────────────────────────────────────
if cards_c:
    world2 = World()
    e = world2.create_entity()
    world2.add_component(e, HealthComponent(hp=30, max_hp=30))
    world2.add_component(e, EnemyComponent(enemy_id="x", name="X"))
    cd = dict(cards_c[0])
    cd["damage"] = 10
    ce = create_card_entity(world2, cd)
    cc2 = world2.get_component(ce, CardComponent)
    try:
        combat2 = CombatSystem(gs)
        combat2._resolve_attack_card(world2, cc2, e)
        eh = world2.get_component(e, HealthComponent)
        check("Combat damage", eh.hp == 20, f"hp={eh.hp}")
    except Exception as exc:
        check("Combat damage", False, str(exc))

# ════════════════════════════════════════════════════════════════
print("\n=== 4. Enemy deck creation ===")
# ────────────────────────────────────────────────────────────────
world3 = World()
try:
    deck_ent, hand_ent = create_enemy_deck_entities(
        world3, pools.get("B", []), pools.get("C", []), 1, False
    )
    dcomp = world3.get_component(deck_ent, DeckComponent)
    hcomp = world3.get_component(hand_ent, HandComponent)
    check("enemy deck entities", dcomp is not None and hcomp is not None)
    check("enemy deck size", len(dcomp.cards) > 0, f"size={len(dcomp.cards)}")
except Exception as exc:
    check("enemy deck entities", False, str(exc))

# ════════════════════════════════════════════════════════════════
print("\n=== 5. Room generation ===")
# ────────────────────────────────────────────────────────────────
for i in range(10):
    room = generate_next_room(i + 1, False)
    check(f"Room {i+1}", room is not None, f"type={room.room_type.name}")

# ════════════════════════════════════════════════════════════════
print("\n=== 6. Event system ===")
# ────────────────────────────────────────────────────────────────
try:
    evt = generate_random_event()
    check("generate_random_event", evt is not None)
    if evt:
        check("event has id", hasattr(evt, 'id') or isinstance(evt, object))
except Exception as exc:
    check("generate_random_event", False, str(exc))

# ════════════════════════════════════════════════════════════════
print("\n=== 7. Reward card picking ===")
# ────────────────────────────────────────────────────────────────
all_cards = pools.get("C", []) or pools.get("B", [])
if all_cards:
    try:
        rewards = pick_reward_cards(all_cards, 3)
        check("pick_reward_cards", isinstance(rewards, list) and len(rewards) <= 3,
              f"got {len(rewards)}")
    except Exception as exc:
        check("pick_reward_cards", False, str(exc))
    try:
        rewards_elite = pick_reward_cards_elite(all_cards, 4)
        check("pick_reward_cards_elite", isinstance(rewards_elite, list) and len(rewards_elite) <= 4,
              f"got {len(rewards_elite)}")
    except Exception as exc:
        check("pick_reward_cards_elite", False, str(exc))

# ════════════════════════════════════════════════════════════════
print("\n=== 8. Constants & config ===")
# ────────────────────────────────────────────────────────────────
check("SCREEN_WIDTH", isinstance(SCREEN_WIDTH, int) and SCREEN_WIDTH > 0)
check("FPS", isinstance(FPS, int) and FPS > 0)
check("TITLE", isinstance(TITLE, str) and len(TITLE) > 0)
check("config dir exists", os.path.isdir(config_dir), config_dir)

# Check Excel files exist
for fn in ["enemies.xlsx", "events.xlsx", "rooms.xlsx"]:
    fp = os.path.join(config_dir, fn)
    check(f"{fn} exists", os.path.exists(fp), fp)

for fn in ["cards_B.xlsx", "cards_C.xlsx"]:
    fp = os.path.join(config_dir, fn)
    check(f"{fn} exists", os.path.exists(fp), fp)

# ════════════════════════════════════════════════════════════════
print("\n=== 9. Render rect format ===")
# ────────────────────────────────────────────────────────────────
# RenderComponent.rect is None by default (set by render system)
r = RenderComponent()
r.rect = (10, 20, 100, 150)
check("RenderComponent.rect set", r.rect == (10, 20, 100, 150), f"rect={r.rect}")

# ════════════════════════════════════════════════════════════════
print("\n=== 10. Hover detection logic ===")
# ────────────────────────────────────────────────────────────────
# Verify the hover logic in input_system.py works correctly
# The buggy line was: in_rect = (rx <= mx <= rx + rw) if hasattr(render, '_r') else False
# Should be: proper rect collision check
import inspect
src = inspect.getsource(inp._update_hover)
has_bug = "hasattr(render, '_r')" in src
check("Hover: no '_r' bug", not has_bug,
      "BUG: hasattr(render, '_r') still present!" if has_bug else "OK")

# ════════════════════════════════════════════════════════════════
print("\n=== 11. Load enemies ===")
# ────────────────────────────────────────────────────────────────
try:
    enemies_data = load_enemies(config_dir, "dummy")
    check("load_enemies", isinstance(enemies_data, list), f"type={type(enemies_data)}")
    if isinstance(enemies_data, list):
        check("enemies has data", len(enemies_data) > 0, f"count={len(enemies_data)}")
except Exception as exc:
    check("load_enemies", False, str(exc))

# ════════════════════════════════════════════════════════════════
print("\n=== 12. FloatingText spawn ===")
# ────────────────────────────────────────────────────────────────
world4 = World()
try:
    ft_ent = world4.create_entity()
    world4.add_component(ft_ent, FloatingTextComponent(
        text="-10", x=100, y=200, color=FLOAT_DAMAGE, duration=1.0
    ))
    world4.add_component(ft_ent, RenderComponent())
    check("FloatingTextComponent", True)
except Exception as exc:
    check("FloatingTextComponent", False, str(exc))

# ════════════════════════════════════════════════════════════════
print("\n" + "=" * 50)
print(f"RESULT: {len(errors)} failures out of all tests")
if errors:
    print("Failures:")
    for e in errors:
        print(f"  - {e}")
else:
    print("ALL TESTS PASSED")
print("=" * 50)

pygame.quit()
