"""KARD — main entry point.
"""

from __future__ import annotations
import pygame
import os
import sys
import random
from debug_probes import probe

# Add project root to path so imports work
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ecs import World
from components import (
    HealthComponent, EnergyComponent,
    WaveComponent, EnemyComponent, CardComponent,
    AttackComponent, HandComponent, DeckComponent,
    PlayerComponent, MinionComponent,
)
from game_state import GameState, Phase
from systems.combat_system import CombatSystem
from systems.keyword_system import KeywordSystem
from systems.render_system import RenderSystem
from systems.input_system import InputSystem
from audio.audio_system import AudioSystem
from audio.music_controller import MusicController
from audio.audio_components import AudioEventComponent, AudioEventType
from card_factory import create_card_entity, pick_reward_cards, pick_reward_cards_elite
from rooms.room_system import (
    RoomType, Room, generate_next_room, battle_gold_reward,
    generate_random_event, merchant_card_price, merchant_remove_price,
    merchant_card_count, campfire_heal_percent,
    EventChoice, set_events, set_room_config,
)
from enemy_factory import (
    create_enemy_deck_entities, enemy_draw_card, enemy_play_card,
    cleanup_enemy_card_entities, enemy_process_turn_ai,
)


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
    audio_sys = AudioSystem(gs)
    input_sys.audio_sys = audio_sys   # Link audio system to input for volume control

    world.add_system(input_sys)     # input first
    world.add_system(combat_sys)     # combat resolution
    world.add_system(keyword_sys)    # keyword effects
    world.add_system(audio_sys)      # audio processing
    world.add_system(render_sys)     # drawing (runs last)

    # ── Generate template Excel files if missing ──────────────────────
    config_dir = os.path.join(os.path.dirname(__file__), "config")
    data_dir = os.path.join(os.path.dirname(__file__), "data")
    os.makedirs(config_dir, exist_ok=True)
    os.makedirs(data_dir, exist_ok=True)

    # Generate card and enemy templates (existing)
    from excel_loader import (
        generate_card_template, generate_enemy_template,
        generate_events_template, generate_room_config_template,
        load_events, load_room_config,
    )
    enemies_path = os.path.join(config_dir, "enemies.xlsx")
    events_path = os.path.join(config_dir, "events.xlsx")
    rooms_path = os.path.join(config_dir, "rooms.xlsx")
    for gen, path in [
        (generate_enemy_template, enemies_path),
        (generate_events_template, events_path),
        (generate_room_config_template, rooms_path),
    ]:
        if not os.path.exists(path):
            try:
                gen(path)
            except Exception as exc:
                print(f"[警告] 无法生成模板 {os.path.basename(path)}: {exc}")

    # Card templates: cards_B.xlsx (3张基础公共牌) + cards_C.xlsx (可编辑池)
    cards_b_path = os.path.join(config_dir, "cards_B.xlsx")
    if not os.path.exists(cards_b_path):
        try:
            generate_card_template(config_dir)
            print("[提示] 已生成卡牌模板: cards_B.xlsx, cards_C.xlsx")
        except Exception as exc:
            print(f"[警告] 无法生成卡牌模板: {exc}")

    # Load events and room config from Excel (fall back to defaults if missing)
    event_list = load_events(config_dir, data_dir)
    room_cfg = load_room_config(config_dir, data_dir)
    if event_list:
        set_events(event_list)
    if room_cfg:
        set_room_config(room_cfg)

    # ── Menu Phase ────────────────────────────────────────────────────
    gs.phase = Phase.MENU
    probe("main::init", "游戏启动", {"phase": "MENU"}, module="main")

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

        # ── Phase: SETTINGS ──────────────────────────────────────
        if gs.phase == Phase.SETTINGS:
            screen.fill(BG_COLOR)
            _draw_settings(screen, gs)
            pygame.display.flip()
            input_sys.update(world, dt, events)
            continue

        # ── Phase: PLAYER_TURN ───────────────────────────────────
        # (input system handles this via mouse/keyboard)

        # ── Phase: ENEMY_TURN ───────────────────────────────────
        if gs.phase == Phase.ENEMY_TURN:
            _process_enemy_turn(world, gs, combat_sys, dt)

        # ── Phase: ROOM_COMPLETE ──────────────────────────────────
        if gs.phase == Phase.ROOM_COMPLETE:
            gs.room_clear_timer += dt
            if gs.room_clear_timer >= 1.5:
                gs.room_clear_timer = 0.0
                _advance_to_next_room(world, gs)

        # ── Phase: REWARD ──────────────────────────────────────
        # (input system handles reward card click)

        # ── Phase: EVENT ───────────────────────────────────────
        # (input system handles event choice click)

        # ── Phase: MERCHANT ──────────────────────────────────────
        # (input system handles buy/sell/leave)

        # ── Phase: CAMPFIRE ──────────────────────────────────────
        # (input system handles upgrade/rest choice)

        # ── Phase: GAME_OVER ──────────────────────────────────
        # (render system draws overlay, input system handles restart)

        # ── Check player death ───────────────────────────────────
        _check_player_death(world, gs, combat_sys)

        # ── Message timer ────────────────────────────────────────
        if gs.message_timer > 0:
            gs.message_timer -= dt
            if gs.message_timer <= 0:
                gs.message = ""

        # ── Update all systems ─────────────────────────────────────
        world.update(dt, events)

        pygame.display.flip()

    pygame.quit()


