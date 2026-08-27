"""DOOM-style DDA raycasting renderer.

A single DDA pipeline renders the scene; ``RenderMode`` only switches the
per-column drawing style (architecture ambiguity #1). Walls are resolved via
the grid ``WorldMap`` with O(1) lookups (ambiguity #2).
"""
import math

try:
    import pygame_ce as pygame
except ImportError:  # pragma: no cover
    import pygame

from doom_game.config import (
    SCREEN_WIDTH, SCREEN_HEIGHT, HALF_HEIGHT, FOV, CAMERA_PLANE_LEN,
    MAX_RENDER_DIST, TEXTURE_SIZE, DOPPLER_MIX, PROJECTILE_COLOR,
)
from doom_game.core.types import TextureType, RenderMode
from doom_game.core.player import Player
from doom_game.core.world_map import WorldMap
from doom_game.core.entities import PickupType
from doom_game.render.noise import NoiseAlgorithm
from doom_game.render.doppler import DopplerEffect


class DOOMRenderer:
    """Grid DDA raycaster with four selectable column styles."""

    def __init__(self, screen_width: int = SCREEN_WIDTH,
                 screen_height: int = SCREEN_HEIGHT):
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.half_height = screen_height // 2
        self.fov = FOV
        self.plane_len = CAMERA_PLANE_LEN
        self.num_rays = screen_width
        # Per-column angle offset relative to the player's facing direction.
        self.ray_angles: list = []
        # Cached procedurally generated wall textures keyed by TextureType.
        self.textures: dict = {}
        # Reusable overlay surfaces (created lazily once a display exists).
        self._dark_overlay = None
        self._doppler_overlay = None
        # Stash the texture X coordinate between cast_ray and render_column so
        # the documented render_column signature stays unchanged.
        self._tex_x = 0
        # Drawing surface, resolved during render().
        self.screen = None

        self.setup_rays()
        self.load_textures()

    # ------------------------------------------------------------------ #
    # Setup
    # ------------------------------------------------------------------ #
    def setup_rays(self) -> None:
        """Pre-compute the per-column angular offset (spread across the FOV)."""
        self.ray_angles = []
        for i in range(self.num_rays):
            # -FOV/2 .. +FOV/2
            offset = (i / self.num_rays - 0.5) * self.fov
            self.ray_angles.append(offset)

    def load_textures(self) -> None:
        """Pre-generate brick/stone/metal/wood textures and cache them."""
        self.textures = {
            TextureType.BRICK: NoiseAlgorithm.generate_wall_texture(
                TEXTURE_SIZE, TEXTURE_SIZE, seed=1),
            TextureType.STONE: NoiseAlgorithm.generate_wall_texture(
                TEXTURE_SIZE, TEXTURE_SIZE, seed=2),
            TextureType.METAL: NoiseAlgorithm.generate_wall_texture(
                TEXTURE_SIZE, TEXTURE_SIZE, seed=3),
            TextureType.WOOD: NoiseAlgorithm.generate_wall_texture(
                TEXTURE_SIZE, TEXTURE_SIZE, seed=4),
        }

    # ------------------------------------------------------------------ #
    # Ray casting (digital differential analysis on the grid)
    # ------------------------------------------------------------------ #
    def cast_ray(self, px: float, py: float, angle: float,
                 world: WorldMap) -> tuple:
        """Cast a single ray using grid DDA.

        Returns ``(distance, texture, side)`` where ``distance`` is the
        Euclidean distance to the hit, ``texture`` is the ``TextureType`` of the
        struck wall (or ``None`` if nothing was hit within range) and ``side``
        is 0 for a vertical (x) wall face, 1 for a horizontal (y) face.
        """
        ray_dir_x = math.cos(angle)
        ray_dir_y = math.sin(angle)

        map_x = int(px)
        map_y = int(py)

        delta_dist_x = abs(1 / ray_dir_x) if ray_dir_x != 0 else 1e30
        delta_dist_y = abs(1 / ray_dir_y) if ray_dir_y != 0 else 1e30

        step_x = 1 if ray_dir_x >= 0 else -1
        step_y = 1 if ray_dir_y >= 0 else -1

        if ray_dir_x < 0:
            side_dist_x = (px - map_x) * delta_dist_x
        else:
            side_dist_x = (map_x + 1.0 - px) * delta_dist_x
        if ray_dir_y < 0:
            side_dist_y = (py - map_y) * delta_dist_y
        else:
            side_dist_y = (map_y + 1.0 - py) * delta_dist_y

        hit = False
        side = 0
        texture = None

        while not hit:
            if side_dist_x < side_dist_y:
                side_dist_x += delta_dist_x
                map_x += step_x
                side = 0
            else:
                side_dist_y += delta_dist_y
                map_y += step_y
                side = 1

            # Out of bounds -> treat as a wall.
            if (map_x < 0 or map_y < 0
                    or map_x >= world.width or map_y >= world.height):
                hit = True
                break

            cell = world.cells[map_y][map_x]
            if cell is not None:
                hit = True
                texture = cell
                break

            # Safety: give up past the maximum render distance.
            if (side_dist_x > MAX_RENDER_DIST
                    and side_dist_y > MAX_RENDER_DIST):
                hit = True
                break

        if texture is None:
            return (MAX_RENDER_DIST, None, side)

        # Perpendicular (fisheye-free) distance along the ray.
        if side == 0:
            perp = (map_x - px + (1 - step_x) / 2) / ray_dir_x
        else:
            perp = (map_y - py + (1 - step_y) / 2) / ray_dir_y
        perp = max(perp, 1e-6)
        return (perp, texture, side)

    # ------------------------------------------------------------------ #
    # Rendering
    # ------------------------------------------------------------------ #
    def render(self, player: Player, world: WorldMap, mode: RenderMode) -> None:
        """Render the whole view for one frame in the given ``mode``."""
        surface = pygame.display.get_surface()
        if surface is None:
            return
        self.screen = surface

        if self._dark_overlay is None:
            self._dark_overlay = pygame.Surface((1, self.screen_height))
            self._doppler_overlay = pygame.Surface((1, self.screen_height))

        # Sky / floor bands.
        surface.fill((100, 150, 255),
                     (0, 0, self.screen_width, self.half_height))
        surface.fill((50, 100, 50),
                     (0, self.half_height,
                      self.screen_width, self.screen_height - self.half_height))

        if mode == RenderMode.WIREFRAME:
            self._render_wireframe(player, world)
            return

        for i in range(self.num_rays):
            offset = self.ray_angles[i]
            world_angle = player.angle + offset
            distance, texture, side = self.cast_ray(
                player.pos.x, player.pos.y, world_angle, world)

            # Fisheye correction.
            corrected = distance * math.cos(offset)
            if corrected <= 0:
                corrected = 0.001

            # Exact wall hit position for texture mapping.
            hit_x = player.pos.x + distance * math.cos(world_angle)
            hit_y = player.pos.y + distance * math.sin(world_angle)
            if side == 0:
                frac = hit_y - math.floor(hit_y)
            else:
                frac = hit_x - math.floor(hit_x)
            self._tex_x = int(frac * TEXTURE_SIZE) % TEXTURE_SIZE

            self.render_column(i, corrected, texture, side, offset, mode)

        # Motion blur only for DOOM_STYLE while actually moving.
        if mode == RenderMode.DOOM_STYLE:
            speed = player.get_speed()
            if speed > 0.001:
                DopplerEffect.apply_motion_blur(
                    surface, speed, player.angle)

    def render_column(self, x: int, distance: float, tex, side: int,
                      ray_angle: float, mode: RenderMode) -> None:
        """Draw a single vertical screen column for the current mode."""
        surface = self.screen
        if tex is None:
            return

        line_height = int(self.screen_height / distance)
        if line_height <= 0:
            return
        line_height = min(line_height, self.screen_height * 4)

        wall_top = self.half_height - line_height // 2
        wall_bottom = wall_top + line_height
        draw_top = max(0, wall_top)
        draw_bottom = min(self.screen_height, wall_bottom)
        if draw_bottom <= draw_top:
            return
        column_height = draw_bottom - draw_top
        src_top = max(0, -wall_top)  # texture rows hidden above the screen

        brightness = max(0.2, 1.0 - distance / MAX_RENDER_DIST)
        if side == 1:  # y-side walls slightly darker (classic DOOM look)
            brightness = max(0.2, brightness * 0.7)

        if mode == RenderMode.SOLID:
            color = DopplerEffect.distance_to_color(distance)
            surface.fill(color, (x, draw_top, 1, column_height))
            return

        texture_surf = self.textures.get(tex)
        if texture_surf is None:
            surface.fill((120, 120, 120), (x, draw_top, 1, column_height))
            return

        tex_x = self._tex_x
        try:
            col = texture_surf.subsurface(
                (tex_x, 0, 1, TEXTURE_SIZE)).copy()
        except Exception:
            col = texture_surf
        scaled = pygame.transform.scale(col, (1, max(1, line_height)))
        surface.blit(scaled, (x, draw_top), (0, src_top, 1, column_height))

        if mode == RenderMode.TEXTURED:
            dark = int((1.0 - brightness) * 255)
            if dark > 0 and self._dark_overlay is not None:
                self._dark_overlay.set_alpha(dark)
                self._dark_overlay.fill((0, 0, 0))
                surface.blit(self._dark_overlay, (x, draw_top),
                             (0, 0, 1, column_height))
        elif mode == RenderMode.DOOM_STYLE:
            dark = int((1.0 - brightness) * 255)
            if dark > 0 and self._dark_overlay is not None:
                self._dark_overlay.set_alpha(dark)
                self._dark_overlay.fill((0, 0, 0))
                surface.blit(self._dark_overlay, (x, draw_top),
                             (0, 0, 1, column_height))
            doppler = DopplerEffect.distance_to_color(distance)
            if self._doppler_overlay is not None:
                self._doppler_overlay.set_alpha(int(DOPPLER_MIX * 255))
                self._doppler_overlay.fill(doppler)
                surface.blit(self._doppler_overlay, (x, draw_top),
                             (0, 0, 1, column_height))

    def _render_wireframe(self, player: Player, world: WorldMap) -> None:
        """WIREFRAME mode: draw only vertical column edges (no fill)."""
        surface = self.screen
        horizon = self.half_height
        pygame.draw.line(surface, (80, 120, 200),
                         (0, horizon), (self.screen_width, horizon), 1)
        for i in range(self.num_rays):
            offset = self.ray_angles[i]
            world_angle = player.angle + offset
            distance, texture, _side = self.cast_ray(
                player.pos.x, player.pos.y, world_angle, world)
            corrected = distance * math.cos(offset)
            if corrected <= 0:
                corrected = 0.001
            line_height = int(self.screen_height / corrected)
            top = max(0, horizon - line_height // 2)
            bottom = min(self.screen_height, horizon + line_height // 2)
            if bottom <= top:
                continue
            color = DopplerEffect.distance_to_color(distance)
            pygame.draw.line(surface, color, (i, top), (i, bottom), 1)

    # ------------------------------------------------------------------ #
    # Sprite / billboard pass (incremental feature)
    # ------------------------------------------------------------------ #
    def render_sprites(self, player: Player, world: WorldMap,
                      enemies: list, pickups: list,
                      projectiles: list = None) -> None:
        """Draw enemies, pickups and projectiles as billboard blocks.

        Uses the classic Lodev camera-space transform: a sprite is projected
        with ``transformX / transformY`` (``transformY > 0`` means it is in
        front of the camera). The block size scales with ``1 / transformY``.
        Empty lists are handled safely so maze mode (no entities) is a no-op.
        ``projectiles`` is a trailing optional parameter so every existing
        call site keeps working unchanged; they render as small bright-orange
        blocks about one third the width of an enemy block.
        """
        surface = pygame.display.get_surface()
        if surface is None:
            return
        if (not enemies) and (not pickups) and (not projectiles):
            return

        dir_x = math.cos(player.angle)
        dir_y = math.sin(player.angle)
        plane_len = self.plane_len
        # Camera plane perpendicular to the facing direction.
        plane_x = -dir_y * plane_len
        plane_y = dir_x * plane_len
        inv_det = 1.0 / (plane_x * dir_y - dir_x * plane_y)

        w = self.screen_width
        h = self.screen_height
        half = self.half_height

        # Build the draw list: (world-x, world-y, color, width-factor).
        blocks = []
        for enemy in enemies:
            if not getattr(enemy, "alive", True):
                continue
            color = (220, 50, 50)            # red = enemy
            blocks.append((enemy.pos.x, enemy.pos.y, color, 0.35))
        for pickup in pickups:
            if getattr(pickup, "taken", False):
                continue
            color = ((40, 210, 40) if pickup.kind == PickupType.HEALTH
                     else (230, 210, 40))   # green = health, yellow = score
            blocks.append((pickup.pos.x, pickup.pos.y, color, 0.35))
        for projectile in (projectiles or []):
            if not getattr(projectile, "alive", True):
                continue
            # Bright orange, ~1/3 the width factor of an enemy block.
            blocks.append((projectile.pos.x, projectile.pos.y,
                           PROJECTILE_COLOR, 0.12))

        for (sx, sy, color, width_factor) in blocks:
            sprite_x = sx - player.pos.x
            sprite_y = sy - player.pos.y
            transform_x = inv_det * (dir_y * sprite_x - dir_x * sprite_y)
            transform_y = inv_det * (-plane_y * sprite_x + plane_x * sprite_y)
            if transform_y <= 0.0001:
                continue  # behind the camera
            sprite_screen_x = int((w / 2) * (1 + transform_x / transform_y))
            draw_h = abs(int(h / transform_y))
            draw_w = max(1, abs(int(w / transform_y * width_factor)))
            if draw_h <= 0:
                continue
            draw_h = min(draw_h, h)
            top = half - draw_h // 2
            rect_x = sprite_screen_x - draw_w // 2
            surface.fill(color, (rect_x, top, draw_w, 1))
