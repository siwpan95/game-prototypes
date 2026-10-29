"""EventScreen - event UI with mouse support and Chinese text."""

from __future__ import annotations

import pygame

from screens.base_screen import BaseScreen
from services.renderer import Renderer
from controllers.event_controller import EventController


class EventScreen(BaseScreen):
    """Event screen for bonfire, shop, and blacksmith encounters."""

    def __init__(self) -> None:
        super().__init__()
        self._event_controller: EventController | None = None
        self._event_data: dict | None = None
        self._result_message: str = ""
        self._show_result: bool = False
        self._option_rects: list[pygame.Rect] = []

    def on_enter(self, **kwargs) -> None:
        self._event_controller = kwargs.get("event_controller")
        self._event_data = kwargs.get("event_data")
        self._selected_index = 0
        self._result_message = ""
        self._show_result = False

    def on_exit(self) -> None:
        self._event_controller = None
        self._event_data = None

    def handle_event(self, event) -> None:
        if self._event_data is None:
            return

        if self._show_result:
            if event.type == pygame.MOUSEBUTTONDOWN:
                self.game.input_handler.consume_click()
                self._show_result = False
                self.game.return_to_map()
            elif event.type == pygame.KEYDOWN and event.key in (pygame.K_RETURN, pygame.K_ESCAPE):
                self._show_result = False
                self.game.return_to_map()
            return

        options = self._event_data.get("options", [])

        # Mouse hover
        if event.type == pygame.MOUSEMOTION:
            self._check_hover(event.pos, options)
            return

        # Mouse click
        if event.type == pygame.MOUSEBUTTONDOWN:
            self.game.input_handler.consume_click()
            self._check_hover(event.pos, options)
            self._select_option()
            return

        if event.type != pygame.KEYDOWN:
            return

        if event.key == pygame.K_UP:
            self._selected_index = max(0, self._selected_index - 1)
        elif event.key == pygame.K_DOWN:
            self._selected_index = min(len(options) - 1, self._selected_index + 1)
        elif event.key == pygame.K_RETURN:
            self._select_option()
        elif event.key == pygame.K_ESCAPE:
            self.game.return_to_map()

    def _check_hover(self, pos: tuple[int, int], options: list) -> None:
        """Check mouse hover over options."""
        for i, rect in enumerate(self._option_rects):
            if rect.collidepoint(pos):
                self._selected_index = i
                return

    def _select_option(self) -> None:
        """Process the selected event option."""
        if self._event_controller is None or self._event_data is None:
            return

        player = self.game.player
        result = self._event_controller.resolve_event_option(
            player, self._event_data, self._selected_index
        )

        self._result_message = result["message"]
        self._show_result = True

    def update(self, dt: float) -> None:
        pass

    def render(self, surface) -> None:
        if self._event_data is None:
            return

        r = self.renderer
        r.fill_bg()

        event = self._event_data

        # Header
        self.draw_header(event.get("name", "事件"))

        # Player status
        self.draw_player_status(self.game.player, y_offset=55)

        # Event panel
        panel_w = 500
        panel_h = 300
        panel_x = r.center_x(panel_w)
        panel_y = 120

        r.draw_rect(panel_x, panel_y, panel_w, panel_h, Renderer.COLOR_PANEL, border_radius=8)

        # Event type indicator
        event_type = event.get("type", "event")
        type_labels = {"bonfire": "篝火", "shop": "商店", "blacksmith": "铁匠", "puzzle": "谜题", "special": "特殊", "shrine": "神龛"}
        type_colors = {
            "bonfire": (200, 120, 40),
            "shop": Renderer.COLOR_GREEN,
            "blacksmith": Renderer.COLOR_BLOCK,
        }
        type_color = type_colors.get(event_type, Renderer.COLOR_TEXT_DIM)
        r.draw_text(type_labels.get(event_type, event_type.upper()), panel_x + panel_w // 2, panel_y + 10,
                    13, type_color, center=True)

        # Description
        desc = event.get("description", "")
        r.draw_text_wrapped(desc, panel_x + 20, panel_y + 35, panel_w - 40, 14,
                           Renderer.COLOR_TEXT)

        # Options
        options = event.get("options", [])
        options_y = panel_y + 100
        self._option_rects.clear()
        for i, option in enumerate(options):
            text = option.get("text", "???")
            cost = option.get("cost", 0)

            color = Renderer.COLOR_GOLD if i == self._selected_index else Renderer.COLOR_TEXT
            prefix = "> " if i == self._selected_index else "  "

            display_text = f"{prefix}{text}"
            if cost > 0:
                display_text += f" [{cost} 灵魂]"

            opt_y = options_y + i * 35
            r.draw_text(display_text, panel_x + 20, opt_y, 14, color)
            self._option_rects.append(pygame.Rect(panel_x + 10, opt_y - 2, panel_w - 20, 32))

        # Result overlay
        if self._show_result:
            result_w = 350
            result_h = 120
            rx = r.center_x(result_w)
            ry = r.center_y(result_h)

            r.draw_rect(rx, ry, result_w, result_h, Renderer.COLOR_PANEL, border_radius=8)
            r.draw_text_wrapped(self._result_message, rx + 20, ry + 20,
                               result_w - 40, 14, Renderer.COLOR_TEXT)
            r.draw_text("按回车或点击继续", rx + result_w // 2, ry + result_h - 25,
                        11, Renderer.COLOR_TEXT_DIM, center=True)

        # Footer
        self.draw_footer("方向键/鼠标: 选择 | 回车/点击: 确认 | Esc: 返回")
