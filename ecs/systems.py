"""
Systems - Logic processors that operate on entities with specific components.
"""

import random
import math
import pygame
from ecs import System
from ecs.components import (
    Position, Speed, RectRender, LineRender, DashedLineRender,
    RoadSurface, RoadEdge, VehicleControl, Drift, GameState, Decoration,
)


# ── Input ─────────────────────────────────────────────────────────

class InputSystem(System):
    """Read keyboard and move player-controlled entities."""

    def __init__(self):
        self.pygame = pygame

    def update(self, world, dt):
        state = world.get_singleton(GameState)
        if not state or not state.alive or state.paused:
            return

        keys = pygame.key.get_pressed()
        dx = 0
        if keys[pygame.K_LEFT]:
            dx -= 5
        if keys[pygame.K_RIGHT]:
            dx += 5

        if dx == 0:
            return

        for entity in world.get_entities_with(Position, VehicleControl):
            pos = world.get_component(entity, Position)
            pos.x += dx


# ── Drift ─────────────────────────────────────────────────────────

class DriftSystem(System):
    """Apply random left/right pushes to entities with a Drift component.
    Push magnitude scales dynamically with distance travelled."""

    def __init__(self, scale_per_km: float = 0.3):
        self.scale_per_km = scale_per_km

    def update(self, world, dt):
        state = world.get_singleton(GameState)
        if not state or not state.alive or state.paused:
            return

        # Dynamic multiplier: grows with distance, starts at 1x
        intensity = 1.0 + state.distance_km * self.scale_per_km

        for entity in world.get_entities_with(Position, Drift):
            drift = world.get_component(entity, Drift)
            base_chance = drift.chance
            # Chance also slightly increases with distance
            if random.random() < base_chance * (1.0 + state.distance_km * 0.1):
                direction = random.choice([-1, 1])
                push = direction * random.uniform(
                    drift.min_push * intensity,
                    drift.max_push * intensity,
                )
                pos = world.get_component(entity, Position)
                pos.x += push
                state.drift_count += 1


# ── Collision ─────────────────────────────────────────────────────

class CollisionSystem(System):
    """Check if the player has hit a road edge. Sets alive=False on death."""

    def __init__(self, road_left: int, road_right: int, edge_width: int, player_width: int):
        self.road_left = road_left
        self.road_right = road_right
        self.edge_width = edge_width
        self.player_width = player_width

    def update(self, world, dt):
        state = world.get_singleton(GameState)
        if not state or not state.alive:
            return

        for entity in world.get_entities_with(Position, VehicleControl):
            pos = world.get_component(entity, Position)
            if pos.x <= self.road_left + self.edge_width:
                state.alive = False
            elif pos.x + self.player_width >= self.road_right - self.edge_width:
                state.alive = False


# ── Scroll & Distance ─────────────────────────────────────────────

class ScrollSystem(System):
    """Scroll dashed lines and accumulate distance."""

    def __init__(self, scroll_speed: float, distance_factor: float, scrolled_height: int):
        self.scroll_speed = scroll_speed
        self.distance_factor = distance_factor
        self.scrolled_height = scrolled_height  # dash + gap

    def update(self, world, dt):
        state = world.get_singleton(GameState)
        if not state or state.paused:
            return

        state.distance_km += self.scroll_speed * self.distance_factor

        for entity in world.get_entities_with(DashedLineRender):
            dash = world.get_component(entity, DashedLineRender)
            dash.offset_y = (dash.offset_y + self.scroll_speed) % self.scrolled_height


# ── Decoration Systems ────────────────────────────────────────────

