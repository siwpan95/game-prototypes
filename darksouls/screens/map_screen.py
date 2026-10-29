"""MapScreen - map UI rendering and route selection, with Chinese UI and mouse support."""

from __future__ import annotations

import pygame

from screens.base_screen import BaseScreen
from services.renderer import Renderer
from controllers.map_controller import GameMap, MapNode


class MapScreen(BaseScreen):
    """Map screen showing the act map with node selection."""

    def __init__(self) -> None:
        super().__init__()
        self._game_map: GameMap | None = None
        self._node_rects: list[tuple[pygame.Rect, int, int]] = []  # (rect, row, col)

    def on_enter(self, **kwargs) -> None:
        self._game_map = kwargs.get("game_map")
        if self._game_map:
            self._selected_index = self._game_map.selected_col

    def on_exit(self) -> None:
        pass

    def handle_event(self, event) -> None:
        if self._game_map is None:
            return

        # Mouse hover to select node
        if event.type == pygame.MOUSEMOTION:
            self._check_node_hover(event.pos)
            return

        # Mouse click to confirm node
        if event.type == pygame.MOUSEBUTTONDOWN:
            self.game.input_handler.consume_click()
            clicked = False
            for rect, row_idx, col_idx in self._node_rects:
                if rect.collidepoint(event.pos):
                    if row_idx == self._game_map.current_row:
                        self._game_map.selected_col = col_idx
                        self._selected_index = col_idx
                        clicked = True
                        break
            if clicked:
                self._confirm_node()
            return

        if event.type != pygame.KEYDOWN:
            return

        if event.key == pygame.K_LEFT:
            self._game_map.move_selection(-1)
            self._selected_index = self._game_map.selected_col
        elif event.key == pygame.K_RIGHT:
            self._game_map.move_selection(1)
            self._selected_index = self._game_map.selected_col
        elif event.key == pygame.K_RETURN:
            self._confirm_node()
        elif event.key == pygame.K_ESCAPE:
            self.game.open_settings()

    def _check_node_hover(self, pos: tuple[int, int]) -> None:
        """Check if mouse is hovering over a map node."""
        for rect, row_idx, col_idx in self._node_rects:
            if rect.collidepoint(pos) and row_idx == self._game_map.current_row:
                self._game_map.selected_col = col_idx
                self._selected_index = col_idx
                return

    def _confirm_node(self) -> None:
        """Confirm selection of the current map node."""
        if self._game_map is None:
            return

        node = self._game_map.current_node()
        if node is None:
            return

        if node.node_type == "battle" or node.node_type == "boss":
            self.game.start_battle(node)
        elif node.node_type in ("event", "bonfire"):
            self.game.start_event(node)
        elif node.node_type == "shop":
            self.game.start_event(node)
        elif node.node_type == "blacksmith":
            self.game.start_event(node)

        self._game_map.advance_row()

    def update(self, dt: float) -> None:
        pass

    def render(self, surface) -> None:
        if self._game_map is None:
            return

        r = self.renderer
        r.fill_bg()

        # Header
        act_data = self.game.data_loader.get_act_data(self._game_map.act)
        act_name = act_data["name"] if act_data else f"第{self._game_map.act}关"
        self.draw_header(f"第{self._game_map.act}关: {act_name}")

        # Player status
        if self.game.player:
            self.draw_player_status(self.game.player, y_offset=55)

        # Draw map
        self._render_map(r)

        # Footer
        footer_text = "方向键/鼠标: 选择节点 | 回车/点击: 确认 | Esc: 设置"
        self.draw_footer(footer_text)

    def _render_map(self, r: Renderer) -> None:
        """Render the full map grid."""
        if self._game_map is None:
            return

        self._node_rects.clear()

        map_x_start = 80
        map_y_start = 120
        row_height = 80
        col_width = 200

        type_labels = {
            "battle": "战斗",
            "boss": "BOSS",
            "event": "事件",
            "bonfire": "篝火",
            "shop": "商店",
            "blacksmith": "铁匠",
        }

        node_colors = {
            "battle": Renderer.COLOR_ATTACK,
            "boss": Renderer.COLOR_GOLD,
            "event": Renderer.COLOR_INTENT_SPECIAL,
            "bonfire": (200, 120, 40),
            "shop": Renderer.COLOR_GREEN,
            "blacksmith": Renderer.COLOR_BLOCK,
        }

        for row_idx, row in enumerate(self._game_map.rows):
            for col_idx, node in enumerate(row):
                x = map_x_start + col_idx * col_width
                y = map_y_start + row_idx * row_height

                is_current_row = (row_idx == self._game_map.current_row)
                is_selected = (is_current_row and col_idx == self._game_map.selected_col)

                color = node_colors.get(node.node_type, Renderer.COLOR_TEXT_DIM)
                bg_color = Renderer.COLOR_PANEL

                if node.cleared:
                    color = Renderer.COLOR_TEXT_DIM
                    bg_color = (25, 22, 35)
                elif is_selected:
                    bg_color = Renderer.COLOR_PANEL_LIGHT

                node_w = 180
                node_h = 60
                r.draw_rect(x, y, node_w, node_h, bg_color, border_radius=6)

                if is_selected:
                    pygame.draw.rect(r._screen, Renderer.COLOR_GOLD,
                                   pygame.Rect(x, y, node_w, node_h), 2, 6)

                # Node type label
                label = type_labels.get(node.node_type, node.node_type.upper())
                r.draw_text(label, x + node_w // 2, y + 8, 11, color, center=True)

                # Enemy name for battle/boss nodes
                if node.node_type in ("battle", "boss") and node.enemy_id:
                    enemy_data = self.game.data_loader.get_enemy_data(node.enemy_id)
                    if enemy_data:
                        r.draw_text(enemy_data["name"], x + node_w // 2, y + 25, 10,
                                    Renderer.COLOR_TEXT_DIM, center=True)

                # Cleared indicator
                if node.cleared:
                    r.draw_text("已完成", x + node_w // 2, y + 40, 10,
                                Renderer.COLOR_GREEN, center=True)

                # Store rect for mouse interaction
                self._node_rects.append((pygame.Rect(x, y, node_w, node_h), row_idx, col_idx))

        # Draw connecting lines
        for row_idx in range(len(self._game_map.rows) - 1):
            current_row = self._game_map.rows[row_idx]
            next_row = self._game_map.rows[row_idx + 1]
            for col_idx, node in enumerate(current_row):
                x1 = map_x_start + col_idx * col_width + 90
                y1 = map_y_start + row_idx * row_height + 60
                for next_col_idx, next_node in enumerate(next_row):
                    x2 = map_x_start + next_col_idx * col_width + 90
                    y2 = map_y_start + (row_idx + 1) * row_height
                    pygame.draw.line(r._screen, Renderer.COLOR_PANEL_LIGHT,
                                   (x1, y1), (x2, y2), 1)
