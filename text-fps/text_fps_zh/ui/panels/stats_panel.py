"""StatsPanel - Player status display with health, armor, noise bars."""
import time
try:
    import pygame_ce as pygame
except ImportError:
    import pygame

from ui.panel import Panel
from ui import colors as C


class StatsPanel(Panel):
    """Right-side panel showing player stats as progress bars and text."""

    BAR_HEIGHT = 14
    BAR_SPACING = 4
    SECTION_SPACING = 8
    FLASH_INTERVAL = 0.5  # seconds for low-HP flash

    def __init__(self, rect: pygame.Rect) -> None:
        super().__init__(rect, bg_color=C.BG_PANEL)
        self.font_hud: pygame.font.Font = pygame.font.Font(None, 14)
        self.font_body: pygame.font.Font = pygame.font.Font(None, 16)
        self._flash_state: bool = True
        self._last_flash: float = time.time()

    def set_font(self, font_hud: pygame.font.Font, font_body: pygame.font.Font) -> None:
        """Set fonts for rendering."""
        self.font_hud = font_hud
        self.font_body = font_body

    def render(self, surface: pygame.Surface, game_state) -> None:
        """Render player stats with progress bars."""
        super().render(surface, game_state)
        if not game_state or not game_state.player:
            return

        player = game_state.player
        x = self.rect.x + 10
        y = self.rect.y + 8
        bar_width = self.rect.width - 20

        # Update flash state for low HP
        now = time.time()
        if now - self._last_flash > self.FLASH_INTERVAL:
            self._flash_state = not self._flash_state
            self._last_flash = now

        # --- 生命值 ---
        self._draw_label(surface, "生命", f"{player.health}/{player.max_health}", x, y)
        y += 16
        hp_ratio = player.health / max(1, player.max_health)
        hp_color = C.HP_RED
        if hp_ratio < 0.3:
            hp_color = C.HP_LOW if self._flash_state else C.HP_RED
        elif hp_ratio > 0.6:
            hp_color = C.AMMO_GREEN
        self._draw_bar(surface, x, y, bar_width, hp_ratio, hp_color)
        y += self.BAR_HEIGHT + self.SECTION_SPACING

        # --- 护甲 ---
        self._draw_label(surface, "护甲", f"{player.armor}/{player.max_armor}", x, y)
        y += 16
        armor_ratio = player.armor / max(1, player.max_armor)
        self._draw_bar(surface, x, y, bar_width, armor_ratio, C.ARMOR_BLUE)
        y += self.BAR_HEIGHT + self.SECTION_SPACING

        # --- 噪音 ---
        self._draw_label(surface, "噪音", f"{player.noise_level}", x, y)
        y += 16
        noise_ratio = min(1.0, player.noise_level / 10.0)
        noise_color = C.NOISE_YELLOW if player.noise_level > 5 else C.AMMO_GREEN
        self._draw_bar(surface, x, y, bar_width, noise_ratio, noise_color)
        y += self.BAR_HEIGHT + self.SECTION_SPACING

        # --- Weapon Info ---
        pygame.draw.line(
            surface, C.DIVIDER,
            (x, y), (x + bar_width, y),
        )
        y += self.SECTION_SPACING

        weapon = player.current_weapon()
        if weapon:
            self._draw_label(surface, "武器", weapon.name, x, y)
            y += 16
            ammo_text = f"弹药: {weapon.ammo}/{weapon.effective_max_ammo()}"
            ammo_surf = self.font_hud.render(ammo_text, True, C.AMMO_GREEN)
            surface.blit(ammo_surf, (x + 4, y))
            y += 14
            # Accuracy
            acc_text = f"命中率: {int(weapon.effective_accuracy() * 100)}%"
            acc_surf = self.font_hud.render(acc_text, True, C.TEXT_SECONDARY)
            surface.blit(acc_surf, (x + 4, y))
            y += 14
            # Damage
            dmg_text = f"伤害: {weapon.effective_damage()}"
            dmg_surf = self.font_hud.render(dmg_text, True, C.TEXT_SECONDARY)
            surface.blit(dmg_surf, (x + 4, y))
            y += 14
            # Mods
            if weapon.mods:
                mods_text = f"改装: {', '.join(m.name for m in weapon.mods)}"
                mods_surf = self.font_hud.render(mods_text, True, C.TEXT_PRIMARY)
                surface.blit(mods_surf, (x + 4, y))
                y += 14
        else:
            no_weapon = self.font_hud.render("无武器", True, C.TEXT_DIM)
            surface.blit(no_weapon, (x + 4, y))
            y += 14

        # --- Status Flags ---
        y += self.SECTION_SPACING
        flags = []
        if player.is_aiming:
            flags.append("瞄准中")
        if player.in_cover:
            flags.append("掩体中")
        if flags:
            flag_text = " | ".join(flags)
            flag_surf = self.font_hud.render(flag_text, True, C.TEXT_PRIMARY)
            surface.blit(flag_surf, (x + 4, y))
            y += 14

        # --- Kills & Level ---
        y += self.SECTION_SPACING
        pygame.draw.line(
            surface, C.DIVIDER,
            (x, y), (x + bar_width, y),
        )
        y += self.SECTION_SPACING

        kills_surf = self.font_hud.render(f"击杀: {player.kills}", True, C.TEXT_SECONDARY)
        surface.blit(kills_surf, (x + 4, y))
        y += 14

        level_name = ""
        if game_state.levels:
            level_name = game_state.levels[-1].name
        level_surf = self.font_hud.render(f"关卡: {level_name}", True, C.TEXT_SECONDARY)
        surface.blit(level_surf, (x + 4, y))
        y += 14

        turn_surf = self.font_hud.render(f"回合: {game_state.turn}", True, C.TEXT_SECONDARY)
        surface.blit(turn_surf, (x + 4, y))

    def _draw_label(self, surface: pygame.Surface, label: str, value: str, x: int, y: int) -> None:
        """Draw a stat label and value."""
        label_surf = self.font_hud.render(f"{label}:", True, C.TEXT_DIM)
        value_surf = self.font_hud.render(value, True, C.TEXT_WHITE)
        surface.blit(label_surf, (x + 2, y))
        surface.blit(value_surf, (x + 2 + label_surf.get_width() + 6, y))

    def _draw_bar(
        self, surface: pygame.Surface, x: int, y: int,
        width: int, ratio: float, color: tuple,
    ) -> None:
        """Draw a progress bar."""
        ratio = max(0.0, min(1.0, ratio))
        # Background
        bg_rect = pygame.Rect(x, y, width, self.BAR_HEIGHT)
        pygame.draw.rect(surface, C.BG_DARK, bg_rect, border_radius=3)
        # Fill
        if ratio > 0:
            fill_width = max(1, int(width * ratio))
            fill_rect = pygame.Rect(x, y, fill_width, self.BAR_HEIGHT)
            pygame.draw.rect(surface, color, fill_rect, border_radius=3)
        # Border
        pygame.draw.rect(surface, C.BORDER_COLOR, bg_rect, width=1, border_radius=3)