class DecorationSpawnSystem(System):
    """Spawns roadside decorations at the top of the screen."""

    def __init__(self, config: dict, road_left: int, road_right: int):
        self.config = config
        self.road_left = road_left
        self.road_right = road_right
        self._frame_counter = 0
        # Build weighted type list
        self._type_weights = []
        self._type_names = []
        for name, props in config["types"].items():
            self._type_names.append(name)
            self._type_weights.append(props["spawn_weight"])

    def _pick_type(self) -> str:
        return random.choices(self._type_names, weights=self._type_weights, k=1)[0]

    def _pick_side(self) -> str:
        return random.choice(["left", "right"])

    def update(self, world, dt):
        state = world.get_singleton(GameState)
        if not state or not state.alive or state.paused:
            return

        self._frame_counter += 1
        interval = self.config.get("spawn_interval", 80)
        if self._frame_counter < interval:
            return
        self._frame_counter = 0

        # Spawn 1-2 decorations per interval
        for _ in range(random.randint(1, 2)):
            deco_type = self._pick_type()
            side = self._pick_side()
            type_cfg = self.config["types"][deco_type]

            # Determine X position (outside road edges)
            margin = 10
            if side == "left":
                x_range = (0, self.road_left - 50)
            else:
                x_range = (self.road_right + 20, 800 - 50)

            if x_range[0] >= x_range[1]:
                continue  # skip if no room

            x = random.randint(x_range[0], x_range[1])
            y = -40  # start above screen

            # Determine size
            min_sz = type_cfg.get("min_size", 18)
            max_sz = type_cfg.get("max_size", 28)
            size = random.randint(min_sz, max_sz)
            color = tuple(type_cfg.get("color", [150, 150, 150]))

            entity = world.create_entity()
            world.add_component(entity, Position(x=x, y=y))
            world.add_component(entity, Decoration(
                deco_type=deco_type, side=side,
                size=size, color=color,
            ))


class DecorationScrollSystem(System):
    """Scroll decorations down and remove off-screen ones."""

    def __init__(self, scroll_speed: float, screen_height: int):
        self.scroll_speed = scroll_speed
        self.screen_height = screen_height

    def update(self, world, dt):
        state = world.get_singleton(GameState)
        if not state or not state.alive or state.paused:
            return

        to_remove = []
        for entity in world.get_entities_with(Position, Decoration):
            pos = world.get_component(entity, Position)
            deco = world.get_component(entity, Decoration)
            if not deco.active:
                continue
            pos.y += self.scroll_speed
            # Remove if off-screen
            if pos.y > self.screen_height + 50:
                to_remove.append(entity)

        for entity in to_remove:
            world.remove_entity(entity)


# ── Render ────────────────────────────────────────────────────────

