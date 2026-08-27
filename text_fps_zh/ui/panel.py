"""Panel - Base class for UI panels."""
try:
    import pygame_ce as pygame
except ImportError:
    import pygame
from typing import Tuple

from ui import colors as C


class Panel:
    """Base class for all UI panels."""

    def __init__(self, rect: pygame.Rect, bg_color: Tuple[int, int, int] = C.BG_PANEL) -> None:
        self.rect = rect
        self.bg_color = bg_color
        self.visible: bool = True

    def render(self, surface: pygame.Surface, game_state) -> None:
        """Render the panel. Override in subclasses."""
        if not self.visible:
            return
        pygame.draw.rect(surface, self.bg_color, self.rect, border_radius=6)

    def handle_click(self, pos: Tuple[int, int], game_state) -> bool:
        """Handle a click. Override in subclasses. Returns True if consumed."""
        if not self.visible:
            return False
        return self.rect.collidepoint(pos)

    def update_hover(self, pos: Tuple[int, int], game_state) -> None:
        """Update hover state. Override in subclasses."""
        pass
