"""InventoryPanel - Player inventory display with item interaction."""
from typing import Optional, Dict

try:
    import pygame_ce as pygame
except ImportError:
    import pygame

from ui.panel import Panel
from ui.button import Button
from ui import colors as C
from core.constants import MAX_INVENTORY
from models.item import Item, Grenade, WeaponModItem


class InventoryPanel(Panel):
    """Right-side panel showing player inventory and room items."""

    ITEM_LINE_HEIGHT = 18
    BUTTON_WIDTH = 70
    BUTTON_HEIGHT = 24

    def __init__(self, rect: pygame.Rect) -> None:
        super().__init__(rect, bg_color=C.BG_PANEL)
        self.font_hud: pygame.font.Font = pygame.font.Font(None, 14)
        self.font_body: pygame.font.Font = pygame.font.Font(None, 16)
        self.selected_index: int = -1
        self._hover_index: int = -1

        # Action buttons (positioned during render)
        self._btn_use = Button(
            pygame.Rect(0, 0, self.BUTTON_WIDTH, self.BUTTON_HEIGHT),
            "使用", callback=None,
        )
        self._btn_drop = Button(
            pygame.Rect(0, 0, self.BUTTON_WIDTH, self.BUTTON_HEIGHT),
            "丢弃", callback=None,
        )
        self._btn_pickup = Button(
            pygame.Rect(0, 0, self.BUTTON_WIDTH + 20, self.BUTTON_HEIGHT),
            "拾取", callback=None,
        )
        self._btn_mod = Button(
            pygame.Rect(0, 0, self.BUTTON_WIDTH, self.BUTTON_HEIGHT),
            "改装", callback=None,
        )

    def set_font(self, font_hud: pygame.font.Font, font_body: pygame.font.Font) -> None:
        """Set fonts for rendering."""
        self.font_hud = font_hud
        self.font_body = font_body

    def render(self, surface: pygame.Surface, game_state) -> None:
        """Render inventory list and action buttons."""
        super().render(surface, game_state)
        if not game_state or not game_state.player:
            return

        player = game_state.player
        room = game_state.current_room
        x = self.rect.x + 8
        y = self.rect.y + 6
        content_width = self.rect.width - 16

        # Section header
        header = self.font_body.render("背包", True, C.TEXT_PRIMARY)
        surface.blit(header, (x, y))
        count_text = f"({len(player.inventory)}/{MAX_INVENTORY})"
        count_surf = self.font_hud.render(count_text, True, C.TEXT_DIM)
        surface.blit(count_surf, (x + header.get_width() + 6, y + 2))
        y += 22

        # Weapon info
        weapon = player.current_weapon()
        if weapon:
            weapon_text = f">> {weapon.name} [{weapon.ammo}/{weapon.effective_max_ammo}]"
            weapon_surf = self.font_hud.render(weapon_text, True, C.AMMO_GREEN)
            surface.blit(weapon_surf, (x + 2, y))
            y += 16
            if weapon.mods:
                for mod in weapon.mods:
                    mod_text = f"  + {mod.name}"
                    mod_surf = self.font_hud.render(mod_text, True, C.TEXT_PRIMARY)
                    surface.blit(mod_surf, (x + 2, y))
                    y += 14
            y += 4

        # Divider
        pygame.draw.line(surface, C.DIVIDER, (x, y), (x + content_width, y))
        y = self._item_list_start_y(player)

        # Item list
        if player.inventory:
            for i, item in enumerate(player.inventory):
                if y + self.ITEM_LINE_HEIGHT > self.rect.y + self.rect.height - 60:
                    more = self.font_hud.render(
                        f"... 还有 {len(player.inventory) - i} 件", True, C.TEXT_DIM
                    )
                    surface.blit(more, (x + 4, y))
                    break

                # Highlight selected
                color = C.TEXT_WHITE
                if i == self.selected_index:
                    sel_rect = pygame.Rect(x - 2, y - 1, content_width + 4, self.ITEM_LINE_HEIGHT)
                    pygame.draw.rect(surface, C.BG_PANEL_LIGHT, sel_rect, border_radius=2)
                    color = C.TEXT_PRIMARY
                elif i == self._hover_index:
                    color = C.TEXT_SECONDARY

                # Item type icon/prefix
                prefix = self._item_prefix(item)
                item_text = f"{prefix} {item.name}"
                item_surf = self.font_hud.render(item_text, True, color)
                surface.blit(item_surf, (x + 4, y))
                y += self.ITEM_LINE_HEIGHT
        else:
            empty_surf = self.font_hud.render("空", True, C.TEXT_DIM)
            surface.blit(empty_surf, (x + 4, y))
            y += self.ITEM_LINE_HEIGHT

        # Action buttons at bottom
        btn_y = self.rect.y + self.rect.height - 30
        self._render_action_buttons(surface, game_state, x, btn_y, content_width)

    def _item_list_start_y(self, player) -> int:
        """Single source of truth for the Y where the item list begins.

        Previously this offset was recomputed in render/handle_click/update_hover
        with a 2px drift between them; centralizing it keeps hitboxes aligned
        with what is drawn.
        """
        y = self.rect.y + 6 + 22  # header row
        weapon = player.current_weapon()
        if weapon:
            y += 16
            if weapon.mods:
                y += 14 * len(weapon.mods)
            y += 4
        y += 6  # divider line
        return y

    def _item_prefix(self, item: Item) -> str:
        """Get a prefix indicator for item type."""
        if isinstance(item, Grenade):
            return "[*]"
        if isinstance(item, WeaponModItem):
            return "[+]"
        if item.item_type == "medkit":
            return "[+]"
        if item.item_type == "armor":
            return "[#]"
        if item.item_type == "ammo":
            return "[=]"
        return "[-]"

    def _render_action_buttons(
        self, surface: pygame.Surface, game_state,
        x: int, y: int, width: int,
    ) -> None:
        """Render Use/Drop/PickUp/Attach buttons at bottom of panel."""
        player = game_state.player
        room = game_state.current_room

        # Determine button enabled states
        has_selection = 0 <= self.selected_index < len(player.inventory)
        selected_item = player.inventory[self.selected_index] if has_selection else None
        is_mod = isinstance(selected_item, WeaponModItem) if selected_item else False
        room_has_items = room and len(room.items) > 0 if room else False

        # Use button
        self._btn_use.rect.x = x
        self._btn_use.rect.y = y
        self._btn_use.enabled = has_selection and selected_item is not None and not is_mod
        self._btn_use.render(surface, self.font_hud)

        # Drop button
        self._btn_drop.rect.x = x + self.BUTTON_WIDTH + 4
        self._btn_drop.rect.y = y
        self._btn_drop.enabled = has_selection
        self._btn_drop.render(surface, self.font_hud)

        # Attach (mod) button
        self._btn_mod.rect.x = x + (self.BUTTON_WIDTH + 4) * 2
        self._btn_mod.rect.y = y
        self._btn_mod.enabled = has_selection and is_mod
        self._btn_mod.render(surface, self.font_hud)

        # Pick Up button
        self._btn_pickup.rect.x = x + (self.BUTTON_WIDTH + 4) * 3
        self._btn_pickup.rect.y = y
        self._btn_pickup.enabled = room_has_items
        self._btn_pickup.render(surface, self.font_hud)

    def handle_click(self, pos, game_state) -> bool:
        """Handle clicks on items or action buttons. Returns action dict or True if consumed."""
        if not self.rect.collidepoint(pos):
            return False

        if not game_state or not game_state.player:
            return True

        player = game_state.player

        # Check action buttons
        if self._btn_use.is_clicked(pos):
            if 0 <= self.selected_index < len(player.inventory):
                return True  # Will be handled by returning action
            return True

        if self._btn_drop.is_clicked(pos):
            if 0 <= self.selected_index < len(player.inventory):
                return True
            return True

        if self._btn_mod.is_clicked(pos):
            if 0 <= self.selected_index < len(player.inventory):
                return True
            return True

        if self._btn_pickup.is_clicked(pos):
            return True

        # Check item list clicks
        x = self.rect.x + 8
        y = self._item_list_start_y(player)

        for i in range(len(player.inventory)):
            if y + self.ITEM_LINE_HEIGHT > self.rect.y + self.rect.height - 60:
                break
            item_rect = pygame.Rect(x - 2, y - 1, self.rect.width - 16, self.ITEM_LINE_HEIGHT)
            if item_rect.collidepoint(pos):
                self.selected_index = i
                return True
            y += self.ITEM_LINE_HEIGHT

        return True

    def get_action(self, pos, game_state) -> Optional[Dict]:
        """Get the action associated with a click. Returns action dict or None."""
        if not self.rect.collidepoint(pos):
            return None

        player = game_state.player

        # Use button
        if self._btn_use.is_clicked(pos):
            if 0 <= self.selected_index < len(player.inventory):
                return {"action": "use_item", "index": self.selected_index}
            return None

        # Drop button
        if self._btn_drop.is_clicked(pos):
            if 0 <= self.selected_index < len(player.inventory):
                return {"action": "drop_item", "index": self.selected_index}
            return None

        # Attach mod button
        if self._btn_mod.is_clicked(pos):
            if 0 <= self.selected_index < len(player.inventory):
                return {"action": "modify_weapon", "index": self.selected_index}
            return None

        # Pick Up button
        if self._btn_pickup.is_clicked(pos):
            return {"action": "pickup"}

        return None

    def update_hover(self, pos, game_state) -> None:
        """Update hover state for buttons and item list."""
        # Buttons
        self._btn_use.update_hover(pos)
        self._btn_drop.update_hover(pos)
        self._btn_mod.update_hover(pos)
        self._btn_pickup.update_hover(pos)

        # Item list hover
        self._hover_index = -1
        if not game_state or not game_state.player:
            return

        player = game_state.player
        x = self.rect.x + 8
        y = self._item_list_start_y(player)

        for i in range(len(player.inventory)):
            if y + self.ITEM_LINE_HEIGHT > self.rect.y + self.rect.height - 60:
                break
            item_rect = pygame.Rect(x - 2, y - 1, self.rect.width - 16, self.ITEM_LINE_HEIGHT)
            if item_rect.collidepoint(pos):
                self._hover_index = i
                break
            y += self.ITEM_LINE_HEIGHT