class RenderSystem(System):
    """Draw all renderable entities to the screen in z-order."""

    def __init__(self, screen: pygame.Surface):
        self.screen = screen

    def update(self, world, dt):
        # 0. Clear whole screen to desert / gobi yellow
        self.screen.fill((210, 180, 80))

        # 1. Road surface (special: uses screen-locked coordinates)
        self._draw_road_surface(world)

        # 2. Decorations behind the road (z < 0)
        self._draw_decorations(world)

        # 3. Center dashed line
        self._draw_dashed_lines(world)

        # 4. Edge lines (yellow boundaries)
        self._draw_edges(world)

        # 5. Rectangles (player car, etc.)
        self._draw_rects(world)

    def _draw_road_surface(self, world):
        sw = self.screen.get_width()
        sh = self.screen.get_height()
        for entity in world.get_entities_with(RoadSurface):
            rs = world.get_component(entity, RoadSurface)
            # Centre the road surface horizontally so it covers the whole screen
            rx = (sw - rs.width) // 2
            pygame.draw.rect(self.screen, rs.color, (rx, 0, rs.width, sh))

    def _draw_decorations(self, world):
        """Draw roadside decorations: cactus, rocks, dead bushes, guardrails."""
        for entity in world.get_entities_with(Position, Decoration):
            pos = world.get_component(entity, Position)
            deco = world.get_component(entity, Decoration)
            if not deco.active:
                continue

            x, y = int(pos.x), int(pos.y)
            sz = deco.size
            c = deco.color

            if deco.deco_type == "cactus":
                self._draw_cactus(x, y, sz, c)
            elif deco.deco_type == "rock":
                self._draw_rock(x, y, sz, c)
            elif deco.deco_type == "dead_bush":
                self._draw_dead_bush(x, y, sz, c)
            elif deco.deco_type == "guardrail":
                self._draw_guardrail(x, y, sz, c)

    def _draw_cactus(self, x: int, y: int, sz: int, color: tuple):
        """Draw a saguaro-style cactus with main trunk and arms."""
        cx = x + sz // 2  # center x
        base_y = y + sz
        body_w = max(3, sz // 5)
        # Main trunk
        pygame.draw.rect(self.screen, color,
                         (cx - body_w // 2, y, body_w, sz))
        # Left arm
        arm_h = sz // 3
        arm_w = max(2, body_w * 3 // 4)
        arm_start_y = y + sz // 3
        arm_end_y = arm_start_y + arm_h
        pygame.draw.rect(self.screen, color,
                         (cx - body_w // 2 - arm_w, arm_end_y - arm_w,
                          arm_w, arm_h))
        pygame.draw.rect(self.screen, color,
                         (cx - body_w // 2 - arm_w, arm_end_y - arm_w,
                          arm_w + body_w // 2, arm_w))
        # Right arm
        arm_start_y2 = y + sz // 2
        arm_end_y2 = arm_start_y2 + arm_h
        pygame.draw.rect(self.screen, color,
                         (cx + body_w // 2, arm_end_y2 - arm_w,
                          arm_w, arm_h))
        pygame.draw.rect(self.screen, color,
                         (cx + body_w // 2, arm_end_y2 - arm_w,
                          arm_w, arm_w))
        # Highlight edge
        hl_color = tuple(min(255, c + 50) for c in color)
        pygame.draw.rect(self.screen, hl_color,
                         (cx - body_w // 2, y, 2, sz))
        # Spines (small dots)
        spine_color = (200, 200, 160)
        for i in range(4):
            sy = y + 5 + i * (sz // 4)
            pygame.draw.circle(self.screen, spine_color,
                               (cx - body_w // 2, sy), 1)
            pygame.draw.circle(self.screen, spine_color,
                               (cx + body_w // 2, sy + 2), 1)

    def _draw_rock(self, x: int, y: int, sz: int, color: tuple):
        """Draw a desert rock / boulder with irregular shape."""
        cx = x + sz // 2
        base_y = y + sz
        rock_h = int(sz * 0.7)
        rock_w = sz
        # Irregular polygon shape
        jitter = lambda v, a: v + random.randint(-a, a)
        rng = max(3, sz // 8)
        points = [
            (jitter(cx - rock_w // 2, rng), jitter(base_y, rng // 2)),
            (jitter(cx - rock_w // 3, rng), jitter(base_y - rock_h + rng, rng // 2)),
            (jitter(cx, rng), jitter(base_y - rock_h - rng // 2, rng // 2)),
            (jitter(cx + rock_w // 3, rng), jitter(base_y - rock_h + rng, rng // 2)),
            (jitter(cx + rock_w // 2, rng), jitter(base_y, rng // 2)),
            (jitter(cx + rock_w // 3, rng), jitter(base_y - 2, rng // 2)),
            (jitter(cx - rock_w // 3, rng), jitter(base_y - 2, rng // 2)),
        ]
        pygame.draw.polygon(self.screen, color, points)
        # Highlight top edge
        hl_color = tuple(min(255, c + 40) for c in color)
        hl_points = [
            (cx - rock_w // 4, base_y - rock_h + 3),
            (cx, base_y - rock_h - 2),
            (cx + rock_w // 4, base_y - rock_h + 3),
        ]
        pygame.draw.polygon(self.screen, hl_color, hl_points)
        # Shadow (darker crevice line)
        dark = tuple(max(0, c - 30) for c in color)
        pygame.draw.line(self.screen, dark,
                         (cx - 3, base_y - rock_h // 3),
                         (cx + 3, base_y - 3), 2)

    def _draw_dead_bush(self, x: int, y: int, sz: int, color: tuple):
        """Draw a dry / dead desert bush (tumbleweed-like)."""
        cx = x + sz // 2
        base_y = y + sz
        bush_h = int(sz * 0.6)
        bush_w = sz
        # Oval body
        ellipse_rect = (cx - bush_w // 2, base_y - bush_h, bush_w, bush_h)
        pygame.draw.ellipse(self.screen, color, ellipse_rect)
        # Twiggy branches
        twig_color = tuple(min(255, c + 20) for c in color)
        twigs = [
            ((cx - bush_w // 3, base_y - bush_h // 4),
             (cx - bush_w // 2, base_y - bush_h + 4)),
            ((cx + bush_w // 3, base_y - bush_h // 3),
             (cx + bush_w // 2 + 2, base_y - bush_h + 2)),
            ((cx, base_y - bush_h + 2),
             (cx, base_y - bush_h - bush_h // 3)),
            ((cx - 4, base_y - bush_h // 2),
             (cx - bush_w // 4, base_y - bush_h + 1)),
            ((cx + 4, base_y - bush_h // 2),
             (cx + bush_w // 4, base_y - bush_h + 1)),
        ]
        for start, end in twigs:
            pygame.draw.line(self.screen, twig_color, start, end, 1)
        # Highlight
        hl_color = tuple(min(255, c + 50) for c in color)
        hl_rect = (cx - bush_w // 3, base_y - bush_h + 1,
                   bush_w // 2, bush_h // 3)
        pygame.draw.ellipse(self.screen, hl_color, hl_rect)

    def _draw_guardrail(self, x: int, y: int, sz: int, color: tuple):
        """Draw a weathered wooden guardrail post in desert style."""
        post_w = max(3, sz // 6)
        post_h = sz
        cx = x + sz // 4
        # Main post
        pygame.draw.rect(self.screen, color,
                         (cx - post_w // 2, y, post_w, post_h))
        # Wood grain lines
        grain_color = tuple(min(255, c + 30) for c in color)
        for gy in range(y + 4, y + post_h - 2, 6):
            pygame.draw.line(self.screen, grain_color,
                             (cx - post_w // 2 + 1, gy),
                             (cx + post_w // 2 - 1, gy), 1)
        # Faded reflective top
        ref_color = (220, 180, 80)
        ref_h = max(2, post_h // 6)
        pygame.draw.rect(self.screen, ref_color,
                         (cx - post_w // 2 - 1, y + post_h // 4,
                          post_w + 2, ref_h))

    def _draw_dashed_lines(self, world):
        for entity in world.get_entities_with(Position, DashedLineRender):
            pos = world.get_component(entity, Position)
            dash = world.get_component(entity, DashedLineRender)
            step = dash.dash_length + dash.gap_length
            screen_h = self.screen.get_height()
            for y in range(int(-dash.offset_y), screen_h + step, step):
                pygame.draw.rect(
                    self.screen, dash.color,
                    (pos.x - dash.line_width // 2, y,
                     dash.line_width, dash.dash_length),
                )

    def _draw_edges(self, world):
        for entity in world.get_entities_with(Position, LineRender):
            pos = world.get_component(entity, Position)
            line = world.get_component(entity, LineRender)
            pygame.draw.line(
                self.screen, line.color,
                (pos.x, pos.y), (line.x2, line.y2),
                line.line_width,
            )

    def _draw_rects(self, world):
        entities = sorted(
            world.get_entities_with(Position, RectRender),
            key=lambda e: world.get_component(e, RectRender).z_order,
        )
        for entity in entities:
            pos = world.get_component(entity, Position)
            rr = world.get_component(entity, RectRender)
            pygame.draw.rect(
                self.screen, rr.color,
                (pos.x, pos.y, rr.width, rr.height),
            )


# ── HUD ───────────────────────────────────────────────────────────

class HUDSystem(System):
    """Draw distance, drift count, and control hints on screen."""

    def __init__(self, screen: pygame.Surface, font, small_font):
        self.screen = screen
        self.font = font
        self.small_font = small_font

    def update(self, world, dt):
        state = world.get_singleton(GameState)
        if not state:
            return

        white = (255, 255, 255)
        grey = (180, 180, 180)

        dist_text = self.font.render(
            f"Distance: {state.distance_km:.2f} km", True, white)
        drift_text = self.font.render(
            f"Drifts: {state.drift_count}", True, white)
        hint_text = self.small_font.render(
            "Arrow keys = steer | P = pause | ESC = quit", True, grey)

        self.screen.blit(dist_text, (10, 10))
        self.screen.blit(drift_text, (10, 50))
        self.screen.blit(hint_text, (10, self.screen.get_height() - 30))
