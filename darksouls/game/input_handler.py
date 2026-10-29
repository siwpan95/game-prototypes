"""InputHandler - maps keyboard and mouse events to game actions."""

import pygame


class InputHandler:
    """Maps pygame key events to semantic game actions, with mouse support."""

    def __init__(self) -> None:
        self._key_map: dict[int, str] = {
            pygame.K_LEFT: "move_left",
            pygame.K_RIGHT: "move_right",
            pygame.K_UP: "move_up",
            pygame.K_DOWN: "move_down",
            pygame.K_RETURN: "confirm",
            pygame.K_ESCAPE: "cancel",
            pygame.K_SPACE: "end_turn",
            pygame.K_d: "view_draw",
            pygame.K_g: "view_discard",
            pygame.K_e: "view_exhaust",
        }
        # Mouse state
        self.mouse_pos: tuple[int, int] = (0, 0)
        self.mouse_clicked: bool = False
        self.mouse_down: bool = False
        self.mouse_released: bool = False

    def process(self, event: pygame.event.Event) -> str | None:
        """Process a pygame event and return the mapped action string,
        or None if the event is not a relevant key press."""
        # Track mouse state
        if event.type == pygame.MOUSEMOTION:
            self.mouse_pos = event.pos
            return "mouse_move"
        elif event.type == pygame.MOUSEBUTTONDOWN:
            self.mouse_pos = event.pos
            self.mouse_clicked = True
            self.mouse_down = True
            return "mouse_click"
        elif event.type == pygame.MOUSEBUTTONUP:
            self.mouse_pos = event.pos
            self.mouse_released = True
            self.mouse_down = False
            return "mouse_release"
        if event.type != pygame.KEYDOWN:
            return None
        return self._key_map.get(event.key)

    def consume_click(self) -> None:
        """Consume the click state after processing."""
        self.mouse_clicked = False
        self.mouse_released = False

    def set_key(self, key: int, action: str) -> None:
        """Remap a key to a different action."""
        self._key_map[key] = action

    def get_key_for_action(self, action: str) -> int | None:
        """Return the key currently mapped to an action, or None."""
        for key, act in self._key_map.items():
            if act == action:
                return key
        return None
