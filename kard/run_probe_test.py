"""Quick probe-smoke test — initializes game and simulates start to trigger probes."""
import os
os.environ['SDL_VIDEODRIVER'] = 'dummy'
os.environ['KARD_DEBUG'] = '1'

import pygame
pygame.init()
screen = pygame.display.set_mode((1280, 720))

import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ecs import World
from game_state import GameState, Phase
from systems.combat_system import CombatSystem
from systems.keyword_system import KeywordSystem
from systems.render_system import RenderSystem
from systems.input_system import InputSystem
from audio.audio_system import AudioSystem
from card_factory import create_card_entity
from excel_loader import load_cards_by_pool
from constants import *

print("=" * 60)
print("  KARD DEBUG PROBES — SMOKE TEST")
print("=" * 60)

# ── Setup ──
world = World()
gs = GameState()
combat_sys = CombatSystem(gs)
keyword_sys = KeywordSystem(gs)
render_sys = RenderSystem(screen, gs)
input_sys = InputSystem(gs, combat_sys)
audio_sys = AudioSystem(gs)
input_sys.audio_sys = audio_sys

world.add_system(input_sys)
world.add_system(combat_sys)
world.add_system(keyword_sys)
world.add_system(audio_sys)
world.add_system(render_sys)

gs.phase = Phase.MENU
from debug_probes import probe

probe("run_probe_test::setup", "初始化完成", {"probe_count": "starting"}, module="main")

# ── Simulate new game start ──
# Replicate _start_new_game essentials
config_dir = os.path.join(os.path.dirname(__file__), "config")
data_dir = os.path.join(os.path.dirname(__file__), "data")

world.clear()

player = world.create_entity()
from components import HealthComponent, EnergyComponent, PlayerComponent
from components import DeckComponent, HandComponent, BoardComponent
from components import EnemyComponent, AttackComponent, CardComponent
from components import MinionComponent, WaveComponent

world.add_component(player, HealthComponent(STARTING_HP, STARTING_HP))
world.add_component(player, EnergyComponent(STARTING_ENERGY, MAX_ENERGY))
world.add_component(player, PlayerComponent())

wave_ent = world.create_entity()
world.add_component(wave_ent, WaveComponent())

deck_ent = world.create_entity()
deck_comp = DeckComponent(owner="player")
pools = load_cards_by_pool(config_dir, data_dir)
card_pool = pools.get("B", [])
card_pool_map = {c["id"]: c for c in (card_pool or [])}
starter_ids = ["strike"] * 5 + ["defend"] * 4 + ["shield_bearer"] * 3
import random
random.shuffle(starter_ids)
for cid in starter_ids:
    if cid in card_pool_map:
        c_ent = create_card_entity(world, card_pool_map[cid])
        deck_comp.cards.append(c_ent)
world.add_component(deck_ent, deck_comp)

hand_ent = world.create_entity()
world.add_component(hand_ent, HandComponent(owner="player"))
for _ in range(INITIAL_HAND_SIZE):
    card = deck_comp.draw_one()
    if card:
        from components import HandComponent as HC
        hand = world.get_component(hand_ent, HC)
        if hand:
            hand.cards.append(card)

board_ent = world.create_entity()
world.add_component(board_ent, BoardComponent())

gs.room_number = 1
gs.is_battle_room = True
gs.is_elite_room = False
gs.gold = 50
gs.phase = Phase.PLAYER_TURN

# ── Spawn an enemy ──
from enemy_factory import generate_wave_enemies, create_enemy_deck_entities
from excel_loader import load_enemies

enemies_data = load_enemies(config_dir, data_dir)
if enemies_data:
    new_enemies = generate_wave_enemies(world, enemies_data, 1, is_elite=False)
    wc = world.get_component(wave_ent, WaveComponent)
    if wc:
        wc.enemies_alive = len(new_enemies)

probe("run_probe_test::game_started", "游戏/战斗已就绪",
      {"room": gs.room_number, "hand_size": INITIAL_HAND_SIZE,
       "enemies": len(new_enemies) if enemies_data else 0},
      module="main")

# ── Simulate playing an AOE attack card (test our fix) ──
# Find an AOE card (arcane_missiles from pool C with target="none")
pools_c = pools.get("C", [])
aoe_cards = [c for c in pools_c if c.get("target") == "none" and c.get("type") == "attack"]
if aoe_cards:
    aoe_data = dict(aoe_cards[0])
    aoe_ent = create_card_entity(world, aoe_data)
    aoe_card = world.get_component(aoe_ent, CardComponent)
    probe("run_probe_test::test_aoe", f"测试AOE攻击卡: {aoe_card.name}",
          {"damage": aoe_card.damage, "target": aoe_card.target_type}, module="combat")

    # Play the AOE card via combat system
    combat_sys.resolve_card(world, aoe_ent, "none")

    # Check enemy HP
    enemy_ents = list(world.get_entities_with(EnemyComponent, HealthComponent))
    for enemy_ent in enemy_ents:
        eh = world.get_component(enemy_ent, HealthComponent)
        probe("run_probe_test::aoe_result", "AOE伤害后敌人状态",
              {"hp": eh.hp, "max_hp": eh.max_hp, "alive": eh.alive}, module="combat")
    world.destroy_entity(aoe_ent)
else:
    probe("run_probe_test::test_aoe", "⚠ 未找到AOE攻击卡用于测试", module="main")

# ── Simulate play a single-target attack ──
strike_cards = [c for c in pools.get("B", []) if c.get("id") == "strike"]
if strike_cards and enemy_ents:
    strike_ent = create_card_entity(world, dict(strike_cards[0]))
    strike_card = world.get_component(strike_ent, CardComponent)
    target = enemy_ents[0]
    probe("run_probe_test::test_strike", f"测试单体攻击: {strike_card.name}",
          {"damage": strike_card.damage, "target": "enemy_entity"}, module="combat")
    combat_sys.resolve_card(world, strike_ent, target)
    eh = world.get_component(target, HealthComponent)
    probe("run_probe_test::strike_result", "打击后敌人状态",
          {"hp": eh.hp, "max_hp": eh.max_hp, "alive": eh.alive}, module="combat")
    world.destroy_entity(strike_ent)

# ── Test room complete flow ──
probe("run_probe_test::room_test", "测试房间清场流程", module="main")
# Manually kill all enemies to trigger room clear
for enemy_ent in list(world.get_entities_with(EnemyComponent, HealthComponent)):
    eh = world.get_component(enemy_ent, HealthComponent)
    if eh:
        eh.hp = 0  # Kill enemy
    combat_sys._check_death(world, enemy_ent)

probe("run_probe_test::phase", "最终阶段",
      {"phase": str(gs.phase), "room": gs.room_number}, module="main")

# ── Probe summary ──
from debug_probes import probe_state_summary, is_enabled
print()

# Clean up
pygame.quit()
print("[OK] 调试探针冒烟测试完成")
