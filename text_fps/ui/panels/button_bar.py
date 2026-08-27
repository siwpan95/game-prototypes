"""ButtonBar - Bottom action bar with directional, combat, and utility buttons."""
from typing import Optional, Dict

try:
    import pygame_ce as pygame
except ImportError:
    import pygame

from ui.panel import Panel
from ui.button import Button
from ui import colors as C
from core.constants import (
    PHASE_PLAYER_TURN, PHASE_ENEMY_TURN,
    PHASE_GAME_OVER, PHASE_VICTORY,
)
from models.item import Grenade, WeaponModItem


class ButtonBar(Panel):
    """Bottom panel with movement, combat, and utility action buttons."""

    DIR_BTN_W = 80
    DIR_BTN_H = 32
    COMBAT_BTN_W = 100
    COMBAT_BTN_H = 32
    ACTION_BTN_W = 120
    ACTION_BTN_H = 32

    def __init__(self, rect: pygame.Rect) -> None:
        super().__init__(rect, bg_color=C.BG_DARK)
        self.font_button: pygame.font.Font = pygame.font.Font(None, 14)
        self.font_hud: pygame.font.Font = pygame.font.Font(None, 14)

        # --- Direction buttons (cross pattern) ---
        dir_x = 30
        dir_y_base = rect.y + 20
        self._btn_north = Button(
            pygame.Rect(dir_x + 44, dir_y_base, self.DIR_BTN_W, self.DIR_BTN_H),
            "North", callback=None,
        )
        self._btn_west = Button(
            pygame.Rect(dir_x, dir_y_base + 36, self.DIR_BTN_W, self.DIR_BTN_H),
            "West", callback=None,
        )
        self._btn_east = Button(
            pygame.Rect(dir_x + 88, dir_y_base + 36, self.DIR_BTN_W, self.DIR_BTN_H),
            "East", callback=None,
        )
        self._btn_south = Button(
            pygame.Rect(dir_x + 44, dir_y_base + 72, self.DIR_BTN_W, self.DIR_BTN_H),
            "South", callback=None,
        )
        self.dir_buttons = {
            "north": self._btn_north,
            "west": self._btn_west,
            "east": self._btn_east,
            "south": self._btn_south,
        }

        # --- Combat buttons (center) ---
        combat_x = 260
        combat_y = rect.y + 20
        self._btn_fire = Button(
            pygame.Rect(combat_x, combat_y, self.COMBAT_BTN_W, self.COMBAT_BTN_H),
            "Fire", callback=None,
        )
        self._btn_aim = Button(
            pygame.Rect(combat_x + 106, combat_y, self.COMBAT_BTN_W, self.COMBAT_BTN_H),
            "Aim", callback=None,
        )
        self._btn_reload = Button(
            pygame.Rect(combat_x + 212, combat_y, self.COMBAT_BTN_W, self.COMBAT_BTN_H),
            "Reload", callback=None,
        )
        self._btn_grenade = Button(
            pygame.Rect(combat_x, combat_y + 36, self.COMBAT_BTN_W, self.COMBAT_BTN_H),
            "Grenade", callback=None,
        )
        self._btn_switch = Button(
            pygame.Rect(combat_x + 106, combat_y + 36, self.COMBAT_BTN_W, self.COMBAT_BTN_H),
            "Switch Wpn", callback=None,
        )
        self._btn_cover = Button(
            pygame.Rect(combat_x + 212, combat_y + 36, self.COMBAT_BTN_W, self.COMBAT_BTN_H),
            "Take Cover", callback=None,
        )
        self.combat_buttons = [
            self._btn_fire, self._btn_aim, self._btn_reload,
            self._btn_grenade, self._btn_switch, self._btn_cover,
        ]

        # --- Action buttons (right) ---
        action_x = 600
        action_y = rect.y + 20
        self._btn_pickup = Button(
            pygame.Rect(action_x, action_y, self.ACTION_BTN_W, self.ACTION_BTN_H),
            "Pick Up", callback=None,
        )
        self._btn_use_item = Button(
            pygame.Rect(action_x + 128, action_y, self.ACTION_BTN_W, self.ACTION_BTN_H),
            "Use Item", callback=None,
        )
        self._btn_mod = Button(
            pygame.Rect(action_x, action_y + 36, self.ACTION_BTN_W, self.ACTION_BTN_H),
            "Mod Weapon", callback=None,
        )
        self.action_buttons = [self._btn_pickup, self._btn_use_item, self._btn_mod]

        # --- New Game button (visible on game over / victory) ---
        self._btn_new_game = Button(
            pygame.Rect(rect.x + rect.width // 2 - 60, rect.y + 80, 120, 36),
            "New Game", callback=None,
        )

        # All buttons for hover update
        self._all_buttons = (
            list(self.dir_buttons.values()) +
            self.combat_buttons +
            self.action_buttons +
            [self._btn_new_game]
        )

    def set_font(self, font_button: pygame.font.Font, font_hud: pygame.font.Font) -> None:
        """Set fonts for rendering."""
        self.font_button = font_button
        self.font_hud = font_hud

    def render(self, surface: pygame.Surface, game_state) -> None:
        """Render all action buttons with proper enabled/disabled states."""
        super().render(surface, game_state)
        if not game_state or not game_state.player:
            return

        player = game_state.player
        room = game_state.current_room
        is_player_turn = game_state.phase == PHASE_PLAYER_TURN
        is_game_over = game_state.phase in (PHASE_GAME_OVER, PHASE_VICTORY)

        if is_game_over:
            self._render_game_over(surface, game_state)
            return

        self._update_button_states(game_state)

        # Section labels
        # Direction label
        lbl = self.font_hud.render("MOVE (W/A/S/D)", True, C.TEXT_DIM)
        surface.blit(lbl, (30 + 10, self.rect.y + 6))

        # Combat label
        lbl = self.font_hud.render("COMBAT (F/A/R/G/C)", True, C.TEXT_DIM)
        surface.blit(lbl, (260 + 20, self.rect.y + 6))

        # Action label
        lbl = self.font_hud.render("ACTIONS (P=Pickup)", True, C.TEXT_DIM)
        surface.blit(lbl, (600 + 20, self.rect.y + 6))

        # Phase indicator
        if not is_player_turn:
            phase_text = "ENEMY TURN..."
            phase_color = C.HP_RED
        else:
            phase_text = "YOUR TURN"
            phase_color = C.AMMO_GREEN
        phase_surf = self.font_hud.render(phase_text, True, phase_color)
        surface.blit(phase_surf, (self.rect.x + self.rect.width - 120, self.rect.y + 6))

        # Render all buttons
        for btn in self.dir_buttons.values():
            btn.render(surface, self.font_button)
        for btn in self.combat_buttons:
            btn.render(surface, self.font_button)
        for btn in self.action_buttons:
            btn.render(surface, self.font_button)

        # Enemy target indicator
        if room:
            living = [e for e in room.enemies if e.is_alive]
            if living and is_player_turn:
                target_y = self.rect.y + 100
                target_label = self.font_hud.render("TARGET:", True, C.TEXT_DIM)
                surface.blit(target_label, (260, target_y))
                for i, e in enumerate(living):
                    hp_ratio = e.health / max(1, e.max_health)
                    hp_color = C.HP_RED if hp_ratio < 0.3 else C.NOISE_YELLOW if hp_ratio < 0.6 else C.AMMO_GREEN
                    e_text = f"  {e.name} HP:{e.health}/{e.max_health}"
                    e_surf = self.font_hud.render(e_text, True, hp_color)
                    surface.blit(e_surf, (260, target_y + 14 + i * 14))

    def _render_game_over(self, surface: pygame.Surface, game_state) -> None:
        """Render game over / victory state."""
        if game_state.phase == PHASE_VICTORY:
            text = "VICTORY!"
            color = C.AMMO_GREEN
        else:
            text = "GAME OVER"
            color = C.HP_RED

        title_font = pygame.font.Font(None, 36)
        title_surf = title_font.render(text, True, color)
        title_rect = title_surf.get_rect(
            center=(self.rect.x + self.rect.width // 2, self.rect.y + 50)
        )
        surface.blit(title_surf, title_rect)

        # Stats
        if game_state.player:
            stats_text = (
                f"Kills: {game_state.player.kills}  |  "
                f"Shots: {game_state.player.shots_fired}  |  "
                f"Turns: {game_state.turn}"
            )
            stats_surf = self.font_hud.render(stats_text, True, C.TEXT_SECONDARY)
            stats_rect = stats_surf.get_rect(
                center=(self.rect.x + self.rect.width // 2, self.rect.y + 80)
            )
            surface.blit(stats_surf, stats_rect)

        self._btn_new_game.enabled = True
        self._btn_new_game.render(surface, self.font_button)

    def _update_button_states(self, game_state) -> None:
        """Update enabled/disabled state of all buttons based on game state."""
        player = game_state.player
        room = game_state.current_room
        is_player_turn = game_state.phase == PHASE_PLAYER_TURN
        living_enemies = [e for e in room.enemies if e.is_alive] if room else []
        has_enemies = len(living_enemies) > 0
        weapon = player.current_weapon()

        # Direction buttons: enabled only for valid exits, no enemies blocking
        for direction, btn in self.dir_buttons.items():
            if not is_player_turn:
                btn.enabled = False
            elif has_enemies:
                btn.enabled = False  # Can't move with enemies present
            elif room and direction in room.exits:
                btn.enabled = True
            else:
                btn.enabled = False

        # Combat buttons
        # Fire: need weapon with ammo, and enemies
        self._btn_fire.enabled = (
            is_player_turn and
            weapon is not None and
            weapon.can_fire() and
            has_enemies
        )
        # Aim: not already aiming, have weapon, player turn
        self._btn_aim.enabled = (
            is_player_turn and
            not player.is_aiming and
            weapon is not None and
            has_enemies
        )
        # Reload: weapon exists and ammo < max
        self._btn_reload.enabled = (
            is_player_turn and
            weapon is not None and
            weapon.ammo < weapon.effective_max_ammo()
        )
        # Grenade: have grenade in inventory, enemies present
        has_grenade = any(isinstance(i, Grenade) for i in player.inventory)
        self._btn_grenade.enabled = (
            is_player_turn and
            has_grenade and
            has_enemies
        )
        # Switch weapon: have more than one weapon
        self._btn_switch.enabled = (
            is_player_turn and
            len(player.weapons) > 1
        )
        # Take cover: not already in cover, room has cover, player turn
        self._btn_cover.enabled = (
            is_player_turn and
            not player.in_cover and
            room is not None and
            room.has_cover()
        )

        # Action buttons
        # Pick Up: room has items
        self._btn_pickup.enabled = (
            is_player_turn and
            room is not None and
            len(room.items) > 0
        )
        # Use Item: have items in inventory
        self._btn_use_item.enabled = (
            is_player_turn and
            len(player.inventory) > 0
        )
        # Mod Weapon: have WeaponModItem in inventory
        has_mod = any(isinstance(i, WeaponModItem) for i in player.inventory)
        self._btn_mod.enabled = (
            is_player_turn and
            has_mod and
            weapon is not None
        )

    def handle_click(self, pos, game_state) -> bool:
        """Handle button clicks. Returns True if click was consumed."""
        if not self.rect.collidepoint(pos):
            return False
        # Just consume the click; action is resolved via get_action()
        return True

    def get_action(self, pos, game_state) -> Optional[Dict]:
        """Get the action associated with a button click. Returns action dict or None."""
        if not self.rect.collidepoint(pos):
            return None

        # New Game button
        if self._btn_new_game.is_clicked(pos):
            return {"action": "new_game"}

        # Direction buttons
        for direction, btn in self.dir_buttons.items():
            if btn.is_clicked(pos):
                return {"action": "move", "direction": direction}

        # Combat buttons
        if self._btn_fire.is_clicked(pos):
            return {"action": "fire"}
        if self._btn_aim.is_clicked(pos):
            return {"action": "aim"}
        if self._btn_reload.is_clicked(pos):
            return {"action": "reload"}
        if self._btn_grenade.is_clicked(pos):
            return {"action": "grenade"}
        if self._btn_switch.is_clicked(pos):
            return {"action": "switch_weapon"}
        if self._btn_cover.is_clicked(pos):
            return {"action": "take_cover"}

        # Action buttons
        if self._btn_pickup.is_clicked(pos):
            return {"action": "pickup"}
        if self._btn_use_item.is_clicked(pos):
            return {"action": "use_item"}
        if self._btn_mod.is_clicked(pos):
            return {"action": "modify_weapon"}

        return None

    def update_hover(self, pos, game_state) -> None:
        """Update hover state for all buttons."""
        for btn in self._all_buttons:
            btn.update_hover(pos)
