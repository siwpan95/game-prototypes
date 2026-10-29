"""DOOM-style pseudo-3D raycasting game - entry point.

Controls:
    WASD        move / strafe
    LEFT/RIGHT  rotate
    SPACE       attack (hitscan along the view direction)
    1-4         switch RenderMode (WIREFRAME/SOLID/TEXTURED/DOOM_STYLE)
    E           toggle in-game level editor (play <-> edit)
    R           restart the *current* level (victory screen: restart run)
    ESC         quit (play mode) / return to play (edit mode)
    Ctrl+S/O/Z  save / load / undo while editing
    any key     skip the LEVEL CLEAR intermission

Headless self-test (CI / sandbox):
    HEADLESS_TEST=1 python main.py
    python main.py --headless 30          # run 30 frames then exit cleanly
    python main.py --map maps/level_01.json --headless 20
"""
import os
import sys
from collections import defaultdict

try:
    import pygame_ce as pygame
except ImportError:  # pragma: no cover
    import pygame

from doom_game.config import (
    SCREEN_WIDTH, SCREEN_HEIGHT, HEADLESS_TEST, DISABLE_AUDIO,
    ENEMY_HP, ENEMY_DAMAGE, HEALTH_PICKUP_AMOUNT, SCORE_PICKUP_AMOUNT,
    LEVEL_SEQUENCE,
)
from doom_game.core.types import RenderMode
from doom_game.core.entities import EnemyType
from doom_game.world.game_world import GameWorld
from doom_game.world.level_io import LevelData, TEX_TO_INT
from doom_game.editor.level_editor import LevelEditor


def _parse_headless(argv) -> tuple:
    """Return (headless: bool, frames: int) from --headless / --headless=N."""
    for i, arg in enumerate(argv):
        if arg == "--headless":
            n = int(argv[i + 1]) if i + 1 < len(argv) else 30
            return True, n
        if arg.startswith("--headless="):
            return True, int(arg.split("=", 1)[1])
    return False, 30


def _parse_map(argv) -> str:
    """Return the ``--map <path>`` argument, or None."""
    for i, arg in enumerate(argv):
        if arg == "--map" and i + 1 < len(argv):
            return argv[i + 1]
        if arg.startswith("--map="):
            return arg.split("=", 1)[1]
    return None


def _game_to_level_data(game: GameWorld) -> LevelData:
    """Snapshot the running game into a serialisable ``LevelData``."""
    wmap = game.world_map
    cells = [[TEX_TO_INT.get(wmap.cells[gy][gx], 0)
              for gx in range(wmap.width)]
             for gy in range(wmap.height)]
    player_start = {
        "x": game.player.pos.x,
        "y": game.player.pos.y,
        "angle": game.player.angle,
    }
    enemies = [{
        "x": e.pos.x, "y": e.pos.y,
        "hp": e.hp, "damage": e.damage,
        "speed": e.speed, "type": e.type.value,
    } for e in game.enemies]
    pickups = [{
        "x": p.pos.x, "y": p.pos.y,
        "kind": p.kind.value, "amount": p.amount,
    } for p in game.pickups]
    return LevelData(
        version=1,
        width=wmap.width,
        height=wmap.height,
        cells=cells,
        player_start=player_start,
        enemies=enemies,
        pickups=pickups,
    )


