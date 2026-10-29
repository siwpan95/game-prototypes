"""Heads-up display: minimap, info panel and audio visualisation."""
import math
import os

try:
    import pygame_ce as pygame
except ImportError:  # pragma: no cover
    import pygame

from doom_game.config import SCREEN_WIDTH, SCREEN_HEIGHT
from doom_game.core.entities import PickupType


class HUD:
    """Draws the on-screen overlay (minimap, text info, audio panel)."""

    # Marker colours for minimap entity dots (R2.7).
    ENEMY_DOT_COLOR = (255, 60, 60)      # red
    HEALTH_DOT_COLOR = (60, 255, 100)    # green
    SCORE_DOT_COLOR = (255, 230, 60)     # yellow
    PROJECTILE_DOT_COLOR = (255, 150, 40)  # orange (matches PROJECTILE_COLOR)

    # Incremental V2 text colours.
    LEVEL_CLEAR_COLOR = (120, 220, 80)   # yellow-green
    VICTORY_COLOR = (255, 215, 80)       # gold

    # HP bar thresholds / colours (R2.8).
    HP_COLOR_HIGH = (60, 200, 80)        # > 60%  -> green
    HP_COLOR_MID = (230, 200, 60)        # 30-60% -> yellow
    HP_COLOR_LOW = (220, 60, 60)         # < 30%  -> red

    @staticmethod
    def _get_font(size: int = 22):
        """Best-effort font loader; returns None when fonts are unavailable."""
        try:
            return pygame.font.SysFont(None, int(size))
        except Exception:
            return None

    def render_minimap(self, surface, game_world, player) -> None:
        """Draw a small top-down maze map with the player marker."""
        if surface is None:
            return
        wmap = game_world.world_map
        map_w = min(200, SCREEN_WIDTH // 5)
        map_h = map_w
        cell = max(2, map_w // max(1, wmap.width))
        ox = SCREEN_WIDTH - map_w - 20
        oy = 20

        pygame.draw.rect(surface, (0, 0, 0),
                         (ox - 4, oy - 4, map_w + 8, map_h + 8))
        for gy in range(wmap.height):
            for gx in range(wmap.width):
                if wmap.cells[gy][gx] is not None:
                    pygame.draw.rect(surface, (120, 120, 130),
                                     (ox + gx * cell, oy + gy * cell,
                                      cell, cell))

        # Entity markers (R2.7): enemies red, health pickups green,
        # score pickups yellow. Dead enemies / taken pickups are skipped.
        dot_r = max(2, cell // 3)
        for enemy in (getattr(game_world, "enemies", None) or []):
            if getattr(enemy, "hp", 0.0) <= 0.0:
                continue
            mx = ox + int(enemy.pos.x * cell)
            my = oy + int(enemy.pos.y * cell)
            pygame.draw.circle(surface, self.ENEMY_DOT_COLOR,
                               (mx, my), dot_r)
        for pickup in (getattr(game_world, "pickups", None) or []):
            if getattr(pickup, "taken", False):
                continue
            color = (self.HEALTH_DOT_COLOR
                     if pickup.kind == PickupType.HEALTH
                     else self.SCORE_DOT_COLOR)
            mx = ox + int(pickup.pos.x * cell)
            my = oy + int(pickup.pos.y * cell)
            pygame.draw.circle(surface, color, (mx, my), dot_r)

        # Projectiles: small orange dots (getattr keeps old callers safe).
        for projectile in (getattr(game_world, "projectiles", None) or []):
            if not getattr(projectile, "alive", True):
                continue
            mx = ox + int(projectile.pos.x * cell)
            my = oy + int(projectile.pos.y * cell)
            pygame.draw.circle(surface, self.PROJECTILE_DOT_COLOR,
                               (mx, my), 2)

        px = ox + int(player.pos.x * cell)
        py = oy + int(player.pos.y * cell)
        pygame.draw.circle(surface, (255, 220, 80),
                           (px, py), max(2, cell // 2))
        ex = px + int(math.cos(player.angle) * cell * 2)
        ey = py + int(math.sin(player.angle) * cell * 2)
        pygame.draw.line(surface, (255, 80, 80), (px, py), (ex, ey), 1)

    def render_info(self, surface, game_world, player, fps) -> None:
        """Draw the text info panel (FPS, mode, position, speed)."""
        if surface is None:
            return
        info = [
            f"FPS: {fps}",
            f"Mode: {game_world.render_mode.name}",
            f"Pos: ({player.pos.x:.1f}, {player.pos.y:.1f})",
            f"Ang: {math.degrees(player.angle):.0f}",
            f"Speed: {player.get_speed():.3f}",
            "WASD move | Arrows turn | 1-4 mode | ESC quit",
        ]
        try:
            font = pygame.font.SysFont(None, 22)
        except Exception:
            font = None
        y = SCREEN_HEIGHT - 130
        for line in info:
            if font is not None:
                txt = font.render(line, True, (220, 220, 220))
                surface.blit(txt, (10, y))
            y += 22

    def render_audio(self, surface, audio) -> None:
        """Draw the audio diagnostics panel if the system is enabled."""
        if surface is None or audio is None:
            return
        audio.visualize(surface, 10, 10, 200, 80)

    def render_hp_bar(self, surface, player) -> None:
        """Draw the player's health bar with ratio-dependent colour (R2.8).

        > 60% green, 30-60% yellow, < 30% red. A ``HP: cur/max`` label is
        drawn next to the bar when a font is available.
        """
        if surface is None or player is None:
            return
        max_hp = float(getattr(player, "max_hp", 0.0) or 0.0)
        hp = max(0.0, min(float(getattr(player, "hp", 0.0)), max_hp))
        ratio = (hp / max_hp) if max_hp > 0.0 else 0.0

        if ratio > 0.6:
            color = self.HP_COLOR_HIGH
        elif ratio >= 0.3:
            color = self.HP_COLOR_MID
        else:
            color = self.HP_COLOR_LOW

        bar_w = max(120, SCREEN_WIDTH // 5)
        bar_h = 18
        bx = 10
        by = SCREEN_HEIGHT - 165
        # Background + border, then the filled portion.
        pygame.draw.rect(surface, (40, 40, 40), (bx, by, bar_w, bar_h))
        fill_w = int(bar_w * ratio)
        if fill_w > 0:
            pygame.draw.rect(surface, color, (bx, by, fill_w, bar_h))
        pygame.draw.rect(surface, (200, 200, 200),
                         (bx, by, bar_w, bar_h), 1)

        font = self._get_font(22)
        if font is not None:
            label = f"HP: {int(round(hp))}/{int(round(max_hp))}"
            txt = font.render(label, True, (230, 230, 230))
            surface.blit(txt, (bx + bar_w + 8,
                               by + (bar_h - txt.get_height()) // 2))

    def render_score(self, surface, player) -> None:
        """Draw the player's score as ``SCORE: N`` text (R2.8)."""
        if surface is None or player is None:
            return
        font = self._get_font(26)
        if font is None:
            return
        score = int(round(float(getattr(player, "score", 0.0) or 0.0)))
        txt = font.render(f"SCORE: {score}", True, (255, 230, 120))
        surface.blit(txt, (10, SCREEN_HEIGHT - 190))

    def render_level_banner(self, surface, game_world) -> None:
        """Draw the persistent ``LEVEL n/total`` banner (L7).

        Single-level (``--map``) mode shows ``LEVEL 1/1``; the legacy maze
        sandbox has no level sequence and shows nothing.
        """
        if surface is None or game_world is None:
            return
        sequence = getattr(game_world, "level_sequence", None) or []
        if not sequence:
            return
        index = int(getattr(game_world, "level_index", 0))
        font = self._get_font(26)
        if font is None:
            return
        txt = font.render(f"LEVEL {index + 1}/{len(sequence)}", True,
                          (220, 220, 255))
        surface.blit(txt, (10, SCREEN_HEIGHT - 215))

    def render_level_clear(self, surface, game_world) -> None:
        """Draw the LEVEL CLEAR intermission card while the timer runs (Q7)."""
        if surface is None or game_world is None:
            return
        if float(getattr(game_world, "level_clear_timer", 0.0)) <= 0.0:
            return
        big = self._get_font(72)
        small = self._get_font(28)
        cx = SCREEN_WIDTH // 2
        cy = SCREEN_HEIGHT // 2
        if big is not None:
            txt = big.render("LEVEL CLEAR", True, self.LEVEL_CLEAR_COLOR)
            surface.blit(txt, (cx - txt.get_width() // 2,
                               cy - txt.get_height()))
        if small is not None:
            hint = small.render("press any key", True, (230, 230, 230))
            surface.blit(hint, (cx - hint.get_width() // 2, cy + 12))

    def render_victory(self, surface, game_world) -> None:
        """Overlay 'YOU WIN' + restart hint on final victory (L5).

        Style deliberately mirrors :meth:`render_death` (translucent mask +
        72pt headline + 28pt hint). Mutually exclusive with the death overlay
        because victory can only be reached with hp > 0.
        """
        if surface is None or game_world is None:
            return
        if not bool(getattr(game_world, "victory", False)):
            return

        # Dim the scene with a translucent overlay (guarded: never crash).
        try:
            overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT),
                                     pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 140))
            surface.blit(overlay, (0, 0))
        except Exception:
            pass

        big = self._get_font(72)
        small = self._get_font(28)
        cx = SCREEN_WIDTH // 2
        cy = SCREEN_HEIGHT // 2
        if big is not None:
            txt = big.render("YOU WIN", True, self.VICTORY_COLOR)
            surface.blit(txt, (cx - txt.get_width() // 2,
                               cy - txt.get_height()))
        if small is not None:
            hint = small.render("Press R to restart", True, (230, 230, 230))
            surface.blit(hint, (cx - hint.get_width() // 2, cy + 12))

    def render_death(self, surface, player) -> None:
        """Overlay 'YOU DIED' + restart hint when the player is dead."""
        if surface is None or player is None:
            return
        if float(getattr(player, "hp", 0.0)) > 0.0:
            return

        # Dim the scene with a translucent overlay (guarded: never crash).
        try:
            overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT),
                                     pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 140))
            surface.blit(overlay, (0, 0))
        except Exception:
            pass

        big = self._get_font(72)
        small = self._get_font(28)
        cx = SCREEN_WIDTH // 2
        cy = SCREEN_HEIGHT // 2
        if big is not None:
            txt = big.render("YOU DIED", True, (220, 40, 40))
            surface.blit(txt, (cx - txt.get_width() // 2,
                               cy - txt.get_height()))
        if small is not None:
            hint = small.render("Press R to restart", True, (230, 230, 230))
            surface.blit(hint, (cx - hint.get_width() // 2, cy + 12))