# ── Room Advancement ────────────────────────────────────────────────────────

def _advance_to_next_room(world: World, gs: GameState) -> None:
    """After room clear delay, determine and set up the next room."""
    probe("main::advance_room", "房间推进", {"room": gs.room_number}, module="main")
    # 安全清理：_handle_room_clear() 已清理过，此处作为兜底确保清理彻底
    # cleanup_enemy_card_entities 会统一清理敌方牌组+手牌+敌方随从
    cleanup_enemy_card_entities(world)

    # Determine last room type for constraints
    last_type = None
    if gs.is_battle_room:
        last_type = RoomType.ELITE if gs.is_elite_room else RoomType.BATTLE
    elif gs.is_event:
        last_type = RoomType.EVENT
    elif gs.is_merchant:
        last_type = RoomType.MERCHANT
    elif gs.is_campfire:
        last_type = RoomType.CAMPFIRE

    # Remember whether we just came from a cleared battle
    was_battle = gs.is_battle_room

    # Generate next room
    room = generate_next_room(last_type, gs.room_number)

    if room.room_type == RoomType.BATTLE or room.room_type == RoomType.ELITE:
        # Battle room — show reward, then start combat
        gs.is_battle_room = True
        gs.is_elite_room = (room.room_type == RoomType.ELITE)
        _show_reward(world, gs)
        gs.phase = Phase.REWARD
    elif was_battle:
        # 刚刚清完一场战斗 → 先展示奖励选牌（结算），再进入非战斗房间
        _show_reward(world, gs)
        gs.is_battle_room = False
        gs.is_elite_room = False
        gs.pending_next_room_type = room
        gs.phase = Phase.REWARD
    elif room.room_type == RoomType.EVENT:
        # Non-battle → event transition (no reward needed)
        gs.is_battle_room = False
        gs.is_elite_room = False
        gs.current_event = generate_random_event()
        gs.event_resolved = False
        gs.phase = Phase.EVENT
    elif room.room_type == RoomType.MERCHANT:
        # Non-battle → merchant transition
        gs.is_battle_room = False
        gs.is_elite_room = False
        _setup_merchant(world, gs)
        gs.phase = Phase.MERCHANT
    elif room.room_type == RoomType.CAMPFIRE:
        # Non-battle → campfire transition
        gs.is_battle_room = False
        gs.is_elite_room = False
        gs.campfire_action = ""
        gs.campfire_done = False
        gs.phase = Phase.CAMPFIRE


def _start_pending_room(world: World, gs: GameState) -> None:
    """After reward card selection, transition to the pending non-battle room."""
    room = gs.pending_next_room_type
    gs.pending_next_room_type = None
    if room is None:
        return
    if room.room_type == RoomType.EVENT:
        gs.current_event = generate_random_event()
        gs.event_resolved = False
        gs.phase = Phase.EVENT
    elif room.room_type == RoomType.MERCHANT:
        _setup_merchant(world, gs)
        gs.phase = Phase.MERCHANT
    elif room.room_type == RoomType.CAMPFIRE:
        gs.campfire_action = ""
        gs.campfire_done = False
        gs.phase = Phase.CAMPFIRE