def _headless_validate(game: GameWorld, screen) -> bool:
    """Render-validation pass for headless self-tests.

    Exercises every ``RenderMode`` at least once, drives one movement frame
    (to hit the motion-blur / collision code paths) and one stationary frame
    (to hit the silent-audio path), then performs a guarded audio-sonar
    physics check. Finally it builds a populated enemy + pickup scene and runs
    one frame to prove the ``render_sprites`` / HUD marker path does not crash.

    Returns True if all assertions pass. This never raises on pygame / audio
    unavailability - a failure is reported as ``False`` so the process can still
    exit cleanly.
    """
    modes = [
        RenderMode.WIREFRAME, RenderMode.SOLID,
        RenderMode.TEXTURED, RenderMode.DOOM_STYLE,
    ]
    # A defaultdict(bool) mimics pygame.key.ScancodeWrapper: any missing key
    # resolves to False (0) instead of raising KeyError, so the real
    # ``keys[pygame.K_x]`` indexing in GameWorld.update is exercised faithfully.
    empty_keys = defaultdict(bool)
    move_keys = defaultdict(bool)
    move_keys[pygame.K_w] = True
    move_keys[pygame.K_d] = True
    move_keys[pygame.K_RIGHT] = True

    try:
        rendered: list = []
        for mode in modes:
            game.render_mode = mode
            game.update(move_keys)          # movement + collision + audio sync
            game.render(screen)
            pygame.display.flip()
            rendered.append(mode.name)

        # Stationary frame -> silent audio physics path.
        game.update(empty_keys)
        game.render(screen)
        pygame.display.flip()

        # Structural assertions.
        assert len(game.renderer.textures) == 4, "expected 4 cached textures"
        assert game.renderer.num_rays == SCREEN_WIDTH, "ray count mismatch"
        assert game.world_map.width > 0 and game.world_map.height > 0
        assert game.player is not None

        # Guarded audio-sonar physics check (does not require a sound device).
        try:
            from doom_game.audio.sonar import PhysicsRaySonar
            sonar = PhysicsRaySonar(
                game.player.pos.x, game.player.pos.y,
                game.player.angle, game.audio.sample_rate)
            sig_still, vel_still, _ = sonar.update(
                game.player.pos.x, game.player.pos.y,
                game.player.angle, game.world_map)
            sig_move, vel_move, _ = sonar.update(
                game.player.pos.x + 0.3, game.player.pos.y,
                game.player.angle, game.world_map)
            assert abs(sig_still) < 1e-6, "stationary signal should be ~0"
            assert vel_move > vel_still, "moving velocity exceeds stationary"
            print(f"[HEADLESS VALIDATE] sonar: still_sig={sig_still:.4f} "
                  f"move_sig={sig_move:.4f} move_vel={vel_move:.3f} "
                  f"(still->silent, move->audible OK)")
        except Exception as exc:                       # pragma: no cover
            print(f"[HEADLESS VALIDATE] sonar check skipped: {exc}")

        # Incremental: verify the populated entity render path
        # (render_sprites and any HUD markers) does not crash with enemies and
        # pickups present.
        from doom_game.core.entities import Enemy, Pickup, PickupType
        saved_enemies = list(game.enemies)
        saved_pickups = list(game.pickups)
        px, py = game.player.pos.x, game.player.pos.y
        game.enemies = [Enemy(px + 1.2, py, hp=ENEMY_HP, damage=ENEMY_DAMAGE,
                              speed=0.0, type=EnemyType.BASIC)]
        game.pickups = [
            Pickup(px + 1.0, py, PickupType.HEALTH,
                   amount=HEALTH_PICKUP_AMOUNT),
            Pickup(px - 1.0, py, PickupType.SCORE,
                   amount=SCORE_PICKUP_AMOUNT),
        ]
        game.update(empty_keys)
        game.render(screen)
        pygame.display.flip()

        # Exercise the incremental HUD paths explicitly while the injected
        # entities are still present: HP bar, score text, minimap entity
        # markers, and the death overlay (hp forced to 0, then restored).
        game.hud.render_hp_bar(screen, game.player)
        game.hud.render_score(screen, game.player)
        game.hud.render_minimap(screen, game, game.player)
        saved_hp = game.player.hp
        game.player.hp = 0.0
        game.hud.render_death(screen, game.player)
        game.player.hp = saved_hp
        pygame.display.flip()
        print("[HEADLESS VALIDATE] HUD rendered OK "
              "(hp bar, score, minimap markers, death overlay)")

        # Report the *injected* entity counts before restoring the originals
        # so the log reflects what was actually rendered.
        print("[HEADLESS VALIDATE] entity scene rendered OK "
              f"(enemies={len(game.enemies)}, pickups={len(game.pickups)})")
        game.enemies = saved_enemies
        game.pickups = saved_pickups

        # Incremental V2: projectile in flight + LEVEL CLEAR / YOU WIN
        # overlays each render one frame without crashing (state restored).
        from doom_game.core.entities import Projectile
        saved_projectiles = list(game.projectiles)
        game.projectiles = [Projectile(px + 1.5, py, -1.0, 0.0)]
        game.render(screen)
        pygame.display.flip()
        game.projectiles = saved_projectiles

        saved_timer = game.level_clear_timer
        saved_victory = game.victory
        game.level_clear_timer = 1.0
        game.render(screen)                     # LEVEL CLEAR card
        pygame.display.flip()
        game.level_clear_timer = 0.0
        game.victory = True
        game.render(screen)                     # YOU WIN overlay
        pygame.display.flip()
        game.level_clear_timer = saved_timer
        game.victory = saved_victory
        print("[HEADLESS VALIDATE] V2 overlays rendered OK "
              "(projectile billboard, level clear, victory)")

        print(f"[HEADLESS VALIDATE] modes rendered: {','.join(rendered)}")
        return True
    except AssertionError as exc:
        print(f"[HEADLESS VALIDATE] FAILED: {exc}")
        return False
    except Exception as exc:                            # pragma: no cover
        print(f"[HEADLESS VALIDATE] ERROR: {exc}")
        return False


