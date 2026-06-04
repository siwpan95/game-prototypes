"""
Endless Highway — ECS Architecture
Entry point: creates the World, spawns entities, runs the game loop.

Audio system added — Deja Vu (Daft Punk) electronic style.
"""

import json
import os
import sys
import pygame

from ecs import World
from ecs.components import (
    Position, RectRender, RoadSurface,
    VehicleControl, Drift, DashedLineRender, LineRender, GameState,
)
from ecs.systems import (
    InputSystem, DriftSystem, CollisionSystem,
    ScrollSystem, RenderSystem, HUDSystem,
    DecorationSpawnSystem, DecorationScrollSystem,
)
from audio.ecs_system import AudioSystem, set_audio_manager, ensure_audio_assets
from audio.audio_manager import AudioManager


def load_config(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def build_world(cfg: dict) -> tuple:
    """Create the ECS world, spawn entities, register systems."""
    world = World()

    # ── Config aliases ────────────────────────────────────────
    w = cfg["window"]
    r = cfg["road"]
    p = cfg["player"]
    d = cfg["drift"]

    SCREEN_W = w["width"]
    SCREEN_H = w["height"]
    LANE_CENTER = SCREEN_W // 2

    road_width = r["width"]
    road_left = LANE_CENTER - road_width // 2
    road_right = LANE_CENTER + road_width // 2
    edge_w = r["edge_line_width"]

    scrolled_h = r["center_dash_length"] + r["center_gap_length"]

    # ── Entities ──────────────────────────────────────────────
    # Road surface (drawn full-width by RenderSystem)
    road_entity = world.create_entity()
    world.add_component(road_entity, RoadSurface(
        width=road_width + 150, height=SCREEN_H,
        color=tuple(r["surface_color"]),
    ))

    # Center dashed line
    dash_entity = world.create_entity()
    world.add_component(dash_entity, Position(x=LANE_CENTER, y=0))
    world.add_component(dash_entity, DashedLineRender(
        dash_length=r["center_dash_length"],
        gap_length=r["center_gap_length"],
        line_width=r["center_line_width"],
        color=tuple(r["center_line_color"]),
    ))

    # Left edge boundary line
    left_edge = world.create_entity()
    world.add_component(left_edge, Position(x=road_left, y=0))
    world.add_component(left_edge, LineRender(
        x2=road_left, y2=SCREEN_H,
        color=tuple(r["edge_line_color"]),
        line_width=edge_w,
    ))

    # Right edge boundary line
    right_edge = world.create_entity()
    world.add_component(right_edge, Position(x=road_right, y=0))
    world.add_component(right_edge, LineRender(
        x2=road_right, y2=SCREEN_H,
        color=tuple(r["edge_line_color"]),
        line_width=edge_w,
    ))

    # Player car
    player = world.create_entity()
    player_x = SCREEN_W // 2 - p["width"] // 2
    player_y = SCREEN_H - p["y_screen_offset"]

    world.add_component(player, Position(x=player_x, y=player_y))
    world.add_component(player, RectRender(
        width=p["width"], height=p["height"],
        color=tuple(p["color"]), z_order=10,
    ))
    world.add_component(player, VehicleControl())
    world.add_component(player, Drift(
        chance=d["chance"],
        min_push=d["min_push"],
        max_push=d["max_push"],
    ))

    # Game-state singleton
    state_entity = world.create_entity()
    world.add_component(state_entity, GameState())

    # ── Systems (order matters) ───────────────────────────────
    world.add_system(InputSystem())
    world.add_system(DriftSystem(scale_per_km=d["scale_per_km"]))
    world.add_system(CollisionSystem(
        road_left=road_left,
        road_right=road_right,
        edge_width=edge_w,
        player_width=p["width"],
    ))
    world.add_system(ScrollSystem(
        scroll_speed=r["scroll_speed"],
        distance_factor=r["distance_factor"],
        scrolled_height=scrolled_h,
    ))

    # ── Decoration systems ─────────────────────────────────
    deco_cfg = cfg.get("decorations", {
        "spawn_interval": 80, "scroll_speed": 5, "types": {}
    })
    world.add_system(DecorationSpawnSystem(deco_cfg, road_left, road_right))
    world.add_system(DecorationScrollSystem(
        scroll_speed=deco_cfg.get("scroll_speed", r["scroll_speed"]),
        screen_height=SCREEN_H,
    ))

    return world, SCREEN_W, SCREEN_H


def show_pause_overlay(screen, large_font, small_font):
    """Draw semi-transparent pause screen."""
    overlay = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 128))
    screen.blit(overlay, (0, 0))
    pause_text = large_font.render("PAUSED", True, (255, 255, 0))
    hint_text = small_font.render("Press P to resume | ESC to quit", True, (255, 255, 255))
    sw, sh = screen.get_size()
    screen.blit(pause_text, (sw // 2 - pause_text.get_width() // 2, sh // 2 - 50))
    screen.blit(hint_text, (sw // 2 - hint_text.get_width() // 2, sh // 2 + 10))


def show_end_screen(screen, state: GameState, large_font, font, small_font,
                    cause: str = "quit"):
    """Show game-over / journey-ended screen, wait for key."""
    screen.fill((0, 0, 0))
    sw, sh = screen.get_size()

    if cause == "crash":
        title = large_font.render("GAME OVER", True, (255, 0, 0))
        sub = font.render("You crashed into the barrier!", True, (255, 255, 0))
    else:
        title = large_font.render("JOURNEY ENDED", True, (255, 255, 0))
        sub = font.render("You chose to end the drive.", True, (255, 255, 0))

    dist = font.render(f"Distance: {state.distance_km:.2f} km", True, (255, 255, 255))
    drifts = font.render(f"Drifts survived: {state.drift_count}", True, (255, 255, 255))
    quit_msg = small_font.render("Press any key to exit...", True, (180, 180, 180))

    screen.blit(title, (sw // 2 - title.get_width() // 2, sh // 2 - 120))
    screen.blit(sub, (sw // 2 - sub.get_width() // 2, sh // 2 - 60))
    screen.blit(dist, (sw // 2 - dist.get_width() // 2, sh // 2 - 10))
    screen.blit(drifts, (sw // 2 - drifts.get_width() // 2, sh // 2 + 40))
    screen.blit(quit_msg, (sw // 2 - quit_msg.get_width() // 2, sh // 2 + 90))

    pygame.display.flip()
    waiting = True
    while waiting:
        for event in pygame.event.get():
            if event.type in (pygame.QUIT, pygame.KEYDOWN):
                waiting = False


def _load_font(face: str, size: int) -> pygame.font.Font:
    """Try to load a system font, fallback to default if unavailable."""
    font_paths = [
        os.path.join(os.environ.get("WINDIR", "C:\\Windows"), "Fonts", "arial.ttf"),
        os.path.join(os.environ.get("WINDIR", "C:\\Windows"), "Fonts", "segoeui.ttf"),
    ]
    for path in font_paths:
        if os.path.isfile(path):
            try:
                return pygame.font.Font(path, size)
            except Exception:
                continue
    try:
        return pygame.font.Font(None, size)
    except Exception:
        return pygame.font.Font(None, 24)


def main():
    # Ensure the script's directory is the working context
    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(script_dir)

    cfg = load_config("config.json")
    f = cfg["fonts"]

    # ── Init pygame (audio included) ──────────────────────────
    pygame.init()
    pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=512)
    screen = pygame.display.set_mode(
        (cfg["window"]["width"], cfg["window"]["height"]))
    pygame.display.set_caption(cfg["window"]["title"])
    clock = pygame.time.Clock()

    # Fonts
    large_font = _load_font(f["large"], f["large_size"])
    font = _load_font(f["normal"], f["normal_size"])
    small_font = _load_font(f["small"], f["small_size"])

    # ── Build ECS world ───────────────────────────────────────
    world, _, _ = build_world(cfg)

    # ── Audio system (Game Audio Engineer implementation) ─────
    # 1. Ensure audio assets exist (generate if missing)
    asset_paths = ensure_audio_assets("audio/assets")
    # 2. Create and initialize AudioManager
    audio_mgr = AudioManager()
    audio_ok = audio_mgr.initialize(asset_paths)
    if audio_ok:
        set_audio_manager(audio_mgr)
        audio_mgr.start_music()
        audio_mgr.start_engine_sfx()
        print("[main] Audio system initialized OK.")
    else:
        print("[main] WARNING: Audio system failed to initialize.")

    # ── Register remaining systems ────────────────────────────
    world.add_system(RenderSystem(screen))
    world.add_system(HUDSystem(screen, font, small_font))
    # AudioSystem runs after game logic, before render
    world.add_system(AudioSystem())

    running = True
    state = world.get_singleton(GameState)

    while running:
        dt = clock.tick(cfg["game"]["fps"]) / 1000.0

        # ── Event processing ─────────────────────────────────
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    if state and state.alive:
                        audio_mgr.trigger_sfx('event:/SFX/UI_Quit')
                        show_end_screen(
                            screen, state, large_font, font, small_font,
                            cause="quit")
                    running = False
                elif event.key == pygame.K_p:
                    if state and state.alive:
                        state.paused = not state.paused
                        # AudioSystem handles UI pause/resume SFX via update()

        # ── Dead? ────────────────────────────────────────────
        if state and not state.alive:
            # Crash SFX triggered by AudioSystem automatically.
            # Fade out music for dramatic effect.
            if audio_ok:
                audio_mgr.stop_music(fade_ms=1500)
            show_end_screen(screen, state, large_font, font, small_font,
                            cause="crash")
            running = False
            break

        # ── Paused? ────────────────────────────────────────
        if state and state.paused:
            show_pause_overlay(screen, large_font, small_font)
            pygame.display.flip()
            continue

        # ── ECS update (includes AudioSystem) ─────────────
        world.update(dt)
        pygame.display.flip()

    # ── Shutdown audio ──────────────────────────────────────
    if audio_ok:
        audio_mgr.shutdown()
    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()
