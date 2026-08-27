"""Renderer - Main rendering orchestrator."""
import os
from typing import List, Optional

try:
    import pygame_ce as pygame
except ImportError:
    import pygame

from core.constants import (
    SCREEN_WIDTH, SCREEN_HEIGHT, TOP_BAR_HEIGHT,
    MAIN_TEXT_WIDTH, SIDE_PANEL_WIDTH, BOTTOM_BAR_HEIGHT,
    FONT_SIZE_BODY, FONT_SIZE_TITLE, FONT_SIZE_HUD, FONT_SIZE_BUTTON,
    PHASE_GAME_OVER, PHASE_VICTORY,
)
from ui import colors as C
try:
    from ui.font_utils import load_cjk_font
except ImportError:
    load_cjk_font = None  # type: ignore
from ui.panel import Panel
from ui.button import Button
from ui.panels.main_panel import MainPanel
from ui.panels.stats_panel import StatsPanel
from ui.panels.inventory_panel import InventoryPanel
from ui.panels.button_bar import ButtonBar

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _load_font(size: int) -> pygame.font.Font:
    """跨平台加载 CJK 字体，回退到项目内置 Fira Code"""
    font = load_cjk_font(size) if load_cjk_font else None
    if font:
        return font

    # 回退：项目内置 Fira Code（仅英文）
    font_path = os.path.join(BASE_DIR, "assets", "fonts", "FiraCode-Regular.ttf")
    if os.path.exists(font_path):
        try:
            return pygame.font.Font(font_path, size)
        except (FileNotFoundError, OSError):
            pass
    return pygame.font.Font(None, size)


