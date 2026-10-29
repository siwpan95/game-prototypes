"""BattleScreen - battle UI rendering and input handling, with Chinese UI and mouse support."""

from __future__ import annotations

import pygame

from screens.base_screen import BaseScreen
from services.renderer import Renderer
from controllers.battle_controller import BattleController


class BattleScreen(BaseScreen):
    """Full battle UI with hand display, enemy info, dice results, and battle log."""

    def __init__(self) -> None:
        super().__init__()
        self._controller: BattleController | None = None
        self._show_draw_pile: bool = False
        self._show_discard_pile: bool = False
        self._show_exhaust_pile: bool = False
        self._enemy_action_timer: float = 0.0
        self._enemy_acting: bool = False
        self._result_shown: bool = False
        self._card_rects: list[pygame.Rect] = []
        self._end_turn_rect: pygame.Rect | None = None

    def on_enter(self, **kwargs) -> None:
        self._controller = kwargs.get("battle_controller")
        self._show_draw_pile = False
        self._show_discard_pile = False
        self._show_exhaust_pile = False
        self._enemy_action_timer = 0.0
        self._enemy_acting = False
        self._result_shown = False
        if self._controller:
            self._controller.start_battle()

    def on_exit(self) -> None:
        self._controller = None

    def handle_event(self, event) -> None:
        if self._controller is None:
            return

        ctrl = self._controller

        # If battle is over, click/Enter goes to loot/game over
        if ctrl.battle_over:
            if event.type == pygame.MOUSEBUTTONDOWN:
                self.game.input_handler.consume_click()
                if ctrl.player_won:
                    self.game.go_to_loot(ctrl)
                else:
                    self.game.go_to_game_over()
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_RETURN:
                if ctrl.player_won:
                    self.game.go_to_loot(ctrl)
                else:
                    self.game.go_to_game_over()
            return

        # If showing a pile viewer
        if self._show_draw_pile or self._show_discard_pile or self._show_exhaust_pile:
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                self._show_draw_pile = False
                self._show_discard_pile = False
                self._show_exhaust_pile = False
            elif event.type == pygame.MOUSEBUTTONDOWN:
                self.game.input_handler.consume_click()
                self._show_draw_pile = False
                self._show_discard_pile = False
                self._show_exhaust_pile = False
            return

        # Enemy is acting - no player input
        if not ctrl.player_turn:
            return

        # Mouse input
        if event.type == pygame.MOUSEMOTION:
            self._handle_mouse_hover(event.pos, ctrl)
            return
        elif event.type == pygame.MOUSEBUTTONDOWN:
            self._handle_mouse_click(event.pos, ctrl)
            return

        # Keyboard input
        if event.type != pygame.KEYDOWN:
            return

        if event.key == pygame.K_LEFT:
            ctrl.select_card(-1)
        elif event.key == pygame.K_RIGHT:
            ctrl.select_card(1)
        elif event.key == pygame.K_RETURN:
            ctrl.play_selected_card()
        elif event.key == pygame.K_SPACE:
            ctrl.end_player_turn()
            self._enemy_acting = True
            self._enemy_action_timer = 0.0
        elif event.key == pygame.K_d:
            self._show_draw_pile = True
        elif event.key == pygame.K_g:
            self._show_discard_pile = True
        elif event.key == pygame.K_e:
            self._show_exhaust_pile = True
        elif event.key == pygame.K_ESCAPE:
            self.game.open_settings()

    def _handle_mouse_hover(self, pos: tuple[int, int], ctrl: BattleController) -> None:
        """Handle mouse hover over cards."""
        for i, rect in enumerate(self._card_rects):
            if rect.collidepoint(pos) and i < len(ctrl.deck.hand):
                ctrl.selected_card_index = i
                return

    def _handle_mouse_click(self, pos: tuple[int, int], ctrl: BattleController) -> None:
        """Handle mouse click on cards and buttons."""
        self.game.input_handler.consume_click()
        # Check card clicks
        for i, rect in enumerate(self._card_rects):
            if rect.collidepoint(pos) and i < len(ctrl.deck.hand):
                ctrl.selected_card_index = i
                ctrl.play_selected_card()
                return
        # Check End Turn button
        if self._end_turn_rect and self._end_turn_rect.collidepoint(pos):
            ctrl.end_player_turn()
            self._enemy_acting = True
            self._enemy_action_timer = 0.0

    def update(self, dt: float) -> None:
        if self._controller is None:
            return

        ctrl = self._controller

        # Handle enemy turn with delay
        if self._enemy_acting and not ctrl.player_turn and not ctrl.battle_over:
            self._enemy_action_timer += dt
            if self._enemy_action_timer >= 0.8:
                done = ctrl.execute_enemy_turn()
                self._enemy_action_timer = 0.0
                if done:
                    self._enemy_acting = False

    def render(self, surface) -> None:
        if self._controller is None:
            return

        r = self.renderer
        ctrl = self._controller
        player = ctrl.player
        enemy = ctrl.enemy

        r.fill_bg()

        # --- Header ---
        act_data = self.game.data_loader.get_act_data(player.current_act)
        act_name = act_data["name"] if act_data else f"第{player.current_act}关"
        self.draw_header(f"第{player.current_act}关: {act_name}")

        # Player status in header
        self.draw_player_status(player, y_offset=55)

        # --- Enemy Area ---
        self._render_enemy(enemy, r)

        # --- Dice Result Area ---
        self._render_dice_results(r)

        # --- Hand Area ---
        self._render_hand(ctrl, r)

        # --- Footer ---
        self._render_footer(ctrl, r)

        # --- Battle Log ---
        self._render_log(ctrl, r)

        # --- Pile viewers (overlay) ---
        if self._show_draw_pile:
            self._render_pile_viewer("抽牌堆", ctrl.deck.draw_pile, r)
        elif self._show_discard_pile:
            self._render_pile_viewer("弃牌堆", ctrl.deck.discard_pile, r)
        elif self._show_exhaust_pile:
            self._render_pile_viewer("消耗堆", ctrl.deck.exhaust_pile, r)

        # --- Battle over overlay ---
        if ctrl.battle_over:
            self._render_battle_over(ctrl, r)

    def _render_enemy(self, enemy, r: Renderer) -> None:
        """Render the enemy section."""
        enemy_y = 110
        enemy_w = 400
        enemy_x = r.center_x(enemy_w)

        # Enemy panel
        r.draw_rect(enemy_x, enemy_y, enemy_w, 100, Renderer.COLOR_PANEL, border_radius=8)

        # Enemy name
        boss_tag = " [BOSS]" if enemy.is_boss else ""
        r.draw_text(f"{enemy.name}{boss_tag}", enemy_x + enemy_w // 2, enemy_y + 8,
                    16, Renderer.COLOR_TEXT, center=True)

        # Enemy HP bar
        hp_text = f"生命: {enemy.hp}/{enemy.max_hp}"
        r.draw_text(hp_text, enemy_x + 10, enemy_y + 30, 11, Renderer.COLOR_ENEMY_HP)
        r.draw_bar(enemy_x + 10, enemy_y + 44, enemy_w - 20, 14,
                   enemy.hp, enemy.max_hp,
                   Renderer.COLOR_ENEMY_HP, Renderer.COLOR_ENEMY_HP_BG)

        # Enemy block
        if enemy.block > 0:
            r.draw_text(f"格挡: {enemy.block}", enemy_x + 10, enemy_y + 62,
                        11, Renderer.COLOR_BLOCK)

        # Enemy vulnerable
        if enemy.vulnerable > 0:
            r.draw_text(f"易伤: {enemy.vulnerable}", enemy_x + 150, enemy_y + 62,
                        11, (200, 100, 100))

        # Enemy stun
        if enemy.is_stunned():
            r.draw_text("眩晕", enemy_x + 280, enemy_y + 62,
                        11, Renderer.COLOR_MISHAP)

        # Enemy intent
        intent_colors = {
            "Attack": Renderer.COLOR_INTENT_ATTACK,
            "Defend": Renderer.COLOR_INTENT_DEFEND,
            "Special": Renderer.COLOR_INTENT_SPECIAL,
        }
        intent_labels = {"Attack": "攻击", "Defend": "防御", "Special": "特殊"}
        intent_color = intent_colors.get(enemy.intent, Renderer.COLOR_TEXT_DIM)
        intent_text = f"意图: {intent_labels.get(enemy.intent, enemy.intent)}"
        if enemy.intent_value:
            intent_text += f" ({enemy.intent_value})"
        r.draw_text(intent_text, enemy_x + 10, enemy_y + 80, 11, intent_color)

    def _render_dice_results(self, r: Renderer) -> None:
        """Render dice roll results area."""
        if self._controller is None:
            return

        ctrl = self._controller
        dice_y = 220
        dice_h = 60
        dice_w = 300
        dice_x = r.center_x(dice_w)

        r.draw_rect(dice_x, dice_y, dice_w, dice_h, Renderer.COLOR_PANEL, border_radius=5)

        if ctrl.dice_result:
            dr = ctrl.dice_result
            roll_text = f"D20: {dr.rolls[0] if dr.rolls else '?'}"
            if dr.modifier:
                roll_text += f" + {dr.modifier} = {dr.total}"

            color = Renderer.COLOR_MISS
            label = "未命中"
            if dr.is_mishap:
                color = Renderer.COLOR_MISHAP
                label = "失误！"
            elif dr.is_crit:
                color = Renderer.COLOR_CRIT
                label = "暴击！"
            elif dr.total >= 6:
                color = Renderer.COLOR_GREEN
                label = "命中"

            r.draw_text(roll_text, dice_x + dice_w // 2, dice_y + 5, 11,
                        Renderer.COLOR_TEXT, center=True)
            r.draw_text(label, dice_x + dice_w // 2, dice_y + 20, 18, color, center=True)

            if ctrl.damage_result and label in ("命中", "暴击！"):
                dmg = ctrl.damage_result
                dmg_text = f"伤害: {'+'.join(str(roll) for roll in dmg.rolls)}"
                if dmg.modifier:
                    dmg_text += f"+{dmg.modifier}"
                dmg_text += f" = {dmg.total}"
                r.draw_text(dmg_text, dice_x + dice_w // 2, dice_y + 42, 11,
                            Renderer.COLOR_ATTACK, center=True)
        else:
            r.draw_text("掷骰攻击！", dice_x + dice_w // 2, dice_y + 20, 14,
                        Renderer.COLOR_TEXT_DIM, center=True)

    def _render_hand(self, ctrl: BattleController, r: Renderer) -> None:
        """Render the player's hand of cards."""
        hand = ctrl.deck.hand
        self._card_rects.clear()
        if not hand:
            return

        hand_y = r.screen_height - 200
        card_w = 120
        card_h = 160
        spacing = 10
        total_w = len(hand) * (card_w + spacing) - spacing
        start_x = r.center_x(total_w)

        for i, card in enumerate(hand):
            x = start_x + i * (card_w + spacing)
            is_selected = (i == ctrl.selected_card_index)
            is_playable = card.cost <= ctrl.player.fp
            rect = r.draw_card(x, hand_y, card_w, card_h, card,
                       selected=is_selected, playable=is_playable)
            self._card_rects.append(pygame.Rect(x, hand_y, card_w, card_h))

    def _render_footer(self, ctrl: BattleController, r: Renderer) -> None:
        """Render footer with pile counts and end turn button."""
        footer_y = r.screen_height - 35

        # Pile counts
        r.draw_text(f"抽牌:{ctrl.deck.draw_pile_size}", 10, footer_y, 11, Renderer.COLOR_TEXT_DIM)
        r.draw_text(f"弃牌:{ctrl.deck.discard_pile_size}", 120, footer_y, 11, Renderer.COLOR_TEXT_DIM)
        r.draw_text(f"消耗:{ctrl.deck.exhaust_pile_size}", 250, footer_y, 11, Renderer.COLOR_TEXT_DIM)

        # End Turn button
        self._end_turn_rect = None
        if ctrl.player_turn and not ctrl.battle_over:
            end_btn_x = r.screen_width - 160
            self._end_turn_rect = pygame.Rect(end_btn_x, footer_y - 5, 150, 30)
            r.draw_button(end_btn_x, footer_y - 5, 150, 30, "结束回合 [Space]",
                         selected=False, font_size=11)

        # Key hints
        r.draw_text("D:抽牌 G:弃牌 E:消耗", 400, footer_y, 9, Renderer.COLOR_TEXT_DIM)

    def _render_log(self, ctrl: BattleController, r: Renderer) -> None:
        """Render the battle log."""
        log_x = r.screen_width - 320
        log_y = 300
        log_w = 310
        log_h = 150

        r.draw_rect(log_x, log_y, log_w, log_h, (25, 22, 35), border_radius=5)
        r.draw_text("战斗日志", log_x + 5, log_y + 2, 10, Renderer.COLOR_TEXT_DIM)

        entry_y = log_y + 16
        for entry in ctrl.log.entries:
            if entry_y < log_y + log_h - 10:
                r.draw_text(entry, log_x + 5, entry_y, 9, Renderer.COLOR_TEXT_DIM)
                entry_y += 14

    def _render_pile_viewer(self, title: str, pile: list, r: Renderer) -> None:
        """Render a pile viewer overlay."""
        overlay_w = 400
        overlay_h = 350
        x = r.center_x(overlay_w)
        y = r.center_y(overlay_h)

        r.draw_rect(x, y, overlay_w, overlay_h, Renderer.COLOR_PANEL, border_radius=8)
        r.draw_text(title, x + overlay_w // 2, y + 10, 16, Renderer.COLOR_TEXT, center=True)
        r.draw_text("按 ESC 或点击关闭", x + overlay_w // 2, y + 30, 11,
                    Renderer.COLOR_TEXT_DIM, center=True)

        if not pile:
            r.draw_text("空", x + overlay_w // 2, y + 60, 14,
                        Renderer.COLOR_TEXT_DIM, center=True)
        else:
            card_w = 90
            card_h = 120
            for i, card in enumerate(pile[:12]):
                col = i % 4
                row = i // 4
                cx = x + 10 + col * (card_w + 5)
                cy = y + 50 + row * (card_h + 5)
                r.draw_card(cx, cy, card_w, card_h, card)

    def _render_battle_over(self, ctrl: BattleController, r: Renderer) -> None:
        """Render battle over overlay."""
        overlay_w = 300
        overlay_h = 120
        x = r.center_x(overlay_w)
        y = r.center_y(overlay_h)

        r.draw_rect(x, y, overlay_w, overlay_h, Renderer.COLOR_PANEL, border_radius=8)

        if ctrl.player_won:
            r.draw_text("胜利！", x + overlay_w // 2, y + 12, 22,
                        Renderer.COLOR_GOLD, center=True)
            r.draw_text(f"获得 {ctrl.enemy.souls} 灵魂", x + overlay_w // 2, y + 45, 14,
                        Renderer.COLOR_TEXT, center=True)
        else:
            r.draw_text("你死了", x + overlay_w // 2, y + 12, 26,
                        Renderer.COLOR_ATTACK, center=True)

        r.draw_text("按回车或点击继续", x + overlay_w // 2, y + 80, 12,
                    Renderer.COLOR_TEXT_DIM, center=True)