def _setup_merchant(world: World, gs: GameState) -> None:
    """Generate merchant cards for sale from all pools."""
    from excel_loader import load_cards_by_pool
    config_dir = os.path.join(os.path.dirname(__file__), "config")
    data_dir = os.path.join(os.path.dirname(__file__), "data")
    pools = load_cards_by_pool(config_dir, data_dir)
    # Merchant sells from pool C (only editable pool) + B (basic)
    card_pool = pools.get("B", []) + pools.get("C", [])

    count = merchant_card_count()
    chosen = random.sample(card_pool, min(count, len(card_pool))) if len(card_pool) >= count else card_pool[:]

    gs.merchant_cards.clear()
    gs.merchant_prices.clear()
    for cdata in chosen:
        ent = create_card_entity(world, cdata)
        gs.merchant_cards.append(ent)
        # Pre-calculate price once to avoid random flashing
        gs.merchant_prices[id(ent)] = merchant_card_price(cdata.get("rarity", "common"))

    gs.merchant_remove_cost = merchant_remove_price()


# ── Phase Logic ──────────────────────────────────────────────────────────────

def _draw_arrow(screen, x: int, y: int, size: int, color: tuple,
                 direction: str = "left") -> None:
    """Draw a triangular arrow button."""
    if direction == "left":
        pts = [(x + size, y), (x, y + size // 2), (x + size, y + size)]
    else:
        pts = [(x, y), (x + size, y + size // 2), (x, y + size)]
    pygame.draw.polygon(screen, color, pts)


def _draw_menu(screen) -> None:
    """Draw the main menu with ascension level selector."""
    font_title = get_font(FONT_TITLE_SIZE)
    font_hint = get_font(FONT_MEDIUM_SIZE)
    font_btn = get_font(FONT_SMALL_SIZE)

    # Title
    title = font_title.render("卡牌 — 无尽地下城", True, (255, 220, 80))
    screen.blit(title, (SCREEN_WIDTH // 2 - title.get_width() // 2, 160))

    # ── Ascension selector ─────────────────────────────────────
    from systems.difficulty_system import ASCENSION_LEVELS, get_difficulty
    dm = get_difficulty()
    asc = dm.ascension
    asc_data = ASCENSION_LEVELS[asc]

    font_asc_label = get_font(FONT_MEDIUM_SIZE)
    asc_label = font_asc_label.render("进阶等级", True, (200, 200, 200))
    screen.blit(asc_label, (SCREEN_WIDTH // 2 - asc_label.get_width() // 2, 250))

    # Left / Right arrows + current level
    arrow_size = 28
    mouse_x, mouse_y = pygame.mouse.get_pos()
    asc_y = 285

    # Left arrow
    lx = SCREEN_WIDTH // 2 - 80
    l_hover = (lx <= mouse_x <= lx + arrow_size and asc_y <= mouse_y <= asc_y + arrow_size)
    l_color = (140, 180, 220) if l_hover else (100, 140, 180)
    _draw_arrow(screen, lx, asc_y, arrow_size, l_color, direction="left")

    # Level display
    asc_color = ASCENSION_COLORS.get(asc, (200, 200, 200))
    asc_text = font_title.render(f"{asc}", True, asc_color)
    screen.blit(asc_text, (SCREEN_WIDTH // 2 - asc_text.get_width() // 2, asc_y - 5))

    # Level name
    asc_name = font_btn.render(asc_data.name, True, asc_color)
    screen.blit(asc_name, (SCREEN_WIDTH // 2 - asc_name.get_width() // 2, asc_y + 40))

    # Right arrow
    rx = SCREEN_WIDTH // 2 + 55
    r_hover = (rx <= mouse_x <= rx + arrow_size and asc_y <= mouse_y <= asc_y + arrow_size)
    r_color = (140, 180, 220) if r_hover else (100, 140, 180)
    _draw_arrow(screen, rx, asc_y, arrow_size, r_color, direction="right")

    # ── Difficulty effects text ─────────────────────────────────
    effects = []
    if asc_data.hp_bonus > 0:
        effects.append(f"敌人HP/ATK +{int(asc_data.hp_bonus*100)}%")
    if asc_data.initial_shield > 0:
        effects.append(f"敌人初始护盾 +{asc_data.initial_shield}/层")
    if asc_data.boss_extra_keywords > 0:
        effects.append(f"Boss额外关键词 +{asc_data.boss_extra_keywords}")
    if asc_data.merchant_price_bonus > 1.0:
        effects.append(f"商人价格 {int(asc_data.merchant_price_bonus*100)}%")
    if asc_data.campfire_heal_mult < 1.0:
        effects.append(f"篝火回复 {int(asc_data.campfire_heal_mult*100)}%")

    font_fx = get_font(FONT_TINY_SIZE)
    for i, fx in enumerate(effects):
        fx_surf = font_fx.render(fx, True, (180, 160, 140))
        screen.blit(fx_surf, (SCREEN_WIDTH // 2 - fx_surf.get_width() // 2, 340 + i * 18))

    # ── Start hint ─────────────────────────────────────────────
    hint = font_hint.render("点击任意位置或按 ENTER 开始游戏", True, (200, 200, 200))
    screen.blit(hint, (SCREEN_WIDTH // 2 - hint.get_width() // 2, 420))

    # Settings button
    btn_w, btn_h = 120, 36
    btn_x = SCREEN_WIDTH // 2 - btn_w // 2
    btn_y = SCREEN_HEIGHT - 80
    mouse = pygame.mouse.get_pos()
    hover = (btn_x <= mouse[0] <= btn_x + btn_w and
             btn_y <= mouse[1] <= btn_y + btn_h)
    color = BUTTON_HOVER if hover else BUTTON_COLOR
    pygame.draw.rect(screen, color, (btn_x, btn_y, btn_w, btn_h), 0, 6)
    btn_text = font_btn.render("设  置", True, BUTTON_TEXT)
    screen.blit(btn_text, (btn_x + btn_w // 2 - btn_text.get_width() // 2,
                           btn_y + btn_h // 2 - btn_text.get_height() // 2))


def _draw_settings(screen, gs: "GameState") -> None:
    """Draw the settings / controls and volume screen."""
    font_title = get_font(FONT_TITLE_SIZE)
    font_sub = get_font(FONT_MEDIUM_SIZE)
    font_ctrl = get_font(FONT_SMALL_SIZE)
    font_btn = get_font(FONT_SMALL_SIZE)
    font_vol = get_font(FONT_SMALL_SIZE)

    # ── Title ─────────────────────────────────────────────────
    title = font_title.render("操作教学", True, (255, 220, 80))
    screen.blit(title, (SCREEN_WIDTH // 2 - title.get_width() // 2, 80))

    # ── Controls list ─────────────────────────────────────────
    controls = [
        ("鼠标左键点击", "选择卡牌 / 打出卡牌 / 攻击敌人"),
        ("鼠标右键 / ESC", "取消当前选择"),
        ("ENTER / 空格键", "结束当前回合"),
    ]

    start_y = 170
    for i, (key_text, desc_text) in enumerate(controls):
        y = start_y + i * 80
        key_surf = font_sub.render(key_text, True, (255, 220, 80))
        screen.blit(key_surf, (SCREEN_WIDTH // 2 - 280, y))
        desc_surf = font_ctrl.render(desc_text, True, TEXT_COLOR)
        screen.blit(desc_surf, (SCREEN_WIDTH // 2 - 280, y + 28))

    # ── Divider ───────────────────────────────────────────────
    div_y = 410
    pygame.draw.line(screen, (80, 80, 80), (SCREEN_WIDTH // 2 - 250, div_y),
                     (SCREEN_WIDTH // 2 + 250, div_y), 1)

    # ── Volume Section Title ──────────────────────────────────
    vol_title = font_sub.render("音量设置", True, (200, 200, 200))
    screen.blit(vol_title, (SCREEN_WIDTH // 2 - vol_title.get_width() // 2, div_y + 15))

    # ── Volume Sliders ────────────────────────────────────────
    _draw_volume_slider(screen, gs, "主音量", gs.master_volume, 460,
                        font_vol, "master")
    _draw_volume_slider(screen, gs, "音乐",  gs.music_volume,  520,
                        font_vol, "music")
    _draw_volume_slider(screen, gs, "音效",  gs.sfx_volume,    580,
                        font_vol, "sfx")

    # ── Back button ───────────────────────────────────────────
    btn_w, btn_h = 160, 40
    btn_x = SCREEN_WIDTH // 2 - btn_w // 2
    btn_y = SCREEN_HEIGHT - 80
    mouse = pygame.mouse.get_pos()
    hover = (btn_x <= mouse[0] <= btn_x + btn_w and
             btn_y <= mouse[1] <= btn_y + btn_h)
    color = BUTTON_HOVER if hover else BUTTON_COLOR
    pygame.draw.rect(screen, color, (btn_x, btn_y, btn_w, btn_h), 0, 6)
    btn_text = font_btn.render("返回主菜单", True, BUTTON_TEXT)
    screen.blit(btn_text, (btn_x + btn_w // 2 - btn_text.get_width() // 2,
                           btn_y + btn_h // 2 - btn_text.get_height() // 2))


def _draw_volume_slider(screen, gs: "GameState", label: str, value: float,
                         y: int, font, slider_name: str) -> None:
    """Draw a single volume slider with label, track, knob, and percentage."""
    mouse = pygame.mouse.get_pos()
    mx, my = mouse

    # ── Label (left side) ─────────────────────────────────────
    label_surf = font.render(label, True, (220, 220, 220))
    label_x = SCREEN_WIDTH // 2 - 280
    screen.blit(label_surf, (label_x, y))

    # ── Slider Track ──────────────────────────────────────────
    track_x = SCREEN_WIDTH // 2 - 100
    track_y = y + 12
    track_w = 200
    track_h = 8
    # Background track
    pygame.draw.rect(screen, (60, 60, 60),
                     (track_x, track_y, track_w, track_h), 0, 4)
    # Filled track
    filled_w = int(track_w * value)
    if filled_w > 0:
        pygame.draw.rect(screen, (100, 160, 220),
                         (track_x, track_y, filled_w, track_h), 0, 4)

    # ── Knob ──────────────────────────────────────────────────
    knob_r = 9
    knob_x = track_x + int(track_w * value)
    knob_y = track_y + track_h // 2
    # Check hover
    is_hover = (knob_x - knob_r - 4 <= mx <= knob_x + knob_r + 4 and
                knob_y - knob_r - 4 <= my <= knob_y + knob_r + 4)
    knob_color = (180, 210, 255) if is_hover else (140, 175, 230)
    pygame.draw.circle(screen, knob_color, (knob_x, knob_y), knob_r)
    pygame.draw.circle(screen, (50, 50, 50), (knob_x, knob_y), knob_r, 1)

    # ── Percentage (right side) ───────────────────────────────
    pct = int(value * 100)
    pct_surf = font.render(f"{pct}%", True, (200, 200, 200))
    screen.blit(pct_surf, (track_x + track_w + 20, y))


def _handle_room_clear(world: World, gs: GameState) -> None:
    """Called when all base enemies (EnemyComponent) are dead — award gold and transition to ROOM_COMPLETE.

    重要区分：
    - 基础敌人 (EnemyComponent)：全部死亡 → 清场。
    - 敌方随从 (MinionComponent, owner="enemy", 无 EnemyComponent)：
      由 cleanup_enemy_card_entities() 统一清理，不影响清场判定。
    """
    probe("main::room_clear", "清场触发", {"room": gs.room_number}, module="main")
    # 守卫：防止被重复调用（例如 AOE 循环中多次触发 _check_death）
    if gs.phase in (Phase.ROOM_COMPLETE, Phase.REWARD, Phase.EVENT,
                    Phase.MERCHANT, Phase.CAMPFIRE, Phase.GAME_OVER):
        return

    # Award gold
    gold = battle_gold_reward(gs.is_elite_room)
    gs.add_gold(gold)
    gs.show_message(f"获得 {gold} 金币！", 2.5)

    # Cleanup enemy card entities (deck/hand/cards) + enemy minions
    # cleanup_enemy_card_entities() 已包含敌方随从 (MinionComponent, owner="enemy") 的清理
    cleanup_enemy_card_entities(world)

    # Increment room number
    gs.room_number += 1

    # Update highest wave
    for e in world.entities:
        pc = world.get_component(e, PlayerComponent)
        if pc:
            if gs.room_number > pc.highest_wave:
                pc.highest_wave = gs.room_number
            break

    gs.phase = Phase.ROOM_COMPLETE
    gs.room_clear_timer = 0.0
    wave_comps = list(world.get_entities_with(WaveComponent))
    if wave_comps:
        w = world.get_component(wave_comps[0], WaveComponent)
        if w:
            w.wave_cleared = True
            w.wave_number = gs.room_number


def _process_enemy_turn(world: World, gs: GameState,
                         combat_sys: CombatSystem, dt: float) -> None:
    """Process enemy intents and card plays with a small delay."""
    gs.enemy_turn_timer += dt

    if gs.enemy_turn_timer < 0.8:   # 0.8s between each enemy action
        return

    gs.enemy_turn_timer = 0.0

    # ── Enemy Card Play ──────────────────────────────────────
    # Enemy draws 1 card then plays 1 card each action tick
    enemy_draw_card(world)
    result = enemy_play_card(world, combat_sys)
    if result:
        gs.show_message(result, 1.5)
    # ───────────────────────────────────────────────────────────

    # Find all alive enemies (skip dead ones so iteration isn't wasted)
    enemy_ents = [
        e for e in world.get_entities_with(EnemyComponent, HealthComponent)
        if world.get_component(e, HealthComponent)
        and world.get_component(e, HealthComponent).alive
    ]
    if gs.enemy_turn_index >= len(enemy_ents):
        # All enemies acted — end enemy turn, start player turn
        probe("main::enemy_turn_end", "敌方回合结束→玩家回合",
              {"room": gs.room_number}, module="main")
        _end_enemy_turn(world, gs, combat_sys)
        return

    enemy = enemy_ents[gs.enemy_turn_index]
    gs.enemy_turn_index += 1

    # ── 使用难度系统增强 AI ──────────────────────────────────
    enemy_process_turn_ai(world, enemy, combat_sys)


def _end_enemy_turn(world: World, gs: GameState, combat_sys) -> None:
    """Clean up after enemy turn.

    敌方随从 (MinionComponent, owner="enemy") 会先攻击玩家，
    但只有基础敌人 (EnemyComponent) 决定战斗是否结束。
    """
    # ── Enemy minions attack player ───────────────────────────
    _enemy_minions_attack(world, combat_sys)

    # Check if all base enemies are dead
    # 只检查 EnemyComponent；敌方随从 (MinionComponent) 不影响清场判定
    enemy_ents = list(world.get_entities_with(EnemyComponent, HealthComponent))
    alive = [e for e in enemy_ents
             if world.get_component(e, HealthComponent)
             and world.get_component(e, HealthComponent).alive]

    # Only base enemies (with EnemyComponent) determine battle end.
    # Minions don't keep the fight going — when the enemy hero dies, battle is over.
    if len(alive) == 0:
        _handle_room_clear(world, gs)
    else:
        # Still enemies alive — player's turn again
        probe("main::phase_trans", "ENEMY→PLAYER",
              {"room": gs.room_number, "alive": len(alive)}, module="main")
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
        # Clear enemy hand (reset for next turn)
        _clear_enemy_hand(world)


def _enemy_minions_attack(world: World, combat_sys) -> None:
    """Enemy minions attack the player once each.

    区分：基础敌人 (EnemyComponent) 通过意图系统行动，此处跳过。
    只处理敌方随从 (MinionComponent, owner="enemy" 且无 EnemyComponent)。
    """
    minion_ents = list(world.get_entities_with(MinionComponent, AttackComponent, HealthComponent))
    for e in minion_ents:
        m = world.get_component(e, MinionComponent)
        h = world.get_component(e, HealthComponent)
        if not m or m.owner != "enemy" or not h or not h.alive:
            continue
        # 跳过基础敌人 — 它们通过 enemy_turn 意图系统单独行动
        if world.get_component(e, EnemyComponent):
            continue
        atk = world.get_component(e, AttackComponent)
        if atk:
            combat_sys.enemy_attack_player(world, e)


def _clear_enemy_hand(world: World) -> None:
    """Discard remaining enemy hand cards."""
    from components import HandComponent
    for e in list(world.get_entities_with(HandComponent)):
        h = world.get_component(e, HandComponent)
        if h and h.owner == "enemy":
            for c_ent in h.cards:
                world.destroy_entity(c_ent)
            h.cards.clear()


def _check_player_death(world: World, gs: GameState, combat_sys) -> None:
    """Check if player is dead and transition to GAME_OVER."""
    if gs.phase == Phase.GAME_OVER:
        return
    if gs.phase in (Phase.MENU, Phase.SETTINGS):
        return

    for e in world.entities:
        h = world.get_component(e, HealthComponent)
        p = world.get_component(e, PlayerComponent)
        if h and p and not h.alive:
            probe("main::player_death", "玩家死亡!",
                  {"room": gs.room_number, "gold": gs.gold}, module="main")
            gs.phase = Phase.GAME_OVER
            # Clean up old enemies
            for en in list(world.get_entities_with(EnemyComponent)):
                world.destroy_entity(en)
            return


def _draw_one_card(world: World) -> None:
    """Draw one card from player deck to player hand."""
    hand = None
    deck = None
    for e in world.get_entities_with(HandComponent):
        h = world.get_component(e, HandComponent)
        if h and h.owner == "player":
            hand = h
            break
    for e in world.get_entities_with(DeckComponent):
        d = world.get_component(e, DeckComponent)
        if d and d.owner == "player":
            deck = d
            break
    if not hand or not deck:
        return
    if len(hand.cards) >= MAX_HAND_SIZE:
        return
    card = deck.draw_one()
    if card:
        hand.cards.append(card)


def _show_reward(world: World, gs: GameState) -> None:
    """Show reward cards to choose from — from enemy pool C.
    Elite rooms get 4 choices with better rarity; normal rooms get 3."""
    from excel_loader import load_cards_by_pool
    config_dir = os.path.join(os.path.dirname(__file__), "config")
    data_dir = os.path.join(os.path.dirname(__file__), "data")
    pools = load_cards_by_pool(config_dir, data_dir)
    card_pool_c = pools.get("C", [])
    if not card_pool_c:
        # Fallback: use pool B if C is empty
        card_pool_c = pools.get("B", [])
    if not card_pool_c:
        return
    if gs.is_elite_room:
        chosen = pick_reward_cards_elite(card_pool_c, 4)
    else:
        chosen = pick_reward_cards(card_pool_c, REWARD_CARD_COUNT)
    gs.reward_cards.clear()
    for cdata in chosen:
        ent = create_card_entity(world, cdata)
        gs.reward_cards.append(ent)


# ── Event Resolution ────────────────────────────────────────────────────────

def resolve_event(world: World, gs: GameState, choice: dict, input_sys) -> str:
    """Resolve an event choice. Returns a result message.
    Called from input_system when a player clicks an event choice.
    """
    action = choice["action"]
    value = choice.get("value")
    result = ""

    # Helper to get player HP
    def get_player_hp():
        for e in world.entities:
            h = world.get_component(e, HealthComponent)
            p = world.get_component(e, PlayerComponent)
            if h and p:
                return h
        return None

    if action == "nothing":
        result = "你安全地离开了。"

    elif action == "gold":
        if isinstance(value, dict):
            lo, hi = value.get("min", 0), value.get("max", 0)
        elif isinstance(value, (list, tuple)):
            lo, hi = value[0], value[1]
        else:
            lo, hi = 5, 15  # fallback
        amount = random.randint(lo, hi)
        gs.add_gold(amount)
        result = f"获得 {amount} 金币！"

    elif action == "random_card":
        from excel_loader import load_cards_by_pool
        config_dir = os.path.join(os.path.dirname(__file__), "config")
        data_dir = os.path.join(os.path.dirname(__file__), "data")
        pools = load_cards_by_pool(config_dir, data_dir)
        card_pool = pools.get("B", []) + pools.get("C", [])
        if card_pool:
            cdata = random.choice(card_pool)
            ent = create_card_entity(world, cdata)
            input_sys._add_to_deck(world, ent)
            result = f"获得卡牌：{cdata['name']}！"
        else:
            result = "没有可用的卡牌。"

    elif action == "trade_hp_gold_card":
        hp_loss = value["hp"]
        gold_gain = value["gold"]
        hp = get_player_hp()
        if hp:
            hp.hp = max(1, hp.hp - hp_loss)
        gs.add_gold(gold_gain)
        # Also give a card from all pools
        from excel_loader import load_cards_by_pool
        config_dir = os.path.join(os.path.dirname(__file__), "config")
        data_dir = os.path.join(os.path.dirname(__file__), "data")
        pools = load_cards_by_pool(config_dir, data_dir)
        card_pool = pools.get("B", []) + pools.get("C", [])
        if card_pool:
            cdata = random.choice(card_pool)
            ent = create_card_entity(world, cdata)
            input_sys._add_to_deck(world, ent)
            result = f"失去 {hp_loss} HP，获得 {gold_gain} 金币 + {cdata['name']}！"
        else:
            result = f"失去 {hp_loss} HP，获得 {gold_gain} 金币。"

    elif action == "remove_card":
        # Transition to remove card UI (simplified: auto-pick random card in player deck)
        deck = None
        for e in world.get_entities_with(DeckComponent):
            d = world.get_component(e, DeckComponent)
            if d and d.owner == "player":
                deck = d
                break
        if deck and deck.cards:
            # Remove a random card from deck
            removed = random.choice(deck.cards)
            card_comp = world.get_component(removed, CardComponent)
            name = card_comp.name if card_comp else "卡牌"
            deck.cards.remove(removed)
            world.destroy_entity(removed)
            result = f"移除了 {name}！"
        elif deck:
            result = "牌组为空，无事发生。"
        else:
            result = "无事发生。"

    elif action == "desecrate":
        gold_gain = value["gold"]
        hp_loss = value["hp"]
        hp = get_player_hp()
        if hp:
            hp.hp = max(1, hp.hp - hp_loss)
        gs.add_gold(gold_gain)
        result = f"失去 {hp_loss} HP，获得 {gold_gain} 金币。"

    elif action == "heal":
        hp = get_player_hp()
        if hp:
            if isinstance(value, float) and value < 1.0:
                amount = int(hp.max_hp * value)
            else:
                amount = value
            actual = hp.heal(amount)
            result = f"回复了 {actual} 点生命！"

    elif action == "shield":
        hp = get_player_hp()
        if hp:
            hp.shield += value
            result = f"获得 {value} 护盾！"

    elif action == "gamble":
        if random.random() < 0.5:
            gs.add_gold(value["win"])
            result = f"赌赢了！获得 {value['win']} 金币！"
        else:
            gs.add_gold(-value["lose"])
            result = f"赌输了！失去 {value['lose']} 金币。"

    elif action == "upgrade_card_free":
        # Find a card in player deck to upgrade
        deck = None
        for e in world.get_entities_with(DeckComponent):
            d = world.get_component(e, DeckComponent)
            if d and d.owner == "player":
                deck = d
                break
        if deck:
            all_cards = deck.cards + deck.discard
            upgradable = []
            for c_ent in all_cards:
                cc = world.get_component(c_ent, CardComponent)
                if cc and not cc.upgraded and cc.pool == "A":
                    upgradable.append((c_ent, cc))
            if upgradable:
                ent, cc = upgradable[0]
                from card_factory import upgrade_card
                up_result = upgrade_card(cc)
                result = up_result
            else:
                result = "没有可升级的卡牌。"
        else:
            result = "无事发生。"

    elif action == "sacrifice_card":
        gold_gain = value
        deck = None
        for e in world.get_entities_with(DeckComponent):
            d = world.get_component(e, DeckComponent)
            if d and d.owner == "player":
                deck = d
                break
        if deck and deck.cards:
            removed = random.choice(deck.cards)
            card_comp = world.get_component(removed, CardComponent)
            name = card_comp.name if card_comp else "卡牌"
            deck.cards.remove(removed)
            world.destroy_entity(removed)
            gs.add_gold(gold_gain)
            result = f"献祭 {name}，获得 {gold_gain} 金币！"
        elif deck:
            result = "没有可献祭的卡牌。"
        else:
            result = "无事发生。"

    elif action == "sacrifice_hp":
        hp_loss = value
        hp = get_player_hp()
        if hp:
            hp.hp = max(1, hp.hp - hp_loss)
        from excel_loader import load_cards_by_pool
        config_dir = os.path.join(os.path.dirname(__file__), "config")
        data_dir = os.path.join(os.path.dirname(__file__), "data")
        pools = load_cards_by_pool(config_dir, data_dir)
        card_pool = pools.get("B", []) + pools.get("C", [])
        rare_pool = [c for c in card_pool if c.get("rarity") in ("rare", "epic")]
        if rare_pool:
            cdata = random.choice(rare_pool)
        else:
            cdata = random.choice(card_pool)
        ent = create_card_entity(world, cdata)
        input_sys._add_to_deck(world, ent)
        result = f"失去 {hp_loss} HP，获得稀有卡牌：{cdata['name']}！"

    elif action == "cursed_card":
        hp_loss = value
        hp = get_player_hp()
        if hp:
            hp.hp = max(1, hp.hp - hp_loss)
        from excel_loader import load_cards_by_pool
        config_dir = os.path.join(os.path.dirname(__file__), "config")
        data_dir = os.path.join(os.path.dirname(__file__), "data")
        pools = load_cards_by_pool(config_dir, data_dir)
        card_pool = pools.get("B", []) + pools.get("C", [])
        epic_pool = [c for c in card_pool if c.get("rarity") == "epic"]
        if epic_pool:
            cdata = random.choice(epic_pool)
        else:
            cdata = random.choice(card_pool)
        ent = create_card_entity(world, cdata)
        input_sys._add_to_deck(world, ent)
        result = f"受到 {hp_loss} 伤害，获得史诗卡牌：{cdata['name']}！"

    elif action == "angel_heal":
        hp = get_player_hp()
        if hp:
            hp.heal(value["hp"])
            hp.shield += value["shield"]
            result = f"回复 {value['hp']} HP + 获得 {value['shield']} 护盾！"

    elif action == "demon_buff":
        hp = get_player_hp()
        if hp:
            loss = int(hp.max_hp * value)
            hp.hp = max(1, hp.hp - loss)
        for e in world.entities:
            pc = world.get_component(e, PlayerComponent)
            if pc:
                pc.temp_attack_buff += 3
                result = f"最大HP -{loss}，永久攻击力 +3！"
                break

    else:
        result = "无事发生。"

    gs.event_resolved = True
    return result


# ── Entry Point ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    main()