class Renderer:
    """Main renderer that coordinates all UI panels and draws the top bar."""

    def __init__(self, screen: pygame.Surface) -> None:
        self.screen = screen
        self.panels: List[Panel] = []

        # Load fonts
        self.font_body = _load_font(FONT_SIZE_BODY)
        self.font_title = _load_font(FONT_SIZE_TITLE)
        self.font_hud = _load_font(FONT_SIZE_HUD)
        self.font_button = _load_font(FONT_SIZE_BUTTON)

        # Layout constants
        main_y = TOP_BAR_HEIGHT
        stats_h = 250
        inventory_y = main_y + stats_h
        inventory_h = SCREEN_HEIGHT - BOTTOM_BAR_HEIGHT - inventory_y

        # Create panels
        self.main_panel = MainPanel(pygame.Rect(0, main_y, MAIN_TEXT_WIDTH, SCREEN_HEIGHT - BOTTOM_BAR_HEIGHT - main_y))
        self.main_panel.set_font(self.font_body)

        self.stats_panel = StatsPanel(pygame.Rect(MAIN_TEXT_WIDTH, main_y, SIDE_PANEL_WIDTH, stats_h))
        self.stats_panel.set_font(self.font_hud, self.font_body)

        self.inventory_panel = InventoryPanel(pygame.Rect(MAIN_TEXT_WIDTH, inventory_y, SIDE_PANEL_WIDTH, inventory_h))
        self.inventory_panel.set_font(self.font_hud, self.font_body)

        self.button_bar = ButtonBar(pygame.Rect(0, SCREEN_HEIGHT - BOTTOM_BAR_HEIGHT, SCREEN_WIDTH, BOTTOM_BAR_HEIGHT))
        self.button_bar.set_font(self.font_button, self.font_hud)

        self.panels = [self.main_panel, self.stats_panel, self.inventory_panel, self.button_bar]

        # Top bar buttons
        self._btn_save = Button(
            pygame.Rect(SCREEN_WIDTH - 280, 6, 60, 28),
            "保存", callback=self._on_save,
        )
        self._btn_load = Button(
            pygame.Rect(SCREEN_WIDTH - 210, 6, 60, 28),
            "加载", callback=self._on_load,
        )
        self._btn_quit = Button(
            pygame.Rect(SCREEN_WIDTH - 140, 6, 60, 28),
            "退出", callback=self._on_quit,
        )
        self.top_buttons = [self._btn_save, self._btn_load, self._btn_quit]

        # Save/Load overlay state
        self.show_save_menu: bool = False
        self.show_load_menu: bool = False
        self._save_slot_buttons: List[Button] = []
        self._load_slot_buttons: List[Button] = []
        self._overlay_close_btn: Optional[Button] = None

    def render(self, game_state) -> None:
        """Render the full frame."""
        self.screen.fill(C.BG_DARK)
        self._draw_top_bar(game_state)

        # Draw dividers between panels
        # Vertical divider between main panel and side panels
        div_x = MAIN_TEXT_WIDTH
        pygame.draw.line(
            self.screen, C.DIVIDER,
            (div_x, TOP_BAR_HEIGHT), (div_x, SCREEN_HEIGHT - BOTTOM_BAR_HEIGHT),
        )
        # Horizontal divider between stats and inventory
        stats_bottom = TOP_BAR_HEIGHT + 250
        pygame.draw.line(
            self.screen, C.DIVIDER,
            (MAIN_TEXT_WIDTH, stats_bottom), (SCREEN_WIDTH, stats_bottom),
        )
        # Horizontal divider above button bar
        pygame.draw.line(
            self.screen, C.DIVIDER,
            (0, SCREEN_HEIGHT - BOTTOM_BAR_HEIGHT), (SCREEN_WIDTH, SCREEN_HEIGHT - BOTTOM_BAR_HEIGHT),
        )

        for panel in self.panels:
            panel.render(self.screen, game_state)

        # Draw save/load overlay if active
        if self.show_save_menu:
            self._draw_slot_overlay(game_state, "保存", self._save_slot_buttons)
        elif self.show_load_menu:
            self._draw_slot_overlay(game_state, "加载", self._load_slot_buttons)

        # Do NOT flip here — main.py handles flip

    def handle_click(self, pos, game_state) -> Optional[dict]:
        """Route click to top bar buttons and panels. Returns action dict or None."""
        # Check save/load overlay first
        if self.show_save_menu:
            action = self._handle_overlay_click(pos, self._save_slot_buttons, "save")
            return action
        if self.show_load_menu:
            action = self._handle_overlay_click(pos, self._load_slot_buttons, "load")
            return action

        # Top bar buttons
        for btn in self.top_buttons:
            if btn.handle_click(pos):
                return None

        # Check inventory panel for actions first (has specific action returns)
        inv_action = self.inventory_panel.get_action(pos, game_state)
        if inv_action is not None:
            return inv_action

        # Check button bar for actions
        bar_action = self.button_bar.get_action(pos, game_state)
        if bar_action is not None:
            return bar_action

        # Let panels consume clicks without actions
        for panel in self.panels:
            if panel.handle_click(pos, game_state):
                return None

        return None

    def handle_scroll(self, dy: int) -> None:
        """Handle mouse wheel scroll for main panel."""
        self.main_panel.handle_scroll(dy)

    def update_hover(self, pos, game_state) -> None:
        """Update hover state on buttons and panels."""
        for btn in self.top_buttons:
            btn.update_hover(pos)
        for panel in self.panels:
            panel.update_hover(pos, game_state)

    def _draw_top_bar(self, game_state) -> None:
        """Draw the top bar with level name, turn, and action buttons."""
        bar_rect = pygame.Rect(0, 0, SCREEN_WIDTH, TOP_BAR_HEIGHT)
        pygame.draw.rect(self.screen, C.BG_PANEL, bar_rect)

        # Level name and turn
        level_name = ""
        turn_text = ""
        if game_state.levels:
            current = game_state.levels[-1]
            level_name = f"关卡 {current.level_id}: {current.name}"
        if game_state.player:
            turn_text = f"回合 {game_state.turn}"

        title_surf = self.font_hud.render(level_name, True, C.TEXT_PRIMARY)
        self.screen.blit(title_surf, (12, 12))

        turn_surf = self.font_hud.render(turn_text, True, C.TEXT_DIM)
        self.screen.blit(turn_surf, (12 + title_surf.get_width() + 16, 12))

        # Phase indicator
        phase_colors = {
            "player_turn": C.AMMO_GREEN,
            "enemy_turn": C.HP_RED,
            "game_over": C.HP_RED,
            "victory": C.AMMO_GREEN,
            "level_complete": C.NOISE_YELLOW,
        }
        phase_labels = {
            "player_turn": "你的回合",
            "enemy_turn": "敌人回合",
            "game_over": "游戏结束",
            "victory": "胜利",
            "level_complete": "关卡完成",
        }
        phase_color = phase_colors.get(game_state.phase, C.TEXT_SECONDARY)
        phase_label = phase_labels.get(game_state.phase, game_state.phase)
        phase_surf = self.font_hud.render(phase_label, True, phase_color)
        self.screen.blit(phase_surf, (SCREEN_WIDTH - 380, 12))

        # Buttons
        for btn in self.top_buttons:
            btn.render(self.screen, self.font_button)

        # Divider line
        pygame.draw.line(
            self.screen, C.DIVIDER,
            (0, TOP_BAR_HEIGHT - 1), (SCREEN_WIDTH, TOP_BAR_HEIGHT - 1),
        )

    def _on_save(self) -> None:
        """Save game callback — show save slot overlay."""
        self.show_save_menu = True
        self.show_load_menu = False
        self._build_slot_buttons("save")

    def _on_load(self) -> None:
        """Load game callback — show load slot overlay."""
        self.show_load_menu = True
        self.show_save_menu = False
        self._build_slot_buttons("load")

    def _on_quit(self) -> None:
        """Quit callback."""
        pygame.event.post(pygame.event.Event(pygame.QUIT))

    def _build_slot_buttons(self, mode: str) -> None:
        """Build slot selection buttons for save/load overlay."""
        from save.save_manager import SaveManager
        sm = SaveManager()
        saves = sm.list_saves()

        buttons = []
        overlay_x = SCREEN_WIDTH // 2 - 100
        overlay_y = SCREEN_HEIGHT // 2 - 80

        for i, save_info in enumerate(saves):
            slot = save_info["slot"]
            exists = save_info.get("exists", False)
            if mode == "save":
                label = f"槽位 {slot}"
            else:
                label = f"槽位 {slot}" + (" (已用)" if exists else " (空)")
            btn = Button(
                pygame.Rect(overlay_x + 10, overlay_y + 40 + i * 36, 180, 30),
                label, callback=None,
                enabled=(mode == "save" or exists),
            )
            buttons.append((btn, slot))

        # Close button
        close_btn = Button(
            pygame.Rect(overlay_x + 10, overlay_y + 40 + len(saves) * 36 + 8, 180, 30),
            "取消", callback=None,
        )

        if mode == "save":
            self._save_slot_buttons = buttons
            self._overlay_close_btn = close_btn
        else:
            self._load_slot_buttons = buttons
            self._overlay_close_btn = close_btn

    def _draw_slot_overlay(self, game_state, title: str, slot_buttons: list) -> None:
        """Draw the save/load slot selection overlay."""
        overlay_x = SCREEN_WIDTH // 2 - 100
        overlay_y = SCREEN_HEIGHT // 2 - 80
        overlay_w = 200
        overlay_h = 40 + len(slot_buttons) * 36 + 50

        # Semi-transparent background
        overlay_surf = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay_surf.fill((0, 0, 0, 150))
        self.screen.blit(overlay_surf, (0, 0))

        # Dialog box
        box_rect = pygame.Rect(overlay_x, overlay_y, overlay_w, overlay_h)
        pygame.draw.rect(self.screen, C.BG_PANEL, box_rect, border_radius=8)
        pygame.draw.rect(self.screen, C.BORDER_COLOR, box_rect, width=2, border_radius=8)

        # Title
        title_surf = self.font_title.render(title, True, C.TEXT_PRIMARY)
        title_rect = title_surf.get_rect(centerx=overlay_x + overlay_w // 2, y=overlay_y + 8)
        self.screen.blit(title_surf, title_rect)

        # Slot buttons
        for btn, _slot in slot_buttons:
            btn.render(self.screen, self.font_button)

        # Close button
        if self._overlay_close_btn:
            self._overlay_close_btn.render(self.screen, self.font_button)

    def _handle_overlay_click(self, pos, slot_buttons: list, mode: str) -> Optional[dict]:
        """Handle clicks on save/load overlay."""
        # Check close button
        if self._overlay_close_btn and self._overlay_close_btn.is_clicked(pos):
            self.show_save_menu = False
            self.show_load_menu = False
            return None

        # Check slot buttons
        for btn, slot in slot_buttons:
            if btn.is_clicked(pos):
                self.show_save_menu = False
                self.show_load_menu = False
                if mode == "save":
                    return {"action": "save", "slot": slot}
                else:
                    return {"action": "load", "slot": slot}

        return None
