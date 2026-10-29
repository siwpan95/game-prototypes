"""Renderer - rendering primitives, font cache, and layout helpers."""

import pygame
import os


class Renderer:
    """Centralized rendering utility with font cache and layout helpers.

    Handles all pygame drawing operations including text rendering,
    rectangles, bars, and card frames.
    """

    # Color palette
    COLOR_BG = (20, 18, 28)
    COLOR_PANEL = (35, 32, 48)
    COLOR_PANEL_LIGHT = (50, 46, 68)
    COLOR_TEXT = (220, 215, 200)
    COLOR_TEXT_DIM = (140, 135, 125)
    COLOR_HP_BAR = (180, 40, 40)
    COLOR_HP_BAR_BG = (60, 20, 20)
    COLOR_FP_BAR = (40, 80, 180)
    COLOR_FP_BAR_BG = (20, 30, 60)
    COLOR_BLOCK = (120, 140, 180)
    COLOR_ENEMY_HP = (160, 50, 50)
    COLOR_ENEMY_HP_BG = (50, 20, 20)
    COLOR_CARD_BG = (45, 42, 58)
    COLOR_CARD_BORDER = (90, 85, 110)
    COLOR_CARD_SELECTED = (255, 215, 0)
    COLOR_ATTACK = (200, 60, 60)
    COLOR_SKILL = (60, 120, 200)
    COLOR_POWER = (160, 60, 200)
    COLOR_GOLD = (255, 215, 0)
    COLOR_GREEN = (60, 180, 60)
    COLOR_CRIT = (255, 100, 50)
    COLOR_MISS = (150, 150, 150)
    COLOR_MISHAP = (200, 50, 200)
    COLOR_INTENT_ATTACK = (220, 80, 80)
    COLOR_INTENT_DEFEND = (80, 150, 220)
    COLOR_INTENT_SPECIAL = (180, 80, 220)
    COLOR_BUTTON = (60, 55, 80)
    COLOR_BUTTON_HOVER = (80, 75, 110)
    COLOR_BUTTON_TEXT = (220, 215, 200)

    def __init__(self, screen: pygame.Surface, base_path: str = "") -> None:
        self._screen = screen
        self._base_path = base_path
        self._font_cache: dict[tuple, pygame.font.Font] = {}
        self._default_font_path: str | None = None
        self._cn_font_path: str | None = None
        self._init_fonts()

    def _init_fonts(self) -> None:
        """Initialize font paths. Try Chinese font first, then fallback."""
        # Try system Chinese fonts
        cn_fonts = [
            os.path.join(os.environ.get("WINDIR", "C:\\Windows"), "Fonts", "simhei.ttf"),
            os.path.join(os.environ.get("WINDIR", "C:\\Windows"), "Fonts", "msyh.ttc"),
            os.path.join(self._base_path, "assets", "fonts", "simhei.ttf"),
        ]
        for fp in cn_fonts:
            if os.path.exists(fp):
                self._cn_font_path = fp
                self._default_font_path = fp
                break

        if self._default_font_path is None:
            # Try bundled fonts
            press_start_path = os.path.join(self._base_path, "assets", "fonts", "PressStart2P.ttf")
            if os.path.exists(press_start_path):
                self._default_font_path = press_start_path
            else:
                consola_path = os.path.join(self._base_path, "assets", "fonts", "Consola.ttf")
                if os.path.exists(consola_path):
                    self._default_font_path = consola_path
                else:
                    arial_path = os.path.join(self._base_path, "assets", "fonts", "Arial.ttf")
                    if os.path.exists(arial_path):
                        self._default_font_path = arial_path

    def _get_font(self, size: int) -> pygame.font.Font:
        """Get a cached font at the given size."""
        key = (self._default_font_path, size)
        if key not in self._font_cache:
            if self._default_font_path and os.path.exists(self._default_font_path):
                self._font_cache[key] = pygame.font.Font(self._default_font_path, size)
            else:
                # Last resort: use pygame default font
                self._font_cache[key] = pygame.font.Font(None, size)
        return self._font_cache[key]

    @property
    def screen_width(self) -> int:
        return self._screen.get_width()

    @property
    def screen_height(self) -> int:
        return self._screen.get_height()

    # --- Text Rendering ---

    def draw_text(
        self,
        text: str,
        x: int,
        y: int,
        size: int = 16,
        color: tuple | None = None,
        center: bool = False,
        right_align: bool = False,
    ) -> pygame.Rect:
        """Draw text at position (x, y).

        Args:
            text: Text string to render.
            x: X position.
            y: Y position.
            size: Font size.
            color: Text color (default: COLOR_TEXT).
            center: If True, center text on x.
            right_align: If True, right-align text on x.

        Returns:
            The bounding rect of the rendered text.
        """
        if color is None:
            color = self.COLOR_TEXT
        font = self._get_font(size)
        surface = font.render(text, True, color)
        rect = surface.get_rect()

        if center:
            rect.centerx = x
            rect.top = y
        elif right_align:
            rect.right = x
            rect.top = y
        else:
            rect.left = x
            rect.top = y

        self._screen.blit(surface, rect)
        return rect

    def draw_text_wrapped(
        self,
        text: str,
        x: int,
        y: int,
        max_width: int,
        size: int = 14,
        color: tuple | None = None,
    ) -> int:
        """Draw word-wrapped text within max_width.

        Returns the total height of the rendered text block.
        """
        if color is None:
            color = self.COLOR_TEXT
        font = self._get_font(size)
        words = text.split(" ")
        lines: list[str] = []
        current_line = ""

        for word in words:
            test_line = f"{current_line} {word}".strip()
            if font.size(test_line)[0] <= max_width:
                current_line = test_line
            else:
                if current_line:
                    lines.append(current_line)
                current_line = word
        if current_line:
            lines.append(current_line)

        current_y = y
        for line in lines:
            self.draw_text(line, x, current_y, size, color)
            current_y += font.get_linesize()
        return current_y - y

    # --- Primitive Drawing ---

    def fill_bg(self, color: tuple | None = None) -> None:
        """Fill the entire screen with a background color."""
        if color is None:
            color = self.COLOR_BG
        self._screen.fill(color)

    def draw_rect(
        self,
        x: int,
        y: int,
        w: int,
        h: int,
        color: tuple,
        border: int = 0,
        border_radius: int = 0,
    ) -> pygame.Rect:
        """Draw a rectangle."""
        rect = pygame.Rect(x, y, w, h)
        if border > 0:
            pygame.draw.rect(self._screen, color, rect, border, border_radius)
        else:
            pygame.draw.rect(self._screen, color, rect, 0, border_radius)
        return rect

    def draw_bar(
        self,
        x: int,
        y: int,
        w: int,
        h: int,
        current: int,
        maximum: int,
        color: tuple,
        bg_color: tuple,
    ) -> pygame.Rect:
        """Draw a progress bar (HP, FP, etc.)."""
        rect = pygame.Rect(x, y, w, h)
        pygame.draw.rect(self._screen, bg_color, rect)
        if maximum > 0:
            fill_w = max(0, int(w * current / maximum))
            fill_rect = pygame.Rect(x, y, fill_w, h)
            pygame.draw.rect(self._screen, color, fill_rect)
        pygame.draw.rect(self._screen, (80, 75, 100), rect, 1)
        return rect

    def draw_card(
        self,
        x: int,
        y: int,
        w: int,
        h: int,
        card,
        selected: bool = False,
        playable: bool = True,
    ) -> pygame.Rect:
        """Draw a card frame with card info."""
        # Card background
        bg_color = self.COLOR_CARD_BG if playable else (30, 28, 40)
        border_color = self.COLOR_CARD_SELECTED if selected else self.COLOR_CARD_BORDER
        border_width = 3 if selected else 1

        rect = pygame.Rect(x, y, w, h)
        pygame.draw.rect(self._screen, bg_color, rect, 0, 5)
        pygame.draw.rect(self._screen, border_color, rect, border_width, 5)

        # Card type color strip
        type_color = {
            "Attack": self.COLOR_ATTACK,
            "Skill": self.COLOR_SKILL,
            "Power": self.COLOR_POWER,
        }.get(card.type, self.COLOR_TEXT_DIM)
        strip_rect = pygame.Rect(x + 2, y + 2, w - 4, 4)
        pygame.draw.rect(self._screen, type_color, strip_rect)

        # Card name
        name_size = max(8, min(12, w // 10))
        self.draw_text(card.name, x + w // 2, y + 8, name_size, self.COLOR_TEXT, center=True)

        # Cost
        self.draw_text(f"FP:{card.cost}", x + 4, y + 22, 9, self.COLOR_FP_BAR)

        # Card effect
        if card.damage != "0":
            self.draw_text(f"DMG:{card.damage}", x + 4, y + 36, 8, self.COLOR_ATTACK)
        if card.block > 0:
            self.draw_text(f"BLK:{card.block}", x + 4, y + 48, 8, self.COLOR_BLOCK)

        # Keywords
        keyword_y = y + 60
        for kw, val in card.keywords.items():
            if keyword_y < y + h - 14:
                self.draw_text(f"{kw}:{val}", x + 4, keyword_y, 7, self.COLOR_GOLD)
                keyword_y += 10

        return rect

    def draw_button(
        self,
        x: int,
        y: int,
        w: int,
        h: int,
        text: str,
        selected: bool = False,
        font_size: int = 14,
    ) -> pygame.Rect:
        """Draw a button with text."""
        color = self.COLOR_BUTTON_HOVER if selected else self.COLOR_BUTTON
        rect = pygame.Rect(x, y, w, h)
        pygame.draw.rect(self._screen, color, rect, 0, 4)
        pygame.draw.rect(self._screen, self.COLOR_CARD_BORDER, rect, 1, 4)
        self.draw_text(text, x + w // 2, y + h // 2 - font_size // 2, font_size,
                       self.COLOR_BUTTON_TEXT, center=True)
        return rect

    # --- Layout Helpers ---

    def center_x(self, width: int) -> int:
        """Return x position to center something of given width."""
        return (self.screen_width - width) // 2

    def center_y(self, height: int) -> int:
        """Return y position to center something of given height."""
        return (self.screen_height - height) // 2
