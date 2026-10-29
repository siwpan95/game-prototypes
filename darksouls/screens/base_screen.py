"""BaseScreen - common rendering helpers for all screens, with mouse support."""

from __future__ import annotations

import pygame

from game.state import State
from services.renderer import Renderer


class BaseScreen(State):
    """Abstract base class for game screens with common rendering helpers.

    All screens inherit from this class and implement:
        on_enter()    - setup when screen becomes active
        on_exit()     - cleanup when screen is deactivated
        handle_event() - process pygame events (keyboard + mouse)
        update()      - update logic
        render()      - draw to screen
    """

    def __init__(self) -> None:
        super().__init__()
        self._selected_index: int = 0
        # Track interactive regions for mouse hover/click
        self._click_regions: list[tuple[pygame.Rect, str, object]] = []

    @property
    def renderer(self) -> Renderer:
        """Get the Renderer from the game object."""
        return self.game.renderer

    @property
    def screen_width(self) -> int:
        return self.renderer.screen_width

    @property
    def screen_height(self) -> int:
        return self.renderer.screen_height

    @property
    def mouse_pos(self) -> tuple[int, int]:
        """Current mouse position from the game's input handler."""
        return self.game.input_handler.mouse_pos

    @property
    def mouse_clicked(self) -> bool:
        """Whether a mouse click just occurred."""
        return self.game.input_handler.mouse_clicked

    def is_hovering(self, rect: pygame.Rect) -> bool:
        """Check if mouse is hovering over the given rect."""
        return rect.collidepoint(self.mouse_pos)

    @staticmethod
    def is_point_in_rect(pos: tuple[int, int], rect: pygame.Rect) -> bool:
        """Check if a point is inside a rectangle."""
        return rect.collidepoint(pos)

    def begin_click_regions(self) -> None:
        """Clear the click regions list for a new frame."""
        self._click_regions.clear()

    def add_click_region(self, rect: pygame.Rect, action: str, data: object = None) -> None:
        """Add a clickable region for the current frame."""
        self._click_regions.append((rect, action, data))

    def check_click(self) -> tuple[str | None, object]:
        """Check if mouse clicked any registered region.
        Returns (action_name, data) or (None, None).
        """
        if not self.mouse_clicked:
            return None, None
        mx, my = self.mouse_pos
        for rect, action, data in reversed(self._click_regions):
            if rect.collidepoint(mx, my):
                self.game.input_handler.consume_click()
                return action, data
        return None, None

    def draw_header(self, title: str) -> None:
        """Draw a standard header bar at the top of the screen."""
        r = self.renderer
        r.draw_rect(0, 0, r.screen_width, 50, Renderer.COLOR_PANEL)
        r.draw_text(title, r.screen_width // 2, 10, 18, Renderer.COLOR_TEXT, center=True)
        pygame.draw.line(r._screen, Renderer.COLOR_PANEL_LIGHT,
                        (0, 50), (r.screen_width, 50), 1)

    def draw_footer(self, text: str = "") -> None:
        """Draw a footer bar at the bottom of the screen."""
        r = self.renderer
        footer_h = 40
        y = r.screen_height - footer_h
        r.draw_rect(0, y, r.screen_width, footer_h, Renderer.COLOR_PANEL)
        if text:
            r.draw_text(text, r.screen_width // 2, y + 10, 12, Renderer.COLOR_TEXT_DIM, center=True)

    def draw_player_status(self, player, y_offset: int = 5) -> None:
        """Draw player HP, FP, Block, Souls in the header area."""
        r = self.renderer
        # HP bar
        hp_label = f"HP: {player.hp}/{player.max_hp}"
        r.draw_text(hp_label, 10, y_offset, 10, Renderer.COLOR_HP_BAR)
        r.draw_bar(10, y_offset + 14, 150, 12, player.hp, player.max_hp,
                   Renderer.COLOR_HP_BAR, Renderer.COLOR_HP_BAR_BG)

        # FP bar
        fp_label = f"FP: {player.fp}/{player.max_fp}"
        r.draw_text(fp_label, 170, y_offset, 10, Renderer.COLOR_FP_BAR)
        r.draw_bar(170, y_offset + 14, 100, 12, player.fp, player.max_fp,
                   Renderer.COLOR_FP_BAR, Renderer.COLOR_FP_BAR_BG)

        # Block
        if player.block > 0:
            r.draw_text(f"BLK: {player.block}", 280, y_offset, 10, Renderer.COLOR_BLOCK)

        # Souls
        r.draw_text(f"Souls: {player.souls}", r.screen_width - 120, y_offset, 10,
                    Renderer.COLOR_GOLD)

        # Stats
        r.draw_text(f"STR:{player.str} DEX:{player.dex}", 10, y_offset + 30, 8,
                    Renderer.COLOR_TEXT_DIM)

    def draw_options(self, options: list[str], selected: int, x: int, y: int,
                     spacing: int = 40, font_size: int = 14) -> list[pygame.Rect]:
        """Draw a vertical list of options with selection highlighting.
        Returns list of option rects for mouse interaction."""
        r = self.renderer
        rects: list[pygame.Rect] = []
        for i, option in enumerate(options):
            is_selected = (i == selected)
            color = Renderer.COLOR_GOLD if is_selected else Renderer.COLOR_TEXT
            prefix = "> " if is_selected else "  "
            text_rect = r.draw_text(f"{prefix}{option}", x, y + i * spacing, font_size, color)
            # Expand click area
            click_rect = pygame.Rect(x - 10, y + i * spacing - 2, 300, spacing - 4)
            rects.append(click_rect)
        return rects
