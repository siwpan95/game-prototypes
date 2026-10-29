"""Button - Clickable UI button component."""
try:
    import pygame_ce as pygame
except ImportError:
    import pygame
from typing import Callable, Optional, Tuple

from ui import colors as C


class Button:
    """A clickable button with hover and disabled states."""

    def __init__(
        self,
        rect: pygame.Rect,
        text: str,
        callback: Optional[Callable] = None,
        enabled: bool = True,
        visible: bool = True,
        tooltip: str = "",
    ) -> None:
        self.rect = rect
        self.text = text
        self.callback = callback
        self.enabled = enabled
        self.hovered = False
        self.visible = visible
        self.tooltip = tooltip

    def render(self, surface: pygame.Surface, font: pygame.font.Font) -> None:
        """Draw the button on the surface."""
        if not self.visible:
            return

        # Determine background color
        if not self.enabled:
            bg = C.BTN_DISABLED
            fg = C.TEXT_DIM
        elif self.hovered:
            bg = C.BTN_HOVER
            fg = C.TEXT_PRIMARY
        else:
            bg = C.BTN_NORMAL
            fg = C.TEXT_WHITE

        # Draw rounded rect
        pygame.draw.rect(surface, bg, self.rect, border_radius=4)
        pygame.draw.rect(surface, C.BORDER_COLOR, self.rect, width=1, border_radius=4)

        # Draw text centered
        text_surf = font.render(self.text, True, fg)
        text_rect = text_surf.get_rect(center=self.rect.center)
        surface.blit(text_surf, text_rect)

    def handle_click(self, pos: Tuple[int, int]) -> bool:
        """Handle a click at pos. Returns True if button was clicked and action triggered."""
        if not self.visible or not self.enabled:
            return False
        if self.is_clicked(pos):
            if self.callback:
                self.callback()
            return True
        return False

    def update_hover(self, pos: Tuple[int, int]) -> None:
        """Update hover state based on mouse position."""
        if not self.visible or not self.enabled:
            self.hovered = False
            return
        self.hovered = self.rect.collidepoint(pos)

    def is_clicked(self, pos: Tuple[int, int]) -> bool:
        """Check if pos is inside the button rect."""
        return self.visible and self.enabled and self.rect.collidepoint(pos)
