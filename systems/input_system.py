"""Input system — handles all mouse/keyboard interactions."""

from __future__ import annotations
import pygame, random, os
from ecs import System, World
from components import (
    CardComponent, RenderComponent, HandComponent,
    BoardComponent, EnergyComponent, DeckComponent,
    EnemyComponent, MinionComponent, WaveComponent,
    HealthComponent, PlayerComponent,
)
from game_state import Phase, GameState
from constants import *
from audio.audio_components import AudioEventComponent, AudioEventType
from rooms.room_system import (
    RoomType, generate_next_room,
    campfire_heal_percent,
)
from enemy_factory import generate_wave_enemies, create_enemy_deck_entities
from excel_loader import load_enemies, load_cards_by_pool
from debug_probes import probe


class InputSystem(System):
    """Processes mouse clicks and keyboard input."""

    def __init__(self, game_state: GameState, combat_system, audio_sys=None) -> None:
        self.gs: GameState = game_state
        self.combat = combat_system
        self.audio_sys = audio_sys
        self.mouse_pressed = False
        self._slider_drag: str | None = None  # 正在拖动的滑块名称

    def update(self, world: World, dt: float, events: list | None = None) -> None:
        if events is None:
            return

        mouse_down = pygame.mouse.get_pressed()[0]
        clicked = mouse_down and not self.mouse_pressed
        released = not mouse_down and self.mouse_pressed
        self.mouse_pressed = mouse_down

        # 设置界面滑块拖拽
        if self.gs.is_settings and mouse_down:
            mx, my = pygame.mouse.get_pos()
            if self._slider_drag is not None:
                self._handle_settings_drag(mx, my)

        if released:
            self._slider_drag = None

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
            self._handle_menu_click(world, mx, my)
            return

        if phase == Phase.SETTINGS:
            self._handle_settings_click(world, mx, my)
            return

        if phase == Phase.REWARD:
            self._handle_reward_click(world, mx, my)
            return

        if phase == Phase.EVENT:
            self._handle_event_click(world, mx, my)
            return

        if phase == Phase.MERCHANT:
            self._handle_merchant_click(world, mx, my)
            return

        if phase == Phase.CAMPFIRE:
            self._handle_campfire_click(world, mx, my)
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
            if render and render.rect and len(render.rect) == 4:
                rx, ry, rw, rh = render.rect
                in_rect = (rx <= mx <= rx + rw and ry <= my <= ry + rh)
                render.hovered = bool(in_rect)

    # ── Menu ─────────────────────────────────────────────────────

    def _handle_menu_click(self, world: World, mx: int, my: int) -> None:
        # ── Ascension arrows ──────────────────────────────────
        arrow_size = 28
        asc_y = 285
        lx = SCREEN_WIDTH // 2 - 80
        rx = SCREEN_WIDTH // 2 + 55

        # Left arrow
        if lx <= mx <= lx + arrow_size and asc_y <= my <= asc_y + arrow_size:
            from systems.difficulty_system import get_difficulty, set_difficulty
            dm = get_difficulty()
            new_asc = max(0, dm.ascension - 1)
            set_difficulty(new_asc)
            return

        # Right arrow
        if rx <= mx <= rx + arrow_size and asc_y <= my <= asc_y + arrow_size:
            from systems.difficulty_system import get_difficulty, set_difficulty, MAX_ASCENSION
            dm = get_difficulty()
            new_asc = min(MAX_ASCENSION, dm.ascension + 1)
            set_difficulty(new_asc)
            return

        # Check if settings button was clicked
        btn_w, btn_h = 120, 36
        btn_x = SCREEN_WIDTH // 2 - btn_w // 2
        btn_y = SCREEN_HEIGHT - 80
        if btn_x <= mx <= btn_x + btn_w and btn_y <= my <= btn_y + btn_h:
            # 触发UI点击音效
            for ent in world.get_entities_with(AudioEventComponent):
                ae = world.get_component(ent, AudioEventComponent)
                if ae:
                    ae.add(AudioEventType.UI_CLICK)
                break
            self.gs.phase = Phase.SETTINGS
            return
        # 触发游戏开始音效
        for ent in world.get_entities_with(AudioEventComponent):
            ae = world.get_component(ent, AudioEventComponent)
            if ae:
                ae.add(AudioEventType.GAME_START)
            break
        # Otherwise start game
        self._start_new_game(world)

    # ── Settings ─────────────────────────────────────────────────

    def _handle_settings_click(self, world: World, mx: int, my: int) -> None:
        """Handle clicks on the settings screen."""
        # Back button
        btn_w, btn_h = 160, 40
        btn_x = SCREEN_WIDTH // 2 - btn_w // 2
        btn_y = SCREEN_HEIGHT - 80
        if btn_x <= mx <= btn_x + btn_w and btn_y <= my <= btn_y + btn_h:
            # 触发UI返回音效
            for ent in world.get_entities_with(AudioEventComponent):
                ae = world.get_component(ent, AudioEventComponent)
                if ae:
                    ae.add(AudioEventType.UI_CLICK)
                break
            self.gs.phase = Phase.MENU
            return

        # ── Volume Sliders ───────────────────────────────────────
        self._handle_volume_slider_click(mx, my)

    def _handle_volume_slider_click(self, mx: int, my: int) -> None:
        """Handle clicks on volume sliders in settings screen."""
        sliders = [
            ("master", self.gs.master_volume, 460),
            ("music",  self.gs.music_volume,  520),
            ("sfx",    self.gs.sfx_volume,     580),
        ]
        track_x = SCREEN_WIDTH // 2 - 100
        track_w = 200

        for name, _, slider_y in sliders:
            if (track_x - 10 <= mx <= track_x + track_w + 10 and
                    slider_y - 10 <= my <= slider_y + 20 + 10):
                # Calculate volume from mouse x position
                ratio = (mx - track_x) / track_w
                ratio = max(0.0, min(1.0, ratio))
                new_val = round(ratio, 2)
                self._apply_volume(name, new_val)
                self._slider_drag = name
                return

    def _apply_volume(self, name: str, value: float) -> None:
        """Apply volume change to game state and audio system."""
        if name == "master":
            self.gs.master_volume = value
        elif name == "music":
            self.gs.music_volume = value
        elif name == "sfx":
            self.gs.sfx_volume = value

        # Apply to audio system immediately
        if self.audio_sys:
            self.audio_sys.set_volume(name, value)

    def _handle_settings_drag(self, mx: int, my: int) -> None:
        """Handle mouse drag on settings screen (volume sliders)."""
        if self._slider_drag is None:
            return

        sliders = {
            "master": (self.gs.master_volume, 460),
            "music":  (self.gs.music_volume,  520),
            "sfx":    (self.gs.sfx_volume,     580),
        }
        info = sliders.get(self._slider_drag)
        if info is None:
            self._slider_drag = None
            return

        track_x = SCREEN_WIDTH // 2 - 100
        track_w = 200
        ratio = (mx - track_x) / track_w
        ratio = max(0.0, min(1.0, ratio))
        new_val = round(ratio, 2)
        self._apply_volume(self._slider_drag, new_val)

    # ── Game Over ───────────────────────────────────────────────

    def _handle_game_over_click(self, world: World) -> None:
        # 触发UI点击音效
        for ent in world.get_entities_with(AudioEventComponent):
            ae = world.get_component(ent, AudioEventComponent)
            if ae:
                ae.add(AudioEventType.UI_CLICK)
            break
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
            self._check_buttons(world, mx, my)
            return

        # Check if it's a hand card
        hand = self._get_player_hand(world)
        if hand and clicked_entity in hand.cards:
            self._select_card(world, clicked_entity)
            return

        self._deselect_all(world)
        self.gs.clear_selection()

    # ── Play Card ───────────────────────────────────────────────

    def _play_card(self, world: World, card_entity, target) -> None:
        card = world.get_component(card_entity, CardComponent)
        energy = self._get_energy(world)
        if not card:
            return
        probe("input::play_card", f"打出: {card.name}",
              {"cost": card.cost, "type": card.card_type,
               "energy": energy.current if energy else "?"}, module="input")
        # 触发打牌音效
        for ent in world.get_entities_with(AudioEventComponent):
            ae = world.get_component(ent, AudioEventComponent)
            if ae:
                ae.add(AudioEventType.CARD_PLAY)
            break

        if energy and energy.current < card.cost:
            self.gs.show_message("能量不足！")
            return

        if energy:
            energy.spend(card.cost)

        self.combat.resolve_card(world, card_entity, target)

        self._remove_from_hand(world, card_entity)

        if card.card_type != "minion":
            self._add_to_discard(world, card_entity)

        self.gs.clear_selection()
        self._deselect_all(world)

    # ── Target Finding ──────────────────────────────────────────

    def _find_click_target(self, world: World, mx: int, my: int, target_type: str):
        if target_type == "enemy":
            # First check base enemies
            for e in world.get_entities_with(EnemyComponent, RenderComponent):
                render = world.get_component(e, RenderComponent)
                if render and render.rect and self._point_in_rect(mx, my, render.rect):
                    return e
            # Also check enemy minions (card-spawned)
            for e in world.get_entities_with(MinionComponent, RenderComponent):
                m = world.get_component(e, MinionComponent)
                if m and m.owner == "enemy" and not world.get_component(e, EnemyComponent):
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
        # Check hand cards (player only)
        hand = self._get_player_hand(world)
        if hand:
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
        # Check enemy minions (card-spawned)
        for e in world.get_entities_with(MinionComponent, RenderComponent):
            m = world.get_component(e, MinionComponent)
            if m and m.owner == "enemy" and not world.get_component(e, EnemyComponent):
                render = world.get_component(e, RenderComponent)
                if render and render.rect and self._point_in_rect(mx, my, render.rect):
                    return e

        return None

    # ── Selection ────────────────────────────────────────────────

    def _select_card(self, world: World, card_entity) -> None:
        # 触发卡牌选择音效
        for ent in world.get_entities_with(AudioEventComponent):
            ae = world.get_component(ent, AudioEventComponent)
            if ae:
                ae.add(AudioEventType.CARD_SELECT)
            break
        self._deselect_all(world)
        self.gs.selected_card_entity = card_entity
        render = world.get_component(card_entity, RenderComponent)
        if render:
            render.selected = True
        card = world.get_component(card_entity, CardComponent)
        if card and card.target_type in ("enemy", "any_minion", "friendly_minion"):
            self._highlight_targets(world, card.target_type)

        # AOE / self-target cards: play immediately, no target selection needed
        if card and card.target_type in ("none", "self"):
            self._play_card(world, card_entity, card.target_type)

    def _select_minion(self, world: World, minion_entity) -> None:
        self._deselect_all(world)
        self.gs.selected_minion_entity = minion_entity
        render = world.get_component(minion_entity, RenderComponent)
        if render:
            render.selected = True
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
            # Also highlight enemy minions
            for e in world.get_entities_with(MinionComponent, RenderComponent):
                m = world.get_component(e, MinionComponent)
                if m and m.owner == "enemy" and not world.get_component(e, EnemyComponent):
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
        # End Turn button
        end_rect = pygame.Rect(SCREEN_WIDTH - 160, SCREEN_HEIGHT - 90, 140, 36)
        if end_rect.collidepoint(mx, my) and self.gs.is_player_turn:
            # 触发结束回合音效
            for ent in world.get_entities_with(AudioEventComponent):
                ae = world.get_component(ent, AudioEventComponent)
                if ae:
                    ae.add(AudioEventType.UI_BUTTON_CLICK)
                break
            self._end_player_turn(world)
            return

    # ── Reward Click ────────────────────────────────────────────

    def _handle_reward_click(self, world: World, mx: int, my: int) -> None:
        for c_ent in self.gs.reward_cards:
            render = world.get_component(c_ent, RenderComponent)
            if render and render.rect and self._point_in_rect(mx, my, render.rect):
                # 触发奖励选择音效
                for ent in world.get_entities_with(AudioEventComponent):
                    ae = world.get_component(ent, AudioEventComponent)
                    if ae:
                        ae.add(AudioEventType.UI_BUTTON_CLICK)
                    break
                self._add_to_deck(world, c_ent)
                self.gs.reward_cards.clear()
                # 如果有待进入的非战斗房间，先过渡
                if self.gs.pending_next_room_type is not None:
                    from main import _start_pending_room
                    _start_pending_room(world, self.gs)
                else:
                    self._start_next_room(world)
                return

    # ── Event Click ─────────────────────────────────────────────

    def _handle_event_click(self, world: World, mx: int, my: int) -> None:
        """Handle clicks on event choices. Rects are hardcoded to match render_system."""
        event = self.gs.current_event
        if not event:
            return

        choices = event.get("choices", [])
        n = len(choices)
        if n == 0:
            return

        # Rects matching render_system._draw_event
        start_y = 280
        for i in range(n):
            rect = pygame.Rect(
                SCREEN_WIDTH // 2 - 260,
                start_y + i * 55,
                520, 45
            )
            if rect.collidepoint(mx, my):
                choice = choices[i]
                # 触发确认音效
                for ent in world.get_entities_with(AudioEventComponent):
                    ae = world.get_component(ent, AudioEventComponent)
                    if ae:
                        ae.add(AudioEventType.UI_BUTTON_CLICK)
                    break
                # Import here to avoid circular import
                from main import resolve_event
                result = resolve_event(world, self.gs, choice, self)
                self.gs.show_message(result, 3.0)
                # Proceed to next room after a brief moment
                self.gs.event_resolved = True
                self.gs.room_clear_timer = 0.0
                return

    def _handle_event_done(self, world: World) -> None:
        """Advance to next room after event."""
        self.gs.room_number += 1
        self._advance_room(world)

    # ── Merchant Click ──────────────────────────────────────────

    def _handle_merchant_click(self, world: World, mx: int, my: int) -> None:
        """Handle clicks in merchant room."""
        # Merchant card purchase (rects matching render_system)
        for i, c_ent in enumerate(self.gs.merchant_cards):
            card = world.get_component(c_ent, CardComponent)
            if not card:
                continue
            price = self.gs.merchant_prices.get(id(c_ent), 50)
            rx = 80 + i * 300
            ry = 250
            rect = pygame.Rect(rx, ry, 270, 200)
            if rect.collidepoint(mx, my):
                if self.gs.gold >= price:
                    # 触发购买音效
                    for ent in world.get_entities_with(AudioEventComponent):
                        ae = world.get_component(ent, AudioEventComponent)
                        if ae:
                            ae.add(AudioEventType.MERCHANT_BUY)
                        break
                    # Buy the card — create a new entity for the deck
                    from card_factory import create_card_entity
                    config_dir = os.path.join(os.path.dirname(__file__), "..", "config")
                    config_dir = os.path.normpath(config_dir)
                    data_dir = os.path.join(os.path.dirname(__file__), "..", "data")
                    data_dir = os.path.normpath(data_dir)
                    pools = load_cards_by_pool(config_dir, data_dir)
                    card_pool = pools.get("B", []) + pools.get("C", [])
                    card_map = {c["id"]: c for c in (card_pool or [])}
                    cdata = card_map.get(card.card_id)
                    if cdata:
                        new_ent = create_card_entity(world, cdata)
                        self._add_to_deck(world, new_ent)
                    self.gs.add_gold(-price)
                    self.gs.show_message(f"购买 {card.name} — 花费 {price} 金币！", 2.0)
                else:
                    self.gs.show_message("金币不足！", 1.5)
                return

        # Remove card button
        rem_rect = pygame.Rect(SCREEN_WIDTH // 2 - 100, 480, 200, 40)
        if rem_rect.collidepoint(mx, my):
            cost = self.gs.merchant_remove_cost
            if self.gs.gold >= cost:
                deck = self._get_player_deck(world)
                if deck and deck.cards:
                    removed = random.choice(deck.cards)
                    card_comp = world.get_component(removed, CardComponent)
                    name = card_comp.name if card_comp else "卡牌"
                    deck.cards.remove(removed)
                    world.destroy_entity(removed)
                    self.gs.add_gold(-cost)
                    self.gs.show_message(f"移除 {name} — 花费 {cost} 金币！", 2.0)
                else:
                    self.gs.show_message("牌组为空！", 1.5)
            else:
                self.gs.show_message("金币不足！", 1.5)
            return

        # Leave button
        leave_rect = pygame.Rect(SCREEN_WIDTH // 2 - 80, 540, 160, 40)
        if leave_rect.collidepoint(mx, my):
            self.gs.room_number += 1
            self._advance_room(world)
            return

    # ── Campfire Click ──────────────────────────────────────────

    def _handle_campfire_click(self, world: World, mx: int, my: int) -> None:
        """Handle clicks in campfire room."""
        if self.gs.campfire_done:
            return

        # Upgrade card button
        up_rect = pygame.Rect(SCREEN_WIDTH // 2 - 300, 240, 280, 60)
        if up_rect.collidepoint(mx, my):
            # Pick a random unupgraded card from player deck
            deck = self._get_player_deck(world)
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
                    result = upgrade_card(cc)
                    # 触发篝火升级音效
                    for ent2 in world.get_entities_with(AudioEventComponent):
                        ae = world.get_component(ent2, AudioEventComponent)
                        if ae:
                            ae.add(AudioEventType.CAMPFIRE_UPGRADE)
                        break
                    self.gs.show_message(result, 3.0)
                else:
                    self.gs.show_message("没有可升级的卡牌。", 2.0)
            self._campfire_done(world)
            return

        # Rest button
        rest_rect = pygame.Rect(SCREEN_WIDTH // 2 + 20, 240, 280, 60)
        if rest_rect.collidepoint(mx, my):
            hp = self._get_player_hp(world)
            if hp:
                amount = int(hp.max_hp * campfire_heal_percent())
                actual = hp.heal(amount)
                self.gs.show_message(f"回复了 {actual} 点生命！", 3.0)
            # 触发篝火休息音效
            for ent in world.get_entities_with(AudioEventComponent):
                ae = world.get_component(ent, AudioEventComponent)
                if ae:
                    ae.add(AudioEventType.CAMPFIRE_REST)
                break
            self._campfire_done(world)
            return

    def _campfire_done(self, world: World) -> None:
        self.gs.campfire_done = True
        self.gs.room_number += 1
        self._advance_room(world)

    # ── Room Advancement ───────────────────────────────────────

    def _advance_room(self, world: World) -> None:
        """Move to the next room after a non-battle room (event/merchant/campfire)."""
        from main import _advance_to_next_room
        _advance_to_next_room(world, self.gs)

    def _start_next_room(self, world: World) -> None:
        """Start the next room after picking a battle reward."""
        wave_comp = self._get_wave_comp(world)
        if not wave_comp:
            return

        wave_comp.wave_number = self.gs.room_number
        wave_comp.wave_cleared = False

        config_dir = os.path.join(os.path.dirname(__file__), "..", "config")
        config_dir = os.path.normpath(config_dir)
        data_dir = os.path.join(os.path.dirname(__file__), "..", "data")
        data_dir = os.path.normpath(data_dir)

        enemies_data = load_enemies(config_dir, data_dir)

        if not enemies_data:
            self.gs.show_message("未找到敌人数据！")
            return

        new_enemies = generate_wave_enemies(
            world, enemies_data, wave_comp.wave_number,
            is_elite=self.gs.is_elite_room,
        )
        wave_comp.enemies_alive = len(new_enemies)

        # ── Create enemy deck/hand from pools B + C ──────────────
        pools = load_cards_by_pool(config_dir, data_dir)
        create_enemy_deck_entities(world, pools.get("B", []), pools.get("C", []),
                                    wave_comp.wave_number, self.gs.is_elite_room)

        # Refresh player energy
        energy = self._get_energy(world)
        if energy:
            energy.refresh()

        self._draw_one(world)

        self.gs.phase = Phase.PLAYER_TURN
        self.gs.clear_selection()

    # ── Keyboard ────────────────────────────────────────────────

    def _handle_key(self, world: World, event) -> None:
        if event.key in (pygame.K_RETURN, pygame.K_SPACE):
            if self.gs.phase == Phase.GAME_OVER:
                for ent in world.get_entities_with(AudioEventComponent):
                    ae = world.get_component(ent, AudioEventComponent)
                    if ae:
                        ae.add(AudioEventType.UI_CLICK)
                    break
                self._start_new_game(world)
            elif self.gs.phase == Phase.MENU:
                for ent in world.get_entities_with(AudioEventComponent):
                    ae = world.get_component(ent, AudioEventComponent)
                    if ae:
                        ae.add(AudioEventType.GAME_START)
                    break
                self._start_new_game(world)
            elif self.gs.is_player_turn:
                for ent in world.get_entities_with(AudioEventComponent):
                    ae = world.get_component(ent, AudioEventComponent)
                    if ae:
                        ae.add(AudioEventType.UI_BUTTON_CLICK)
                    break
                self._end_player_turn(world)
            elif self.gs.is_event and self.gs.event_resolved:
                self._handle_event_done(world)
            elif self.gs.is_campfire and self.gs.campfire_done:
                pass  # already advanced

        if event.key == pygame.K_ESCAPE:
            if self.gs.is_settings:
                self.gs.phase = Phase.MENU
                return
            self.gs.clear_selection()
            self._deselect_all(world)

    # ── Game Start / Restart ────────────────────────────────────

    def _start_new_game(self, world: World) -> None:
        from card_factory import create_card_entity
        probe("input::new_game", "开始新游戏",
              {"asc": self.gs.ascension_level}, module="input")

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

        # Create deck entity and populate starter deck from pools A + B
        deck_ent = world.create_entity()
        deck_comp = DeckComponent(owner="player")

        config_dir = os.path.join(os.path.dirname(__file__), "..", "config")
        config_dir = os.path.normpath(config_dir)
        data_dir = os.path.join(os.path.dirname(__file__), "..", "data")
        data_dir = os.path.normpath(data_dir)

        pools = load_cards_by_pool(config_dir, data_dir)
        # Player starts with B (basic) pool only
        card_pool = pools.get("B", [])
        card_pool_map = {c["id"]: c for c in (card_pool or [])}

        starter_ids = (["strike"] * 5 + ["defend"] * 4 +
                       ["shield_bearer"] * 3)
        valid_ids = [sid for sid in starter_ids if sid in card_pool_map]
        random.shuffle(valid_ids)

        for cid in valid_ids:
            c_ent = create_card_entity(world, card_pool_map[cid])
            deck_comp.cards.append(c_ent)

        world.add_component(deck_ent, deck_comp)

        # Create hand entity (player)
        hand_ent = world.create_entity()
        world.add_component(hand_ent, HandComponent(owner="player"))

        # Create board entity
        board_ent = world.create_entity()
        world.add_component(board_ent, BoardComponent())

        # Draw starting hand
        for _ in range(INITIAL_HAND_SIZE):
            self._draw_one(world)

        # Reset game state for new game
        self.gs.room_number = 1
        self.gs.is_battle_room = True
        self.gs.is_elite_room = False
        self.gs.gold = 50
        self.gs.event_resolved = False
        self.gs.campfire_done = False
        self.gs.merchant_cards.clear()
        self.gs.merchant_prices.clear()
        self.gs.reward_cards.clear()
        self.gs.pending_next_room_type = None

        # ── Sync ascension level to game state ────────────────────
        from systems.difficulty_system import get_difficulty
        self.gs.ascension_level = get_difficulty().ascension

        # Start first room (always battle)
        self.gs.phase = Phase.PLAYER_TURN
        self.gs.clear_selection()
        self._start_next_room(world)

    # ── Helpers ──────────────────────────────────────────────────

    def _draw_one(self, world: World) -> None:
        hand = self._get_player_hand(world)
        deck = self._get_player_deck(world)
        if not hand or not deck:
            return
        if len(hand.cards) >= MAX_HAND_SIZE:
            return
        card = deck.draw_one()
        if card:
            hand.cards.append(card)

    def _remove_from_hand(self, world: World, card_entity) -> None:
        hand = self._get_player_hand(world)
        if not hand:
            return
        if card_entity in hand.cards:
            hand.cards.remove(card_entity)

    def _add_to_discard(self, world: World, card_entity) -> None:
        deck = self._get_player_deck(world)
        if not deck:
            return
        deck.add_to_discard(card_entity)

    def _add_to_deck(self, world: World, card_entity) -> None:
        deck = self._get_player_deck(world)
        if not deck:
            return
        # C→A conversion: enemy cards earned become player trophies (pool A)
        cc = world.get_component(card_entity, CardComponent)
        if cc and cc.pool in ("C", "B"):
            cc.pool = "A"
        deck.cards.append(card_entity)

    def _end_player_turn(self, world: World) -> None:
        probe("input::end_turn", "玩家主动结束回合",
              {"room": self.gs.room_number}, module="input")
        # Let combat system handle end-turn logic
        self.combat.end_player_turn(world)
        # Reset enemy hand for new turn
        for e in list(world.get_entities_with(HandComponent)):
            h = world.get_component(e, HandComponent)
            if h and h.owner == "enemy":
                for c_ent in h.cards:
                    world.destroy_entity(c_ent)
                h.cards.clear()
        self.gs.phase = Phase.ENEMY_TURN
        self.gs.enemy_turn_index = 0
        self.gs.enemy_turn_timer = 0.0

    def _get_energy(self, world: World) -> EnergyComponent | None:
        for e in world.entities:
            eng = world.get_component(e, EnergyComponent)
            if eng:
                return eng
        return None

    def _get_player_hand(self, world: World) -> HandComponent | None:
        for e in world.get_entities_with(HandComponent):
            h = world.get_component(e, HandComponent)
            if h and h.owner == "player":
                return h
        return None

    def _get_player_deck(self, world: World) -> DeckComponent | None:
        for e in world.get_entities_with(DeckComponent):
            d = world.get_component(e, DeckComponent)
            if d and d.owner == "player":
                return d
        return None

    def _get_player_hp(self, world: World) -> HealthComponent | None:
        for e in world.entities:
            h = world.get_component(e, HealthComponent)
            p = world.get_component(e, PlayerComponent)
            if h and p:
                return h
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