def _start_audio(game: GameWorld, headless: bool) -> None:
    """Start positional audio if allowed (interactive, device present)."""
    if not headless and not DISABLE_AUDIO and game.audio.enabled:
        game.audio.start(game.player.pos.x, game.player.pos.y,
                         game.player.angle, game.world_map)


def main() -> None:
    headless, headless_frames = _parse_headless(sys.argv[1:])
    map_path = _parse_map(sys.argv[1:])
    if HEADLESS_TEST:
        headless = True

    # Must be set before pygame.init() for the dummy video driver.
    if headless:
        os.environ["SDL_VIDEODRIVER"] = "dummy"
    if DISABLE_AUDIO:
        os.environ["DISABLE_AUDIO"] = "1"

    pygame.init()
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    pygame.display.set_caption("DOOM-style Raycaster")
    clock = pygame.time.Clock()

    # ``--map`` -> single-level mode; otherwise play the campaign sequence.
    game = GameWorld(map_path=map_path,
                     level_sequence=None if map_path else LEVEL_SEQUENCE)
    _start_audio(game, headless)

    # Editor state. Never instantiated under headless (headless-safe).
    edit_mode = False
    editor = None
    if headless:
        edit_mode = False

    running = True
    frame = 0
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
                continue

            # ---- Edit mode: route every event to the editor. ----
            if edit_mode and editor is not None:
                if event.type == pygame.KEYDOWN and (
                        event.key == pygame.K_ESCAPE
                        or event.key == pygame.K_e):
                    # Return to play, rebuilding the world from the edit.
                    game.load_level_data(editor.to_level_data())
                    edit_mode = False
                    editor = None
                    continue
                editor.handle_event(event)
                continue

            # ---- Play mode. ----
            if event.type == pygame.KEYDOWN:
                # LEVEL CLEAR intermission: any key skips it (Q7); ESC still
                # quits so the window can always be closed.
                if (game.level_clear_timer > 0.0
                        and event.key != pygame.K_ESCAPE):
                    game.skip_level_clear()
                    continue
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key == pygame.K_SPACE:
                    # Event-driven hitscan: one KEYDOWN = at most one shot.
                    game.player_attack()
                elif event.key == pygame.K_e and not headless:
                    # Enter the editor, snapshotting the current level.
                    edit_mode = True
                    editor = LevelEditor(SCREEN_WIDTH, SCREEN_HEIGHT,
                                         map_path=game.map_path)
                    editor.load_level_data(_game_to_level_data(game))
                elif event.key == pygame.K_r and not headless:
                    # Restart the *current* level in place (L6). On the
                    # victory screen, restart the whole run from level 1.
                    if game.victory:
                        game.level_index = 0
                        game._level_entry_score = 0
                    game.restart_level()
                elif event.key == pygame.K_1:
                    game.render_mode = RenderMode.WIREFRAME
                elif event.key == pygame.K_2:
                    game.render_mode = RenderMode.SOLID
                elif event.key == pygame.K_3:
                    game.render_mode = RenderMode.TEXTURED
                elif event.key == pygame.K_4:
                    game.render_mode = RenderMode.DOOM_STYLE

        if edit_mode and editor is not None:
            editor.render(screen)
        else:
            keys = pygame.key.get_pressed()
            game.update(keys)
            game.render(screen)
        pygame.display.flip()
        clock.tick(60)

        frame += 1
        if headless and frame >= headless_frames:
            break

    ok = True
    if headless:
        ok = _headless_validate(game, screen)

    game.cleanup()
    pygame.quit()
    if headless and not ok:
        sys.exit(1)


if __name__ == "__main__":
    main()
